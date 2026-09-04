from typing import Dict, Any, Tuple
from strategies.base_strategy import BaseStrategy

class RsiBollingerStrategy(BaseStrategy):
    """
    RSI + Bollinger Bantları Scalping Stratejisi.
    Kısa vadeli grafiklerde fiyat alt banda yaklaştığında ve RSI aşırı satım
    bölgesindeyken dipten alış, üst banda ulaştığında veya aşırı alım bölgesine
    çıktığında kâr satışı hedefler.
    """
    def __init__(self, params: Dict[str, Any] = None):
        params = params or {}
        super().__init__("RSI_Bollinger_Scalper", params)
        self.rsi_oversold = float(self.params.get("rsi_oversold", 35.0))
        self.rsi_overbought = float(self.params.get("rsi_overbought", 65.0))

    def evaluate(self, snapshot: Dict[str, Any], open_positions_count: int) -> Tuple[str, str]:
        price = snapshot.get("price", 0.0)
        rsi = snapshot.get("rsi", 50.0)
        bb_lower = snapshot.get("bb_lower", 0.0)
        bb_upper = snapshot.get("bb_upper", 0.0)
        bb_middle = snapshot.get("bb_middle", 0.0)

        if price <= 0:
            return "HOLD", "Fiyat verisi bekleniyor"

        # ALIŞ SİNYALİ (BUY)
        # Fiyat alt bant civarında veya altında VE RSI aşırı satım bölgesinde
        if rsi <= self.rsi_oversold and price <= (bb_lower * 1.002):
            return "BUY", f"Dip Kırılımı: RSI={rsi:.1f} (<= {self.rsi_oversold}) & Fiyat={price:.4f} <= Alt Bant ({bb_lower:.4f})"

        # Daha esnek scalping: Eğer RSI < 32 ise doğrudan ucuz bölge
        if rsi < 32.0:
            return "BUY", f"Aşırı Satım Seviyesi: RSI={rsi:.1f} (< 32.0)"

        # SATIŞ SİNYALİ (SELL)
        # RSI aşırı alım veya fiyat üst banda çarptı
        if rsi >= self.rsi_overbought or (bb_upper > 0 and price >= bb_upper):
            return "SELL", f"Zirve / Aşırı Alım: RSI={rsi:.1f} (>= {self.rsi_overbought}) veya Fiyat >= Üst Bant ({bb_upper:.4f})"

        return "HOLD", f"Nötr Piyasa (RSI: {rsi:.1f}, Fiyat: {price:.4f})"
