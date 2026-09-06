import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.market_scanner import MicroMomentumTracker, MarketScanner

def test_micro_momentum_tracker_and_anti_dump():
    tracker = MicroMomentumTracker(window_seconds=15, cooldown_seconds=5, min_momentum_pct=0.5)

    # 1. Durum: Yeni gelen coin takibe alınır
    approved, reason, elapsed = tracker.observe("HOT_TRY", current_price=10.0)
    assert not approved
    assert elapsed == 0
    assert "İzlemesi" in reason or "Kalibrasyon" in reason or "Takibe" in reason

    # 2. Durum: Süre devam ediyor ama ivme yetersiz
    tracker.first_seen["HOT_TRY"] = time.time() - 5
    approved, reason, elapsed = tracker.observe("HOT_TRY", current_price=10.01)
    assert not approved
    assert "İzlemesi" in reason or "Kalibrasyon" in reason

    # 3. Durum: Düşen bıçak / Dump engellenmeli
    falling_coin = "CRASH_TRY"
    tracker.record_tick(falling_coin, 10.0, timestamp=time.time() - 10)
    tracker.record_tick(falling_coin, 9.90, timestamp=time.time() - 8)
    tracker.record_tick(falling_coin, 9.80, timestamp=time.time() - 5)
    approved, reason, elapsed = tracker.observe(falling_coin, current_price=9.60)
    assert not approved
    assert "Düşüş" in reason or "Dump" in reason or "düşen bıçak" in reason
    assert tracker.is_cooling_down(falling_coin)

    # 4. Durum: Zaman aşımı (15s doldu ve ivme yok) -> Dinlenmeye alınmalı
    flat_coin = "FLAT_TRY"
    tracker.record_tick(flat_coin, 10.0, timestamp=time.time() - 20)
    tracker.first_seen[flat_coin] = time.time() - 20
    approved, reason, elapsed = tracker.observe(flat_coin, current_price=10.005)
    assert not approved
    assert "Zaman aşımı" in reason or "zaman aşımı" in reason or "taze adaylara" in reason
    assert tracker.is_cooling_down(flat_coin)

    # 5. Durum: İvme teyidi (Fiyat +%0.80 yükseldi)
    burst_coin = "BURST_TRY"
    tracker.record_tick(burst_coin, 10.0, timestamp=time.time() - 8)
    tracker.first_seen[burst_coin] = time.time() - 8
    approved, reason, elapsed = tracker.observe(burst_coin, current_price=10.08)
    assert approved is True
    assert "MOMENTUM TEYİDİ" in reason


def test_prebuy_10s_anti_dump_filter():
    tracker = MicroMomentumTracker(window_seconds=60, cooldown_seconds=10)

    # 1. Başlangıç: 10s ön-alım izlemesine başla
    ok, msg, el = tracker.observe_prebuy("SAFE_TRY", 100.0, observation_seconds=10, max_allowed_drop_pct=0.30)
    assert ok is False
    assert "Ön-Alım" in msg

    # 2. 5 saniye sonra fiyat sabit/hafif artıda (+%0.10) -> İzleme devam etmeli
    tracker.prebuy_tracking["SAFE_TRY"]["start_time"] = time.time() - 5
    ok, msg, el = tracker.observe_prebuy("SAFE_TRY", 100.10, observation_seconds=10, max_allowed_drop_pct=0.30)
    assert ok is False
    assert "İzleniyor" in msg

    # 3. 10 saniye doldu ve düşüş yok -> Alım ONAYLANMALI
    tracker.prebuy_tracking["SAFE_TRY"]["start_time"] = time.time() - 11
    ok, msg, el = tracker.observe_prebuy("SAFE_TRY", 100.15, observation_seconds=10, max_allowed_drop_pct=0.30)
    assert ok is True
    assert "Onaylandı" in msg or "Teyidi Tamamlandı" in msg

    # 4. Düşüş Vakası: Ön-alım sırasında fiyat %0.50 sert düştü -> ALIM İPTAL EDİLMELİ
    tracker.observe_prebuy("DUMP_TRY", 100.0, observation_seconds=10, max_allowed_drop_pct=0.30)
    ok, msg, el = tracker.observe_prebuy("DUMP_TRY", 99.40, observation_seconds=10, max_allowed_drop_pct=0.30) # %-0.60 düşüş
    assert ok is False
    assert "iptal edildi" in msg or "düşüş" in msg
    assert tracker.is_cooling_down("DUMP_TRY")

    # 5. Durgunluk Vakası: 10s boyunca hiç fiyat oynamadı (0 tick, flatline) -> ALIM İPTAL EDİLMELİ
    tracker.observe_prebuy("DEAD_TRY", 100.0, observation_seconds=10, max_allowed_drop_pct=0.30)
    tracker.prebuy_tracking["DEAD_TRY"]["start_time"] = time.time() - 11
    ok, msg, el = tracker.observe_prebuy("DEAD_TRY", 100.0, observation_seconds=10, max_allowed_drop_pct=0.30)
    assert ok is False
    assert "Durgunluk" in msg or "iptal edildi" in msg
    assert tracker.is_cooling_down("DEAD_TRY")

