import time
import requests
import logging
from typing import List, Dict, Any, Optional, Set, Tuple
from core.binance_client import BinanceTrClient

logger = logging.getLogger("MarketScanner")

# Hariç tutulacak sabit koinler ve itibari para birimleri
STABLE_ASSETS = {
    "USDT", "USDC", "FDUSD", "TUSD", "BUSD", "EUR", "EURI", "AEUR", "TRY", "PAX", "DAI"
}

class CandidateWatchlist:
    """
    Piyasa radarının tespit ettiği coinleri anlık canlı tahtada izleyen gözlem radarı.
    Kural: 45 saniye içerisinde en az %1.50 (min_gain_pct) oranında gerçek yukarı patlama / ivme gösteren
    coinleri onaylar. 45 saniye içinde bu ivmeyi gösteremeyen veya düşen coinleri takipten çıkarır,
    dinlenmeye alır ve radarın diğer coinlere geçmesini sağlar (Dinamik Aday Rotasyonu).
    """
    def __init__(
        self,
        min_observation_seconds: int = 45,
        min_gain_pct: float = 1.0,
        timeout_cooldown_seconds: int = 5,
        min_burst_count: int = 2,
    ):
        self.min_observation_seconds = min_observation_seconds
        self.min_gain_pct = min_gain_pct
        self.timeout_cooldown_seconds = timeout_cooldown_seconds
        self.min_burst_count = min_burst_count
        self.tracking: Dict[str, Dict[str, Any]] = {}
        self.cooldowns: Dict[str, float] = {}

    def is_cooling_down(self, symbol: str) -> bool:
        """Coinin gözlem zaman aşımı dinlenmesinde olup olmadığını kontrol eder."""
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
            return True, "Doğrudan Onaylandı", 0

        now = time.time()

        # 1. Zaman aşımı dinlenme kontrolü (Radar diğer coinlere yönlendirilir)
        if symbol in self.cooldowns:
            if now < self.cooldowns[symbol]:
                rem = int(self.cooldowns[symbol] - now)
                return False, f"⏳ Zaman aşımı dinlenmesinde ({rem}sn kaldı, radar diğer coinleri tarıyor)", 0
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
            return False, f"Takibe alındı (0/{self.min_observation_seconds}s | İvme: %0.00 / Hedef: %{self.min_gain_pct:.2f} | Patlama: 0/{self.min_burst_count})", 0

        info = self.tracking[symbol]
        info["last_seen"] = now
        info["history"].append((now, current_price))
        info["rsi_list"].append(rsi)

        # Son 90 saniyeden eski verileri temizle
        cutoff = now - max(90.0, self.min_observation_seconds * 2.0)
        info["history"] = [(t, p) for t, p in info["history"] if t >= cutoff]
        if len(info["rsi_list"]) > 40:
            info["rsi_list"].pop(0)

        elapsed = int(now - info["first_seen"])

        # 45s (1. Tur) ve 90s (Ekstra 2. Tur) pencerelerindeki veriler
        cutoff_single = now - self.min_observation_seconds
        prices_single = [p for t, p in info["history"] if t >= cutoff_single] or [current_price]
        lowest_single = min(prices_single)
        first_single = prices_single[0]
        gain_single = max(
            ((current_price - lowest_single) / lowest_single) * 100.0 if lowest_single > 0 else 0.0,
            ((current_price - first_single) / first_single) * 100.0 if first_single > 0 else 0.0,
        )
        bursts_single = sum(1 for i in range(1, len(prices_single)) if prices_single[i] > prices_single[i-1])

        cutoff_double = now - (self.min_observation_seconds * 2.0)
        prices_double = [p for t, p in info["history"] if t >= cutoff_double] or [current_price]
        lowest_double = min(prices_double)
        first_double = prices_double[0]
        gain_double = max(
            ((current_price - lowest_double) / lowest_double) * 100.0 if lowest_double > 0 else 0.0,
            ((current_price - first_double) / first_double) * 100.0 if first_double > 0 else 0.0,
        )
        bursts_double = sum(1 for i in range(1, len(prices_double)) if prices_double[i] > prices_double[i-1])

        # Bir hareketin "patlama" sayılması için gereken asgari ivme eşiği (%0.75)
        single_burst_threshold = self.min_gain_pct / 2.0

        # Eğer coin 45s içinde en az 1 defa patlama (%0.75+ ivme) yakaladıysa listeden çıkarılmaz, 1 tur daha (+45s) takip edilir
        has_first_burst = (gain_single >= single_burst_threshold) or (gain_double >= single_burst_threshold)
        max_allowed_seconds = (self.min_observation_seconds * 2) if has_first_burst else self.min_observation_seconds

        window_prices = prices_double if (has_first_burst and elapsed >= self.min_observation_seconds) else prices_single
        burst_count = bursts_double if (has_first_burst and elapsed >= self.min_observation_seconds) else bursts_single
        max_recent_gain = gain_double if (has_first_burst and elapsed >= self.min_observation_seconds) else gain_single

        # 2. Kural: 45s / 90s içerisinde hedeflenen kazanç (%1.50) ve en az 2 defa patlama yakalandı mı?
        if max_recent_gain >= self.min_gain_pct and burst_count >= self.min_burst_count:
            return True, f"🚀 ÇİFTE PATLAMA TEYİDİ ({burst_count}/{self.min_burst_count}): {min(elapsed, max_allowed_seconds)}sn içinde %{max_recent_gain:+.2f} yükseldi ve {burst_count} defa patlama teyit edildi (Hedef: >= %{self.min_gain_pct:.2f})", elapsed

        # 3. Kural: Sürekli düşen bıçak kontrolü -> Takipten çıkar ve diğer coinlere geç
        if len(window_prices) >= 4 and all(window_prices[i] > window_prices[i+1] for i in range(len(window_prices)-1)):
            if symbol in self.tracking:
                del self.tracking[symbol]
            self.cooldowns[symbol] = now + self.timeout_cooldown_seconds
            return False, f"⚠️ Düşüş eğiliminde (İvme: %{max_recent_gain:+.2f}), düşen bıçak engellendi -> Radar diğer coinlere geçti", elapsed

        # 4. Kural: İzleme süresi dolmadıysa takip devam eder (1 patlama varsa 2. tur boyunca devam eder)
        if elapsed < max_allowed_seconds:
            if elapsed >= self.min_observation_seconds:
                return False, f"İzleniyor - Ekstra 2. Tur ({elapsed}/{max_allowed_seconds}s | 1 Patlama yakalandı, 2. teyit bekleniyor | İvme: %{max_recent_gain:+.2f})", elapsed
            else:
                burst_info = f" | Patlama: {burst_count}/{self.min_burst_count}" if self.min_burst_count > 1 else ""
                return False, f"İzleniyor ({elapsed}/{self.min_observation_seconds}s | Anlık İvme: %{max_recent_gain:+.2f}{burst_info} / Hedef: %{self.min_gain_pct:.2f})", elapsed
        else:
            # 5. Kural: Süre doldu (hiç patlama yoksa 45s, 1 patlama varsa 90s sonunda 2. gelmediyse) -> Takipten çıkar, dinlendir
            if symbol in self.tracking:
                del self.tracking[symbol]
            self.cooldowns[symbol] = now + self.timeout_cooldown_seconds
            return False, f"🔄 GÖZLEM ZAMAN AŞIMI ({elapsed}s): %{self.min_gain_pct:.2f} ivme veya {self.min_burst_count} patlama yakalanamadı ({burst_count}/{self.min_burst_count}), radar diğer coinlere geçti ({self.timeout_cooldown_seconds}s dinlenme)", elapsed

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
        cutoff_single = now - self.min_observation_seconds
        prices_single = [p for t, p in info["history"] if t >= cutoff_single] or [info.get("first_price", 0.0)]
        lowest_single = min(prices_single)
        gain_single = ((prices_single[-1] - lowest_single) / lowest_single) * 100.0 if lowest_single > 0 else 0.0
        bursts_single = sum(1 for i in range(1, len(prices_single)) if prices_single[i] > prices_single[i-1])

        cutoff_double = now - (self.min_observation_seconds * 2.0)
        prices_double = [p for t, p in info["history"] if t >= cutoff_double] or [info.get("first_price", 0.0)]
        lowest_double = min(prices_double)
        gain_double = ((prices_double[-1] - lowest_double) / lowest_double) * 100.0 if lowest_double > 0 else 0.0
        bursts_double = sum(1 for i in range(1, len(prices_double)) if prices_double[i] > prices_double[i-1])

        single_burst_threshold = self.min_gain_pct / 2.0
        has_first_burst = (gain_single >= single_burst_threshold) or (gain_double >= single_burst_threshold)
        max_allowed_seconds = (self.min_observation_seconds * 2) if has_first_burst else self.min_observation_seconds
        burst_count = bursts_double if (has_first_burst and elapsed >= self.min_observation_seconds) else bursts_single
        pct = gain_double if (has_first_burst and elapsed >= self.min_observation_seconds) else gain_single

        return {
            "status": "tracking",
            "elapsed": elapsed,
            "min_sec": max_allowed_seconds,
            "change_pct": round(pct, 2),
            "target_gain_pct": self.min_gain_pct,
            "burst_count": burst_count,
            "min_burst_count": self.min_burst_count,
            "is_ready": pct >= self.min_gain_pct and burst_count >= self.min_burst_count,
        }

class MarketScanner:
    """
    Binance TR pazarındaki tüm çiftleri tarayarak en çok dalgalanan (volatil)
    ve hacimli coinleri otomatik tespit eden piyasa radarı.
    Yalnızca Binance TR'de listeli ve işlem gören çiftleri seçer.
    """
    def __init__(self, client: Optional[BinanceTrClient] = None, quote_asset: str = "TRY", min_volume_try: float = 5000000.0):
        self.client = client or BinanceTrClient()
        self.quote_asset = quote_asset.upper()
        self.min_volume_try = min_volume_try
        self.cached_top_pairs: List[Dict[str, Any]] = []
        self.tr_listed_symbols: Set[str] = set()
        self.last_scan_time: float = 0.0
        self.scan_cache_ttl_seconds: int = 15  # 15 saniye aralıkla yeniden tara
        self.watchlist = CandidateWatchlist(min_observation_seconds=45, min_gain_pct=1.0, timeout_cooldown_seconds=5, min_burst_count=2)
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

    def scan_top_active_pairs(
        self,
        limit: int = 8,
        force_refresh: bool = False,
        only_uptrend: bool = True,
        min_gain_pct: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Binance TR'de işlem gören en hareketli TRY çiftlerini tespit eder ve sıralar.
        Zaman aşımına uğramış (dinlenmedeki) coinleri arkaya atar, taze adayları öne alır.
        only_uptrend=True ise düşüş trendindeki (negatif 24s getiri) coinleri eler.
        """
        now = time.time()
        if not force_refresh and (now - self.last_scan_time < self.scan_cache_ttl_seconds) and self.cached_top_pairs:
            pairs = sorted(
                self.cached_top_pairs,
                key=lambda x: (
                    1 if self.watchlist.is_cooling_down(x["symbol"]) else 0,
                    -x.get("abs_change", 0.0)
                )
            )
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

            # Binance TR sembol biçimi: Örn. SOL_TRY
            tr_symbol = f"{base}_{suffix}"

            # Yalnızca Binance TR'de listeli olanları kabul et
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

            valid_pairs.append({
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
            })

        # Dinlenmede olmayan taze adayları öne, en yüksek volatiliteye göre sırala
        valid_pairs.sort(key=lambda x: (
            1 if self.watchlist.is_cooling_down(x["symbol"]) else 0,
            -x["abs_change"]
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
