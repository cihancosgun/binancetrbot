import os
import secrets
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional, Dict, Any

from bot import BinanceTrBot
from config import load_config, save_config

app = FastAPI(title="Binance TR Al-Sat Botu")

# Aktif oturum token'ları havuzu
active_sessions: set[str] = set()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

os.makedirs(TEMPLATES_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "css"), exist_ok=True)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(ROOT_DIR, "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/reports", StaticFiles(directory=REPORTS_DIR, html=True), name="reports")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Bot örneğini başlat
bot_instance = BinanceTrBot()

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    # Eğer yapılandırmada kimlik doğrulama kapalıysa doğrudan devam et
    auth_cfg = getattr(bot_instance.config, "auth", None)
    if not auth_cfg or not getattr(auth_cfg, "enabled", True):
        return await call_next(request)

    path = request.url.path

    # Herkese açık rotalar (statik dosyalar, login sayfası ve login API'si)
    if (
        path.startswith("/static")
        or path in ("/login", "/api/login", "/favicon.ico")
    ):
        return await call_next(request)

    # Oturum doğrulaması
    token = request.cookies.get("session_token")
    if token and token in active_sessions:
        return await call_next(request)

    # Kimlik doğrulanmamışsa: API için 401, sayfalar için login'e yönlendir
    if path.startswith("/api/"):
        return JSONResponse(status_code=401, content={"status": "error", "message": "Giriş yapmanız gerekiyor."})

    return RedirectResponse(url="/login", status_code=303)

@app.on_event("shutdown")
def shutdown_event():
    bot_instance.is_running = False
    if hasattr(bot_instance, "client") and hasattr(bot_instance.client, "session"):
        try:
            bot_instance.client.session.close()
        except Exception:
            pass

class StartRequest(BaseModel):
    duration_minutes: Optional[int] = 15
    strategy: Optional[str] = None
    symbol: Optional[str] = None
    budget_per_trade: Optional[float] = None
    auto_select_coin: Optional[bool] = None
    target_coins_count: Optional[int] = None
    candidate_observation_seconds: Optional[int] = None
    trailing_activation_pct: Optional[float] = None
    symbol_cooldown_seconds: Optional[int] = None
    only_uptrend: Optional[bool] = None

class ConfigUpdateRequest(BaseModel):
    take_profit_pct: Optional[float] = None
    stop_loss_pct: Optional[float] = None
    trailing_stop_pct: Optional[float] = None
    trailing_activation_pct: Optional[float] = None
    symbol_cooldown_seconds: Optional[int] = None
    budget_per_trade: Optional[float] = None
    strategy: Optional[str] = None
    symbol: Optional[str] = None
    rsi_oversold: Optional[float] = None
    rsi_overbought: Optional[float] = None
    auto_select_coin: Optional[bool] = None
    target_coins_count: Optional[int] = None
    auto_fill_portfolio: Optional[bool] = None
    candidate_observation_seconds: Optional[int] = None
    filter_falling_coins: Optional[bool] = None
    only_uptrend: Optional[bool] = None

class LoginRequest(BaseModel):
    username: str
    password: str

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    token = request.cookies.get("session_token")
    if token and token in active_sessions:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(request=request, name="login.html")

@app.post("/api/login")
async def api_login(req: LoginRequest):
    auth_cfg = getattr(bot_instance.config, "auth", None)
    expected_user = getattr(auth_cfg, "username", "admin") if auth_cfg else "admin"
    expected_pass = getattr(auth_cfg, "password", "admin123") if auth_cfg else "admin123"

    if req.username == expected_user and req.password == expected_pass:
        token = secrets.token_hex(32)
        active_sessions.add(token)
        response = JSONResponse(content={"status": "success", "username": req.username})
        response.set_cookie(
            key="session_token",
            value=token,
            httponly=True,
            samesite="lax",
            max_age=86400 * 7,  # 7 gün geçerli
        )
        return response

    return JSONResponse(
        status_code=401,
        content={"status": "error", "message": "Kullanıcı adı veya parola hatalı!"}
    )

@app.get("/logout")
@app.post("/api/logout")
async def logout_endpoint(request: Request):
    token = request.cookies.get("session_token")
    if token in active_sessions:
        active_sessions.discard(token)
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("session_token")
    return response

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/api/state")
async def get_state():
    return bot_instance.get_dashboard_state()

@app.post("/api/start")
async def start_bot(req: StartRequest):
    if req.strategy:
        bot_instance.config.strategy.active = req.strategy
        bot_instance.strategy = bot_instance._init_strategy()
    if req.symbol:
        bot_instance.config.trading.symbol = req.symbol
        bot_instance.market_data.symbol = req.symbol
    if req.budget_per_trade:
        bot_instance.config.trading.budget_per_trade = req.budget_per_trade
    if req.auto_select_coin is not None:
        bot_instance.config.trading.auto_select_coin = req.auto_select_coin
    if req.target_coins_count is not None:
        bot_instance.config.trading.target_coins_count = req.target_coins_count
        bot_instance.config.trading.max_open_positions = req.target_coins_count
        bot_instance.risk_manager.max_open_positions = req.target_coins_count
    if req.candidate_observation_seconds is not None:
        bot_instance.config.trading.candidate_observation_seconds = req.candidate_observation_seconds
        bot_instance.scanner.watchlist.min_observation_seconds = req.candidate_observation_seconds
    if req.trailing_activation_pct is not None:
        bot_instance.config.strategy.trailing_activation_pct = req.trailing_activation_pct
        bot_instance.risk_manager.trailing_activation_pct = req.trailing_activation_pct
    if req.symbol_cooldown_seconds is not None:
        bot_instance.config.strategy.symbol_cooldown_seconds = req.symbol_cooldown_seconds
        bot_instance.risk_manager.symbol_cooldown_seconds = req.symbol_cooldown_seconds
    if req.only_uptrend is not None:
        bot_instance.config.trading.only_uptrend = req.only_uptrend

    bot_instance.start(duration_minutes=req.duration_minutes)
    return {"status": "started", "duration": req.duration_minutes}

@app.post("/api/stop")
async def stop_bot():
    res = bot_instance.stop()
    return res

@app.post("/api/force_buy")
async def force_buy():
    pos = bot_instance.force_test_buy(reason="Kullanıcı Test Alımı")
    if pos:
        return {"status": "success", "position": pos}
    return JSONResponse(status_code=400, content={"status": "error", "message": "Pozisyon açılamadı. Fiyat alınamadı veya bütçe yetersiz."})

class ClosePositionRequest(BaseModel):
    position_id: str

@app.post("/api/force_close")
@app.post("/api/close_all")
async def close_all_positions():
    closed = bot_instance.force_close_all(reason="Kullanıcı Tümünü Sat Emri")
    return {"status": "success", "closed_count": len(closed), "trades": closed}

@app.post("/api/close_position")
async def close_single_position(req: ClosePositionRequest):
    trade = bot_instance.close_single_position(req.position_id, reason="Kullanıcı Manuel Satış")
    if trade:
        return {"status": "success", "trade": trade}
    return JSONResponse(status_code=400, content={"status": "error", "message": "Pozisyon kapatılamadı"})

@app.post("/api/config")
async def update_config(req: ConfigUpdateRequest):
    cfg = bot_instance.config
    if req.take_profit_pct is not None:
        cfg.strategy.take_profit_pct = req.take_profit_pct
        bot_instance.risk_manager.take_profit_pct = req.take_profit_pct
    if req.stop_loss_pct is not None:
        cfg.strategy.stop_loss_pct = req.stop_loss_pct
        bot_instance.risk_manager.stop_loss_pct = req.stop_loss_pct
    if req.trailing_stop_pct is not None:
        cfg.strategy.trailing_stop_pct = req.trailing_stop_pct
        bot_instance.risk_manager.trailing_stop_pct = req.trailing_stop_pct
    if req.trailing_activation_pct is not None:
        cfg.strategy.trailing_activation_pct = req.trailing_activation_pct
        bot_instance.risk_manager.trailing_activation_pct = req.trailing_activation_pct
    if req.symbol_cooldown_seconds is not None:
        cfg.strategy.symbol_cooldown_seconds = req.symbol_cooldown_seconds
        bot_instance.risk_manager.symbol_cooldown_seconds = req.symbol_cooldown_seconds
    if req.budget_per_trade is not None:
        cfg.trading.budget_per_trade = req.budget_per_trade
    if req.strategy is not None:
        cfg.strategy.active = req.strategy
        bot_instance.strategy = bot_instance._init_strategy()
    if req.symbol is not None:
        cfg.trading.symbol = req.symbol
        bot_instance.market_data.symbol = req.symbol
    if req.rsi_oversold is not None:
        cfg.strategy.rsi_oversold = req.rsi_oversold
    if req.rsi_overbought is not None:
        cfg.strategy.rsi_overbought = req.rsi_overbought
    if req.auto_select_coin is not None:
        cfg.trading.auto_select_coin = req.auto_select_coin
    if req.target_coins_count is not None:
        cfg.trading.target_coins_count = req.target_coins_count
        cfg.trading.max_open_positions = req.target_coins_count
        bot_instance.risk_manager.max_open_positions = req.target_coins_count
    if req.auto_fill_portfolio is not None:
        cfg.trading.auto_fill_portfolio = req.auto_fill_portfolio
    if req.candidate_observation_seconds is not None:
        cfg.trading.candidate_observation_seconds = req.candidate_observation_seconds
        bot_instance.scanner.watchlist.min_observation_seconds = req.candidate_observation_seconds
    if req.filter_falling_coins is not None:
        cfg.trading.filter_falling_coins = req.filter_falling_coins
    if req.only_uptrend is not None:
        cfg.trading.only_uptrend = req.only_uptrend

    save_config(cfg)
    return {"status": "updated", "config": bot_instance.get_dashboard_state()["config"]}

@app.get("/api/reports")
async def list_reports():
    if not os.path.exists(REPORTS_DIR):
        return []
    files = [f for f in os.listdir(REPORTS_DIR) if f.endswith(".html")]
    files.sort(reverse=True)
    return [{"filename": f, "path": f"/reports/{f}"} for f in files]
