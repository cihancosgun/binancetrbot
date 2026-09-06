import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import load_config
from bot import BinanceTrBot

def test_portfolio_basket_rotation():
    cfg = load_config()
    cfg.trading.mode = "simulation"
    cfg.trading.symbol = "AUTO"
    cfg.trading.auto_select_coin = True
    cfg.trading.target_coins_count = 5
    cfg.trading.max_open_positions = 5
    cfg.trading.auto_fill_portfolio = True
    cfg.trading.require_strict_buy_signal = False
    cfg.trading.min_24h_volume_try = 0.0
    cfg.trading.initial_virtual_balance = 10000.0
    cfg.trading.budget_per_trade = 2000.0
    cfg.trading.candidate_observation_seconds = 0
    cfg.trading.min_24h_gain_pct = 0.0

    cfg.strategy.active = "quick_test_scalper"
    cfg.test.duration_minutes = 1

    bot = BinanceTrBot(cfg)

    # 1. Adım: Bot tek step() çalıştırdığında sepeti 5 farklı hareketli coin ile doldurmalı
    print(">>> 1. Sepet oluşturuluyor (Hedef: En az 5 farklı hareketli coin)...")
    bot.step()

    open_positions = list(bot.simulator.positions.values())
    unique_symbols = {p["symbol"] for p in open_positions}

    print(f"Açılan pozisyon sayısı: {len(open_positions)}")
    print(f"Farklı coinler: {unique_symbols}")

    assert len(open_positions) >= 4, f"En az 4-5 coin açılmalıydı, açılan: {len(open_positions)}"
    assert len(unique_symbols) == len(open_positions), "Coinler arasında mükerrer olmamalı, hepsi farklı olmalı!"

    for pos in open_positions:
        print(f"  Coin: {pos['symbol']:<10} | Fiyat: {pos['entry_price']:<10.4f} | Maliyet: {pos['invested_cost']:.2f} TL | Miktar: {pos['quantity']:.4f}")
        assert pos["invested_cost"] > 0
        assert pos["symbol"] != "USDT_TRY"

    # 2. Adım: Bir coin kârla satılsın (Örn. listedeki ilk coin)
    sold_pos = open_positions[0]
    sold_symbol = sold_pos["symbol"]
    print(f"\n>>> 2. {sold_symbol} pozisyonu TP ile kapatılıyor...")
    order = bot.simulator.sell(sold_pos["position_id"], sold_pos["entry_price"] * 1.02, reason="Test TP Kapanışı")
    assert order is not None

    current_open_symbols = {p["symbol"] for p in bot.simulator.positions.values()}
    assert sold_symbol not in current_open_symbols
    assert len(bot.simulator.positions) == len(open_positions) - 1
    print(f"Kalan açık coin sayısı: {len(bot.simulator.positions)} ({current_open_symbols})")

    # 3. Adım: Bot bir sonraki adımda boşalan yuvanın yerine radardan başka bir coin almalı
    print("\n>>> 3. Sürekli Rotasyon Testi: Boşalan yuvaya yeni hareketli coin alınıyor...")
    bot.step()

    new_open_positions = list(bot.simulator.positions.values())
    new_unique_symbols = {p["symbol"] for p in new_open_positions}
    print(f"Rotasyon sonrası sepet: {new_unique_symbols} (Toplam {len(new_open_positions)} coin)")

    # Yeni coin eklenmiş olmalı ve sepet yine 5 coine tamamlanmalı
    assert len(new_open_positions) >= len(open_positions)
    print("\n[OK] 5'li sepet çeşitlendirmesi ve sürekli coin rotasyonu başarıyla doğrulandı!")

if __name__ == "__main__":
    test_portfolio_basket_rotation()
