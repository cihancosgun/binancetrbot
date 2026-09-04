from typing import Dict, Any, Tuple
from strategies.base_strategy import BaseStrategy

class MomentumEmaStrategy(BaseStrategy):
    """
    Hızlı Trend & Momentum Stratejisi (EMA Kesişimleri).
    Hızlı EMA (örn: 9) Yavaş EMA'yı (örn: 21) yukarı kestiğinde alış sinyali üretir.
    Aşağı yönlü kesişimlerde ise satışı tetikler.
    """
    def __init__(self, params: Dict[str, Any] = None):
        params = params or {}
        super().__init__("Momentum_EMA_Trend", params)
        self.prev_diff: float = 0.0

    def evaluate(self, snapshot: Dict[str, Any], open_positions_count: int) -> Tuple[str, str]:
        ema_fast = snapshot.get("ema_fast", 0.0)
        ema_slow = snapshot.get("ema_slow", 0.0)
        price = snapshot.get("price", 0.0)

        if ema_fast <= 0 or ema_slow <= 0 or price <= 0:
            return "HOLD", "EMA verileri hesaplanıyor..."

        diff = ema_fast - ema_slow

        # Golden Cross (Hızlı EMA Yavaş EMA'yı yukarı kesiyor)
        if self.prev_diff <= 0 and diff > 0:
            self.prev_diff = diff
            return "BUY", f"Yukarı Trend Başlangıcı: EMA Fast ({ema_fast:.4f}) > EMA Slow ({ema_slow:.4f})"

        # Death Cross (Hızlı EMA Yavaş EMA'yı aşağı kesiyor)
        if self.prev_diff >= 0 and diff < 0:
            self.prev_diff = diff
            return "SELL", f"Aşağı Yönlü Kırılım: EMA Fast ({ema_fast:.4f}) < EMA Slow ({ema_slow:.4f})"

        self.prev_diff = diff
        return "HOLD", f"Trend Takipte (EMA Fark: {diff:.4f})"
