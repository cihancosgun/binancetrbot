import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config import load_config
from bot import BinanceTrBot

def main():
    print("=== KISA DOĞRULAMA TESTİ (10 SANİYE) BAŞLATILIYOR ===")
    cfg = load_config()
    cfg.trading.mode = "simulation"
    cfg.trading.symbol = "USDT_TRY"
    cfg.strategy.active = "grid_scalper"  # scalper for quick trigger test

    bot = BinanceTrBot(cfg)
    bot.start(duration_minutes=1)  # 1 dk

    # 8 saniye boyunca piyasayı izle
    time.sleep(8)

    # Durdur ve rapor oluştur
    res = bot.stop()
    print("Durdurma sonucu:", res)
    print("Oluşan raporlar:", bot.last_report)
    print("Kapanan işlemler sayısı:", len(bot.simulator.closed_trades))
    print("Açık pozisyon sayısı:", len(bot.simulator.positions))
    print("Güncel sanal bakiye:", bot.simulator.cash)

if __name__ == "__main__":
    main()
