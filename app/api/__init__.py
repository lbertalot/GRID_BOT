from fastapi import APIRouter
from app.api import trade
from app.api import strategies

router = APIRouter()
router.include_router(trade.router)
router.include_router(strategies.router) 