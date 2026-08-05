from datetime import datetime
from fastapi import APIRouter

from app.core.trading_mode import get_trading_mode_snapshot

router = APIRouter()


@router.get("/")
async def root():
    return {
        "message": "Grid Trading Bot",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "trading": get_trading_mode_snapshot(),
    }


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "trading": get_trading_mode_snapshot(),
    }


@router.get("/health/trading-mode")
async def trading_mode():
    """Explicit alias for UX clients that only need mode clarity."""
    return {
        "timestamp": datetime.now().isoformat(),
        "trading": get_trading_mode_snapshot(),
    }


@router.get("/health/liveness")
async def liveness():
    return {"status": "alive", "timestamp": datetime.now().isoformat()}


@router.get("/health/readiness")
async def readiness():
    # Si se requiere, aquí se podrían agregar checks de DB/Redis de forma no bloqueante
    return {
        "status": "ready",
        "timestamp": datetime.now().isoformat(),
        "trading": get_trading_mode_snapshot(),
    }
