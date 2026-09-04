import os
import pytest
from config import load_config, save_config, resolve_config_path, BotConfig

def test_resolve_config_path():
    # 1. Custom path explicitly passed
    assert resolve_config_path(config_path="custom_conf.yaml") == "custom_conf.yaml"

    # 2. Test mode resolution
    test_path = resolve_config_path(mode="test")
    assert "test" in test_path

    # 3. Live mode resolution
    live_path = resolve_config_path(mode="live")
    assert "live" in live_path or "config.yaml" in live_path

def test_load_and_save_config_test_mode(tmp_path):
    temp_test_yaml = str(tmp_path / "config.test.yaml")
    cfg = BotConfig()
    cfg.trading.mode = "simulation"
    cfg.trading.budget_per_trade = 1234.0
    cfg.loaded_config_path = temp_test_yaml

    save_config(cfg, config_path=temp_test_yaml)
    assert os.path.exists(temp_test_yaml)

    loaded = load_config(config_path=temp_test_yaml)
    assert loaded.trading.budget_per_trade == 1234.0
    assert loaded.loaded_config_path == temp_test_yaml

def test_load_and_save_config_live_mode(tmp_path):
    temp_live_yaml = str(tmp_path / "config.live.yaml")
    cfg = BotConfig()
    cfg.trading.mode = "live"
    cfg.trading.budget_per_trade = 555.0
    cfg.loaded_config_path = temp_live_yaml

    save_config(cfg, config_path=temp_live_yaml)
    assert os.path.exists(temp_live_yaml)

    loaded = load_config(config_path=temp_live_yaml)
    assert loaded.trading.budget_per_trade == 555.0
    assert loaded.loaded_config_path == temp_live_yaml
