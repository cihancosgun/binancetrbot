import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import load_config
from bot import BinanceTrBot

def test_radar_auto_mode():
    cfg = load_config()
    cfg.trading.mode = "simulation"
    cfg.trading.symbol = "AUTO"
    cfg.trading.auto_select_coin = True
    cfg.trading.candidate_observation_seconds = 0
    cfg.strategy.active = "quick_test_scalper"
    cfg.test.duration_minutes = 1

    bot = BinanceTrBot(cfg)

    # 1. Radarı doğrula
    top_coins = bot.scanner.scan_top_active_pairs(limit=5)
    assert len(top_coins) >= 3
    print("Radar tarafından tespit edilen en hareketli coinler:")
    for c in top_coins[:3]:
        print(f"  -> {c['symbol']}: %{c['change_pct']} (Fiyat: {c['price']})")

    # 2. Botu başlat
    bot.start(duration_minutes=1)
    time.sleep(3)

    # 3. Otomatik alım veya radar alımı tetikleme
    state = bot.get_dashboard_state()
    assert "radar_top_coins" in state
    assert len(state["radar_top_coins"]) > 0

    # 4. Anında test alımı otomatik en hareketli coini seçmeli
    pos = bot.force_test_buy(reason="Radar Otomasyon Alımı")
    assert pos is not None
    assert pos["symbol"] != "USDT_TRY"  # Sabit koin seçilmemeli
    print(f"Otomatik seçilen ve alınan hareketli coin: {pos['symbol']} | Fiyat: {pos['entry_price']}")

    # 5. Pozisyonu kapat ve botu durdur
    time.sleep(2)
    closed = bot.force_close_all(reason="Radar Test Kapatma")
    assert len(closed) >= 1
    stop_res = bot.stop()
    assert stop_res["status"] == "stopped"

    print("[OK] Piyasa radarı ve otomatik coin seçici başarıyla doğrulandı!")

if __name__ == "__main__":
    test_radar_auto_mode()
