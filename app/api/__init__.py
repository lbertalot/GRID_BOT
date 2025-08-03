from fastapi import APIRouter
from app.api import trade
from app.api import strategies
from app.api import metrics
from app.api import prometheus
from app.api import metrics_routes

router = APIRouter(prefix="/api")
router.include_router(trade.router, prefix="/trade")
router.include_router(strategies.router, prefix="/strategies")
router.include_router(metrics.router, prefix="/metrics")
router.include_router(prometheus.router, prefix="/prometheus")
# metrics_routes ya tiene su propio prefijo /api/v1/metrics 