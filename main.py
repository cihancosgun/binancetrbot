import argparse
import sys
import os
from typing import Optional
import uvicorn

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from config import load_config, resolve_config_path
from bot import BinanceTrBot

def run_cli_session(duration_minutes: int, strategy: Optional[str] = None, symbol: Optional[str] = None, config_path: Optional[str] = None, mode: str = "test"):
    """
    Doğrudan terminal üzerinden CLI oturumu yapar (Test veya Canlı mod).
    """
    resolved_path = resolve_config_path(config_path=config_path, mode=mode)
    cfg = load_config(config_path=resolved_path, mode=mode)
    
    if symbol:
        cfg.trading.symbol = symbol
    if strategy:
        cfg.strategy.active = strategy
    if duration_minutes:
        cfg.test.duration_minutes = duration_minutes

    mode_label = "🔴 GERÇEK EMİR (LIVE)" if cfg.trading.mode == "live" else "🟢 SİMÜLASYON (TEST)"
    
    print("=" * 65)
    print(f"🤖 Binance TR Al-Sat Botu - CLI Oturumu")
    print(f"⚙️ Çalışma Modu   : {mode_label}")
    print(f"📁 Yapılandırma   : {resolved_path}")
    print(f"⏱️ Süre           : {duration_minutes} Dakika")
    print(f"📈 Parite / Radar : {cfg.trading.symbol} | Strateji: {cfg.strategy.active}")
    print("=" * 65)

    bot = BinanceTrBot(cfg)
    bot.start(duration_minutes=duration_minutes)

    try:
        while bot.is_running:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nKullanıcı tarafından durduruldu...")
        bot.stop()

    print("\n✅ Oturum tamamlandı!")
    if bot.last_report:
        print(f"📊 Rapor Dosyası: {bot.last_report.get('html')}")

def run_web_dashboard(host: str = "0.0.0.0", port: int = 8000, config_path: Optional[str] = None, mode: str = "test"):
    """
    Modern Web Takip Panelini belirtilen mod veya yapılandırma ile başlatır.
    """
    resolved_path = resolve_config_path(config_path=config_path, mode=mode)
    os.environ["BOT_CONFIG_FILE"] = resolved_path
    os.environ["BOT_MODE"] = mode

    mode_label = "🔴 CANLI (LIVE)" if mode == "live" else "🟢 TEST (SİMÜLASYON)"

    print("=" * 65)
    print(f"🚀 Binance TR Bot Web Paneli Başlatılıyor...")
    print(f"⚙️ Çalışma Modu   : {mode_label}")
    print(f"📁 Yapılandırma   : {resolved_path}")
    print(f"🌐 Tarayıcınızda açın: http://{host}:{port}")
    print("=" * 65)
    
    uvicorn.run("web.app:app", host=host, port=port, reload=False)

def main():
    parser = argparse.ArgumentParser(
        description="Binance TR Al-Sat Botu (Test & Canlı Mod Desteği)",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["test", "simulation", "live"],
        default="test",
        help="Çalışma modu:\n  test       : Sanal bakiye ile test simülasyonu (Varsayılan: config.test.yaml)\n  live       : Gerçek Binance TR API emirleri (Varsayılan: config.live.yaml)"
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Özel YAML yapılandırma dosya yolu (örn: config.test.yaml, config.live.yaml)"
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Web paneli yerine Terminal CLI modunda çalıştır"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=15,
        help="CLI modu test/oturum süresi (dakika, varsayılan: 15)"
    )
    parser.add_argument(
        "--strategy",
        type=str,
        default=None,
        choices=["adaptive_regime", "rsi_bollinger", "momentum_ema", "grid_scalper", "quick_test_scalper"],
        help="Aktif ticaret stratejisi"
    )
    parser.add_argument(
        "--symbol",
        type=str,
        default=None,
        help="İşlem çifti (örn: AUTO, USDT_TRY, BTC_TRY, SOL_TRY)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Web sunucu portu (varsayılan: 8000)"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Web sunucu host adresi (varsayılan: 0.0.0.0)"
    )

    args = parser.parse_args()

    mode = "live" if args.mode == "live" else "test"

    if args.cli:
        run_cli_session(
            duration_minutes=args.duration,
            strategy=args.strategy,
            symbol=args.symbol,
            config_path=args.config,
            mode=mode
        )
    else:
        run_web_dashboard(
            host=args.host,
            port=args.port,
            config_path=args.config,
            mode=mode
        )

if __name__ == "__main__":
    main()
