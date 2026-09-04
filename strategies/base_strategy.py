from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple

class BaseStrategy(ABC):
    """
    Tüm algoritmik stratejiler için temel sınıf.
    """
    def __init__(self, name: str, params: Dict[str, Any]):
        self.name = name
        self.params = params

    @abstractmethod
    def evaluate(self, snapshot: Dict[str, Any], open_positions_count: int) -> Tuple[str, str]:
        """
        Anlık piyasa verisi (snapshot) üzerinden işlem sinyali üretir.
        Döner:
            signal: "BUY", "SELL" veya "HOLD"
            reason: Kararın gerekçesi (örn: "RSI aşırı satım: 28.4 < 35")
        """
        pass
