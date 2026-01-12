from datetime import datetime
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def root():
    return {
        "message": "Grid Trading Bot",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }


@router.get("/health")
async def health_check():
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat()
    }


@router.get("/health/liveness")
async def liveness():
    return {
        "status": "alive",
        "timestamp": datetime.now().isoformat()
    }


@router.get("/health/readiness")
async def readiness():
    # Si se requiere, aquí se podrían agregar checks de DB/Redis de forma no bloqueante
    return {
        "status": "ready",
        "timestamp": datetime.now().isoformat()
    }

