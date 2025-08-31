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


