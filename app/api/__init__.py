from fastapi import APIRouter
from app.api import trade
from app.api import strategies
from app.api import metrics
from app.api import prometheus
from app.api import metrics_routes

router = APIRouter(prefix="/api")
router.include_router(trade.router, prefix="/trade")
router.include_router(strategies.router, prefix="/strategies")
# Evitar doble prefijo para métricas: 'metrics' ya define '/metrics'
router.include_router(prometheus.router, prefix="/prometheus")
# No incluir metrics.router aquí; se incluye desde main con prefijo '/api/metrics'
