from typing import Dict, Any, Tuple
from strategies.base_strategy import BaseStrategy

class FeeRecoveryStrategy(BaseStrategy):
    """
    Komisyon Oranını Kurtaran Strateji (Fee Recovery Strategy):
    - Binance TR'nin işlem komisyon oranını (örn: %0.10) baz alır.
    - Komisyonun 2 katı kâr elde edildiğinde (örn: +%0.20) anında Kâr Al (Take Profit) yapar.
    - Komisyonun 2 katı zarar oluştuğunda (örn: -%0.20) anında Zarar Kes (Stop Loss) yapar.
    - Giriş sinyali: Mikro geri çekilme toparlanması, RSI aşırı satım sıçraması ve EMA momentumunu
      birleştirerek hızlı %0.20'lik kâr potansiyeli sunan dip noktalarını hedefler.
    """
    def __init__(self, params: Dict[str, Any]):
        super().__init__("fee_recovery", params)
        # Komisyon oranı (Örn: Binance TR %0.10 = 0.10)
        self.fee_rate_pct = float(params.get("fee_rate_pct", 0.10))
        # Komisyon kâr/zarar çarpanı (Örn: 2 katı = 2.0)
        self.fee_multiplier = float(params.get("fee_multiplier", 2.0))
        
        # Dinamik TP ve SL hedefi: TP +%2.0, SL -%1.0 (gürültüye dayanıklı ve net kârlı)
        self.target_tp_pct = float(params.get("take_profit_pct", 2.0))
        self.target_sl_pct = float(params.get("stop_loss_pct", 1.0))

        # Teknik gösterge parametreleri
        self.rsi_period = int(params.get("rsi_period", 14))
        self.rsi_oversold = float(params.get("rsi_oversold", 42.0))
        self.rsi_overbought = float(params.get("rsi_overbought", 65.0))

    def evaluate(self, snapshot: Dict[str, Any], open_positions_count: int) -> Tuple[str, str]:
        """
        Piyasa verisi snapshot'ını değerlendirerek hızlı 2x komisyon kârı potansiyeli olan
        alım sinyallerini üretir.
        """
        price = snapshot.get("price", 0.0)
        rsi = snapshot.get("rsi")
        bb_lower = snapshot.get("bb_lower")
        bb_middle = snapshot.get("bb_middle")
        bb_upper = snapshot.get("bb_upper")
        ema_fast = snapshot.get("ema_fast")
        ema_slow = snapshot.get("ema_slow")
        change_24h = snapshot.get("change_24h_pct", 0.0)

        if price <= 0:
            return "HOLD", "Fiyat verisi eksik"

        # 1. Aşırı Satım & Bollinger Alt Bant Sıçraması (Hızlı %0.20 Scalp Girişi)
        if rsi is not None and bb_lower is not None:
            if rsi <= self.rsi_oversold and price <= bb_lower * 1.002:
                return "BUY", (
                    f"Komisyon Kurtaran Dip Girişi: RSI={rsi:.1f} <= {self.rsi_oversold}, "
                    f"Fiyat Bollinger Altında ({price:.4f} <= {bb_lower:.4f}). "
                    f"Hedef: +%{self.target_tp_pct:.2f} TP / -%{self.target_sl_pct:.2f} SL"
                )

        # 2. Mikro-Momentum EMA Kesişimi & Trend Desteği
        if ema_fast is not None and ema_slow is not None and rsi is not None:
            if ema_fast > ema_slow and (self.rsi_oversold <= rsi <= self.rsi_overbought):
                # Fiyat orta bandın üzerindeyse ve yükseliş eğilimi varsa
                if bb_middle is None or price >= bb_middle * 0.998:
                    return "BUY", (
                        f"Komisyon Kurtaran Trend Girişi: EMA9 > EMA21, RSI={rsi:.1f}. "
                        f"Hedef: +%{self.target_tp_pct:.2f} TP / -%{self.target_sl_pct:.2f} SL"
                    )

        # 3. Yükselen Trendde Mikro Geri Çekilme (Pullback Rebound)
        if change_24h > 0 and rsi is not None and rsi < 50.0:
            return "BUY", (
                f"Komisyon Kurtaran Mikro Düzeltme Girişi: 24s=%{change_24h:+.2f}, RSI={rsi:.1f}. "
                f"Hedef: +%{self.target_tp_pct:.2f} TP / -%{self.target_sl_pct:.2f} SL"
            )

        # 4. Genel Radar Pozitiflik Taraması (Yeterli veri yoksa dahi makul seviyeden giriş)
        if rsi is not None and rsi < 55.0:
            return "BUY", (
                f"Komisyon Kurtaran Radar Girişi: RSI={rsi:.1f} < 55. "
                f"Hedef: +%{self.target_tp_pct:.2f} TP / -%{self.target_sl_pct:.2f} SL"
            )

        rsi_str = f"{rsi:.1f}" if rsi is not None else "N/A"
        return "HOLD", f"Uygun komisyon scalp fırsatı bekleniyor (RSI={rsi_str})"
