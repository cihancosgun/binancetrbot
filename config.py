import os
import yaml
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

@dataclass
class TradingConfig:
    mode: str = "simulation"
    symbol: str = "AUTO"             # "AUTO" means dynamic scanner mode
    auto_select_coin: bool = True    # Otomatik en hareketli coinleri bul ve al-sat yap
    target_coins_count: int = 5      # Portföyde daima tutulacak en az farklı coin sayısı
    max_open_positions: int = 5      # Aynı anda açık olabilecek maksimum pozisyon
    auto_fill_portfolio: bool = False # Sadece strateji BUY sinyali verdiğinde al (acele doldurma)
    require_strict_buy_signal: bool = True # Strateji teyidi olmadan işlem açmama
    top_coins_limit: int = 0         # Taranacak coin havuzu (0 = Tüm Binance TR TRY çiftlerini tara ve rotasyon yap)
    min_24h_volume_try: float = 5000000.0 # En az 5 Milyon TL 24s hacim (sığ meme coinleri ele)
    initial_virtual_balance: float = 10000.0
    budget_per_trade: float = 2000.0         # Her bir coine ayrılacak bütçe (TL)
    candidate_observation_seconds: int = 45 # Aday coini almadan önce 45 saniye gözlemleme süresi (sn)
    min_observation_gain_pct: float = 1.0    # Aday coin için gözlem penceresinde gereken min yükseliş ivmesi (%1.0)
    candidate_min_burst_count: int = 2       # 45s içinde onay için gereken en az patlama/yükseliş dalgası sayısı
    candidate_timeout_cooldown_seconds: int = 5 # 45s içinde ivme yakalayamayan coinin dinlenme süresi (sn)
    filter_falling_coins: bool = True        # Sürekli tepe aşağı düşen coinleri engelleme
    only_uptrend: bool = True                # Radarda sadece pozitif/yükseliş trendindeki coinleri tara
    min_24h_gain_pct: float = 0.0            # En az 24 saatlik getiri eşiği (%0.0)
    fee_rate_pct: float = 0.1
    prevent_rebuy_churn: bool = True         # Satıp hemen aynı coini alacaksa boşuna komisyon ödememe (Devir Koruması)
    loss_cooldown_seconds: int = 300         # Zarar kesilen coine 5 dk (300s) ceza beklemesi

@dataclass
class TestConfig:
    duration_minutes: int = 15
    auto_stop: bool = True

@dataclass
class StrategyConfig:
    active: str = "fee_recovery"             # Komisyon Oranını Kurtaran Strateji (Varsayılan)
    take_profit_pct: float = 1.0             # Kâr Al (%1.00)
    stop_loss_pct: float = 1.0               # Zarar Kes (%1.00)
    trailing_stop_pct: float = 0.50          # İz Süren Stop Mesafesi (%0.50)
    trailing_activation_pct: float = 0.80    # Trailing Stop Devreye Girme Eşiği (%0.80)
    portfolio_stop_loss_pct: float = 2.0     # Tüm Portföy Zarar Kes Eşiği (%2.00)
    fee_multiplier: float = 2.0              # Komisyon Çarpanı
    cooldown_seconds: int = 10
    symbol_cooldown_seconds: int = 90        # Aynı coine tekrar girmek için bekleme süresi (90 sn)
    loss_cooldown_seconds: int = 300         # Zarar kesilen coine ceza süresi (300 sn)
    # Additional optional strategy parameters
    rsi_period: int = 14
    rsi_oversold: float = 42.0
    rsi_overbought: float = 65.0
    bollinger_period: int = 20
    bollinger_std_dev: float = 2.0
    ema_fast: int = 9
    ema_slow: int = 21

@dataclass
class ApiConfig:
    base_url: str = "https://www.binance.tr"
    ws_url: str = "wss://stream-cloud.binance.tr/ws"
    api_key: str = ""
    secret_key: str = ""

@dataclass
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8000

@dataclass
class AuthConfig:
    enabled: bool = True
    username: str = "admin"
    password: str = "admin123"

@dataclass
class BotConfig:
    trading: TradingConfig = field(default_factory=TradingConfig)
    test: TestConfig = field(default_factory=TestConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    api: ApiConfig = field(default_factory=ApiConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)
    loaded_config_path: str = "config.test.yaml"

def resolve_config_path(config_path: Optional[str] = None, mode: Optional[str] = None) -> str:
    """
    Belirtilen parametrelere, çevre değişkenlerine veya çalışma moduna göre
    en uygun yapılandırma dosya yolunu belirler.
    """
    # 1. Doğrudan parametre olarak geçildiyse
    if config_path:
        return config_path
    
    # 2. Çevre değişkeninden belirtilmişse
    env_config = os.environ.get("BOT_CONFIG_FILE")
    if env_config:
        return env_config

    # 3. Mod bazlı çözümleme (Parametre veya BOT_MODE çevre değişkeni)
    active_mode = (mode or os.environ.get("BOT_MODE", "test")).lower()

    if active_mode in ("live", "prod", "production"):
        candidates = [
            "config.live.yaml",
            "config-live.yaml",
            "config.yaml",
            "config.live.example.yaml",
            "config.example.yaml",
        ]
        default_target = "config.live.yaml"
    else:  # test, simulation
        candidates = [
            "config.test.yaml",
            "config-test.yaml",
            "config.yaml",
            "config.test.example.yaml",
            "config.example.yaml",
        ]
        default_target = "config.test.yaml"

    for cand in candidates:
        if os.path.exists(cand):
            return cand

    return default_target

def load_config(config_path: Optional[str] = None, mode: Optional[str] = None) -> BotConfig:
    """
    Yapılandırma dosyasını yükler. 'test' veya 'live' moduna göre ilgili YAML dosyasını seçer.
    """
    resolved_path = resolve_config_path(config_path=config_path, mode=mode)
    
    if not os.path.exists(resolved_path):
        cfg = BotConfig()
        cfg.loaded_config_path = resolved_path
        if mode:
            cfg.trading.mode = "live" if mode.lower() in ("live", "prod") else "simulation"
        return cfg
    
    with open(resolved_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    trading_data = data.get("trading", {})
    test_data = data.get("test", {})
    strategy_data = data.get("strategy", {})
    api_data = data.get("api", {})
    server_data = data.get("server", {})
    auth_data = data.get("auth", {})

    cfg = BotConfig(
        trading=TradingConfig(**{k: v for k, v in trading_data.items() if k in TradingConfig.__dataclass_fields__}),
        test=TestConfig(**{k: v for k, v in test_data.items() if k in TestConfig.__dataclass_fields__}),
        strategy=StrategyConfig(**{k: v for k, v in strategy_data.items() if k in StrategyConfig.__dataclass_fields__}),
        api=ApiConfig(**{k: v for k, v in api_data.items() if k in ApiConfig.__dataclass_fields__}),
        server=ServerConfig(**{k: v for k, v in server_data.items() if k in ServerConfig.__dataclass_fields__}),
        auth=AuthConfig(**{k: v for k, v in auth_data.items() if k in AuthConfig.__dataclass_fields__}),
        loaded_config_path=resolved_path,
    )

    if mode:
        if mode.lower() in ("live", "prod"):
            cfg.trading.mode = "live"
        elif mode.lower() in ("test", "simulation"):
            cfg.trading.mode = "simulation"

    # TEST EMNİYETİ: Eğer pytest veya test ortamı çalışıyorsa modu KESİNLİKLE 'simulation' yap!
    if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("BOT_TESTING") == "1":
        cfg.trading.mode = "simulation"

    return cfg

def save_config(config: BotConfig, config_path: Optional[str] = None) -> None:
    """
    Yapılandırmayı YAML dosyasına kaydeder. Dosya belirtilmemişse aktif yüklenen dosyaya kaydeder.
    """
    target_path = config_path or getattr(config, "loaded_config_path", None) or resolve_config_path(mode=config.trading.mode)

    data = {
        "trading": {
            "mode": config.trading.mode,
            "symbol": config.trading.symbol,
            "auto_select_coin": config.trading.auto_select_coin,
            "target_coins_count": config.trading.target_coins_count,
            "auto_fill_portfolio": config.trading.auto_fill_portfolio,
            "top_coins_limit": config.trading.top_coins_limit,
            "initial_virtual_balance": config.trading.initial_virtual_balance,
            "budget_per_trade": config.trading.budget_per_trade,
            "max_open_positions": config.trading.max_open_positions,
            "min_24h_volume_try": getattr(config.trading, "min_24h_volume_try", 5000000.0),
            "candidate_observation_seconds": getattr(config.trading, "candidate_observation_seconds", 45),
            "min_observation_gain_pct": getattr(config.trading, "min_observation_gain_pct", 1.0),
            "candidate_min_burst_count": getattr(config.trading, "candidate_min_burst_count", 2),
            "candidate_timeout_cooldown_seconds": getattr(config.trading, "candidate_timeout_cooldown_seconds", 5),
            "filter_falling_coins": getattr(config.trading, "filter_falling_coins", True),
            "only_uptrend": getattr(config.trading, "only_uptrend", True),
            "min_24h_gain_pct": getattr(config.trading, "min_24h_gain_pct", 0.0),
            "fee_rate_pct": config.trading.fee_rate_pct,
            "prevent_rebuy_churn": getattr(config.trading, "prevent_rebuy_churn", True),
        },
        "test": {
            "duration_minutes": config.test.duration_minutes,
            "auto_stop": config.test.auto_stop,
        },
        "strategy": {
            "active": config.strategy.active,
            "take_profit_pct": config.strategy.take_profit_pct,
            "stop_loss_pct": config.strategy.stop_loss_pct,
            "trailing_stop_pct": config.strategy.trailing_stop_pct,
            "trailing_activation_pct": getattr(config.strategy, "trailing_activation_pct", 0.20),
            "portfolio_stop_loss_pct": getattr(config.strategy, "portfolio_stop_loss_pct", 2.0),
            "fee_multiplier": getattr(config.strategy, "fee_multiplier", 2.0),
            "cooldown_seconds": config.strategy.cooldown_seconds,
            "symbol_cooldown_seconds": getattr(config.strategy, "symbol_cooldown_seconds", 60),
            "rsi_period": config.strategy.rsi_period,
            "rsi_oversold": config.strategy.rsi_oversold,
            "rsi_overbought": config.strategy.rsi_overbought,
            "bollinger_period": config.strategy.bollinger_period,
            "bollinger_std_dev": config.strategy.bollinger_std_dev,
            "ema_fast": config.strategy.ema_fast,
            "ema_slow": config.strategy.ema_slow,
        },
        "api": {
            "base_url": config.api.base_url,
            "ws_url": config.api.ws_url,
            "api_key": config.api.api_key,
            "secret_key": config.api.secret_key,
        },
        "server": {
            "host": config.server.host,
            "port": config.server.port,
        },
        "auth": {
            "enabled": config.auth.enabled,
            "username": config.auth.username,
            "password": config.auth.password,
        },
    }
    with open(target_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
