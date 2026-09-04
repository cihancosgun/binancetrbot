import time
from typing import Dict, Any, Optional, Tuple

class RiskManager:
    """
    Pozisyon risk yönetimi: Kâr Al (TP), Zarar Kes (SL), İz Süren Stop (Trailing Stop),
    Başa-baş (Breakeven) koruması ve sembol bazlı işlem sıklığı (Cooldown) kontrollerini yürütür.
    """
    def __init__(
        self,
        take_profit_pct: float = 1.8,
        stop_loss_pct: float = 1.0,
        trailing_stop_pct: float = 0.6,
        trailing_activation_pct: float = 0.8,
        cooldown_seconds: int = 10,
        symbol_cooldown_seconds: int = 60,
        max_open_positions: int = 5,
        fee_rate_pct: float = 0.1,
    ):
        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct
        self.trailing_stop_pct = trailing_stop_pct
        self.trailing_activation_pct = trailing_activation_pct
        self.cooldown_seconds = cooldown_seconds
        self.symbol_cooldown_seconds = symbol_cooldown_seconds
        self.max_open_positions = max_open_positions
        self.fee_rate_pct = fee_rate_pct
        self.last_trade_time: float = 0.0
        self.symbol_exit_times: Dict[str, float] = {}

    def can_open_position(
        self,
        current_positions_count: int,
        is_basket_filling: bool = False,
        symbol: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Yeni bir pozisyon açılabilir mi kontrol eder.
        5'li sepet doldururken farklı coinlerin alımına izin verir ancak aynı coinin
        peş peşe alınıp komisyona boğulmasını engeller.
        """
        if current_positions_count >= self.max_open_positions:
            return False, f"Maksimum açık pozisyon limitine ulaşıldı ({self.max_open_positions})"

        now = time.time()

        # Sembol bazlı cooldown (aynı coine peş peşe girmeme)
        if symbol and symbol in self.symbol_exit_times:
            elapsed_sym = now - self.symbol_exit_times[symbol]
            if elapsed_sym < self.symbol_cooldown_seconds:
                remaining = int(self.symbol_cooldown_seconds - elapsed_sym)
                return False, f"{symbol} için bekleme süresi aktif ({remaining}s kaldı)"

        # Genel cooldown
        if not is_basket_filling:
            elapsed = now - self.last_trade_time
            if elapsed < self.cooldown_seconds:
                return False, f"Cooldown süresi bekleniyor ({int(self.cooldown_seconds - elapsed)}s kaldı)"

        return True, "Uygun"

    def record_trade_entry(self, symbol: Optional[str] = None) -> None:
        self.last_trade_time = time.time()

    def record_trade_exit(self, symbol: str) -> None:
        """Bir pozisyon kapandığında o coinin zaman damgasını kaydeder."""
        if symbol:
            self.symbol_exit_times[symbol] = time.time()

    def evaluate_exit(self, position: Dict[str, Any], current_price: float) -> Tuple[bool, str, float]:
        """
        Açık pozisyonun kapatılması gerekip gerekmediğini değerlendirir.
        Döner: (kapatılmalı_mı, neden, anlık_kâr_yüzdesi)
        """
        entry_price = position["entry_price"]
        highest_price = position.get("highest_price", entry_price)

        # En yüksek görülen fiyatı güncelle
        if current_price > highest_price:
            highest_price = current_price
            position["highest_price"] = highest_price

        # Anlık brüt kâr/zarar yüzdesi
        pnl_pct = ((current_price - entry_price) / entry_price) * 100.0

        # 1. Zarar Kes (Stop-Loss)
        if pnl_pct <= -self.stop_loss_pct:
            return True, f"STOP-LOSS tetiklendi ({pnl_pct:.2f}% <= -{self.stop_loss_pct}%)", pnl_pct

        # 2. Akıllı İz Süren Stop (Breakeven Korumalı Trailing Stop)
        # Kural: Trailing Stop ancak pozisyon en az trailing_activation_pct (örn: +%0.80) kadar
        # kâra geçtikten sonra devreye girer! Küçük gürültüde erken kapatıp komisyona yenilmez.
        if highest_price > entry_price:
            peak_gain_pct = ((highest_price - entry_price) / entry_price) * 100.0
            if peak_gain_pct >= self.trailing_activation_pct:
                drop_from_peak_pct = ((highest_price - current_price) / highest_price) * 100.0
                if drop_from_peak_pct >= self.trailing_stop_pct:
                    # Komisyon koruma: İki yönlü komisyon (0.1% + 0.1% = 0.20%)
                    min_clean_exit = self.fee_rate_pct * 2.0
                    if pnl_pct >= min_clean_exit:
                        return True, f"TRAILING STOP tetiklendi (Zirve: {peak_gain_pct:.2f}%, Düşüş: {drop_from_peak_pct:.2f}%, Net Kâr: +{pnl_pct:.2f}%)", pnl_pct
                    else:
                        # Başa-baş seviyesinde kapat
                        return True, f"BREAKEVEN / İZ SÜREN STOP tetiklendi (Komisyon korundu, Kâr: +{pnl_pct:.2f}%)", pnl_pct

        # 3. Kâr Al (Take-Profit)
        if pnl_pct >= self.take_profit_pct:
            return True, f"TAKE-PROFIT tetiklendi (+{pnl_pct:.2f}% >= +{self.take_profit_pct}%)", pnl_pct

        return False, "Pozisyon devam ediyor", pnl_pct
