import time
import threading
import logging
from typing import Dict, Any, Optional

from config import BotConfig, load_config, save_config
from core.binance_client import BinanceTrClient
from core.market_data import MarketDataEngine
from core.market_scanner import MarketScanner
from core.risk_manager import RiskManager
from core.simulator import SimulatorEngine
from core.live_trader import LiveTraderEngine
from strategies.fee_recovery import FeeRecoveryStrategy
from strategies.adaptive_regime import AdaptiveRegimeStrategy
from strategies.rsi_bollinger import RsiBollingerStrategy
from strategies.momentum_ema import MomentumEmaStrategy
from strategies.grid_scalper import GridScalperStrategy
from strategies.quick_test_scalper import QuickTestScalperStrategy
from reporting.performance import PerformanceMetrics
from reporting.report_generator import ReportGenerator

import sys
import os

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("BinanceTrBot")

class BinanceTrBot:
    """
    Tüm motorları, stratejileri ve işlem döngüsünü yöneten ana bot koordinatörü.
    Otomatik piyasa radarı ile en çok dalgalanan coinleri bulur ve al-sat yapar.
    """
    def __init__(self, config: Optional[BotConfig] = None):
        self.config = config or load_config()
        self.client = BinanceTrClient(
            api_key=self.config.api.api_key,
            secret_key=self.config.api.secret_key,
            base_url=self.config.api.base_url,
        )
        self.scanner = MarketScanner(
            quote_asset="TRY",
            min_volume_try=getattr(self.config.trading, "min_24h_volume_try", 5000000.0)
        )
        obs_sec = getattr(self.config.trading, "candidate_observation_seconds", 15)
        self.scanner.watchlist.min_observation_seconds = obs_sec
        obs_gain = getattr(self.config.trading, "min_observation_gain_pct", 0.50)
        self.scanner.watchlist.min_gain_pct = obs_gain
        obs_cd = getattr(self.config.trading, "candidate_timeout_cooldown_seconds", 10)
        self.scanner.watchlist.timeout_cooldown_seconds = obs_cd
        obs_burst = getattr(self.config.trading, "candidate_min_burst_count", 1)
        self.scanner.watchlist.min_burst_count = obs_burst
        self.market_engines: Dict[str, MarketDataEngine] = {}
        default_sym = "SOL_TRY" if self.config.trading.symbol == "AUTO" else self.config.trading.symbol
        self.market_data = self.get_engine_for(default_sym)
        self.risk_manager = RiskManager(
            take_profit_pct=self.config.strategy.take_profit_pct,
            stop_loss_pct=self.config.strategy.stop_loss_pct,
            trailing_stop_pct=self.config.strategy.trailing_stop_pct,
            trailing_activation_pct=getattr(self.config.strategy, "trailing_activation_pct", 1.0),
            breakeven_trigger_pct=getattr(self.config.strategy, "breakeven_trigger_pct", 0.90),
            cooldown_seconds=getattr(self.config.strategy, "cooldown_seconds", 5),
            symbol_cooldown_seconds=getattr(self.config.strategy, "symbol_cooldown_seconds", 30),
            loss_cooldown_seconds=getattr(self.config.strategy, "loss_cooldown_seconds", 180),
            max_open_positions=self.config.trading.max_open_positions,
            fee_rate_pct=self.config.trading.fee_rate_pct,
            portfolio_stop_loss_pct=getattr(self.config.strategy, "portfolio_stop_loss_pct", 2.5),
            prevent_rebuy_churn=getattr(self.config.trading, "prevent_rebuy_churn", False),
        )
        self.simulator = SimulatorEngine(
            initial_balance=self.config.trading.initial_virtual_balance,
            fee_rate_pct=self.config.trading.fee_rate_pct,
        )
        self.live_trader = LiveTraderEngine(
            self.client,
            symbol=self.config.trading.symbol,
            max_open_positions=self.config.trading.max_open_positions,
        )
        self.report_generator = ReportGenerator()

        self.strategy = self._init_strategy()
        self.is_running = False
        self.session_start_time: Optional[float] = None
        self.session_duration_seconds: int = self.config.test.duration_minutes * 60
        self.thread: Optional[threading.Thread] = None
        self.last_report: Optional[Dict[str, str]] = None
        self.latest_snapshot: Dict[str, Any] = {}
        self.logs: list[str] = []
        self.heartbeat_counter: int = 0
        self.step_count: int = 0
        is_live = self.config.trading.mode == "live"
        self.current_status_text: str = "Hazır - Canlı İşlem Bekleniyor" if is_live else "Hazır - Test Bekleniyor"

    def _init_strategy(self):
        strat_name = self.config.strategy.active
        fee_rate = getattr(self.config.trading, "fee_rate_pct", 0.10)
        params = {
            "fee_rate_pct": fee_rate,
            "fee_multiplier": 2.0,
            "rsi_period": self.config.strategy.rsi_period,
            "rsi_oversold": self.config.strategy.rsi_oversold,
            "rsi_overbought": self.config.strategy.rsi_overbought,
            "bollinger_period": self.config.strategy.bollinger_period,
            "bollinger_std_dev": self.config.strategy.bollinger_std_dev,
            "ema_fast": self.config.strategy.ema_fast,
            "ema_slow": self.config.strategy.ema_slow,
            "pullback_pct": 0.15,
            "adx_trend_threshold": 22.0,
        }
        if strat_name in ("fee_recovery", "komisyon_kurtaran"):
            # Komisyon oranını kurtaran risk parametrelerini uygula
            self.risk_manager.apply_fee_recovery_mode(
                fee_rate_pct=fee_rate,
                fee_multiplier=getattr(self.config.strategy, "fee_multiplier", 2.0),
                take_profit_pct=self.config.strategy.take_profit_pct,
                stop_loss_pct=self.config.strategy.stop_loss_pct,
            )
            return FeeRecoveryStrategy(params)
        elif strat_name == "adaptive_regime":
            return AdaptiveRegimeStrategy(params)
        elif strat_name == "momentum_ema":
            return MomentumEmaStrategy(params)
        elif strat_name == "grid_scalper":
            return GridScalperStrategy(params)
        elif strat_name == "quick_test_scalper":
            return QuickTestScalperStrategy(params)
        elif strat_name == "rsi_bollinger":
            return RsiBollingerStrategy(params)
        else:
            self.risk_manager.apply_fee_recovery_mode(
                fee_rate_pct=fee_rate,
                fee_multiplier=getattr(self.config.strategy, "fee_multiplier", 2.0),
                take_profit_pct=self.config.strategy.take_profit_pct,
                stop_loss_pct=self.config.strategy.stop_loss_pct,
            )
            return FeeRecoveryStrategy(params)

    def log(self, message: str) -> None:
        log_entry = f"[{time.strftime('%H:%M:%S')}] {message}"
        logger.info(message)
        self.logs.append(log_entry)
        if len(self.logs) > 300:
            self.logs.pop(0)

    def start(self, duration_minutes: Optional[int] = None) -> None:
        if self.is_running:
            return

        if duration_minutes is not None:
            self.session_duration_seconds = duration_minutes * 60

        # Yeni oturum başlatıldığında tamamlanan işlemleri temizle (oturum raporlaması için)
        if self.config.trading.mode == "live":
            self.live_trader.reset_session_trades()
        else:
            self.simulator.reset_session_trades()

        self.is_running = True
        self.session_start_time = time.time()
        self.log(f"🚀 Bot başlatıldı! Mod: {self.config.trading.mode.upper()} | Parite: {self.config.trading.symbol} | Süre: {int(self.session_duration_seconds / 60)} dk")

        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self) -> Dict[str, Any]:
        if not self.is_running:
            return {"status": "already_stopped"}

        self.is_running = False
        self.log("🛑 Bot durduruldu. Rapor oluşturuluyor...")
        report_files = self._generate_final_report()
        self.last_report = report_files
        self.log(f"📊 Rapor kaydedildi: {report_files.get('html')}")
        return {"status": "stopped", "report": report_files}

    def _run_loop(self) -> None:
        while self.is_running:
            try:
                self.step()

                # Test süresi kontrolü
                if self.session_duration_seconds > 0 and self.session_start_time:
                    elapsed = time.time() - self.session_start_time
                    if elapsed >= self.session_duration_seconds:
                        self.log("⏱️ Test süresi tamamlandı! Otomatik durduruluyor...")
                        self.stop()
                        break

            except Exception as e:
                self.log(f"⚠️ Hata: {str(e)}")

            # 1.5 saniye aralıkla canlı takip (durdurma sinyaline anında yanıt verir)
            for _ in range(15):
                if not self.is_running:
                    break
                time.sleep(0.1)

    def get_engine_for(self, symbol: str) -> MarketDataEngine:
        if symbol not in self.market_engines:
            self.market_engines[symbol] = MarketDataEngine(self.client, symbol=symbol)
        return self.market_engines[symbol]

    def force_test_buy(self, symbol: Optional[str] = None, budget: Optional[float] = None, reason: str = "Manuel Test Alımı") -> Optional[Dict[str, Any]]:
        """
        Kullanıcının hemen pozisyon açıp TP/SL'i izleyebilmesi için anında alım yapar.
        Sembol belirtilmemişse radarın bulduğu 1 numaralı en hareketli coini otomatik seçer.
        """
        target_symbol = symbol
        if not target_symbol or target_symbol == "AUTO":
            top = self.scanner.scan_top_active_pairs(limit=3)
            target_symbol = top[0]["symbol"] if top else "SOL_TRY"

        engine = self.get_engine_for(target_symbol)
        snapshot = engine.update_market_state()
        price = snapshot.get("price", 0.0) if snapshot else 0.0

        if price <= 0:
            self.log(f"⚠️ {target_symbol} için anlık fiyat alınamadı.")
            return None

        trade_budget = budget or self.config.trading.budget_per_trade
        if self.config.trading.mode == "simulation":
            if self.simulator.cash < trade_budget:
                if self.simulator.cash >= 50.0:
                    trade_budget = self.simulator.cash
                else:
                    self.simulator.cash += 2000.0

        self.log(f"⚡ ANINDA TEST ALIMI TETİKLENDİ: Parite={target_symbol}, Fiyat={price:.4f} TL, Bütçe={trade_budget:.2f} TL")

        if self.config.trading.mode == "simulation":
            pos = self.simulator.buy(target_symbol, price, trade_budget, reason=reason)
            if pos:
                self.risk_manager.record_trade_entry()
                self.log(f"🟢 Sanal Pozisyon Açıldı [{target_symbol}]: Miktar={pos['quantity']:.4f} | Maliyet={trade_budget:.2f} TL")
                return pos
        else:
            pos = self.live_trader.buy(price, trade_budget, reason=reason)
            if pos:
                self.risk_manager.record_trade_entry()
                self.log(f"🟢 CANLI Pozisyon Açıldı [{target_symbol}]: Miktar={pos['quantity']:.4f}")
                return pos
        return None

    def force_close_all(self, reason: str = "Manuel Pozisyon Kapatma") -> list:
        closed = []
        if self.config.trading.mode == "simulation":
            for pos_id, pos in list(self.simulator.positions.items()):
                sym = pos["symbol"]
                engine = self.get_engine_for(sym)
                snap = engine.update_market_state()
                price = snap["price"] if snap and snap["price"] > 0 else pos["current_price"]
                order = self.simulator.sell(pos_id, price, reason=reason)
                if order:
                    closed.append(order)
                    self.log(f"🛑 Pozisyon Kapatıldı [{sym}]: Net K/Z={order['net_pnl']:.2f} TL ({order['pnl_pct']:.2f}%)")
        else:
            for pos_id, pos in list(self.live_trader.positions.items()):
                sym = pos["symbol"]
                engine = self.get_engine_for(sym)
                snap = engine.update_market_state()
                price = snap["price"] if snap and snap["price"] > 0 else pos["entry_price"]
                order = self.live_trader.sell(pos_id, price, reason=reason)
                if order:
                    closed.append(order)
                    self.log(f"🛑 Canlı Pozisyon Kapatıldı [{sym}]: Net K/Z={order['net_pnl']:.2f} TL")
        return closed

    def close_single_position(self, position_id: str, reason: str = "Manuel Satış") -> Optional[Dict[str, Any]]:
        mode = self.config.trading.mode
        if mode == "simulation":
            pos = self.simulator.positions.get(position_id)
            if not pos:
                return None
            sym = pos["symbol"]
            engine = self.get_engine_for(sym)
            snap = engine.update_market_state()
            price = snap["price"] if snap and snap["price"] > 0 else pos.get("current_price", pos["entry_price"])
            order = self.simulator.sell(position_id, price, reason=reason)
            if order:
                self.risk_manager.record_trade_exit(sym)
                self.log(f"🛑 Manuel Pozisyon Kapatıldı [{sym}]: Net K/Z={order['net_pnl']:.2f} TL (%{order['pnl_pct']:.2f})")
                return order
        else:
            pos = self.live_trader.positions.get(position_id)
            if not pos:
                return None
            sym = pos["symbol"]
            engine = self.get_engine_for(sym)
            snap = engine.update_market_state()
            price = snap["price"] if snap and snap["price"] > 0 else pos["entry_price"]
            order = self.live_trader.sell(position_id, price, reason=reason)
            if order:
                self.risk_manager.record_trade_exit(sym)
                self.log(f"🛑 Canlı Manuel Pozisyon Kapatıldı [{sym}]: Net K/Z={order['net_pnl']:.2f} TL")
                return order
        return None

    def step(self) -> None:
        """
        Her döngü adımı:
        1. Açık pozisyonların anlık fiyatlarını ve TP/SL durumlarını kontrol et
        2. Bütçe ve pozisyon limitine göre yeni işlem hakkı var mı bak
        3. 'auto_select_coin' aktifse en hareketli coinleri tara ve uygun olanı yakala
        """
        self.step_count += 1
        mode = self.config.trading.mode

        # 1. Açık Pozisyonları Güncelle & Kâr Al / Stop Loss Değerlendir
        top_leaders = [p["symbol"] for p in getattr(self.scanner, "cached_top_pairs", [])[:3]]
        if mode == "simulation":
            open_positions = list(self.simulator.positions.values())
            for pos in open_positions:
                sym = pos["symbol"]
                engine = self.get_engine_for(sym)
                snap = engine.update_market_state()
                cur_p = snap["price"] if snap and snap["price"] > 0 else pos["current_price"]
                self.simulator.update_market_price(sym, cur_p)

                should_close, reason, pnl_pct = self.risk_manager.evaluate_exit(pos, cur_p)
                if should_close:
                    is_profitable = pnl_pct > 0 and ("TAKE-PROFIT" in reason or "TRAILING" in reason or "BREAKEVEN" in reason)
                    strat_sig, _ = self.strategy.evaluate(snap, len(open_positions)) if snap else ("HOLD", "")
                    is_top = sym in top_leaders
                    rollover_ok, rollover_msg = self.risk_manager.should_rollover_position(
                        pos, cur_p, is_profitable_exit=is_profitable, strategy_signal=strat_sig, is_top_leader=is_top
                    )
                    if rollover_ok:
                        pos["entry_price"] = cur_p
                        pos["highest_price"] = cur_p
                        self.log(f"🔄 POZİSYON DEVRİ [{sym}]: Kâr seviyesine ulaşıldı (+%{pnl_pct:.2f}), trend sürdüğü ve coin lider kaldığı için satılmadan pozisyon devredildi. Yeni taban fiyat: {cur_p:.4f} TL")
                        continue

                    self.log(f"🎯 POZİSYON KAPANIŞI [{sym}]: {reason}")
                    trade = self.simulator.sell(pos["position_id"], cur_p, reason=reason)
                    if trade:
                        is_loss_exit = pnl_pct <= 0 or "STOP-LOSS" in reason
                        self.risk_manager.record_trade_exit(sym, is_loss=is_loss_exit)
                        self.log(f"✅ Satış Gerçekleşti [{sym}]: Fiyat={cur_p:.4f} TL | Net K/Z={trade['net_pnl']:.2f} TL (%{trade['pnl_pct']:.2f})")

            open_count = len(self.simulator.positions)
            # Portföy Düzeyinde Toplam Kâr/Zarar ve %2 Zarar Kes Kontrolü (Simülasyon)
            summary = self.simulator.get_summary()
            port_pnl_pct = summary.get("total_pnl_pct", 0.0)
            port_sl_triggered, port_reason = self.risk_manager.evaluate_portfolio_stop_loss(port_pnl_pct)
            if port_sl_triggered:
                self.log(f"🚨 {port_reason}! Sermaye kaybını sınırlamak için TÜM AÇIK POZİSYONLAR SATILIYOR VE BOT DURDURULUYOR...")
                self.force_close_all(reason=port_reason)
                self.current_status_text = f"🚨 Portföy Stop-Loss Tetiklendi (%{port_pnl_pct:.2f}) - Bot Durduruldu"
                self.stop()
                return
        else:
            open_positions = list(self.live_trader.positions.values())
            for pos in open_positions:
                sym = pos["symbol"]
                engine = self.get_engine_for(sym)
                snap = engine.update_market_state()
                cur_p = snap["price"] if snap and snap["price"] > 0 else pos["entry_price"]
                self.live_trader.update_market_price(sym, cur_p)

                should_close, reason, pnl_pct = self.risk_manager.evaluate_exit(pos, cur_p)
                if should_close:
                    is_profitable = pnl_pct > 0 and ("TAKE-PROFIT" in reason or "TRAILING" in reason or "BREAKEVEN" in reason)
                    strat_sig, _ = self.strategy.evaluate(snap, len(open_positions)) if snap else ("HOLD", "")
                    is_top = sym in top_leaders
                    rollover_ok, rollover_msg = self.risk_manager.should_rollover_position(
                        pos, cur_p, is_profitable_exit=is_profitable, strategy_signal=strat_sig, is_top_leader=is_top
                    )
                    if rollover_ok:
                        pos["entry_price"] = cur_p
                        pos["highest_price"] = cur_p
                        self.log(f"🔄 CANLI POZİSYON DEVRİ [{sym}]: Kâr (+%{pnl_pct:.2f}) sonrası pozisyon devredildi. Yeni taban: {cur_p:.4f} TL")
                        continue

                    self.log(f"🎯 CANLI KAPANIŞ [{sym}]: {reason}")
                    trade = self.live_trader.sell(pos["position_id"], cur_p, reason=reason)
                    if trade:
                        is_loss_exit = pnl_pct <= 0 or "STOP-LOSS" in reason
                        self.risk_manager.record_trade_exit(sym, is_loss=is_loss_exit)
                        self.log(f"✅ Canlı Satış [{sym}]: Fiyat={cur_p:.4f} TL | Net K/Z={trade['net_pnl']:.2f} TL")

            open_count = len(self.live_trader.positions)
            # Canlı Portföy Düzeyinde %2 Zarar Kes Kontrolü (Canlı Hesap)
            summary = self.live_trader.get_summary()
            port_pnl_pct = summary.get("total_pnl_pct", 0.0)
            port_sl_triggered, port_reason = self.risk_manager.evaluate_portfolio_stop_loss(port_pnl_pct)
            if port_sl_triggered:
                self.log(f"🚨 {port_reason}! Canlı hesap sermaye kaybını sınırlamak için TÜM CANLI POZİSYONLAR SATILIYOR VE BOT DURDURULUYOR...")
                self.force_close_all(reason=port_reason)
                self.current_status_text = f"🚨 Canlı Portföy Stop-Loss Tetiklendi (%{port_pnl_pct:.2f}) - Bot Durduruldu"
                self.stop()
                return

        # 2. Yeni İşlem Açılabilir mi?
        can_open, open_reason = self.risk_manager.can_open_position(open_count)

        # 3. Otomatik Tarama veya Tekil Parite İncelemesi
        is_auto = self.config.trading.auto_select_coin or self.config.trading.symbol == "AUTO"

        if is_auto:
            target_count = getattr(self.config.trading, "target_coins_count", 5)
            only_up = getattr(self.config.trading, "only_uptrend", True)
            min_gain = getattr(self.config.trading, "min_24h_gain_pct", 0.0)
            top_pairs = self.scanner.scan_top_active_pairs(
                limit=getattr(self.config.trading, "top_coins_limit", 0),
                only_uptrend=only_up,
                min_gain_pct=min_gain,
            )
            open_symbols = {p["symbol"] for p in open_positions}
            slots_needed = max(0, target_count - open_count)

            # Durum metnini güncelle
            if open_count > 0:
                self.current_status_text = f"Dinamik Portföy: {open_count}/{target_count} Coin Aktif (Tüm Pazar Taranıyor)"
            else:
                top_names = [f"{p['symbol']} (%{p['change_pct']:+.1f})" for p in top_pairs[:3]]
                self.current_status_text = f"Portföy Dolduruluyor: Liderler [{', '.join(top_names)}]"

            # Periyodik Log
            self.heartbeat_counter += 1
            if self.heartbeat_counter % 4 == 0:
                if open_count > 0:
                    pos_summaries = [f"{pos['symbol']}: {pos.get('unrealized_pnl', 0):+.2f}TL (%{pos.get('unrealized_pnl_pct', 0):+.2f})" for pos in open_positions[:5]]
                    self.log(f"📊 [PORTFÖY DURUMU ({open_count}/{target_count} COİN)] {' | '.join(pos_summaries)}")
                else:
                    obs_summaries = []
                    for p in top_pairs[:4]:
                        sym = p["symbol"]
                        info = self.scanner.watchlist.get_info(sym)
                        if info.get("status") == "cooling_down":
                            obs_summaries.append(f"{sym}: ⏳{info.get('cooldown_remaining', 0)}s")
                        elif info.get("elapsed", 0) > 0:
                            obs_summaries.append(f"{sym}: %{info.get('change_pct', 0.0):+.2f} ({info.get('elapsed')}/{info.get('min_sec')}s)")
                        else:
                            obs_summaries.append(f"{sym}: (%{p['change_pct']:+.1f})")
                    obs_text = " | ".join(obs_summaries)
                    min_g = getattr(self.config.trading, 'min_observation_gain_pct', 1.5)
                    self.log(f"🔍 [RADAR İZLEME ({len(top_pairs)} Coin)] {obs_text} -> Patlama (Hedef: >= %{min_g:.2f}) bekleniyor...")

            slots_needed = target_count - open_count

            if slots_needed > 0:
                top_pairs = self.scanner.scan_top_active_pairs(
                    limit=getattr(self.config.trading, "top_coins_limit", 0),
                    only_uptrend=getattr(self.config.trading, "only_uptrend", True),
                    min_gain_pct=getattr(self.config.trading, "min_24h_gain_pct", 0.0),
                )
                open_symbols = {p["symbol"] for p in open_positions}
                if mode == "simulation":
                    available_cash = self.simulator.cash
                else:
                    available_cash = self.live_trader.get_real_balances().get("TRY", 0.0)

                per_coin_budget = min(self.config.trading.budget_per_trade, available_cash / max(1, slots_needed))

                # Radarı en yüksek hacimli/skorlu taze adaylara odakla (tüm pazarı tek saniyede spamlamaz)
                candidate_pairs = [p for p in top_pairs if p["symbol"] not in open_symbols][:max(8, slots_needed * 2)]

                for pair in candidate_pairs:
                    if slots_needed <= 0:
                        break

                    sym = pair["symbol"]

                    can_buy_slot, _ = self.risk_manager.can_open_position(open_count, is_basket_filling=True, symbol=sym)
                    if not can_buy_slot:
                        continue

                    cur_p = pair.get("price", 0.0)
                    engine = None
                    snap = None
                    if cur_p <= 0:
                        engine = self.get_engine_for(sym)
                        snap = engine.update_market_state()
                        cur_p = snap.get("price", 0.0) if snap else 0.0
                    if cur_p <= 0:
                        continue

                    filter_falling = getattr(self.config.trading, "filter_falling_coins", True)
                    if filter_falling:
                        is_approved, obs_reason, elapsed_sec = self.scanner.watchlist.observe(sym, cur_p)
                        if "ZAMAN AŞIMI" in obs_reason or "düşen bıçak" in obs_reason:
                            self.log(f"🔄 [{sym}] {obs_reason}")
                        elif is_approved:
                            self.log(f"🚀 [{sym}] {obs_reason}")

                        if not is_approved:
                            continue
                    else:
                        obs_reason = "Doğrudan Alım"

                    engine = self.get_engine_for(sym)
                    snap = engine.update_market_state()
                    if not snap or snap.get("price", 0) <= 0:
                        snap = {"price": cur_p, "rsi": 50.0, "change_24h_pct": pair.get("change_pct", 0.0)}

                    signal, signal_reason = self.strategy.evaluate(snap, open_count)

                    obs_sec = getattr(self.scanner.watchlist, "min_observation_seconds", getattr(self.config.trading, "candidate_observation_seconds", 45))
                    require_strict = getattr(self.config.trading, "require_strict_buy_signal", True)
                    auto_fill = getattr(self.config.trading, "auto_fill_portfolio", False)

                    # Eğer aday gözlem radarı aktifse ve çifte patlama onayı verildiyse (is_approved=True),
                    # alım derhal gerçekleştirilir. Aday gözlem kapalıysa (0 sn) teknik gösterge sinyali (BUY) aranır.
                    if filter_falling and obs_sec > 0:
                        should_buy = is_approved
                        buy_reason = f"{obs_reason}"
                    else:
                        should_buy = (signal == "BUY") if (require_strict or not auto_fill) else True
                        buy_reason = f"{signal_reason} ({obs_reason})"

                    if should_buy:
                        if per_coin_budget < 10.0:
                            self.log(f"⚠️ [{sym}] Alım bütçesi yetersiz ({per_coin_budget:.2f} TL < 10 TL minimum). Alım atlandı.")
                            continue

                        if mode == "simulation":
                            pos = self.simulator.buy(sym, cur_p, per_coin_budget, reason=buy_reason)
                            if pos:
                                open_symbols.add(sym)
                                open_count += 1
                                slots_needed -= 1
                                available_cash -= per_coin_budget
                                self.risk_manager.record_trade_entry(sym)
                                if sym in self.scanner.watchlist.tracking:
                                    del self.scanner.watchlist.tracking[sym]
                                self.log(f"🟢 Portföye Eklendi [{sym}]: Miktar={pos['quantity']:.4f} | Maliyet={per_coin_budget:.2f} TL | Sepet: {open_count}/{target_count} Coin Dolu | Neden: {buy_reason}")
                        else:
                            pos = self.live_trader.buy(sym, cur_p, per_coin_budget, reason=buy_reason)
                            if pos:
                                open_symbols.add(sym)
                                open_count += 1
                                slots_needed -= 1
                                available_cash -= per_coin_budget
                                self.risk_manager.record_trade_entry(sym)
                                if sym in self.scanner.watchlist.tracking:
                                    del self.scanner.watchlist.tracking[sym]
                                self.log(f"🟢 CANLI Portföye Eklendi [{sym}]: Miktar={pos['quantity']:.4f} | Sepet: {open_count}/{target_count} | Neden: {buy_reason}")
        else:
            # Tekil parite modu (örn. USDT_TRY)
            sym = self.config.trading.symbol
            engine = self.get_engine_for(sym)
            snap = engine.update_market_state()
            if not snap or snap["price"] <= 0:
                return

            self.latest_snapshot = snap
            cur_p = snap["price"]
            signal, signal_reason = self.strategy.evaluate(snap, open_count)

            if open_count > 0:
                self.current_status_text = f"Pozisyon Takip Ediliyor ({open_count} açık)"
            else:
                self.current_status_text = f"Piyasa Taranıyor: {signal_reason}"

            if can_open and signal == "BUY":
                budget = self.config.trading.budget_per_trade
                self.log(f"⚡ ALIŞ SİNYALİ [{sym}]: {signal_reason}")
                if mode == "simulation":
                    pos = self.simulator.buy(sym, cur_p, budget, reason=signal_reason)
                    if pos:
                        self.risk_manager.record_trade_entry()
                        self.log(f"🟢 Sanal Alış Açıldı [{sym}]: Fiyat={cur_p:.4f} TL | Maliyet={budget:.2f} TL")
                else:
                    pos = self.live_trader.buy(sym, cur_p, budget, reason=signal_reason)
                    if pos:
                        self.risk_manager.record_trade_entry()
                        self.log(f"🟢 CANLI Alış Açıldı [{sym}]: Fiyat={cur_p:.4f} TL")

    def _generate_final_report(self) -> Dict[str, str]:
        current_price = self.latest_snapshot.get("price", 0.0)
        if self.config.trading.mode == "live":
            summary = self.live_trader.get_summary(current_price)
            closed_trades = self.live_trader.closed_trades
            equity_curve = []
        else:
            summary = self.simulator.get_summary(current_price)
            closed_trades = self.simulator.closed_trades
            equity_curve = self.simulator.equity_curve

        metrics = PerformanceMetrics.calculate(
            initial_balance=summary["initial_balance"],
            final_equity=summary["total_equity"],
            closed_trades=closed_trades,
            equity_curve=equity_curve,
        )

        cfg_dict = {
            "trading": {
                "mode": self.config.trading.mode,
                "symbol": self.config.trading.symbol,
                "budget_per_trade": self.config.trading.budget_per_trade,
            },
            "strategy": {
                "active": self.config.strategy.active,
                "take_profit_pct": self.config.strategy.take_profit_pct,
                "stop_loss_pct": self.config.strategy.stop_loss_pct,
            },
            "test": {
                "duration_minutes": int(self.session_duration_seconds / 60),
            }
        }

        return self.report_generator.generate_report(
            config_data=cfg_dict,
            metrics=metrics,
            closed_trades=closed_trades,
            equity_curve=equity_curve,
        )

    def get_dashboard_state(self) -> Dict[str, Any]:
        """
        Web paneli için anlık durum bilgisi.
        Ağ çağrısı yapmadan tamamen bellek içi (in-memory) çalışarak sunucu ve arayüz donmasını önler.
        """
        is_live = self.config.trading.mode == "live"
        current_price = self.latest_snapshot.get("price", 0.0)
        if is_live:
            summary = self.live_trader.get_summary(current_price)
        else:
            summary = self.simulator.get_summary(current_price)

        elapsed_seconds = 0
        remaining_seconds = 0
        if self.is_running and self.session_start_time:
            elapsed_seconds = int(time.time() - self.session_start_time)
            if self.session_duration_seconds > 0:
                remaining_seconds = max(0, self.session_duration_seconds - elapsed_seconds)

        radar_pairs = getattr(self.scanner, "cached_top_pairs", []) or []
        if not radar_pairs and hasattr(self, "scanner"):
            radar_pairs = self.scanner.scan_top_active_pairs(limit=0, force_refresh=False)

        return {
            "is_running": self.is_running,
            "mode": self.config.trading.mode,
            "symbol": self.config.trading.symbol,
            "strategy": self.config.strategy.active,
            "elapsed_seconds": elapsed_seconds,
            "remaining_seconds": remaining_seconds,
            "session_duration_minutes": int(self.session_duration_seconds / 60),
            "market": self.latest_snapshot,
            "portfolio": summary,
            "config": {
                "budget_per_trade": self.config.trading.budget_per_trade,
                "take_profit_pct": self.config.strategy.take_profit_pct,
                "stop_loss_pct": self.config.strategy.stop_loss_pct,
                "trailing_stop_pct": self.config.strategy.trailing_stop_pct,
                "trailing_activation_pct": getattr(self.config.strategy, "trailing_activation_pct", 0.20),
                "portfolio_stop_loss_pct": getattr(self.config.strategy, "portfolio_stop_loss_pct", 2.0),
                "symbol_cooldown_seconds": getattr(self.config.strategy, "symbol_cooldown_seconds", 60),
                "rsi_oversold": self.config.strategy.rsi_oversold,
                "rsi_overbought": self.config.strategy.rsi_overbought,
                "auto_select_coin": self.config.trading.auto_select_coin,
                "target_coins_count": getattr(self.config.trading, "target_coins_count", 5),
                "auto_fill_portfolio": getattr(self.config.trading, "auto_fill_portfolio", True),
                "candidate_observation_seconds": getattr(self.config.trading, "candidate_observation_seconds", 45),
                "min_observation_gain_pct": getattr(self.config.trading, "min_observation_gain_pct", 1.5),
                "candidate_min_burst_count": getattr(self.config.trading, "candidate_min_burst_count", 2),
                "candidate_timeout_cooldown_seconds": getattr(self.config.trading, "candidate_timeout_cooldown_seconds", 5),
                "filter_falling_coins": getattr(self.config.trading, "filter_falling_coins", True),
                "only_uptrend": getattr(self.config.trading, "only_uptrend", True),
                "prevent_rebuy_churn": getattr(self.config.trading, "prevent_rebuy_churn", True),
            },
            "status_text": self.current_status_text,
            "current_regime": getattr(self.strategy, "current_regime", "RANGING"),
            "step_count": self.step_count,
            "radar_top_coins": radar_pairs,
            "logs": self.logs[-60:],
            "last_report": self.last_report,
        }
