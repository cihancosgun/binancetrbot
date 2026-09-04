import os
import pytest
from unittest.mock import patch

# Pytest oturumu başlarken global test ortam değişkenini ata
os.environ["BOT_TESTING"] = "1"

@pytest.fixture(scope="session", autouse=True)
def enforce_test_simulation_mode():
    """
    Test paketi çalışırken botun veya web uygulamasının
    KESİNLİKLE gerçek Binance TR hesabına emir göndermesini engeller.
    Modu zorunlu olarak 'simulation' yapar ve canlı emir iletimini kilitler.
    """
    # 1. web.app üzerindeki bot_instance'ı simulation moduna çek
    try:
        from web.app import bot_instance
        bot_instance.config.trading.mode = "simulation"
    except Exception:
        pass

    # 2. BinanceTrClient.create_order'a emniyet kilidi koy
    from core.binance_client import BinanceTrClient
    def safe_create_order_guard(self, *args, **kwargs):
        raise RuntimeError("GÜVENLİK KİLİDİ: Test paketi çalışırken Binance TR'ye gerçek emir gönderilemez!")

    with patch.object(BinanceTrClient, "create_order", side_effect=safe_create_order_guard):
        yield

    os.environ.pop("BOT_TESTING", None)
