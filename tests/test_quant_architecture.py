import pytest
import time
from core.risk_manager import RiskManager
from core.market_scanner import MarketScanner, CandidateWatchlist
from strategies.adaptive_regime import AdaptiveRegimeStrategy
from core.simulator import SimulatorEngine

def test_quant_scanner_scoring_and_ranking():
    scanner = MarketScanner(quote_asset="TRY", min_volume_try=1000000.0)
    
    pair_a = {
        "symbol": "BTC_TRY",
        "change_pct": 3.5,
        "volume_try": 50000000.0,
        "high": 105.0,
        "low": 100.0,
    }
    pair_b = {
        "symbol": "MEME_TRY",
        "change_pct": -2.0,
        "volume_try": 2000000.0,
        "high": 10.0,
        "low": 9.5,
    }
    
    score_a = scanner.calculate_quant_score(pair_a)
    score_b = scanner.calculate_quant_score(pair_b)
    
    assert score_a > score_b
    assert score_a > 5.0


def test_quant_risk_manager_breakeven_lock():
    rm = RiskManager(
        take_profit_pct=2.0,
        stop_loss_pct=1.0,
        breakeven_trigger_pct=0.90,
        trailing_activation_pct=1.0,
        trailing_stop_pct=0.50,
        fee_rate_pct=0.10
    )
    
    position = {
        "symbol": "SOL_TRY",
        "entry_price": 100.0,
        "highest_price": 100.0,
        "entry_time": time.time(),
        "quantity": 10.0,
    }
    
    # 1. Price moves up +0.95% (100.95) -> Breakeven should lock
    should_close, reason, pnl = rm.evaluate_exit(position, 100.95)
    assert should_close is False
    assert position.get("breakeven_locked") is True
    
    # 2. Price pulls back to 100.20 (below 0.22% clean exit) -> Breakeven stop should trigger with profit
    should_close, reason, pnl = rm.evaluate_exit(position, 100.20)
    assert should_close is True
    assert "BREAKEVEN" in reason
    assert pnl >= 0.20


def test_quant_risk_manager_trailing_stop_ride():
    rm = RiskManager(
        take_profit_pct=5.0,
        stop_loss_pct=1.0,
        trailing_activation_pct=1.0,
        trailing_stop_pct=0.50,
    )
    
    position = {
        "symbol": "ETH_TRY",
        "entry_price": 100.0,
        "highest_price": 100.0,
        "entry_time": time.time(),
        "quantity": 5.0,
    }
    
    # Price rises to 103.0 (+3.0%)
    rm.evaluate_exit(position, 103.0)
    assert position["highest_price"] == 103.0
    
    # Price drops from 103.0 to 102.4 (-0.58% drop from peak >= 0.50% trailing stop)
    should_close, reason, pnl = rm.evaluate_exit(position, 102.4)
    assert should_close is True
    assert "TRAILING STOP" in reason
    assert pnl == pytest.approx(2.4, rel=1e-2)


def test_quant_stagnation_exit():
    rm = RiskManager(
        take_profit_pct=2.0,
        stop_loss_pct=1.0,
        max_holding_seconds=900
    )
    
    position = {
        "symbol": "AVAX_TRY",
        "entry_price": 100.0,
        "highest_price": 100.1,
        "entry_time": time.time() - 950, # 15+ mins ago
        "quantity": 10.0,
    }
    
    # Flat price (100.05) after 15 mins
    should_close, reason, pnl = rm.evaluate_exit(position, 100.05)
    assert should_close is True
    assert "DURGUNLUK" in reason or "ZAMAN AŞIMI" in reason
