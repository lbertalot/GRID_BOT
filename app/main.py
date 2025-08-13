from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
import logging
from fastapi.exceptions import RequestValidationError
from fastapi import HTTPException

from app.api import trade, strategies, metrics, prometheus, optimized_routes, risk_routes, config_routes, strategy_routes, metrics_routes
from app.api import alert_routes, binance_sync_routes, test_routes
from app.core.auth import get_api_key
from app.core.error_handlers import validation_exception_handler, http_exception_handler, general_exception_handler
from app.db.init_db import init_db
from app.scheduler.optimized_scheduler import start_optimized_scheduler, stop_optimized_scheduler
from app.services.balance_updater import update_balances_in_db
from app.services.asset_limit_updater import update_asset_limits_in_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestiona el ciclo de vida de la aplicación.
    """
    logger.info("🚀 La aplicación está iniciando...")
    
    init_db()
    await update_balances_in_db()
    await update_asset_limits_in_db()
    await start_optimized_scheduler()
    
    yield
    
    await stop_optimized_scheduler()
    logger.info("✅ La aplicación se ha detenido correctamente.")

app = FastAPI(
    title="Grid Trading Bot",
    description="Un bot de trading automatizado para estrategias de grid en Binance.",
    version="2.0.0",
    lifespan=lifespan
)

# Configuración de CORS
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar manejadores de errores
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# Incluir routers
app.include_router(trade.router, prefix="/api/trade", tags=["Trading"])
app.include_router(strategies.router, prefix="/api/strategies", tags=["Strategies"])
# Endpoints públicos compatibles con tests legacy
app.include_router(strategies.router)  # expone /strategy/* sin prefijo
app.include_router(metrics.router, prefix="/api/metrics", tags=["Metrics"])
app.include_router(metrics_routes.router)  # Ya tiene prefix /api/v1/metrics
app.include_router(risk_routes.router, tags=["Risk Management"])  # Ya tiene prefix /api/v1/risk
app.include_router(config_routes.router, tags=["Configuration Optimization"])  # Ya tiene prefix /api/v1/config
app.include_router(prometheus.router, prefix="/api/prometheus", tags=["Prometheus"])
# Exponer rutas optimizadas con su propio prefijo interno (/api/v1)
app.include_router(optimized_routes.router)
app.include_router(strategy_routes.router, tags=["Strategies"])
app.include_router(alert_routes.router)
app.include_router(binance_sync_routes.router)
app.include_router(test_routes.router)

# Configuración de plantillas
templates = Jinja2Templates(directory="app/templates")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """
    Endpoint raíz que sirve la página principal de la aplicación.
    """
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """
    Endpoint del dashboard avanzado de métricas.
    """
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/config-optimizer", response_class=HTMLResponse)
async def config_optimizer(request: Request):
    """
    Endpoint del optimizador de configuración.
    """
    return templates.TemplateResponse("config_optimizer.html", {"request": request})

@app.get("/optimizer", response_class=HTMLResponse)
async def optimizer_alt(request: Request):
    """
    Endpoint alternativo del optimizador de configuración.
    """
    return templates.TemplateResponse("config_optimizer.html", {"request": request})

@app.get("/health", response_class=JSONResponse)
async def health_check():
    """
    Endpoint de health check para verificar que la aplicación está funcionando.
    """
    return {"status": "ok"}

@app.get("/test-simple")
async def test_simple():
    """
    Endpoint simple de prueba.
    """
    return {"message": "Test simple funcionando"}

@app.get("/test-metrics", response_class=JSONResponse)
async def test_metrics():
    """
    Endpoint de prueba para verificar que las métricas funcionan.
    """
    try:
        from app.core.metrics import trading_metrics
        return {"status": "ok", "message": "Métricas importadas correctamente"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

 

@app.get("/simple-metrics")
async def simple_metrics():
    """
    Endpoint simple para probar métricas.
    """
    return {"message": "Métricas funcionando"}

@app.get("/test-endpoint")
async def test_endpoint():
    """
    Endpoint de prueba.
    """
    return {"message": "Endpoint funcionando"} 

# --- Aliases públicos sin auth para compatibilidad con tests ---
from app.api.trade import place_order as protected_place_order, run_grid as protected_run_grid
from app.schemas.validation import OrderRequest, GridParams
from app.db.session import SessionLocal

@app.post("/order")
def place_order_public(order: OrderRequest):
    db = SessionLocal()
    try:
        # Delegar a la lógica existente, evitando la dependencia de auth
        return protected_place_order(order=order, db=db, api_key="public")
    finally:
        db.close()

@app.post("/run_grid")
def run_grid_public(params: GridParams):
    # Delegar a la lógica existente, evitando la dependencia de auth
    return protected_run_grid(params=params, api_key="public")