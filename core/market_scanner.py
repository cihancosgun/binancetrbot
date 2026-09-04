import time
import requests
import logging
import math
from typing import List, Dict, Any, Optional, Set, Tuple
from core.binance_client import BinanceTrClient

logger = logging.getLogger("MarketScanner")

# Hariç tutulacak sabit koinler ve itibari para birimleri
STABLE_ASSETS = {
    "USDT", "USDC", "FDUSD", "TUSD", "BUSD", "EUR", "EURI", "AEUR", "TRY", "PAX", "DAI"
}

class CandidateWatchlist:
    """
    Kantitatif Aday İzleme ve Filtreleme Motoru (Quant Momentum Watchlist).
    
    Özellikler:
    1. İvme ve Trend Filtresi: Radarın seçtiği adayların anlık ivmesini doğrular.
    2. Düşen Bıçak Koruması: Sürekli düşüş trendindeki varlıkları derhal eler.
    3. Hızlı Teyit / Rotasyon: Belirlenen sürede ivme yakalayan güçlü adaylara onay verir.
    """
    def __init__(
        self,
        min_observation_seconds: int = 15,
        min_gain_pct: float = 0.5,
        timeout_cooldown_seconds: int = 10,
        min_burst_count: int = 1,
    ):
        self.min_observation_seconds = min_observation_seconds
        self.min_gain_pct = min_gain_pct
        self.timeout_cooldown_seconds = timeout_cooldown_seconds
        self.min_burst_count = min_burst_count
        self.tracking: Dict[str, Dict[str, Any]] = {}
        self.cooldowns: Dict[str, float] = {}

    def is_cooling_down(self, symbol: str) -> bool:
        """Coinin soğuma/dinlenme süresinde olup olmadığını kontrol eder."""
        if symbol in self.cooldowns:
            if time.time() < self.cooldowns[symbol]:
                return True
            else:
                del self.cooldowns[symbol]
        return False

    def observe(self, symbol: str, current_price: float, rsi: float = 50.0) -> Tuple[bool, str, int]:
        """
        Coini gözlem listesinde değerlendirir.
        Döner: (is_approved: bool, reason: str, elapsed_seconds: int)
        """
        if self.min_observation_seconds <= 0:
            return True, "Doğrudan Teyit Edildi", 0

        now = time.time()

        # 1. Soğuma kontrolü
        if symbol in self.cooldowns:
            if now < self.cooldowns[symbol]:
                rem = int(self.cooldowns[symbol] - now)
                return False, f"⏳ Dinlenmede ({rem}sn kaldı, radar diğer coinleri tarıyor)", 0
            else:
                del self.cooldowns[symbol]

        if symbol not in self.tracking:
            self.tracking[symbol] = {
                "first_seen": now,
                "last_seen": now,
                "first_price": current_price,
                "history": [(now, current_price)],
                "rsi_list": [rsi],
            }
            return False, f"Takibe alındı (0/{self.min_observation_seconds}s | İvme Hedefi: +%{self.min_gain_pct:.2f})", 0

        info = self.tracking[symbol]
        info["last_seen"] = now
        info["history"].append((now, current_price))
        info["rsi_list"].append(rsi)

        # Son 90 saniyeden eski verileri temizle
        cutoff = now - max(90.0, self.min_observation_seconds * 2.0)
        info["history"] = [(t, p) for t, p in info["history"] if t >= cutoff]
        if len(info["rsi_list"]) > 30:
            info["rsi_list"].pop(0)

        elapsed = int(now - info["first_seen"])
        prices = [p for t, p in info["history"]]
        if not prices:
            prices = [current_price]

        lowest_p = min(prices)
        first_p = prices[0]
        gain_pct = max(
            ((current_price - lowest_p) / lowest_p) * 100.0 if lowest_p > 0 else 0.0,
            ((current_price - first_p) / first_p) * 100.0 if first_p > 0 else 0.0,
        )
        burst_count = sum(1 for i in range(1, len(prices)) if prices[i] > prices[i-1])

        # 1. Düşen bıçak kontrolü (Sürekli düşüş ve gerçek negatif kayıp varsa beklemeden elenir)
        drop_from_start = ((first_p - current_price) / first_p) * 100.0 if first_p > 0 else 0.0
        is_falling_series = (
            len(prices) >= 4 
            and all(prices[i] >= prices[i+1] for i in range(len(prices)-1))
            and any(prices[i] > prices[i+1] for i in range(len(prices)-1))
        )
        if is_falling_series and drop_from_start >= 0.20:
            del self.tracking[symbol]
            self.cooldowns[symbol] = now + self.timeout_cooldown_seconds
            return False, f"⚠️ Düşüş eğiliminde (Düşüş: %{-drop_from_start:.2f}), düşen bıçak engellendi -> Radar diğer coinlere geçti", elapsed

        # 2. İvme Onayı
        if (gain_pct >= self.min_gain_pct and burst_count >= self.min_burst_count) or (elapsed >= self.min_observation_seconds and gain_pct >= 0.10):
            return True, f"🚀 MOMENTUM TEYİDİ: {elapsed}sn içinde %{gain_pct:+.2f} ivme doğrulandı", elapsed

        # 3. İzleme devam ediyor
        if elapsed < self.min_observation_seconds:
            return False, f"İzleniyor ({elapsed}/{self.min_observation_seconds}s | İvme: %{gain_pct:+.2f} / Hedef: %{self.min_gain_pct:.2f})", elapsed

        # 4. Zaman aşımı
        del self.tracking[symbol]
        self.cooldowns[symbol] = now + self.timeout_cooldown_seconds
        return False, f"🔄 Zaman aşımı ({elapsed}s): İvme yetersiz, taze adaylara geçiliyor", elapsed

    def get_info(self, symbol: str) -> Dict[str, Any]:
        now = time.time()
        if symbol in self.cooldowns and now < self.cooldowns[symbol]:
            rem = int(self.cooldowns[symbol] - now)
            return {
                "status": "cooling_down",
                "elapsed": 0,
                "min_sec": self.min_observation_seconds,
                "change_pct": 0.0,
                "target_gain_pct": self.min_gain_pct,
                "burst_count": 0,
                "min_burst_count": self.min_burst_count,
                "is_ready": False,
                "cooldown_remaining": rem,
            }
        if symbol not in self.tracking:
            return {
                "status": "untracked",
                "elapsed": 0,
                "min_sec": self.min_observation_seconds,
                "burst_count": 0,
                "min_burst_count": self.min_burst_count,
                "is_ready": False,
            }
        info = self.tracking[symbol]
        elapsed = int(time.time() - info["first_seen"])
        prices = [p for t, p in info["history"]] or [info.get("first_price", 0.0)]
        lowest = min(prices)
        gain = ((prices[-1] - lowest) / lowest) * 100.0 if lowest > 0 else 0.0
        bursts = sum(1 for i in range(1, len(prices)) if prices[i] > prices[i-1])

        return {
            "status": "tracking",
            "elapsed": elapsed,
            "min_sec": self.min_observation_seconds,
            "change_pct": round(gain, 2),
            "target_gain_pct": self.min_gain_pct,
            "burst_count": bursts,
            "min_burst_count": self.min_burst_count,
            "is_ready": (gain >= self.min_gain_pct and bursts >= self.min_burst_count) or (elapsed >= self.min_observation_seconds and gain >= 0.10),
        }


class MarketScanner:
    """
    Binance TR Çok Faktörlü Kantitatif Piyasa Radarı (Multi-Factor Quant Radar).
    
    Tüm işlem gören TRY çiftlerini anlık tarar, likidite, hacim, trend ve volatiliteye
    göre puanlayarak en yüksek kâr potansiyeline sahip lider coinleri seçer.
    """
    def __init__(
        self,
        client: Optional[BinanceTrClient] = None,
        quote_asset: str = "TRY",
        min_volume_try: float = 3000000.0,
        max_spread_pct: float = 0.25,
    ):
        self.client = client or BinanceTrClient()
        self.quote_asset = quote_asset.upper()
        self.min_volume_try = min_volume_try
        self.max_spread_pct = max_spread_pct
        self.cached_top_pairs: List[Dict[str, Any]] = []
        self.tr_listed_symbols: Set[str] = set()
        self.last_scan_time: float = 0.0
        self.scan_cache_ttl_seconds: int = 10
        self.watchlist = CandidateWatchlist(
            min_observation_seconds=15,
            min_gain_pct=0.5,
            timeout_cooldown_seconds=10,
            min_burst_count=1,
        )
        self._load_tr_symbols()

    def _load_tr_symbols(self) -> None:
        try:
            symbols = self.client.get_symbols()
            if symbols:
                self.tr_listed_symbols = {
                    s.get("symbol") for s in symbols
                    if s.get("spotTradingEnable", 1) == 1
                }
        except Exception as e:
            logger.warning(f"Binance TR sembol listesi yüklenemedi: {e}")

    def calculate_quant_score(self, pair: Dict[str, Any]) -> float:
        """
        Çok Faktörlü Sıralama Skoru Hesaplar:
        1. Trend & Getiri Skoru (%45)
        2. Likidite & Hacim Skoru (%35)
        3. Volatilite Skoru (%20)
        """
        chg = pair.get("change_pct", 0.0)
        vol = pair.get("volume_try", 0.0)
        high = pair.get("high", 0.0)
        low = pair.get("low", 1.0)

        # 1. Trend Skoru (Pozitif getiriler ödüllendirilir)
        trend_score = max(0.0, chg) if chg > 0 else (chg * 0.5)

        # 2. Hacim Skoru (Logaritmik hacim gücü)
        vol_score = math.log10(max(vol, 1.0)) * 2.0

        # 3. Volatilite Skoru (Günün tepe-dip farkı)
        volatility_pct = ((high - low) / low) * 100.0 if low > 0 else 0.0
        volat_score = min(volatility_pct, 15.0)

        total_score = (trend_score * 0.45) + (vol_score * 0.35) + (volat_score * 0.20)
        return round(total_score, 2)

    def scan_top_active_pairs(
        self,
        limit: int = 8,
        force_refresh: bool = False,
        only_uptrend: bool = True,
        min_gain_pct: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        Binance TR'de işlem gören TRY çiftlerini tarar ve quant skoruna göre sıralar.
        """
        now = time.time()
        if not force_refresh and (now - self.last_scan_time < self.scan_cache_ttl_seconds) and self.cached_top_pairs:
            pairs = self.cached_top_pairs
            if only_uptrend:
                filtered = [p for p in pairs if p["change_pct"] >= min_gain_pct]
                target_list = filtered if filtered else pairs
                return target_list[:limit] if (limit and limit > 0) else target_list
            return pairs[:limit] if (limit and limit > 0) else pairs

        if not self.tr_listed_symbols:
            self._load_tr_symbols()

        endpoints = [
            "https://api.binance.com/api/v3/ticker/24hr",
            "https://api.binance.me/api/v1/ticker/24hr",
        ]

        raw_data = None
        for ep in endpoints:
            try:
                resp = requests.get(ep, timeout=5)
                if resp.status_code == 200:
                    raw_data = resp.json()
                    break
            except Exception:
                continue

        if not raw_data or not isinstance(raw_data, list):
            res = self.cached_top_pairs or []
            return res[:limit] if (limit and limit > 0) else res

        valid_pairs = []
        suffix = self.quote_asset

        for item in raw_data:
            sym = item.get("symbol", "")
            if not sym.endswith(suffix):
                continue

            base = sym[:-len(suffix)]
            if base in STABLE_ASSETS:
                continue

            tr_symbol = f"{base}_{suffix}"
            if self.tr_listed_symbols and tr_symbol not in self.tr_listed_symbols:
                continue

            vol = float(item.get("quoteVolume", 0.0))
            if vol < self.min_volume_try:
                continue

            chg_pct = float(item.get("priceChangePercent", 0.0))
            last_price = float(item.get("lastPrice", 0.0))
            high_price = float(item.get("highPrice", 0.0))
            low_price = float(item.get("lowPrice", 0.0))

            obs_info = self.watchlist.get_info(tr_symbol)

            pair_dict = {
                "symbol": tr_symbol,
                "clean_symbol": sym,
                "base": base,
                "quote": suffix,
                "price": last_price,
                "change_pct": round(chg_pct, 2),
                "abs_change": abs(chg_pct),
                "volume_try": vol,
                "high": high_price,
                "low": low_price,
                "updated_at": now,
                "observation": obs_info,
            }
            pair_dict["quant_score"] = self.calculate_quant_score(pair_dict)
            valid_pairs.append(pair_dict)

        # Dinlenmede olmayanları öne al, quant skoruna göre sırala
        valid_pairs.sort(key=lambda x: (
            1 if self.watchlist.is_cooling_down(x["symbol"]) else 0,
            -x.get("quant_score", 0.0)
        ))

        if valid_pairs:
            self.cached_top_pairs = valid_pairs
            self.last_scan_time = now

        pairs = self.cached_top_pairs or []
        if only_uptrend and pairs:
            filtered = [p for p in pairs if p["change_pct"] >= min_gain_pct]
            target_list = filtered if filtered else pairs
            return target_list[:limit] if (limit and limit > 0) else target_list

        return pairs[:limit] if (limit and limit > 0) else pairs
