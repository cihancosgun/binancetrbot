import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from core.market_scanner import CandidateWatchlist

def test_candidate_observation_and_anti_dump():
    # 30 saniye gözlem süresi olan takip havuzu
    watchlist = CandidateWatchlist(min_observation_seconds=30)

    # 1. Durum: Yeni gelen coin acele edilip hemen alınmamalı (0 saniye)
    approved, reason, elapsed = watchlist.observe("HOT_TRY", current_price=10.0, rsi=50.0)
    assert not approved
    assert elapsed == 0
    assert "Yeni takibe alındı" in reason
    print("1. Yeni coin takibe alındı (Onaylanmadı):", reason)

    # 2. Durum: 15 saniye geçti ama 30 saniye dolmadı -> Hâlâ alınmamalı
    watchlist.tracking["HOT_TRY"]["first_seen"] = time.time() - 15
    approved, reason, elapsed = watchlist.observe("HOT_TRY", current_price=10.05, rsi=52.0)
    assert not approved
    assert elapsed >= 15
    assert "İzleniyor" in reason
    print("2. 15 saniye izlendi (Henüz 30s dolmadı, onaylanmadı):", reason)

    # 3. Durum: Sürekli tepe aşağı inen coin (Düşen bıçak / Dump)
    # Fiyat 10.0'dan 9.50'ye çakılıyor
    falling_coin = "CRASH_TRY"
    watchlist.observe(falling_coin, current_price=10.0, rsi=50.0)
    # 35 saniye geçmiş gibi simüle et
    watchlist.tracking[falling_coin]["first_seen"] = time.time() - 35
    # Art arda düşüş ekle
    watchlist.observe(falling_coin, current_price=9.90, rsi=42.0)
    watchlist.observe(falling_coin, current_price=9.80, rsi=38.0)
    watchlist.observe(falling_coin, current_price=9.70, rsi=34.0)
    approved, reason, elapsed = watchlist.observe(falling_coin, current_price=9.60, rsi=30.0)
    assert not approved
    assert "Tepe aşağı" in reason or "düşen bıçak" in reason
    print("3. Tepe aşağı inen coin engellendi:", reason)

    # 4. Durum: Mantıklı hareket (En az 30s izlendi, taban yaptı ve toparlanıyor)
    good_coin = "GOOD_TRY"
    watchlist.observe(good_coin, current_price=5.0, rsi=45.0)
    watchlist.tracking[good_coin]["first_seen"] = time.time() - 32
    watchlist.observe(good_coin, current_price=4.98, rsi=44.0)
    watchlist.observe(good_coin, current_price=5.02, rsi=48.0)
    approved, reason, elapsed = watchlist.observe(good_coin, current_price=5.05, rsi=52.0)
    assert approved
    assert "Mantıklı hareket onaylandı" in reason
    print("4. Mantıklı hareket gösteren coin onaylandı:", reason)

    print("\n[OK] Aday coin gözlem süresi ve düşen bıçak engelleme başarıyla doğrulandı!")

if __name__ == "__main__":
    test_candidate_observation_and_anti_dump()
