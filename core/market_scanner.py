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
    Piyasa radarının tespit ettiği hareketli coinleri hemen almak yerine en az 30 saniye
    canlı tahta ve fiyat hareketleriyle izleyen, sürekli tepe aşağı düşen (dump / düşen bıçak)
    coinleri eleyen ve yalnızca mantıklı yukarı tepki / stabilizasyon gösterenleri onaylayan gözlem radarı.
    """
    def __init__(self, min_observation_seconds: int = 30):
        self.min_observation_seconds = min_observation_seconds
        self.tracking: Dict[str, Dict[str, Any]] = {}

    def observe(self, symbol: str, current_price: float, rsi: float = 50.0) -> Tuple[bool, str, int]:
        """
        Coini gözlem listesinde değerlendirir.
        Döner: (is_approved: bool, reason: str, elapsed_seconds: int)
        """
        now = time.time()
        if symbol not in self.tracking:
            self.tracking[symbol] = {
                "first_seen": now,
                "last_seen": now,
                "first_price": current_price,
                "lowest_price": current_price,
                "highest_price": current_price,
                "prices": [current_price],
                "rsi_list": [rsi],
            }
            if self.min_observation_seconds <= 0:
                return True, "Doğrudan Onaylandı", 0
            return False, f"Yeni takibe alındı (0/{self.min_observation_seconds}s)", 0

        info = self.tracking[symbol]
        info["last_seen"] = now
        info["prices"].append(current_price)
        if len(info["prices"]) > 80:
            info["prices"].pop(0)

        if current_price < info["lowest_price"]:
            info["lowest_price"] = current_price
        if current_price > info["highest_price"]:
            info["highest_price"] = current_price

        info["rsi_list"].append(rsi)
        if len(info["rsi_list"]) > 30:
            info["rsi_list"].pop(0)

        elapsed = int(now - info["first_seen"])
        first_p = info["first_price"]
        pct_change = ((current_price - first_p) / first_p) * 100.0 if first_p > 0 else 0.0

        # 1. Kural: En az 30 saniye izlenmeli (acele etmesin)
        if elapsed < self.min_observation_seconds:
            return False, f"İzleniyor ({elapsed}/{self.min_observation_seconds}s | Takip Değişimi: %{pct_change:+.2f})", elapsed

        # 2. Kural: Sürekli tepe aşağı inen coini engelleme (Anti-dump / Düşen bıçak filtresi)
        recent_prices = info["prices"][-4:]
        is_falling = len(recent_prices) >= 4 and all(recent_prices[i] > recent_prices[i+1] for i in range(len(recent_prices)-1))

        if pct_change < -0.25 or is_falling:
            return False, f"⚠️ Tepe aşağı düşüş eğiliminde (%{pct_change:+.2f}), düşen bıçak engellendi", elapsed

        # 3. Kural: RSI aşırı zayıf ve düşüş sürüyorsa engelle
        recent_rsi = sum(info["rsi_list"][-3:]) / len(info["rsi_list"][-3:]) if info["rsi_list"] else 50.0
        if recent_rsi < 30.0 and pct_change < -0.10:
            return False, f"⚠️ RSI zayıf ({recent_rsi:.1f}) ve satış baskısı sürüyor", elapsed

        # 4. Kural: Mantıklı hareket onayı (Fiyat dengelenmiş veya dipten yukarı dönmüş)
        bounce_from_low = ((current_price - info["lowest_price"]) / info["lowest_price"]) * 100.0 if info["lowest_price"] > 0 else 0.0

        if pct_change >= -0.10 or bounce_from_low >= 0.08:
            return True, f"✅ Mantıklı hareket onaylandı ({elapsed}s izlendi | Değişim: %{pct_change:+.2f} | Dip Tepkisi: %{bounce_from_low:+.2f})", elapsed

        return False, f"Yatay/Kararsız seyir ({elapsed}s, %{pct_change:+.2f}), toparlanma bekleniyor", elapsed

    def get_info(self, symbol: str) -> Dict[str, Any]:
        if symbol not in self.tracking:
            return {"status": "untracked", "elapsed": 0, "min_sec": self.min_observation_seconds}
        info = self.tracking[symbol]
        elapsed = int(time.time() - info["first_seen"])
        first_p = info["first_price"]
        cur_p = info["prices"][-1] if info["prices"] else first_p
        pct = ((cur_p - first_p) / first_p) * 100.0 if first_p > 0 else 0.0
        return {
            "elapsed": elapsed,
            "min_sec": self.min_observation_seconds,
            "change_pct": round(pct, 2),
            "is_ready": elapsed >= self.min_observation_seconds,
        }

class MarketScanner:
    """
    Binance TR pazarındaki tüm çiftleri tarayarak en çok dalgalanan (volatil)
    ve hacimli coinleri otomatik tespit eden piyasa radarı.
    Yalnızca Binance TR'de listeli ve işlem gören çiftleri seçer.
    """
    def __init__(self, client: Optional[BinanceTrClient] = None, quote_asset: str = "TRY", min_volume_try: float = 100000.0):
        self.client = client or BinanceTrClient()
        self.quote_asset = quote_asset.upper()
        self.min_volume_try = min_volume_try
        self.cached_top_pairs: List[Dict[str, Any]] = []
        self.tr_listed_symbols: Set[str] = set()
        self.last_scan_time: float = 0.0
        self.scan_cache_ttl_seconds: int = 15  # 15 saniye aralıkla yeniden tara
        self.watchlist = CandidateWatchlist(min_observation_seconds=30)
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
        only_uptrend=True ise düşüş trendindeki (negatif 24s getiri) coinleri eler,
        yalnızca pozitif veya toparlanan yükseliş trendindeki coinleri seçer.
        """
        now = time.time()
        if not force_refresh and (now - self.last_scan_time < self.scan_cache_ttl_seconds) and self.cached_top_pairs:
            pairs = self.cached_top_pairs
            if only_uptrend:
                filtered = [p for p in pairs if p["change_pct"] >= min_gain_pct]
                return filtered[:limit] if filtered else pairs[:limit]
            return pairs[:limit]

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
            return self.cached_top_pairs[:limit] if self.cached_top_pairs else []

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

        # En yüksek volatiliteye göre sırala
        valid_pairs.sort(key=lambda x: x["abs_change"], reverse=True)

        if valid_pairs:
            self.cached_top_pairs = valid_pairs
            self.last_scan_time = now

        pairs = self.cached_top_pairs or []
        if only_uptrend and pairs:
            filtered = [p for p in pairs if p["change_pct"] >= min_gain_pct]
            return filtered[:limit] if filtered else pairs[:limit]

        return pairs[:limit]
