import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import load_config
from bot import BinanceTrBot

def test_live_session_flow():
    cfg = load_config()
    cfg.trading.mode = "simulation"
    cfg.trading.symbol = "USDT_TRY"
    cfg.trading.auto_select_coin = False
    cfg.trading.candidate_observation_seconds = 0
    cfg.strategy.active = "quick_test_scalper"
    cfg.test.duration_minutes = 1

    bot = BinanceTrBot(cfg)
    bot.start(duration_minutes=1)

    # 1. Bekle ve canlı veri çekimini doğrula
    time.sleep(3)
    assert bot.is_running is True
    assert len(bot.logs) > 0

    # 2. Manuel test alımı tetikle
    pos = bot.force_test_buy(reason="Otomasyon Test Alımı")
    assert pos is not None
    assert len(bot.simulator.positions) >= 1
    assert bot.simulator.cash < 10000.0

    # 3. Fiyat güncellensin ve durum takip edilsin
    time.sleep(3)
    bot.step()
    state = bot.get_dashboard_state()
    assert state["portfolio"]["open_positions_count"] >= 1
    assert "Pozisyon" in state["status_text"] or "Portföy" in state["status_text"]

    # 4. Pozisyonu kapat
    closed = bot.force_close_all(reason="Test Kapatma")
    assert len(closed) >= 1
    assert len(bot.simulator.positions) == 0
    assert len(bot.simulator.closed_trades) >= 1

    # 5. Botu durdur ve raporu doğrula
    stop_res = bot.stop()
    assert stop_res["status"] == "stopped"
    assert bot.last_report is not None
    assert os.path.exists(bot.last_report["html"])
    assert os.path.exists(bot.last_report["json"])

    print("[OK] Canlı test akışı, anında alım, takip ve raporlama testi başarıyla tamamlandı!")

if __name__ == "__main__":
    test_live_session_flow()
