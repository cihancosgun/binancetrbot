import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from web.app import app, bot_instance

client = TestClient(app)

def test_auth_and_web_endpoints():
    # Test esnasinda gercek borsaya emir gitmesini onlemek icin modu simulation yap
    original_mode = bot_instance.config.trading.mode
    bot_instance.config.trading.mode = "simulation"

    try:
        # 1. Login sayfasi render ediliyor mu?
        res_login_page = client.get("/login")
        assert res_login_page.status_code == 200
        assert "Giriş Yap" in res_login_page.text

        # 2. Yetkisiz erisim ana sayfadan /login'e yonlendiriyor mu?
        res_unauth = client.get("/", follow_redirects=False)
        assert res_unauth.status_code == 303
        assert "/login" in res_unauth.headers["location"]

        # 3. Hatali parola ile giris testi (401 donmeli)
        res_bad_login = client.post("/api/login", json={"username": "admin", "password": "wrongpassword"})
        assert res_bad_login.status_code == 401
        assert res_bad_login.json()["status"] == "error"

        # 4. Dogru kimlik bilgileri ile giris testi (200 donmeli ve cookie vermeli)
        auth_cfg = bot_instance.config.auth
        res_good_login = client.post("/api/login", json={"username": auth_cfg.username, "password": auth_cfg.password})
        assert res_good_login.status_code == 200
        assert res_good_login.json()["status"] == "success"
        assert "session_token" in res_good_login.cookies

        # 5. Giris yapilmis oturumla ana sayfa erisimi
        res_index = client.get("/")
        assert res_index.status_code == 200
        assert "Binance TR Algoritmik Al-Sat Botu" in res_index.text

        # 6. State API
        res_state = client.get("/api/state")
        assert res_state.status_code == 200
        data = res_state.json()
        assert "portfolio" in data
        assert "market" in data

        # 7. Reports API
        res_reports = client.get("/api/reports")
        assert res_reports.status_code == 200
        assert isinstance(res_reports.json(), list)

        # 8. Pozisyon Kapatma API (Mock ile test edilir, canli hesaba ASLA dokunmaz)
        with patch.object(bot_instance, "force_close_all", return_value=[]) as mock_close_all:
            res_close_all = client.post("/api/close_all")
            assert res_close_all.status_code == 200
            assert res_close_all.json()["status"] == "success"
            assert mock_close_all.called

        # 9. Gecersiz ID ile tekil pozisyon kapatma testi
        with patch.object(bot_instance, "close_single_position", return_value=None):
            res_close_single = client.post("/api/close_position", json={"position_id": "non_existent_id"})
            assert res_close_single.status_code == 400

        # 10. Full Config GET API Testi
        res_full_cfg = client.get("/api/config/full")
        assert res_full_cfg.status_code == 200
        cfg_data = res_full_cfg.json()
        assert cfg_data["status"] == "success"
        assert "trading" in cfg_data["config"]
        assert "strategy" in cfg_data["config"]
        assert "api" in cfg_data["config"]
        assert "auth" in cfg_data["config"]
        assert "server" in cfg_data["config"]
        assert "loaded_config_path" in cfg_data
        assert "available_files" in cfg_data

        # 11. Full Config POST API Testi
        update_payload = {
            "trading": {
                "budget_per_trade": 150.0,
                "target_coins_count": 6,
                "candidate_observation_seconds": 25,
                "only_uptrend": True,
                "min_24h_volume_try": 6000000.0,
            },
            "strategy": {
                "take_profit_pct": 1.75,
                "stop_loss_pct": 0.95,
                "trailing_stop_pct": 0.35,
                "enable_partial_tp": True,
                "partial_tp_pct": 0.70,
                "partial_tp_ratio": 0.50,
            },
            "test": {
                "duration_minutes": 20,
            }
        }
        res_update = client.post("/api/config/full", json=update_payload)
        assert res_update.status_code == 200
        res_update_data = res_update.json()
        assert res_update_data["status"] == "success"
        assert bot_instance.config.trading.budget_per_trade == 150.0
        assert bot_instance.config.trading.target_coins_count == 6
        assert bot_instance.config.strategy.take_profit_pct == 1.75
        assert bot_instance.risk_manager.take_profit_pct == 1.75
        assert bot_instance.risk_manager.partial_tp_pct == 0.70
        assert bot_instance.config.test.duration_minutes == 20

        # 12. Switch Mode API Testi
        res_switch = client.post("/api/config/switch_mode", json={"mode": "simulation"})
        assert res_switch.status_code == 200
        assert res_switch.json()["status"] == "success"

        # 13. Reset Default Config API Testi
        res_reset = client.post("/api/config/reset_default", json={"mode": "simulation"})
        assert res_reset.status_code == 200
        assert res_reset.json()["status"] == "success"

        # 14. API Connection Test endpoint (Mocking ping, server_time, account_info)
        with patch("core.binance_client.BinanceTrClient.ping", return_value=True), \
             patch("core.binance_client.BinanceTrClient.get_server_time", return_value=1700000000000), \
             patch("core.binance_client.BinanceTrClient.get_account_info", return_value={"code": 0, "data": {"balances": [{"asset": "TRY", "free": "1000", "locked": "0"}]}}):
            res_test_api = client.post("/api/test_api", json={
                "api_key": "test_api_key_12345",
                "secret_key": "test_secret_key_12345",
                "base_url": "https://www.binance.tr"
            })
            assert res_test_api.status_code == 200
            assert res_test_api.json()["status"] == "success"
            assert res_test_api.json()["authenticated"] is True

        # 15. Cikis yapma testi (Logout)
        res_logout = client.get("/logout", follow_redirects=False)
        assert res_logout.status_code == 303
        assert "/login" in res_logout.headers["location"]

        print("[OK] Tum Auth, Web API, Full Config ve Arayuz testleri basariyla gecti!")
    finally:
        bot_instance.config.trading.mode = original_mode

if __name__ == "__main__":
    test_auth_and_web_endpoints()

