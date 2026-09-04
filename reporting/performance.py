from typing import List, Dict, Any

class PerformanceMetrics:
    """
    Test veya canlı seans sonrası performans metriklerini hesaplar.
    """
    @staticmethod
    def calculate(
        initial_balance: float,
        final_equity: float,
        closed_trades: List[Dict[str, Any]],
        equity_curve: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        total_trades = len(closed_trades)
        winning_trades = [t for t in closed_trades if t.get("is_win", False)]
        losing_trades = [t for t in closed_trades if not t.get("is_win", False)]

        win_rate = (len(winning_trades) / total_trades * 100.0) if total_trades > 0 else 0.0

        net_pnl = final_equity - initial_balance
        net_pnl_pct = (net_pnl / initial_balance * 100.0) if initial_balance > 0 else 0.0

        gross_profit = sum(t["net_pnl"] for t in winning_trades)
        gross_loss = abs(sum(t["net_pnl"] for t in losing_trades))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)

        # En Yüksek Çekilme (Max Drawdown)
        max_drawdown_pct = 0.0
        max_drawdown_amount = 0.0
        peak = initial_balance
        for pt in equity_curve:
            eq = pt.get("equity", initial_balance)
            if eq > peak:
                peak = eq
            dd = peak - eq
            dd_pct = (dd / peak * 100.0) if peak > 0 else 0.0
            if dd_pct > max_drawdown_pct:
                max_drawdown_pct = dd_pct
                max_drawdown_amount = dd

        avg_trade_pnl = (net_pnl / total_trades) if total_trades > 0 else 0.0
        avg_hold_time = (sum(t.get("hold_time_seconds", 0) for t in closed_trades) / total_trades) if total_trades > 0 else 0.0

        best_trade = max([t["net_pnl"] for t in closed_trades], default=0.0)
        worst_trade = min([t["net_pnl"] for t in closed_trades], default=0.0)

        return {
            "initial_balance": round(initial_balance, 2),
            "final_equity": round(final_equity, 2),
            "net_pnl": round(net_pnl, 2),
            "net_pnl_pct": round(net_pnl_pct, 2),
            "total_trades": total_trades,
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": round(win_rate, 2),
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "profit_factor": round(profit_factor, 2),
            "max_drawdown_pct": round(max_drawdown_pct, 2),
            "max_drawdown_amount": round(max_drawdown_amount, 2),
            "avg_trade_pnl": round(avg_trade_pnl, 2),
            "avg_hold_time_seconds": round(avg_hold_time, 1),
            "best_trade": round(best_trade, 2),
            "worst_trade": round(worst_trade, 2),
        }
