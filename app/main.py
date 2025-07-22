from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
import logging
from fastapi.exceptions import RequestValidationError
from fastapi import HTTPException

from app.api import trade, strategies, metrics, prometheus, optimized_routes
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
app.include_router(metrics.router, prefix="/api/metrics", tags=["Metrics"])
app.include_router(prometheus.router, prefix="/api/prometheus", tags=["Prometheus"])
app.include_router(optimized_routes.router, prefix="/api/optimized", tags=["Optimized"])

# Configuración de plantillas
templates = Jinja2Templates(directory="app/templates")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """
    Endpoint raíz que sirve la página principal de la aplicación.
    """
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/health", response_class=JSONResponse)
async def health_check():
    """
    Endpoint de health check para verificar que la aplicación está funcionando.
    """
    return {"status": "ok"} 