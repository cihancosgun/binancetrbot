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
    # 45 saniye gözlem süresi ve %1.5 anlık patlama eşiği olan takip havuzu
    watchlist = CandidateWatchlist(min_observation_seconds=45, min_gain_pct=1.5)

    # 1. Durum: Yeni gelen coin acele edilip hemen alınmamalı (0 saniye)
    approved, reason, elapsed = watchlist.observe("HOT_TRY", current_price=10.0, rsi=50.0)
    assert not approved
    assert elapsed == 0
    assert "Takibe alındı" in reason
    print("1. Yeni coin takibe alındı (Onaylanmadı):", reason)

    # 2. Durum: 20 saniye geçti ama ivme yetersiz (+%0.30 < +%1.50) -> Hâlâ alınmamalı
    watchlist.tracking["HOT_TRY"]["first_seen"] = time.time() - 20
    approved, reason, elapsed = watchlist.observe("HOT_TRY", current_price=10.03, rsi=52.0)
    assert not approved
    assert elapsed >= 20
    assert "İzleniyor" in reason
    print("2. 20 saniye izlendi (İvme yetersiz, onaylanmadı):", reason)

    # 3. Durum: Sürekli tepe aşağı inen coin (Düşen bıçak / Dump)
    falling_coin = "CRASH_TRY"
    watchlist.observe(falling_coin, current_price=10.0, rsi=50.0)
    watchlist.tracking[falling_coin]["first_seen"] = time.time() - 35
    watchlist.observe(falling_coin, current_price=9.90, rsi=42.0)
    watchlist.observe(falling_coin, current_price=9.80, rsi=38.0)
    approved, reason, elapsed = watchlist.observe(falling_coin, current_price=9.70, rsi=34.0)
    assert not approved
    assert "düşen bıçak" in reason or "Düşüş eğiliminde" in reason
    assert watchlist.is_cooling_down(falling_coin)
    print("3. Tepe aşağı inen coin engellendi ve dinlenmeye alındı:", reason)

    # 4. Durum: 45 saniyeyi aştı ama ivme yok (Yatay/ölü coin, kazanç < %1.5) -> Zaman aşımına uğramalı ve dinlenmeye alınmalı
    flat_coin = "FLAT_TRY"
    watchlist.observe(flat_coin, current_price=10.0, rsi=50.0)
    watchlist.tracking[flat_coin]["first_seen"] = time.time() - 50
    approved, reason, elapsed = watchlist.observe(flat_coin, current_price=10.05, rsi=51.0)
    assert not approved
    assert "ZAMAN AŞIMI" in reason or "radar diğer coinlere geçti" in reason
    assert watchlist.is_cooling_down(flat_coin)
    assert flat_coin not in watchlist.tracking
    print("4. 45s içinde yükselmeyen coin elendi ve radar diğer coinlere geçti:", reason)

    # 4b. Durum: Dinlenmedeki coine hemen tekrar alım isteği gelirse radar engeller
    approved2, reason2, _ = watchlist.observe(flat_coin, current_price=10.09, rsi=52.0)
    assert not approved2
    assert "dinlenmesinde" in reason2
    print("4b. Dinlenmedeki coin doğrudan engellendi:", reason2)

    # 5. Durum: 45 saniye içinde çifte patlama teyidi (En az 2 defa yükseliş dalgası ve +%2.00 >= %1.50)
    burst_coin = "BURST_TRY"
    watchlist.observe(burst_coin, current_price=5.0, rsi=45.0)
    watchlist.tracking[burst_coin]["first_seen"] = time.time() - 30
    
    # İlk patlama dalgası (5.0 -> 5.08, +%1.60), ama henüz 1 patlama olduğu için 2. teyit beklenir (min_burst_count=2)
    approved_1, reason_1, _ = watchlist.observe(burst_coin, current_price=5.08, rsi=58.0)
    assert not approved_1
    assert "İzleniyor" in reason_1 or "Patlama" in reason_1
    print("5a. 1. patlama dalgası görüldü (2. teyit bekleniyor):", reason_1)

    # İkinci patlama dalgası (5.08 -> 5.10, 2. yükseliş dalgası tamamlandı)
    approved_2, reason_2, elapsed_2 = watchlist.observe(burst_coin, current_price=5.10, rsi=62.0)
    assert approved_2
    assert "PATLAMA TEYİDİ" in reason_2
    assert "%+2.00" in reason_2 or "%+1." in reason_2
    # 6. Durum: 45 saniyelik ilk turda 1 defa patlama yakalandıysa takipten çıkarılmamalı, 2. tura (+45s) uzatılmalı
    extend_coin = "EXTEND_TRY"
    watchlist.observe(extend_coin, current_price=10.0, rsi=50.0)
    watchlist.observe(extend_coin, current_price=10.15, rsi=55.0) # 1. patlama dalgası yakalandı (+%1.50)
    
    # 55 saniye geçti (Normalde 45s dolunca elenirdi, ama 1 patlaması olduğu için 90s'ye kadar 2. tur devam eder)
    watchlist.tracking[extend_coin]["first_seen"] = time.time() - 55
    approved_ext, reason_ext, elapsed_ext = watchlist.observe(extend_coin, current_price=10.15, rsi=55.0)
    assert not approved_ext
    assert "2. Tur" in reason_ext or "Ekstra" in reason_ext
    assert extend_coin in watchlist.tracking # Listeden çıkarılmadı!
    assert not watchlist.is_cooling_down(extend_coin)
    print("6. 45s dolmasına rağmen 1 patlaması olan coin 2. turda tutuldu:", reason_ext)

    # 2. tur içinde (60. saniyede) 2. patlama gelirse onaylanır
    approved_ext2, reason_ext2, _ = watchlist.observe(extend_coin, current_price=10.25, rsi=65.0)
    assert approved_ext2
    assert "PATLAMA TEYİDİ" in reason_ext2
    print("6b. 2. turda 2. patlama yakalanarak onaylandı:", reason_ext2)

    print("\n[OK] 45 saniye zaman aşımı, çifte patlama teyidi, 1-patlama ekstra tur uzatma ve dinamik aday rotasyonu başarıyla doğrulandı!")

if __name__ == "__main__":
    test_candidate_observation_and_anti_dump()
