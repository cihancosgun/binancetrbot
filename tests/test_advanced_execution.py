import time
import pytest
from config import BotConfig, StrategyConfig, TradingConfig
from core.simulator import SimulatorEngine
from core.risk_manager import RiskManager
from core.market_scanner import MarketScanner, CandidateWatchlist
from strategies.adaptive_regime import AdaptiveRegimeStrategy

def test_partial_take_profit_simulator():
    sim = SimulatorEngine(initial_balance=1000.0, fee_rate_pct=0.10)
    pos = sim.buy("AVAX_TRY", 100.0, 500.0, reason="Test Entry")
    assert pos is not None
    assert abs(pos["quantity"] - 4.995) < 0.001
    assert pos["invested_cost"] == 500.0

    # Sell 50%
    sell_trade = sim.sell(pos["position_id"], 101.0, fraction=0.50, reason="🎯 KADEMELİ KÂR AL (TP1: %+1.00)")
    assert sell_trade is not None
    assert sell_trade["side"] == "PARTIAL_SELL"
    assert sell_trade["is_partial"] is True
    assert abs(pos["quantity"] - (4.995 * 0.5)) < 0.001
    assert pos["invested_cost"] == 250.0
    assert pos["partial_tp_taken"] is True

    # Check risk manager exit evaluation after TP1 taken
    risk_mgr = RiskManager(enable_partial_tp=True, partial_tp_pct=0.85, partial_tp_ratio=0.50, take_profit_pct=2.0)
    should_close, reason, pnl = risk_mgr.evaluate_exit(pos, 101.0)
    # Since partial_tp_taken is True, evaluate_exit should not trigger TP1 again
    assert "KADEMELİ KÂR AL" not in reason

    # Now sell the remainder on final TP
    final_trade = sim.sell(pos["position_id"], 102.5, fraction=1.0, reason="🎯 TAKE-PROFIT: %+2.50")
    assert final_trade is not None
    assert final_trade["side"] == "SELL"
    assert final_trade["is_partial"] is False
    assert pos["position_id"] not in sim.positions
    assert len(sim.closed_trades) == 2

def test_adaptive_regime_rsi_filter():
    strat = AdaptiveRegimeStrategy()
    
    # Overbought snapshot (RSI 75) in Bullish Trend -> Should HOLD (Anti-FOMO)
    snap_overbought = {
        "price": 100.0,
        "ema_fast": 102.0,
        "ema_slow": 98.0,
        "ema_trend_pct": 0.20,
        "rsi": 75.0,
        "adx": 30.0,
        "plus_di": 28.0,
        "minus_di": 12.0,
        "bb_upper": 105.0,
        "bb_lower": 95.0,
        "atr": 1.5,
        "volatility_ratio": 1.2,
        "change_24h_pct": 2.5,
    }
    sig, reason = strat.evaluate(snap_overbought, open_positions_count=0)
    assert sig == "HOLD"
    assert "Aşırı Alım" in reason or "RSI" in reason or "Bekleniyor" in reason

    # Healthy momentum pullback snapshot (RSI 52, near EMA) -> Should BUY
    snap_healthy = {
        "price": 100.0,
        "ema_fast": 100.1,
        "ema_slow": 98.0,
        "ema_trend_pct": 0.20,
        "rsi": 52.0,
        "adx": 30.0,
        "plus_di": 28.0,
        "minus_di": 12.0,
        "bb_upper": 105.0,
        "bb_lower": 95.0,
        "atr": 1.5,
        "volatility_ratio": 1.2,
        "change_24h_pct": 2.5,
    }
    sig2, reason2 = strat.evaluate(snap_healthy, open_positions_count=0)
    assert sig2 == "BUY"

def test_prebuy_stagnancy_filter():
    wl = CandidateWatchlist(window_seconds=10)
    
    # Simulate completely flat coin with no tick change
    now = time.time()
    wl.prebuy_tracking["FLAT_TRY"] = {
        "start_time": now - 12.0,
        "start_price": 10.0,
        "highest_price": 10.0,
        "ticks": [(now - 12.0, 10.0)],
    }

    is_ok, msg, el = wl.observe_prebuy("FLAT_TRY", 10.0, observation_seconds=10)
    assert is_ok is False
    assert "Durgunluk" in msg or "durgun" in msg

def test_btc_dump_shield():
    scanner = MarketScanner(client=None, min_volume_try=1000.0, btc_dump_shield_pct=0.35)
    
    now = time.time()
    scanner.tracker.record_tick("BTC_TRY", 100000.0, timestamp=now - 50.0)
    scanner.tracker.record_tick("BTC_TRY", 100050.0, timestamp=now - 20.0)

    is_dump, _ = scanner.is_btc_dumping()
    assert is_dump is False

    # Simulate BTC sudden 0.6% dump
    scanner.tracker.record_tick("BTC_TRY", 99400.0, timestamp=now)
    is_dump, msg = scanner.is_btc_dumping()
    assert is_dump is True
    assert "Satış Dalgası" in msg or "Kalkanı" in msg
