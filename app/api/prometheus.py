from fastapi import APIRouter
from app.core.metrics import get_trading_metrics, get_binance_metrics, get_strategy_metrics

router = APIRouter()

@router.get("/trading")
async def prometheus_trading_metrics():
    """Métricas de trading para Prometheus (sin autenticación)"""
    return get_trading_metrics()

@router.get("/binance")
async def prometheus_binance_metrics():
    """Métricas de Binance para Prometheus (sin autenticación)"""
    return get_binance_metrics()

@router.get("/strategies")
async def prometheus_strategy_metrics():
    """Métricas de estrategias para Prometheus (sin autenticación)"""
    return get_strategy_metrics() 