from typing import Dict, Any, Tuple
from strategies.base_strategy import BaseStrategy

class GridScalperStrategy(BaseStrategy):
    """
    Mikro-Aralık Grid Scalper Stratejisi.
    Kısa vadeli 15-20 dakikalık testlerde sık işlem fırsatı yakalamak için tasarlanmıştır.
    Fiyat kısa vadeli referans fiyatından %0.2 veya daha fazla gerilediğinde alış sinyali üretir,
    kâr hedefine ulaştığında satış yapar.
    """
    def __init__(self, params: Dict[str, Any] = None):
        params = params or {}
        super().__init__("Grid_Micro_Scalper", params)
        self.pullback_pct = float(self.params.get("pullback_pct", 0.15))
        self.reference_price: float = 0.0

    def evaluate(self, snapshot: Dict[str, Any], open_positions_count: int) -> Tuple[str, str]:
        price = snapshot.get("price", 0.0)
        spread_pct = snapshot.get("spread_pct", 0.0)

        if price <= 0:
            return "HOLD", "Fiyat bekleniyor"

        if self.reference_price <= 0:
            self.reference_price = price
            return "HOLD", f"Referans fiyat belirlendi: {price:.4f}"

        # Fiyat hareketine göre referans fiyatı dinamik kaydır
        diff_pct = ((price - self.reference_price) / self.reference_price) * 100.0

        if diff_pct <= -self.pullback_pct and open_positions_count == 0:
            self.reference_price = price
            return "BUY", f"Mikro Geri Çekilme: Fiyat %{abs(diff_pct):.2f} düştü ({price:.4f})"

        # Referans fiyatı yukarı doğru güncelle (yükselen piyasada takip)
        if price > self.reference_price:
            self.reference_price = (self.reference_price * 0.7) + (price * 0.3)

        return "HOLD", f"Grid İzlemede (Ref: {self.reference_price:.4f}, Fark: %{diff_pct:.2f})"
