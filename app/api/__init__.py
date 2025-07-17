from fastapi import APIRouter
from app.api import trade

router = APIRouter()
router.include_router(trade.router) 