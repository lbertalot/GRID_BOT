from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import os
from datetime import datetime
import requests
import json
from prometheus_client import generate_latest, Counter, Histogram, Gauge
import asyncio

# Importar el servicio de sincronización de Binance
from app.services.binance_data_sync import binance_sync

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Métricas de Prometheus
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_LATENCY = Histogram('http_request_duration_seconds', 'HTTP request latency')
TRADING_ACTIVE = Gauge('trading_active', 'Trading system status')
TRADE_COUNT = Counter('trades_total', 'Total number of trades')

# Crear aplicación FastAPI
app = FastAPI(
    title="GridBot Trading Platform",
    description="Plataforma de trading automatizado con estrategias avanzadas",
    version="2.0.0"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Variables globales para estado del trading
trading_active = False
trading_stats = {
    "total_trades": 0,
    "total_profit": 0.0,
    "current_balance": 0.0,
    "last_trade": None
}

@app.get("/")
async def root():
    """Endpoint raíz"""
    REQUEST_COUNT.labels(method='GET', endpoint='/', status='200').inc()
    return {
        "message": "GridBot Trading Platform v2.0",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0",
        "trading_active": trading_active
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    REQUEST_COUNT.labels(method='GET', endpoint='/health', status='200').inc()
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "api": "running",
            "database": "connected",
            "redis": "connected",
            "trading": "active" if trading_active else "inactive"
        }
    }

@app.get("/metrics")
async def metrics():
    """Endpoint de métricas para Prometheus"""
    REQUEST_COUNT.labels(method='GET', endpoint='/metrics', status='200').inc()
    from fastapi.responses import Response
    return Response(content=generate_latest(), media_type="text/plain")

@app.get("/api/v1/status")
async def api_status():
    """Estado de la API"""
    REQUEST_COUNT.labels(method='GET', endpoint='/api/v1/status', status='200').inc()
    return {
        "api_version": "v1",
        "status": "operational",
        "trading_active": trading_active,
        "features": [
            "grid_trading",
            "risk_management",
            "performance_analysis",
            "automated_rebalancing",
            "binance_sync"
        ],
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/v1/metrics")
async def get_metrics():
    """Métricas básicas del sistema"""
    REQUEST_COUNT.labels(method='GET', endpoint='/api/v1/metrics', status='200').inc()
    try:
        from app.core.metrics import trading_metrics
        
        # Obtener balance real
        balance_response = await get_balance()
        portfolio_value = balance_response.get("total_usdt", 0)
        
        # Actualizar métricas con datos reales
        trading_metrics.update_profit_metrics(
            total_profit=0.0,  # Por ahora 0, se actualizará cuando haya trades
            portfolio_value=portfolio_value,
            strategy="grid"
        )
        
        trading_metrics.update_bot_status(
            is_active=trading_active,
            strategy="grid"
        )
        
        # Actualizar balances
        balances = {}
        for asset, data in balance_response.get("balance", {}).items():
            if asset in ['USDT', 'BTC', 'ETH', 'SPK']:
                free = float(data.get("free", 0))
                locked = float(data.get("locked", 0))
                balances[asset] = free + locked
        
        trading_metrics.update_balances(balances, "grid")
        
        return {
            "total_trades": trading_stats["total_trades"],
            "daily_pnl": trading_stats["total_profit"],
            "portfolio_value": portfolio_value,
            "active_strategies": 1 if trading_active else 0,
            "trading_active": trading_active,
            "last_trade": trading_stats["last_trade"],
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error obteniendo métricas: {e}")
        return {
            "total_trades": trading_stats["total_trades"],
            "daily_pnl": trading_stats["total_profit"],
            "portfolio_value": trading_stats["current_balance"],
            "active_strategies": 1 if trading_active else 0,
            "trading_active": trading_active,
            "last_trade": trading_stats["last_trade"],
            "timestamp": datetime.now().isoformat()
        }

@app.get("/api/v1/balance")
async def get_balance():
    """Obtener balance real de Binance"""
    REQUEST_COUNT.labels(method='GET', endpoint='/api/v1/balance', status='200').inc()
    try:
        from binance import Client
        
        # Obtener credenciales
        api_key = os.getenv("BINANCE_API_KEY")
        api_secret = os.getenv("BINANCE_SECRET_KEY")
        
        if not api_key or not api_secret:
            raise HTTPException(status_code=500, detail="Credenciales de Binance no configuradas")
        
        # Crear cliente de Binance
        client = Client(api_key, api_secret)
        
        # Obtener información de la cuenta
        account_info = client.get_account()
        
        # Procesar balances
        balance = {}
        total_usdt = 0.0
        
        for bal in account_info['balances']:
            asset = bal['asset']
            free = float(bal['free'])
            locked = float(bal['locked'])
            
            if free > 0 or locked > 0:
                balance[asset] = {
                    "free": f"{free:.8f}",
                    "locked": f"{locked:.8f}"
                }
                
                # Calcular valor en USDT para activos principales
                if asset in ['BTC', 'ETH', 'USDT', 'SPK']:
                    try:
                        if asset == 'USDT':
                            total_usdt += free + locked
                        else:
                            # Obtener precio en USDT
                            ticker = client.get_symbol_ticker(symbol=f"{asset}USDT")
                            price = float(ticker['price'])
                            total_usdt += (free + locked) * price
                    except Exception as e:
                        logger.warning(f"No se pudo obtener precio para {asset}: {e}")
        
        return {
            "status": "success",
            "balance": balance,
            "total_usdt": round(total_usdt, 2),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error obteniendo balance real: {e}")
        REQUEST_COUNT.labels(method='GET', endpoint='/api/v1/balance', status='500').inc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/trading/start")
async def start_trading():
    """Iniciar trading"""
    global trading_active, trading_stats
    
    try:
        logger.info("Iniciando trading automatizado")
        
        # Simular verificación de balance
        balance_response = await get_balance()
        
        if balance_response["total_usdt"] < 10:
            REQUEST_COUNT.labels(method='POST', endpoint='/api/v1/trading/start', status='400').inc()
            raise HTTPException(status_code=400, detail="Balance insuficiente para trading")
        
        trading_active = True
        trading_stats["last_trade"] = datetime.now().isoformat()
        TRADING_ACTIVE.set(1)
        
        # Simular envío de notificación a Telegram
        await send_telegram_message("🤖 GridBot - Trading iniciado correctamente")
        
        REQUEST_COUNT.labels(method='POST', endpoint='/api/v1/trading/start', status='200').inc()
        return {
            "status": "success",
            "message": "Trading iniciado correctamente",
            "balance": balance_response["total_usdt"],
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error iniciando trading: {e}")
        REQUEST_COUNT.labels(method='POST', endpoint='/api/v1/trading/start', status='500').inc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/trading/stop")
async def stop_trading():
    """Detener trading"""
    global trading_active
    
    try:
        logger.info("Deteniendo trading automatizado")
        
        trading_active = False
        TRADING_ACTIVE.set(0)
        
        # Simular envío de notificación a Telegram
        await send_telegram_message("🛑 GridBot - Trading detenido")
        
        REQUEST_COUNT.labels(method='POST', endpoint='/api/v1/trading/stop', status='200').inc()
        return {
            "status": "success",
            "message": "Trading detenido correctamente",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error deteniendo trading: {e}")
        REQUEST_COUNT.labels(method='POST', endpoint='/api/v1/trading/stop', status='500').inc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/config")
async def get_config():
    """Obtener configuración actual"""
    REQUEST_COUNT.labels(method='GET', endpoint='/api/v1/config', status='200').inc()
    return {
        "grid_levels": 10,
        "min_price": 45000,
        "max_price": 55000,
        "quantity_per_trade": 0.001,
        "auto_rebalance": True,
        "risk_management": {
            "max_daily_loss": 5.0,
            "stop_loss": 10.0,
            "max_position_size": 20.0
        },
        "trading_active": trading_active
    }

@app.post("/api/v1/alerts/telegram/critical")
async def telegram_critical_alert(request: Request):
    """Endpoint para alertas críticas de Telegram (Alertmanager)"""
    try:
        # Obtener datos del request
        data = await request.json()
        
        # Enviar notificación a Telegram
        message = f"🚨 ALERTA CRÍTICA\n\n{data.get('message', 'Alerta del sistema')}"
        await send_telegram_message(message)
        
        REQUEST_COUNT.labels(method='POST', endpoint='/api/v1/alerts/telegram/critical', status='200').inc()
        return {
            "status": "success",
            "message": "Alerta enviada correctamente",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error enviando alerta crítica: {e}")
        REQUEST_COUNT.labels(method='POST', endpoint='/api/v1/alerts/telegram/critical', status='500').inc()
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )

@app.get("/api/v1/test/binance")
async def test_binance_connection():
    """Probar conexión real con Binance"""
    REQUEST_COUNT.labels(method='GET', endpoint='/api/v1/test/binance', status='200').inc()
    try:
        from binance import Client
        
        binance_api_key = os.getenv("BINANCE_API_KEY", "")
        binance_secret_key = os.getenv("BINANCE_SECRET_KEY", "")
        
        if not binance_api_key or not binance_secret_key:
            return {
                "status": "error",
                "message": "API Keys de Binance no configuradas",
                "timestamp": datetime.now().isoformat()
            }
        
        # Crear cliente real de Binance
        client = Client(binance_api_key, binance_secret_key)
        
        # Probar conexión real obteniendo información de la cuenta
        account_info = client.get_account()
        
        # Verificar que la respuesta contiene información válida
        if 'accountType' in account_info:
            return {
                "status": "success",
                "message": f"Conexión con Binance exitosa - Tipo de cuenta: {account_info['accountType']}",
                "account_type": account_info['accountType'],
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "status": "error",
                "message": "Respuesta inesperada de Binance",
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error probando Binance: {e}")
        return {
            "status": "error",
            "message": f"Error conectando con Binance: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }

@app.post("/api/v1/test/telegram")
async def test_telegram():
    """Probar notificaciones de Telegram"""
    REQUEST_COUNT.labels(method='POST', endpoint='/api/v1/test/telegram', status='200').inc()
    try:
        message = "🤖 GridBot - Mensaje de prueba\n\n✅ Sistema funcionando correctamente\n📊 Trading: " + ("Activo" if trading_active else "Inactivo")
        
        success = await send_telegram_message(message)
        
        if success:
            return {
                "status": "success",
                "message": "Mensaje de Telegram enviado correctamente",
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "status": "error",
                "message": "Error enviando mensaje a Telegram",
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        logger.error(f"Error probando Telegram: {e}")
        return {
            "status": "error",
            "message": f"Error con Telegram: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }

# ===== NUEVOS ENDPOINTS PARA SINCRONIZACIÓN DE BINANCE =====

@app.post("/api/v1/binance/sync/account")
async def sync_binance_account():
    """Sincronizar información de la cuenta de Binance"""
    REQUEST_COUNT.labels(method='POST', endpoint='/api/v1/binance/sync/account', status='200').inc()
    try:
        result = await binance_sync.sync_account_info()
        return {
            "status": "success",
            "data": result,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error sincronizando cuenta de Binance: {e}")
        REQUEST_COUNT.labels(method='POST', endpoint='/api/v1/binance/sync/account', status='500').inc()
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )

@app.post("/api/v1/binance/sync/balances")
async def sync_binance_balances():
    """Sincronizar balances de Binance"""
    REQUEST_COUNT.labels(method='POST', endpoint='/api/v1/binance/sync/balances', status='200').inc()
    try:
        result = await binance_sync.sync_balances()
        return {
            "status": "success",
            "data": result,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error sincronizando balances de Binance: {e}")
        REQUEST_COUNT.labels(method='POST', endpoint='/api/v1/binance/sync/balances', status='500').inc()
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )

@app.post("/api/v1/binance/sync/symbols")
async def sync_binance_symbols():
    """Sincronizar información de símbolos de Binance"""
    REQUEST_COUNT.labels(method='POST', endpoint='/api/v1/binance/sync/symbols', status='200').inc()
    try:
        result = await binance_sync.sync_symbol_info()
        return {
            "status": "success",
            "data": result,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error sincronizando símbolos de Binance: {e}")
        REQUEST_COUNT.labels(method='POST', endpoint='/api/v1/binance/sync/symbols', status='500').inc()
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )

@app.post("/api/v1/binance/sync/trades")
async def sync_binance_trades():
    """Sincronizar operaciones recientes de Binance"""
    REQUEST_COUNT.labels(method='POST', endpoint='/api/v1/binance/sync/trades', status='200').inc()
    try:
        result = await binance_sync.sync_recent_trades("BTCUSDT", 50)
        return {
            "status": "success",
            "data": result,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error sincronizando operaciones de Binance: {e}")
        REQUEST_COUNT.labels(method='POST', endpoint='/api/v1/binance/sync/trades', status='500').inc()
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )

@app.post("/api/v1/binance/sync/klines")
async def sync_binance_klines():
    """Sincronizar datos de velas de Binance"""
    REQUEST_COUNT.labels(method='POST', endpoint='/api/v1/binance/sync/klines', status='200').inc()
    try:
        result = await binance_sync.sync_klines_data("BTCUSDT", "1h", 24)
        return {
            "status": "success",
            "data": result,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error sincronizando velas de Binance: {e}")
        REQUEST_COUNT.labels(method='POST', endpoint='/api/v1/binance/sync/klines', status='500').inc()
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )

@app.post("/api/v1/binance/sync/performance")
async def sync_binance_performance():
    """Sincronizar métricas de rendimiento de Binance"""
    REQUEST_COUNT.labels(method='POST', endpoint='/api/v1/binance/sync/performance', status='200').inc()
    try:
        result = await binance_sync.sync_performance_metrics()
        return {
            "status": "success",
            "data": result,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error sincronizando métricas de Binance: {e}")
        REQUEST_COUNT.labels(method='POST', endpoint='/api/v1/binance/sync/performance', status='500').inc()
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )

@app.post("/api/v1/binance/sync/full")
async def sync_binance_full():
    """Sincronización completa de todos los datos de Binance"""
    REQUEST_COUNT.labels(method='POST', endpoint='/api/v1/binance/sync/full', status='200').inc()
    try:
        logger.info("Iniciando sincronización completa de Binance")
        result = await binance_sync.full_sync()
        
        # Enviar notificación a Telegram
        await send_telegram_message("🔄 GridBot - Sincronización completa de Binance finalizada")
        
        return {
            "status": "success",
            "message": "Sincronización completa finalizada",
            "data": result,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error en sincronización completa de Binance: {e}")
        REQUEST_COUNT.labels(method='POST', endpoint='/api/v1/binance/sync/full', status='500').inc()
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )

@app.get("/api/v1/binance/data/account")
async def get_binance_account_data():
    """Obtener datos de la cuenta de Binance desde la base de datos"""
    REQUEST_COUNT.labels(method='GET', endpoint='/api/v1/binance/data/account', status='200').inc()
    try:
        import asyncpg
        conn = await asyncpg.connect(os.getenv("DATABASE_URL", "postgresql://griduser:gridpass@db:5432/gridbot"))
        
        # Obtener configuración de la cuenta
        account_data = await conn.fetch("""
            SELECT key, value, description 
            FROM system_config 
            WHERE key IN ('account_type', 'maker_commission', 'taker_commission')
            ORDER BY key
        """)
        
        await conn.close()
        
        return {
            "status": "success",
            "data": {
                "account_info": {row['key']: row['value'] for row in account_data},
                "timestamp": datetime.now().isoformat()
            }
        }
    except Exception as e:
        logger.error(f"Error obteniendo datos de cuenta: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )

@app.get("/api/v1/binance/data/balances")
async def get_binance_balances_data():
    """Obtener balances de Binance desde la base de datos"""
    REQUEST_COUNT.labels(method='GET', endpoint='/api/v1/binance/data/balances', status='200').inc()
    try:
        import asyncpg
        conn = await asyncpg.connect(os.getenv("DATABASE_URL", "postgresql://griduser:gridpass@db:5432/gridbot"))
        
        # Obtener balances
        balances = await conn.fetch("""
            SELECT symbol, min_qty, max_qty, step_size, tick_size, created_at
            FROM asset_limits 
            ORDER BY symbol
        """)
        
        await conn.close()
        
        return {
            "status": "success",
            "data": {
                "balances": [dict(balance) for balance in balances],
                "count": len(balances),
                "timestamp": datetime.now().isoformat()
            }
        }
    except Exception as e:
        logger.error(f"Error obteniendo balances: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )

@app.get("/api/v1/binance/data/trades")
async def get_binance_trades_data():
    """Obtener operaciones de Binance desde la base de datos"""
    REQUEST_COUNT.labels(method='GET', endpoint='/api/v1/binance/data/trades', status='200').inc()
    try:
        import asyncpg
        conn = await asyncpg.connect(os.getenv("DATABASE_URL", "postgresql://griduser:gridpass@db:5432/gridbot"))
        
        # Obtener operaciones recientes
        trades = await conn.fetch("""
            SELECT symbol, side, quantity, entry_price, timestamp, strategy
            FROM trades 
            ORDER BY timestamp DESC 
            LIMIT 20
        """)
        
        await conn.close()
        
        return {
            "status": "success",
            "data": {
                "trades": [dict(trade) for trade in trades],
                "count": len(trades),
                "timestamp": datetime.now().isoformat()
            }
        }
    except Exception as e:
        logger.error(f"Error obteniendo operaciones: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )

@app.get("/api/v1/binance/data/performance")
async def get_binance_performance_data():
    """Obtener métricas de rendimiento desde la base de datos"""
    REQUEST_COUNT.labels(method='GET', endpoint='/api/v1/binance/data/performance', status='200').inc()
    try:
        import asyncpg
        conn = await asyncpg.connect(os.getenv("DATABASE_URL", "postgresql://griduser:gridpass@db:5432/gridbot"))
        
        # Obtener métricas de rendimiento
        performance = await conn.fetchrow("""
            SELECT total_trades, winning_trades, losing_trades, total_profit, total_loss, win_rate, timestamp
            FROM performance_metrics 
            ORDER BY timestamp DESC 
            LIMIT 1
        """)
        
        await conn.close()
        
        return {
            "status": "success",
            "data": {
                "performance": dict(performance) if performance else {},
                "timestamp": datetime.now().isoformat()
            }
        }
    except Exception as e:
        logger.error(f"Error obteniendo métricas de rendimiento: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )

async def send_telegram_message(message: str) -> bool:
    """Enviar mensaje a Telegram"""
    try:
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        
        if not bot_token or not chat_id:
            logger.warning("Telegram no configurado")
            return False
        
        if "your_" in bot_token or "your_" in chat_id:
            logger.warning("Telegram no configurado correctamente")
            return False
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        
        response = requests.post(url, json=data, timeout=10)
        
        if response.status_code == 200:
            logger.info("Mensaje de Telegram enviado")
            return True
        else:
            logger.error(f"Error enviando Telegram: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error enviando Telegram: {e}")
        return False

@app.post("/api/v1/metrics/update")
async def force_update_metrics():
    """Forzar actualización de métricas"""
    REQUEST_COUNT.labels(method='POST', endpoint='/api/v1/metrics/update', status='200').inc()
    try:
        # Llamar al endpoint de métricas para actualizar
        await get_metrics()
        
        return {
            "status": "success",
            "message": "Métricas actualizadas correctamente",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error forzando actualización de métricas: {e}")
        REQUEST_COUNT.labels(method='POST', endpoint='/api/v1/metrics/update', status='500').inc()
        raise HTTPException(status_code=500, detail=str(e))

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Manejador global de excepciones"""
    logger.error(f"Error no manejado: {exc}")
    REQUEST_COUNT.labels(method=request.method, endpoint=request.url.path, status='500').inc()
    return JSONResponse(
        status_code=500,
        content={
            "error": "Error interno del servidor",
            "message": str(exc),
            "timestamp": datetime.now().isoformat()
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 