from prometheus_client import Counter, Gauge, Histogram, Summary, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response
import time
from typing import Dict, Any

# ============================================================================
# MÉTRICAS DE TRADING
# ============================================================================

# Contadores de órdenes
orders_executed = Counter(
    'gridbot_orders_total', 
    'Total orders executed', 
    ['symbol', 'side', 'type', 'strategy']
)

orders_failed = Counter(
    'gridbot_orders_failed_total', 
    'Total failed orders', 
    ['symbol', 'side', 'type', 'error_type']
)

# Volumen de trading
trading_volume = Counter(
    'gridbot_volume_total', 
    'Total trading volume', 
    ['symbol', 'side']
)

# Ganancias/pérdidas
profit_loss = Gauge(
    'gridbot_profit_loss', 
    'Current profit/loss', 
    ['symbol', 'strategy']
)

# ============================================================================
# MÉTRICAS DE SISTEMA
# ============================================================================

# Estado del sistema
api_requests_total = Counter(
    'gridbot_api_requests_total',
    'Total API requests',
    ['method', 'endpoint', 'status']
)

api_request_duration = Histogram(
    'gridbot_api_request_duration_seconds',
    'API request duration in seconds',
    ['method', 'endpoint']
)

# Uso de recursos
memory_usage = Gauge(
    'gridbot_memory_usage_bytes',
    'Memory usage in bytes'
)

cpu_usage = Gauge(
    'gridbot_cpu_usage_percent',
    'CPU usage percentage'
)

# ============================================================================
# MÉTRICAS DE BINANCE API
# ============================================================================

binance_api_calls = Counter(
    'gridbot_binance_api_calls_total',
    'Total Binance API calls',
    ['endpoint', 'status']
)

binance_api_latency = Histogram(
    'gridbot_binance_api_latency_seconds',
    'Binance API latency in seconds',
    ['endpoint']
)

binance_connection_status = Gauge(
    'gridbot_binance_connection_status',
    'Binance connection status (1=connected, 0=disconnected)'
)

# ============================================================================
# MÉTRICAS DE ESTRATEGIAS
# ============================================================================

active_strategies = Gauge(
    'gridbot_active_strategies',
    'Number of active strategies',
    ['strategy_type']
)

strategy_performance = Gauge(
    'gridbot_strategy_performance',
    'Strategy performance percentage',
    ['strategy_type', 'symbol']
)

grid_levels_active = Gauge(
    'gridbot_grid_levels_active',
    'Number of active grid levels',
    ['symbol', 'strategy_id']
)

# ============================================================================
# MÉTRICAS DE BALANCE
# ============================================================================

balance_total = Gauge(
    'gridbot_balance_total',
    'Total balance',
    ['asset']
)

balance_locked = Gauge(
    'gridbot_balance_locked',
    'Locked balance',
    ['asset']
)

# ============================================================================
# FUNCIONES UTILITARIAS
# ============================================================================

def record_order_execution(symbol: str, side: str, order_type: str, strategy: str, quantity: float, price: float):
    """Registra una orden ejecutada exitosamente"""
    try:
        orders_executed.labels(symbol=symbol, side=side, type=order_type, strategy=strategy).inc()
        
        # Calcular volumen
        volume = quantity * price
        trading_volume.labels(symbol=symbol, side=side).inc(volume)
        
        # Actualizar balance estimado
        if side == "BUY":
            # Compra: reducir USDT, aumentar asset
            balance_total.labels(asset="USDT").dec(volume)
            balance_total.labels(asset=symbol.replace("USDT", "")).inc(quantity)
        else:
            # Venta: aumentar USDT, reducir asset
            balance_total.labels(asset="USDT").inc(volume)
            balance_total.labels(asset=symbol.replace("USDT", "")).dec(quantity)
        
        print(f"📊 Métrica registrada: Orden {side} {quantity} {symbol} @ ${price}")
    except Exception as e:
        print(f"❌ Error registrando métrica de orden: {e}")

def record_order_failure(symbol: str, side: str, order_type: str, error_type: str):
    """Registra una orden fallida"""
    try:
        orders_failed.labels(symbol=symbol, side=side, type=order_type, error_type=error_type).inc()
        print(f"📊 Métrica registrada: Orden fallida {side} {symbol} - {error_type}")
    except Exception as e:
        print(f"❌ Error registrando métrica de orden fallida: {e}")

def record_api_request(method: str, endpoint: str, status: int, duration: float):
    """Registra una petición API"""
    try:
        api_requests_total.labels(method=method, endpoint=endpoint, status=status).inc()
        api_request_duration.labels(method=method, endpoint=endpoint).observe(duration)
    except Exception as e:
        print(f"❌ Error registrando métrica de API: {e}")

def record_binance_api_call(endpoint: str, status: str, duration: float):
    """Registra una llamada a la API de Binance"""
    try:
        binance_api_calls.labels(endpoint=endpoint, status=status).inc()
        binance_api_latency.labels(endpoint=endpoint).observe(duration)
    except Exception as e:
        print(f"❌ Error registrando métrica de Binance: {e}")

def update_balance(asset: str, free: float, locked: float):
    """Actualiza métricas de balance"""
    try:
        balance_total.labels(asset=asset).set(free)
        balance_locked.labels(asset=asset).set(locked)
    except Exception as e:
        print(f"❌ Error actualizando métrica de balance: {e}")

def update_strategy_status(strategy_type: str, active_count: int):
    """Actualiza el estado de las estrategias"""
    try:
        active_strategies.labels(strategy_type=strategy_type).set(active_count)
    except Exception as e:
        print(f"❌ Error actualizando métrica de estrategia: {e}")

def update_profit_loss(symbol: str, strategy: str, pnl: float):
    """Actualiza ganancias/pérdidas"""
    try:
        profit_loss.labels(symbol=symbol, strategy=strategy).set(pnl)
    except Exception as e:
        print(f"❌ Error actualizando métrica de P&L: {e}")

# ============================================================================
# ENDPOINTS DE MÉTRICAS
# ============================================================================

def get_metrics() -> Response:
    """Endpoint para obtener métricas de Prometheus"""
    try:
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST
        )
    except Exception as e:
        print(f"❌ Error generando métricas: {e}")
        return Response(
            content="",
            media_type=CONTENT_TYPE_LATEST
        )

def get_trading_metrics() -> Dict[str, Any]:
    """Endpoint para obtener métricas específicas de trading"""
    return {
        "orders_executed": {
            "total": 0,  # Valor por defecto
            "by_symbol": {}
        },
        "trading_volume": {
            "total": 0,  # Valor por defecto
            "by_symbol": {}
        },
        "profit_loss": {
            "total": 0,  # Valor por defecto
            "by_strategy": {}
        }
    }

def get_binance_metrics() -> Dict[str, Any]:
    """Endpoint para obtener métricas de Binance API"""
    return {
        "api_calls": {
            "total": 0,  # Valor por defecto
            "by_endpoint": {}
        },
        "latency": {
            "average": 0,  # Valor por defecto
            "by_endpoint": {}
        },
        "connection_status": 1  # Valor por defecto (conectado)
    }

def get_strategy_metrics() -> Dict[str, Any]:
    """Endpoint para obtener métricas de estrategias"""
    return {
        "active_strategies": {
            "total": 0,  # Valor por defecto
            "by_type": {}
        },
        "performance": {
            "by_strategy": {}
        },
        "grid_levels": {
            "total": 0,  # Valor por defecto
            "by_symbol": {}
        }
    }

# ============================================================================
# MIDDLEWARE SIMPLIFICADO PARA MÉTRICAS
# ============================================================================

class MetricsMiddleware:
    """Middleware simplificado para registrar métricas automáticamente"""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            method = scope["method"]
            path = scope["path"]
            
            # Registrar inicio de petición
            start_time = time.time()
            
            # Wrapper para capturar la respuesta
            async def send_wrapper(message):
                if message["type"] == "http.response.start":
                    # Calcular duración
                    duration = time.time() - start_time
                    status = message.get("status", 500)
                    
                    # Registrar métrica de forma segura
                    try:
                        record_api_request(method, path, status, duration)
                    except Exception as e:
                        print(f"❌ Error en middleware de métricas: {e}")
                
                await send(message)
            
            # Continuar con la petición
            await self.app(scope, receive, send_wrapper)
        else:
            await self.app(scope, receive, send) 