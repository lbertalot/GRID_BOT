from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
import logging
from fastapi.exceptions import RequestValidationError
from fastapi import HTTPException

from app.api import metrics_routes
from app.core.error_handlers import validation_exception_handler, http_exception_handler, general_exception_handler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestiona el ciclo de vida de la aplicación.
    """
    logger.info("🚀 La aplicación está iniciando...")
    
    yield
    
    logger.info("✅ La aplicación se ha detenido correctamente.")

app = FastAPI(
    title="Grid Trading Bot - Dashboard",
    description="Dashboard de métricas avanzadas para Grid Trading Bot.",
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

# Incluir solo el router de métricas avanzadas
app.include_router(metrics_routes.router, tags=["Advanced Metrics"])

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

@app.get("/health", response_class=JSONResponse)
async def health_check():
    """
    Endpoint de health check para verificar que la aplicación está funcionando.
    """
    return {"status": "ok", "service": "dashboard-only"} 