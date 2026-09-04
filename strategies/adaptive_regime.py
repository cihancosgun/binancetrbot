from typing import Dict, Any, Tuple
from strategies.base_strategy import BaseStrategy

class AdaptiveRegimeStrategy(BaseStrategy):
    """
    Piyasa Rejimi Tespit Eden Hibrit Algoritma (Adaptive Market Regime Strategy).
    
    Piyasanın anlık karakterini (Rejimini) 3 duruma ayırır:
    1. BULLISH_TREND (Yükseliş Trendi - ADX >= 22 & EMA9 > EMA21):
       -> Momentum takibi: Düzeltmelerde (Pullback) alır, kârı Breakeven Trailing Stop ile sürer.
    2. RANGING (Yatay Kanal - ADX < 22 & Daralan Bantlar):
       -> Mean-Reversion Scalp: Bollinger alt bandından ve RSI dip seviyeden alıp tepede hızlı kârla çıkar.
    3. DEFENSIVE_DUMP (Çöküş / Düşen Bıçak - Sert Satış Baskısı):
       -> Savunma modu: Kesinlikle alım yapmaz, sermayeyi nakitte korur.
    """
    def __init__(self, params: Dict[str, Any] = None):
        super().__init__(name="adaptive_regime", params=params or {})
        self.adx_trend_threshold = self.params.get("adx_trend_threshold", 22.0)
        self.current_regime = "INITIALIZING"

    def detect_regime(self, snapshot: Dict[str, Any]) -> Tuple[str, str]:
        """
        Piyasanın anlık rejimini ve gerekçesini tespit eder.
        """
        adx = snapshot.get("adx", 18.0)
        plus_di = snapshot.get("plus_di", 20.0)
        minus_di = snapshot.get("minus_di", 20.0)
        ema_trend_pct = snapshot.get("ema_trend_pct", 0.0)
        rsi = snapshot.get("rsi", 50.0)
        price = snapshot.get("price", 0.0)
        ema_slow = snapshot.get("ema_slow", price)
        bb_lower = snapshot.get("bb_lower", 0.0)

        # 1. Çöküş / Düşen Bıçak / Panik Rejimi (Defensive)
        # Şiddetli eksi momentum veya RSI çöküşü
        if (minus_di > plus_di + 8.0 and ema_trend_pct < -0.35) or (rsi < 30.0 and price < ema_slow * 0.99):
            return "DEFENSIVE_DUMP", f"🛑 ÇÖKÜŞ/PANİK: Satış baskısı yüksek (RSI: {rsi:.1f}, -DI: {minus_di:.1f} > +DI: {plus_di:.1f})"

        # 2. Güçlü Yükseliş Trendi Rejimi (Bullish Trend)
        if adx >= self.adx_trend_threshold and plus_di > minus_di and ema_trend_pct >= 0.03:
            return "BULLISH_TREND", f"🚀 GÜÇLÜ TREND: Yükseliş ivmesi aktif (ADX: {adx:.1f}, +DI: {plus_di:.1f}, Eğim: %{ema_trend_pct:+.2f})"

        # 3. Yatay Salınım / Testere Rejimi (Ranging)
        return "RANGING", f"🔄 YATAY KANAL: Trend zayıf, dalgalı bant hareketi (ADX: {adx:.1f}, Eğim: %{ema_trend_pct:+.2f})"

    def evaluate(self, snapshot: Dict[str, Any], open_positions_count: int) -> Tuple[str, str]:
        price = snapshot.get("price", 0.0)
        if price <= 0:
            return "HOLD", "Geçersiz fiyat verisi"

        regime, regime_reason = self.detect_regime(snapshot)
        self.current_regime = regime

        rsi = snapshot.get("rsi", 50.0)
        bb_lower = snapshot.get("bb_lower", 0.0)
        bb_upper = snapshot.get("bb_upper", 0.0)
        bb_middle = snapshot.get("bb_middle", 0.0)
        ema_fast = snapshot.get("ema_fast", price)
        ema_slow = snapshot.get("ema_slow", price)
        adx = snapshot.get("adx", 18.0)

        # REJİM 1: SAVUNMA / ÇÖKÜŞ
        if regime == "DEFENSIVE_DUMP":
            return "HOLD", f"{regime_reason} -> Sermaye koruması aktif, alım engellendi"

        # REJİM 2: GÜÇLÜ YÜKSELİŞ TRENDİ (MOMENTUM & PULLBACK)
        if regime == "BULLISH_TREND":
            # Yükselen trendde pullback (düzeltme) alımı:
            # RSI 38-58 arasına gevşemiş veya fiyat EMA9/EMA21 desteğine dokunmuş
            is_pullback = (36.0 <= rsi <= 56.0)
            is_near_ema_support = (price <= ema_fast * 1.003 and price >= ema_slow * 0.995)

            if is_pullback or is_near_ema_support:
                return "BUY", f"🚀 [TREND MOMENTUM ALIMI] Düzeltme tamamlandı (ADX: {adx:.1f}, RSI: {rsi:.1f}, Fiyat={price:.4f})"
            else:
                return "HOLD", f"🚀 [TREND SÜRÜYOR] Yükseliş devam ediyor, düzeltme (pullback) bekleniyor (RSI: {rsi:.1f})"

        # REJİM 3: YATAY / KANAL SALINIMI (MEAN-REVERSION SCALPER)
        if regime == "RANGING":
            # Bollinger alt bandına yakın ve RSI aşırı satıma yaklaşmış
            is_near_lower_bb = (bb_lower > 0 and price <= bb_lower * 1.004)
            is_oversold = (rsi <= 40.0)

            if is_near_lower_bb and is_oversold:
                return "BUY", f"🔄 [YATAY KANAL ALIMI] Bollinger Alt Bant & RSI Dip Tepkisi (RSI: {rsi:.1f}, Alt Bant={bb_lower:.4f})"
            else:
                return "HOLD", f"🔄 [YATAY KANAL] Fiyat kanal ortasında, alt bant desteği bekleniyor (RSI: {rsi:.1f})"

        return "HOLD", "Beklemede"
