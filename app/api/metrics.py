from fastapi import APIRouter, Depends
from app.core.metrics import (
    get_metrics, 
    get_trading_metrics, 
    get_binance_metrics, 
    get_strategy_metrics,
    record_order_execution,
    record_order_failure,
    update_balance,
    update_strategy_status,
    update_profit_loss
)
from app.core.auth import get_api_key
from typing import Dict, Any

router = APIRouter(prefix="/metrics", tags=["metrics"])

@router.get("/")
async def metrics():
    """Endpoint principal de métricas de Prometheus"""
    return get_metrics()

@router.get("/trading")
async def trading_metrics(api_key: str = Depends(get_api_key)):
    """Métricas específicas de trading"""
    return get_trading_metrics()

@router.get("/binance")
async def binance_metrics(api_key: str = Depends(get_api_key)):
    """Métricas de la API de Binance"""
    return get_binance_metrics()

@router.get("/strategies")
async def strategy_metrics(api_key: str = Depends(get_api_key)):
    """Métricas de estrategias"""
    return get_strategy_metrics()

# Endpoints públicos para Prometheus (sin autenticación)
@router.get("/prometheus/trading")
async def prometheus_trading_metrics():
    """Métricas de trading para Prometheus (sin autenticación)"""
    return get_trading_metrics()

@router.get("/prometheus/binance")
async def prometheus_binance_metrics():
    """Métricas de Binance para Prometheus (sin autenticación)"""
    return get_binance_metrics()

@router.get("/prometheus/strategies")
async def prometheus_strategy_metrics():
    """Métricas de estrategias para Prometheus (sin autenticación)"""
    return get_strategy_metrics()

@router.post("/record-order")
async def record_order(
    symbol: str,
    side: str,
    order_type: str,
    strategy: str,
    quantity: float,
    price: float,
    success: bool = True,
    error_type: str = "",
    api_key: str = Depends(get_api_key)
):
    """Registra una orden para métricas"""
    if success:
        record_order_execution(symbol, side, order_type, strategy, quantity, price)
        return {"message": "Orden registrada exitosamente"}
    else:
        record_order_failure(symbol, side, order_type, error_type or "unknown")
        return {"message": "Orden fallida registrada"}

@router.post("/update-balance")
async def update_balance_metric(
    asset: str,
    free: float,
    locked: float,
    api_key: str = Depends(get_api_key)
):
    """Actualiza métricas de balance"""
    update_balance(asset, free, locked)
    return {"message": f"Balance de {asset} actualizado"}

@router.post("/update-strategy")
async def update_strategy_metric(
    strategy_type: str,
    active_count: int,
    api_key: str = Depends(get_api_key)
):
    """Actualiza métricas de estrategias"""
    update_strategy_status(strategy_type, active_count)
    return {"message": f"Estrategia {strategy_type} actualizada"}

@router.post("/update-pnl")
async def update_pnl_metric(
    symbol: str,
    strategy: str,
    pnl: float,
    api_key: str = Depends(get_api_key)
):
    """Actualiza métricas de ganancias/pérdidas"""
    update_profit_loss(symbol, strategy, pnl)
    return {"message": f"PnL de {symbol} ({strategy}) actualizado"}

@router.get("/health")
async def metrics_health():
    """Health check para métricas"""
    return {
        "status": "healthy",
        "metrics_endpoints": {
            "prometheus": "/metrics/",
            "trading": "/metrics/trading",
            "binance": "/metrics/binance",
            "strategies": "/metrics/strategies"
        }
    } 