import pytest
import time
from core.simulator import SimulatorEngine
from core.risk_manager import RiskManager
from reporting.performance import PerformanceMetrics
from core.binance_client import BinanceTrClient
from strategies.rsi_bollinger import RsiBollingerStrategy
from strategies.momentum_ema import MomentumEmaStrategy

def test_simulator_buy_and_sell():
    sim = SimulatorEngine(initial_balance=10000.0, fee_rate_pct=0.1)
    assert sim.cash == 10000.0

    # 1. Alış işlemi
    pos = sim.buy(symbol="USDT_TRY", price=40.0, budget_try=1000.0, reason="Test Buy")
    assert pos is not None
    assert sim.cash == 9000.0
    assert len(sim.positions) == 1

    # Net miktar kontrolü: 1000 TL - %0.1 fee (1 TL) = 999 TL / 40.0 = 24.975 adet
    assert pos["quantity"] == pytest.approx(24.975, 0.001)

    # 2. Fiyat artışı ve güncelleme
    sim.update_market_price("USDT_TRY", current_price=41.0)
    summary = sim.get_summary(current_price=41.0)
    assert summary["unrealized_pnl"] > 0

    # 3. Satış işlemi
    order = sim.sell(pos["position_id"], price=41.0, reason="TP")
    assert order is not None
    assert len(sim.positions) == 0
    assert len(sim.closed_trades) == 1
    assert order["is_win"] is True
    assert sim.cash > 10000.0  # Kâr ile bakiye arttı

def test_risk_manager_triggers():
    rm = RiskManager(take_profit_pct=1.0, stop_loss_pct=0.5, trailing_stop_pct=0.3)
    pos = {"entry_price": 100.0, "highest_price": 100.0}

    # Fiyat %0.6 düşerse SL tetiklenmeli
    close_sl, reason_sl, _ = rm.evaluate_exit(pos, current_price=99.4)
    assert close_sl is True
    assert "STOP-LOSS" in reason_sl

    # Fiyat %1.2 artarsa TP tetiklenmeli
    pos2 = {"entry_price": 100.0, "highest_price": 100.0}
    close_tp, reason_tp, _ = rm.evaluate_exit(pos2, current_price=101.2)
    assert close_tp is True
    assert "TAKE-PROFIT" in reason_tp

def test_performance_metrics():
    closed_trades = [
        {"net_pnl": 50.0, "is_win": True, "hold_time_seconds": 60},
        {"net_pnl": -20.0, "is_win": False, "hold_time_seconds": 45},
    ]
    metrics = PerformanceMetrics.calculate(
        initial_balance=10000.0,
        final_equity=10030.0,
        closed_trades=closed_trades,
        equity_curve=[{"equity": 10000.0}, {"equity": 10050.0}, {"equity": 10030.0}]
    )
    assert metrics["total_trades"] == 2
    assert metrics["winning_trades"] == 1
    assert metrics["losing_trades"] == 1
    assert metrics["win_rate"] == 50.0
    assert metrics["net_pnl"] == 30.0

def test_strategies_signals():
    strat = RsiBollingerStrategy({"rsi_oversold": 30.0, "rsi_overbought": 70.0})
    snapshot_oversold = {
        "price": 39.5,
        "rsi": 25.0,
        "bb_lower": 40.0,
        "bb_upper": 42.0,
        "bb_middle": 41.0,
    }
    sig, _ = strat.evaluate(snapshot_oversold, open_positions_count=0)
    assert sig == "BUY"

    snapshot_overbought = {
        "price": 42.5,
        "rsi": 75.0,
        "bb_lower": 40.0,
        "bb_upper": 42.0,
        "bb_middle": 41.0,
    }
    sig2, _ = strat.evaluate(snapshot_overbought, open_positions_count=1)
    assert sig2 == "SELL"

def test_binance_tr_live_public_api():
    client = BinanceTrClient()
    depth = client.get_depth("USDT_TRY", limit=5)
    assert depth.get("code") == 0
    assert len(depth.get("data", {}).get("bids", [])) > 0

    best = client.get_best_prices("USDT_TRY")
    assert best is not None
    assert best["bid"] > 0
    assert best["ask"] >= best["bid"]
