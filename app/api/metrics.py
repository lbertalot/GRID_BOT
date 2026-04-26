from fastapi import APIRouter, Depends
from app.core.metrics import (
    get_trading_metrics,
    get_binance_metrics,
    get_strategy_metrics,
    record_order_execution,
    record_order_failure,
    update_balance,
    update_strategy_status,
    update_profit_loss,
    gridbot_orders_total,
    gridbot_volume_total,
    gridbot_api_requests_total,
    record_api_request,
)
from app.core.auth import get_api_key
import time

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/")
async def metrics():
    """Endpoint principal de métricas de Prometheus"""
    start_time = time.time()
    try:
        from fastapi.responses import Response
        from prometheus_client import generate_latest

        # Asegurar que existan series gridbot_* aunque no haya tráfico
        try:
            gridbot_api_requests_total.labels(
                method="GET", endpoint="/bootstrap", status_code="200"
            ).inc(0)
            gridbot_orders_total.labels(
                side="BUY", asset="BTCUSDT", strategy="grid"
            ).inc(0)
            gridbot_volume_total.labels(asset="BTCUSDT", strategy="grid").inc(0)
        except Exception:
            pass
        content = generate_latest()
        duration = time.time() - start_time
        record_api_request("GET", "/api/metrics/metrics/", 200, duration)
        return Response(
            content=content, media_type="text/plain; version=0.0.4; charset=utf-8"
        )
    except Exception as e:
        duration = time.time() - start_time
        record_api_request("GET", "/api/metrics/metrics/", 500, duration)
        return {"error": f"Error en métricas: {e}"}


@router.get("/health")
async def metrics_health():
    """Health check de métricas"""
    start_time = time.time()
    try:
        result = {
            "status": "healthy",
            "metrics_endpoints": {
                "prometheus": "/api/metrics/metrics/",
                "trading": "/api/metrics/trading",
                "binance": "/api/metrics/binance",
                "strategies": "/api/metrics/strategies",
            },
        }
        duration = time.time() - start_time
        record_api_request("GET", "/api/metrics/health", 200, duration)
        return result
    except Exception as e:
        duration = time.time() - start_time
        record_api_request("GET", "/api/metrics/health", 500, duration)
        raise e


@router.get("/trading")
async def trading_metrics():
    """Métricas de trading"""
    start_time = time.time()
    try:
        result = get_trading_metrics()
        duration = time.time() - start_time
        record_api_request("GET", "/api/metrics/trading", 200, duration)
        return result
    except Exception as e:
        duration = time.time() - start_time
        record_api_request("GET", "/api/metrics/trading", 500, duration)
        raise e


@router.get("/binance")
async def binance_metrics():
    """Métricas de Binance"""
    start_time = time.time()
    try:
        result = get_binance_metrics()
        duration = time.time() - start_time
        record_api_request("GET", "/api/metrics/binance", 200, duration)
        return result
    except Exception as e:
        duration = time.time() - start_time
        record_api_request("GET", "/api/metrics/binance", 500, duration)
        raise e


@router.get("/strategies")
async def strategy_metrics():
    """Métricas de estrategias"""
    start_time = time.time()
    try:
        result = get_strategy_metrics()
        duration = time.time() - start_time
        record_api_request("GET", "/api/metrics/strategies", 200, duration)
        return result
    except Exception as e:
        duration = time.time() - start_time
        record_api_request("GET", "/api/metrics/strategies", 500, duration)
        raise e


# Endpoints públicos para Prometheus (sin autenticación)
@router.get("/prometheus/trading")
async def prometheus_trading_metrics():
    """Métricas de trading para Prometheus (sin autenticación)"""
    start_time = time.time()
    try:
        from fastapi.responses import Response
        from prometheus_client import generate_latest

        # Generar métricas de Prometheus directamente
        metrics_content = generate_latest()

        duration = time.time() - start_time
        record_api_request(
            "GET", "/api/metrics/metrics/prometheus/trading", 200, duration
        )

        return Response(
            content=metrics_content,
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    except Exception as e:
        duration = time.time() - start_time
        record_api_request(
            "GET", "/api/metrics/metrics/prometheus/trading", 500, duration
        )
        return {"error": f"Error generando métricas: {str(e)}"}


@router.get("/prometheus/binance")
async def prometheus_binance_metrics():
    """Métricas de Binance para Prometheus (sin autenticación)"""
    start_time = time.time()
    try:
        result = get_binance_metrics()
        duration = time.time() - start_time
        record_api_request("GET", "/api/prometheus/binance", 200, duration)
        return result
    except Exception as e:
        duration = time.time() - start_time
        record_api_request("GET", "/api/prometheus/binance", 500, duration)
        raise e


@router.get("/prometheus/strategies")
async def prometheus_strategy_metrics():
    """Métricas de estrategias para Prometheus (sin autenticación)"""
    start_time = time.time()
    try:
        result = get_strategy_metrics()
        duration = time.time() - start_time
        record_api_request("GET", "/api/prometheus/strategies", 200, duration)
        return result
    except Exception as e:
        duration = time.time() - start_time
        record_api_request("GET", "/api/prometheus/strategies", 500, duration)
        raise e


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
    api_key: str = Depends(get_api_key),
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
    asset: str, free: float, locked: float, api_key: str = Depends(get_api_key)
):
    """Actualiza métricas de balance"""
    update_balance(asset, free, locked)
    return {"message": f"Balance de {asset} actualizado"}


@router.post("/update-strategy")
async def update_strategy_metric(
    strategy_type: str, active_count: int, api_key: str = Depends(get_api_key)
):
    """Actualiza métricas de estrategias"""
    update_strategy_status(strategy_type, active_count)
    return {"message": f"Estrategia {strategy_type} actualizada"}


@router.post("/update-pnl")
async def update_pnl_metric(
    symbol: str, strategy: str, pnl: float, api_key: str = Depends(get_api_key)
):
    """Actualiza métricas de ganancias/pérdidas"""
    update_profit_loss(symbol, strategy, pnl)
    return {"message": f"PnL de {symbol} ({strategy}) actualizado"}
