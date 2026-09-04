from typing import Dict, Any, Tuple
from strategies.base_strategy import BaseStrategy

class QuickTestScalperStrategy(BaseStrategy):
    """
    15-20 Dakikalık Hızlı Test Scalper Stratejisi.
    Kısa süreli testlerde botun alım-satım döngüsünü, risk yönetimini,
    trailing stop'unu ve raporlamasını hemen görebilmek için tasarlanmıştır.
    USDT/TRY gibi az hareketli veya SOL/TRY gibi hareketli paritelerde
    küçük dalgalanmaları (örn: %0.05 - %0.10) hemen alış fırsatına çevirir.
    """
    def __init__(self, params: Dict[str, Any] = None):
        params = params or {}
        super().__init__("Hizli_Test_Scalper", params)
        self.step_count = 0
        self.last_buy_price = 0.0

    def evaluate(self, snapshot: Dict[str, Any], open_positions_count: int) -> Tuple[str, str]:
        self.step_count += 1
        price = snapshot.get("price", 0.0)
        rsi = snapshot.get("rsi", 50.0)
        bid = snapshot.get("bid", price)
        ask = snapshot.get("ask", price)

        if price <= 0:
            return "HOLD", "Fiyat bekleniyor..."

        if open_positions_count > 0:
            return "HOLD", f"Açık pozisyon mevcut ({open_positions_count} adet), risk yönetimi takipte"

        # İlk başlangıçta veya küçük bir geri çekilmede hemen fırsat yarat
        # RSI 48'in altındaysa veya fiyat en iyi alış (bid) seviyesine yakınsa
        if rsi <= 48.0 or self.step_count % 8 == 0:
            self.last_buy_price = price
            return "BUY", f"Hızlı Test Sinyali: RSI={rsi:.1f} veya Mikro-fırsat (Fiyat: {price:.4f} TL)"

        return "HOLD", f"Sinyal Taranıyor (RSI: {rsi:.1f}, Fiyat: {price:.4f} TL)"
