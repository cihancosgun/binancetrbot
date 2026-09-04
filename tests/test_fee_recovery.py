import pytest
from strategies.fee_recovery import FeeRecoveryStrategy
from core.risk_manager import RiskManager
from config import load_config, BotConfig
from bot import BinanceTrBot

def test_fee_recovery_strategy_targets():
    params = {
        "fee_rate_pct": 0.10,
        "fee_multiplier": 2.0,
        "rsi_oversold": 42.0,
        "take_profit_pct": 2.0,
        "stop_loss_pct": 1.0,
    }
    strategy = FeeRecoveryStrategy(params)
    assert strategy.target_tp_pct == pytest.approx(2.0)
    assert strategy.target_sl_pct == pytest.approx(1.0)

    # 1. Oversold signal
    snapshot_oversold = {
        "price": 100.0,
        "rsi": 38.0,
        "bb_lower": 100.0,
        "change_24h_pct": 1.5,
    }
    signal, reason = strategy.evaluate(snapshot_oversold, open_positions_count=0)
    assert signal == "BUY"
    assert "2.00" in reason

    # 2. HOLD with float RSI
    snapshot_hold = {
        "price": 100.0,
        "rsi": 60.0,
        "bb_lower": 90.0,
        "bb_middle": 95.0,
        "ema_fast": 95.0,
        "ema_slow": 96.0,
        "change_24h_pct": -0.5,
    }
    signal, reason = strategy.evaluate(snapshot_hold, open_positions_count=0)
    assert signal == "HOLD"
    assert "RSI=60.0" in reason

    # 3. HOLD with None RSI
    snapshot_no_rsi = {
        "price": 100.0,
        "rsi": None,
    }
    signal, reason = strategy.evaluate(snapshot_no_rsi, open_positions_count=0)
    assert signal == "HOLD"
    assert "RSI=N/A" in reason

def test_risk_manager_fee_recovery_and_portfolio_sl():
    rm = RiskManager(
        fee_rate_pct=0.10,
        portfolio_stop_loss_pct=2.0
    )
    rm.apply_fee_recovery_mode(fee_rate_pct=0.10, fee_multiplier=2.0, take_profit_pct=1.0, stop_loss_pct=1.0)

    assert rm.take_profit_pct == pytest.approx(1.0)
    assert rm.stop_loss_pct == pytest.approx(1.0)

    position = {
        "symbol": "SOL_TRY",
        "entry_price": 100.0,
        "quantity": 10.0,
        "highest_price": 100.0,
    }

    # Test TP at +1.0% (price = 101.05)
    should_close, reason, pnl = rm.evaluate_exit(position, current_price=101.05)
    assert should_close is True
    assert "TAKE-PROFIT" in reason

    # Test SL at -1.0% (price = 98.95)
    position_sl = {
        "symbol": "SOL_TRY",
        "entry_price": 100.0,
        "quantity": 10.0,
        "highest_price": 100.0,
    }
    should_close, reason, pnl = rm.evaluate_exit(position_sl, current_price=98.95)
    assert should_close is True
    assert "STOP-LOSS" in reason

    # Test Portfolio Stop-Loss at -2.0%
    triggered, reason = rm.evaluate_portfolio_stop_loss(-1.5)
    assert triggered is False

    triggered, reason = rm.evaluate_portfolio_stop_loss(-2.01)
    assert triggered is True
    assert "PORTFÖY STOP-LOSS" in reason

def test_bot_fee_recovery_default_init():
    cfg = load_config()
    cfg.trading.mode = "simulation"
    bot = BinanceTrBot(cfg)

    assert bot.strategy.name in ("fee_recovery", "adaptive_regime")
    assert bot.risk_manager.take_profit_pct == pytest.approx(cfg.strategy.take_profit_pct)
    assert bot.risk_manager.stop_loss_pct == pytest.approx(cfg.strategy.stop_loss_pct)
    assert bot.risk_manager.portfolio_stop_loss_pct == pytest.approx(cfg.strategy.portfolio_stop_loss_pct)
