import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.market_scanner import CandidateWatchlist

def test_candidate_observation_and_anti_dump():
    watchlist = CandidateWatchlist(min_observation_seconds=15, min_gain_pct=0.5, timeout_cooldown_seconds=5)

    # 1. Durum: Yeni gelen coin takibe alınır
    approved, reason, elapsed = watchlist.observe("HOT_TRY", current_price=10.0, rsi=50.0)
    assert not approved
    assert elapsed == 0
    assert "Takibe alındı" in reason

    # 2. Durum: Süre devam ediyor ama ivme yetersiz
    watchlist.tracking["HOT_TRY"]["first_seen"] = time.time() - 5
    approved, reason, elapsed = watchlist.observe("HOT_TRY", current_price=10.01, rsi=52.0)
    assert not approved
    assert "İzleniyor" in reason

    # 3. Durum: Düşen bıçak / Dump engellenmeli
    falling_coin = "CRASH_TRY"
    watchlist.observe(falling_coin, current_price=10.0, rsi=50.0)
    watchlist.tracking[falling_coin]["first_seen"] = time.time() - 10
    watchlist.observe(falling_coin, current_price=9.90, rsi=42.0)
    watchlist.observe(falling_coin, current_price=9.80, rsi=38.0)
    approved, reason, elapsed = watchlist.observe(falling_coin, current_price=9.70, rsi=34.0)
    assert not approved
    assert "düşen bıçak" in reason or "Düşüş eğiliminde" in reason
    assert watchlist.is_cooling_down(falling_coin)

    # 4. Durum: Zaman aşımı (15s doldu ve ivme yok) -> Dinlenmeye alınmalı
    flat_coin = "FLAT_TRY"
    watchlist.observe(flat_coin, current_price=10.0, rsi=50.0)
    watchlist.tracking[flat_coin]["first_seen"] = time.time() - 20
    approved, reason, elapsed = watchlist.observe(flat_coin, current_price=10.005, rsi=50.0)
    assert not approved
    assert "Zaman aşımı" in reason or "zaman aşımı" in reason or "taze adaylara" in reason
    assert watchlist.is_cooling_down(flat_coin)

    # 5. Durum: İvme teyidi (Fiyat +%0.80 yükseldi)
    burst_coin = "BURST_TRY"
    watchlist.observe(burst_coin, current_price=10.0, rsi=50.0)
    watchlist.tracking[burst_coin]["first_seen"] = time.time() - 8
    approved, reason, elapsed = watchlist.observe(burst_coin, current_price=10.08, rsi=60.0)
    assert approved is True
    assert "MOMENTUM TEYİDİ" in reason
