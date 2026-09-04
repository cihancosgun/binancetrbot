import pytest
from strategies.adaptive_regime import AdaptiveRegimeStrategy
from core.market_data import MarketDataEngine
from core.binance_client import BinanceTrClient

def test_adaptive_regime_bullish_trend():
    strat = AdaptiveRegimeStrategy({"adx_trend_threshold": 22.0})
    snapshot = {
        "price": 100.0,
        "adx": 28.0,
        "plus_di": 32.0,
        "minus_di": 12.0,
        "ema_trend_pct": 0.5,
        "rsi": 46.0,          # Düzeltme (Pullback) seviyesinde
        "ema_fast": 100.2,
        "ema_slow": 99.5,
        "bb_lower": 98.0,
        "bb_upper": 102.0,
    }
    regime, reason = strat.detect_regime(snapshot)
    assert regime == "BULLISH_TREND"
    assert "GÜÇLÜ TREND" in reason

    sig, eval_reason = strat.evaluate(snapshot, open_positions_count=0)
    assert sig == "BUY"
    assert "MOMENTUM ALIMI" in eval_reason

def test_adaptive_regime_ranging():
    strat = AdaptiveRegimeStrategy({"adx_trend_threshold": 22.0})
    snapshot = {
        "price": 99.0,
        "adx": 16.0,          # Trend yok, yatay
        "plus_di": 18.0,
        "minus_di": 19.0,
        "ema_trend_pct": 0.02,
        "rsi": 36.0,          # Aşırı satım / alt bant
        "bb_lower": 99.0,
        "bb_middle": 100.0,
        "bb_upper": 101.0,
        "ema_fast": 100.0,
        "ema_slow": 100.0,
    }
    regime, reason = strat.detect_regime(snapshot)
    assert regime == "RANGING"
    assert "YATAY KANAL" in reason

    sig, eval_reason = strat.evaluate(snapshot, open_positions_count=0)
    assert sig == "BUY"
    assert "YATAY KANAL ALIMI" in eval_reason

def test_adaptive_regime_defensive_dump():
    strat = AdaptiveRegimeStrategy({"adx_trend_threshold": 22.0})
    snapshot = {
        "price": 90.0,
        "adx": 35.0,
        "plus_di": 10.0,
        "minus_di": 40.0,     # Şiddetli satış baskısı
        "ema_trend_pct": -1.2,
        "rsi": 24.0,          # Çöküş
        "bb_lower": 92.0,
        "bb_middle": 98.0,
        "bb_upper": 104.0,
        "ema_fast": 93.0,
        "ema_slow": 97.0,
    }
    regime, reason = strat.detect_regime(snapshot)
    assert regime == "DEFENSIVE_DUMP"
    assert "ÇÖKÜŞ" in reason

    sig, eval_reason = strat.evaluate(snapshot, open_positions_count=0)
    # Çöküşte DÜŞEN BIÇAK TUTULMAZ, alım yapılmamalıdır!
    assert sig == "HOLD"
    assert "Sermaye koruması aktif" in eval_reason

def test_market_data_adx_and_atr_calculation():
    engine = MarketDataEngine(BinanceTrClient(), symbol="SOL_TRY")
    highs = [10.0, 10.5, 11.0, 11.2, 11.5, 11.8, 12.0, 12.2, 12.5, 12.8, 13.0, 13.2, 13.5, 13.8, 14.0, 14.2]
    lows =  [9.8,  10.0, 10.3, 10.8, 11.0, 11.2, 11.5, 11.8, 12.0, 12.2, 12.5, 12.8, 13.0, 13.1, 13.4, 13.8]
    closes = [9.9, 10.4, 10.9, 11.1, 11.4, 11.7, 11.9, 12.1, 12.4, 12.7, 12.9, 13.1, 13.4, 13.7, 13.9, 14.1]

    adx_data = engine.calculate_adx(highs, lows, closes, period=10)
    assert "adx" in adx_data
    assert "plus_di" in adx_data
    assert "minus_di" in adx_data
    assert adx_data["plus_di"] > adx_data["minus_di"]  # Sürekli yükselen fiyat

    atr = engine.calculate_atr(highs, lows, closes, period=10)
    assert atr > 0.0
