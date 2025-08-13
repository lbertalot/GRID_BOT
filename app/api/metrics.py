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
    update_profit_loss,
    api_requests_total,
    record_api_request
)
from app.core.auth import get_api_key
from typing import Dict, Any
import asyncio
from binance import Client
import os
from dotenv import load_dotenv
import time

router = APIRouter(prefix="/metrics", tags=["metrics"])

@router.get("/")
async def metrics():
    """Endpoint principal de métricas de Prometheus"""
    start_time = time.time()
    try:
        from fastapi.responses import Response
        from prometheus_client import generate_latest
        content = generate_latest()
        duration = time.time() - start_time
        record_api_request("GET", "/api/metrics/metrics/", 200, duration)
        return Response(content=content, media_type="text/plain; version=0.0.4; charset=utf-8")
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
                "strategies": "/api/metrics/strategies"
            }
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

@router.post("/update-pnl")
async def update_pnl_metrics():
    """Actualizar métricas de P&L en tiempo real"""
    start_time = time.time()
    try:
        # Cargar variables de entorno
        load_dotenv()
        api_key = os.getenv("BINANCE_API_KEY")
        api_secret = os.getenv("BINANCE_API_SECRET")
        
        if not api_key or not api_secret:
            duration = time.time() - start_time
            record_api_request("POST", "/api/metrics/update-pnl", 400, duration)
            return {"error": "Credenciales de Binance no configuradas"}
        
        # Conectar a Binance
        client = Client(api_key, api_secret)
        
        # Obtener información de la cuenta
        account = client.get_account()
        
        # Calcular valor total del portfolio
        total_value_usdt = 0.0
        asset_values = {}
        
        for balance in account['balances']:
            asset = balance['asset']
            free = float(balance['free'])
            locked = float(balance['locked'])
            total = free + locked
            
            if total > 0:
                if asset == 'USDT':
                    value_usdt = total
                elif asset == 'BUSD':
                    value_usdt = total  # BUSD ≈ USDT
                else:
                    # Obtener precio en USDT
                    try:
                        ticker = client.get_symbol_ticker(symbol=f"{asset}USDT")
                        price_usdt = float(ticker['price'])
                        value_usdt = total * price_usdt
                    except:
                        value_usdt = 0.0
                
                asset_values[asset] = {
                    'amount': total,
                    'value_usdt': value_usdt
                }
                total_value_usdt += value_usdt
        
        # Calcular P&L aproximado (asumiendo que empezaste con $100)
        initial_investment = 100.0  # Ajusta según tu inversión inicial
        pnl_absolute = total_value_usdt - initial_investment
        pnl_percentage = (pnl_absolute / initial_investment * 100) if initial_investment > 0 else 0.0
        
        # Determinar estado de trading
        status = 2 if pnl_absolute > 0 else 0 if pnl_absolute < 0 else 1
        
        # Registrar métricas usando el sistema de métricas
        update_balance("PORTFOLIO", total_value_usdt)
        update_strategy_status("overall", status)
        update_profit_loss("PORTFOLIO", "overall", pnl_absolute)
        
        # Ordenar assets por valor
        sorted_assets = sorted(asset_values.items(), key=lambda x: x[1]['value_usdt'], reverse=True)
        top_assets = []
        
        for asset, data in sorted_assets[:5]:  # Top 5
            if data['value_usdt'] > 1.0:
                top_assets.append({
                    'asset': asset,
                    'amount': data['amount'],
                    'value_usdt': data['value_usdt']
                })
        
        result = {
            "success": True,
            "data": {
                "total_value_usdt": total_value_usdt,
                "pnl_absolute": pnl_absolute,
                "pnl_percentage": pnl_percentage,
                "trading_status": status,
                "status_text": "GANANDO" if status == 2 else "PERDIENDO" if status == 0 else "NEUTRAL",
                "top_assets": top_assets,
                "initial_investment": initial_investment
            }
        }
        
        duration = time.time() - start_time
        record_api_request("POST", "/api/metrics/update-pnl", 200, duration)
        return result
        
    except Exception as e:
        duration = time.time() - start_time
        record_api_request("POST", "/api/metrics/update-pnl", 500, duration)
        return {"error": f"Error calculando P&L: {str(e)}"}

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
        record_api_request("GET", "/api/metrics/metrics/prometheus/trading", 200, duration)
        
        return Response(
            content=metrics_content,
            media_type="text/plain; version=0.0.4; charset=utf-8"
        )
        
    except Exception as e:
        duration = time.time() - start_time
        record_api_request("GET", "/api/metrics/metrics/prometheus/trading", 500, duration)
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