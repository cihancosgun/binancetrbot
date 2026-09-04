import time
import math
from typing import List, Dict, Any, Optional
from core.binance_client import BinanceTrClient

class MarketDataEngine:
    """
    Binance TR için anlık piyasa verisi, mum geçmişi ve teknik gösterge (RSI, Bollinger, EMA) hesaplayıcı motor.
    """
    def __init__(self, client: BinanceTrClient, symbol: str = "USDT_TRY"):
        self.client = client
        self.symbol = symbol
        self.price_history: List[float] = []
        self.candle_closes: List[float] = []
        self.candle_highs: List[float] = []
        self.candle_lows: List[float] = []
        self.last_price: float = 0.0
        self.last_bid: float = 0.0
        self.last_ask: float = 0.0
        self.last_spread_pct: float = 0.0
        self.last_update_time: float = 0.0
        self.last_klines_update_time: float = 0.0
        self.cache_ttl_seconds: float = 0.8
        self.klines_cache_ttl_seconds: float = 12.0
        self._cached_snapshot: Optional[Dict[str, Any]] = None

    def update_market_state(self, force: bool = False) -> Optional[Dict[str, Any]]:
        """
        Binance TR'den anlık derinlik ve fiyatı çeker, geçmişi günceller.
        Önbellek mekanizması ile sunucuyu ve arayüzü kilitlemeyi/kasmayı engeller.
        """
        now = time.time()
        if not force and (now - self.last_update_time < self.cache_ttl_seconds) and self._cached_snapshot:
            return self._cached_snapshot

        prices = self.client.get_best_prices(self.symbol)
        if not prices:
            return self._cached_snapshot

        self.last_bid = prices["bid"]
        self.last_ask = prices["ask"]
        self.last_price = prices["bid"] if prices["bid"] > 0 else prices["mid"]
        self.last_spread_pct = prices["spread_pct"]
        self.last_update_time = now

        self.price_history.append(self.last_price)
        if len(self.price_history) > 500:
            self.price_history.pop(0)

        # Mum verilerini her saniye değil, 12 saniyede bir çekerek gereksiz ağ yükünü ve gecikmeyi önle
        if (now - self.last_klines_update_time >= self.klines_cache_ttl_seconds) or not self.candle_closes:
            klines = self.client.get_klines(self.symbol, interval="1m", limit=50)
            if klines:
                closes, highs, lows = [], [], []
                for k in klines:
                    if isinstance(k, list) and len(k) >= 5:
                        highs.append(float(k[2]))
                        lows.append(float(k[3]))
                        closes.append(float(k[4]))
                    elif isinstance(k, dict) and "close" in k:
                        c_val = float(k["close"])
                        highs.append(float(k.get("high", c_val)))
                        lows.append(float(k.get("low", c_val)))
                        closes.append(c_val)
                if closes:
                    self.candle_closes = closes
                    self.candle_highs = highs
                    self.candle_lows = lows
                    self.last_klines_update_time = now
            else:
                if len(self.price_history) >= 2:
                    self.candle_closes = self.price_history[-50:]
                    self.candle_highs = self.price_history[-50:]
                    self.candle_lows = self.price_history[-50:]

        self._cached_snapshot = self.get_snapshot()
        return self._cached_snapshot

    def calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """
        Göreceli Güç Endeksi (RSI) hesaplar.
        """
        if len(prices) < period + 1:
            return 50.0  # Yeterli veri yoksa nötr

        gains = []
        losses = []
        for i in range(1, len(prices)):
            change = prices[i] - prices[i - 1]
            if change >= 0:
                gains.append(change)
                losses.append(0.0)
            else:
                gains.append(0.0)
                losses.append(abs(change))

        # Wilder's smoothing
        recent_gains = gains[-period:]
        recent_losses = losses[-period:]
        avg_gain = sum(recent_gains) / period
        avg_loss = sum(recent_losses) / period

        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0

        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return round(rsi, 2)

    def calculate_bollinger_bands(self, prices: List[float], period: int = 20, num_std: float = 2.0) -> Dict[str, float]:
        """
        Bollinger Bantlarını hesaplar (Alt bant, Orta bant/SMA, Üst bant).
        """
        if len(prices) < period:
            current = prices[-1] if prices else self.last_price
            return {"upper": current * 1.01, "middle": current, "lower": current * 0.99}

        recent = prices[-period:]
        middle = sum(recent) / period
        variance = sum((x - middle) ** 2 for x in recent) / period
        std_dev = math.sqrt(variance)

        upper = middle + (std_dev * num_std)
        lower = middle - (std_dev * num_std)

        return {
            "upper": round(upper, 6),
            "middle": round(middle, 6),
            "lower": round(lower, 6),
        }

    def calculate_ema(self, prices: List[float], period: int) -> float:
        """
        Üssel Hareketli Ortalama (EMA) hesaplar.
        """
        if not prices:
            return self.last_price
        if len(prices) < period:
            return sum(prices) / len(prices)

        multiplier = 2.0 / (period + 1.0)
        ema = sum(prices[:period]) / period
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        return round(ema, 6)

    def calculate_atr(self, highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
        """
        Ortalama Gerçek Aralık (Average True Range - ATR) hesaplar.
        """
        n = min(len(highs), len(lows), len(closes))
        if n < 2:
            return 0.0
        trs = []
        for i in range(1, n):
            h = highs[i]
            l = lows[i]
            prev_c = closes[i - 1]
            tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
            trs.append(tr)
        if not trs:
            return 0.0
        recent = trs[-period:]
        return round(sum(recent) / len(recent), 6)

    def calculate_adx(self, highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> Dict[str, float]:
        """
        Average Directional Index (ADX) hesaplar.
        ADX >= 22 -> Güçlü Trend
        ADX < 20 -> Yatay Kanal
        """
        n = min(len(highs), len(lows), len(closes))
        if n < period + 1:
            return {"adx": 18.0, "plus_di": 20.0, "minus_di": 20.0}

        plus_dms = []
        minus_dms = []
        trs = []

        for i in range(1, n):
            h_diff = highs[i] - highs[i - 1]
            l_diff = lows[i - 1] - lows[i]

            plus_dm = h_diff if (h_diff > l_diff and h_diff > 0) else 0.0
            minus_dm = l_diff if (l_diff > h_diff and l_diff > 0) else 0.0

            tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))

            plus_dms.append(plus_dm)
            minus_dms.append(minus_dm)
            trs.append(tr)

        if len(trs) < period:
            return {"adx": 18.0, "plus_di": 20.0, "minus_di": 20.0}

        tr_smooth = sum(trs[-period:])
        plus_smooth = sum(plus_dms[-period:])
        minus_smooth = sum(minus_dms[-period:])

        if tr_smooth <= 0:
            return {"adx": 18.0, "plus_di": 20.0, "minus_di": 20.0}

        plus_di = (plus_smooth / tr_smooth) * 100.0
        minus_di = (minus_smooth / tr_smooth) * 100.0

        di_sum = plus_di + minus_di
        dx = (abs(plus_di - minus_di) / di_sum) * 100.0 if di_sum > 0 else 0.0

        return {
            "adx": round(dx, 2),
            "plus_di": round(plus_di, 2),
            "minus_di": round(minus_di, 2),
        }

    def get_snapshot(self) -> Dict[str, Any]:
        """
        Strateji ve arayüz için anlık piyasa ve gösterge özetini döner.
        """
        series = self.candle_closes if len(self.candle_closes) >= 15 else self.price_history
        highs = self.candle_highs if len(self.candle_highs) >= 15 else series
        lows = self.candle_lows if len(self.candle_lows) >= 15 else series

        rsi = self.calculate_rsi(series, period=14)
        bb = self.calculate_bollinger_bands(series, period=20, num_std=2.0)
        ema_fast = self.calculate_ema(series, period=9)
        ema_slow = self.calculate_ema(series, period=21)

        # Bollinger Bandwidth (%)
        bb_width_pct = 0.0
        if bb["middle"] > 0:
            bb_width_pct = ((bb["upper"] - bb["lower"]) / bb["middle"]) * 100.0

        # EMA Trend Slope (%)
        ema_trend_pct = 0.0
        if ema_slow > 0:
            ema_trend_pct = ((ema_fast - ema_slow) / ema_slow) * 100.0

        adx_data = self.calculate_adx(highs, lows, series, period=14)
        atr = self.calculate_atr(highs, lows, series, period=14)

        return {
            "symbol": self.symbol,
            "price": self.last_price,
            "bid": self.last_bid,
            "ask": self.last_ask,
            "spread_pct": round(self.last_spread_pct, 3),
            "rsi": rsi,
            "bb_upper": bb["upper"],
            "bb_middle": bb["middle"],
            "bb_lower": bb["lower"],
            "bb_width_pct": round(bb_width_pct, 2),
            "ema_fast": ema_fast,
            "ema_slow": ema_slow,
            "ema_trend_pct": round(ema_trend_pct, 2),
            "adx": adx_data["adx"],
            "plus_di": adx_data["plus_di"],
            "minus_di": adx_data["minus_di"],
            "atr": atr,
            "timestamp": self.last_update_time,
            "history_len": len(self.price_history),
        }
