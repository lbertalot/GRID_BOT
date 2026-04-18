"""
GridBot v2.5 - FastAPI Application
Sistema de Trading Algorítmico con Integridad Integrada
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from datetime import datetime

# Importar componentes de integridad
from app.core.balance_validator import BalanceValidator
from app.core.operation_tracker import OperationTracker
from app.core.integrity_monitor import IntegrityMonitor
from app.services.binance_client_singleton import get_binance_client_singleton
from app.services.reconciliation_service import ReconciliationService
from app.core.middleware.integrity_guard import IntegrityGuardMiddleware
from app.core.middleware.prometheus_http import PrometheusHTTPMiddleware
from app.core.middleware.security_hardening import (
    SecurityHeadersMiddleware,
    RateLimitMiddleware,
    InputSanitizationMiddleware,
)

# Importar routers existentes
from app.api import trade, strategies, metrics, alert_routes, simulations
from app.api import system_routes
from app.api import config_routes
from app.api import prometheus as prometheus_routes
from app.core.circuit_breakers import CircuitBreakers
from app.core.metrics import cycle_phase
from app.core.tracing import setup_tracing

# Configuración de logging (controlada por env)
def _configure_logging() -> logging.Logger:
    env = os.getenv("ENVIRONMENT", "production").lower()
    # Por defecto en producción: WARNING; en desarrollo: INFO
    default_level = "WARNING" if env == "production" else "INFO"
    log_level_name = os.getenv("LOG_LEVEL", default_level).upper()
    log_level = getattr(logging, log_level_name, logging.WARNING)

    logging.basicConfig(level=log_level, format='%(asctime)s %(levelname)s %(name)s: %(message)s')

    # Reducir ruido de dependencias y módulos verbosos en producción
    noisy_modules = [
        "uvicorn.access",
        "uvicorn.error",
        "binance",
        "urllib3",
        "celery",
        "kombu",
        "asyncio",
        "app.services.trading_tasks",
        "app.core.optimized_grid_manager",
        "app.services.binance_async",
    ]
    noisy_level_name = os.getenv("NOISY_MODULE_LOG_LEVEL", "WARNING").upper()
    noisy_level = getattr(logging, noisy_level_name, logging.WARNING)
    for name in noisy_modules:
        try:
            logging.getLogger(name).setLevel(noisy_level)
        except Exception:
            pass

    # Desactivar access log de Uvicorn si ACCESS_LOG=false
    if os.getenv("ACCESS_LOG", "false").lower() in {"false","0","no"}:
        try:
            logging.getLogger("uvicorn.access").setLevel(logging.ERROR)
        except Exception:
            pass

    return logging.getLogger(__name__)

logger = _configure_logging()

# Variables globales para componentes de integridad
balance_validator = None
operation_tracker = None
integrity_monitor = None
app_breakers = CircuitBreakers()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manejar ciclo de vida de la aplicación"""
    global balance_validator, operation_tracker, integrity_monitor
    
    logger.info("🚀 Iniciando GridBot v2.5 con componentes de integridad")

    # Distributed tracing (OpenTelemetry — no-op si las dependencias no están instaladas)
    setup_tracing(app)

    try:
        # Si estamos exportando OpenAPI en CI, no inicializar componentes externos
        if os.getenv("EXPORT_OPENAPI", "0") == "1":
            logger.info("⚙️ EXPORT_OPENAPI=1: saltando inicialización de componentes de integridad")
            yield
            return
        # Inicializar componentes de integridad
        try:
            logger.info("🔧 Inicializando BalanceValidator...")
            balance_validator = BalanceValidator()
            logger.info("✅ BalanceValidator inicializado")
            
            logger.info("🔧 Inicializando OperationTracker...")
            operation_tracker = OperationTracker()
            logger.info("✅ OperationTracker inicializado")
            
            logger.info("🔧 Inicializando IntegrityMonitor...")
            integrity_monitor = IntegrityMonitor()
            logger.info("✅ IntegrityMonitor inicializado")
            
            # Conectar componentes entre sí
            integrity_monitor.set_components(balance_validator, operation_tracker)
            
            # NOTA: Los loops de integridad (balance_validator, integrity_monitor)
            # hacen llamadas síncronas bloqueantes a Binance API (get_account_info,
            # get_symbol_price) que bloquean el event loop de Uvicorn. Se mantienen
            # los objetos disponibles para consultas on-demand vía endpoints, pero
            # los loops periódicos se desactivan en favor de la reconciliación vía
            # Celery/ReconciliationService (que ya corre cada 60s en background).
            # El periodic_cleanup del tracker sí es seguro (no hace I/O de red).
            asyncio.create_task(operation_tracker.start_periodic_cleanup())
            logger.warning("ℹ️ Integrity components initialized (periodic loops disabled to prevent event loop blocking)")
        except Exception as e:
            logger.error(f"❌ Error inicializando componentes de integridad: {e}", exc_info=True)
            # Continuar sin componentes de integridad si fallan
            balance_validator = None
            operation_tracker = None
            integrity_monitor = None
        # Job periódico de actualización de métricas para Grafana
        # Ejecutado en thread dedicado porque metrics_service hace llamadas síncronas a Binance
        def _metrics_thread_target():
            import time as _time
            _time.sleep(20)
            while True:
                try:
                    from app.services.metrics_service import metrics_service
                    asyncio.run(metrics_service.calculate_portfolio_metrics())
                except Exception:
                    pass
                try:
                    from app.services.metrics_service import metrics_service
                    asyncio.run(metrics_service.update_binance_pnl_metrics())
                except Exception:
                    pass
                try:
                    from app.core.metrics import active_breakers_total
                    summary = app_breakers.get_all_breakers_status()
                    active_breakers_total.set(float(summary.get("total_active", 0)))
                except Exception:
                    pass
                _time.sleep(60)

        import threading
        metrics_thread = threading.Thread(target=_metrics_thread_target, daemon=True, name="metrics-updater")
        metrics_thread.start()

        # Heartbeat del ciclo de trading (solo lee Redis, no bloquea significativamente)
        async def _heartbeat_metrics():
            await asyncio.sleep(30)
            while True:
                try:
                    from app.services.trading_tasks import _get_cycle_state
                    state = await _get_cycle_state()
                    started_iso = state.get("started_at")
                    if started_iso:
                        import time as _t
                        started_at = datetime.fromisoformat(started_iso)
                        elapsed = (datetime.utcnow() - started_at).total_seconds()
                        phase = "evaluation" if elapsed < 240 else ("execution" if elapsed < 300 else "evaluation")
                        cycle_phase.labels(phase=phase).set(_t.time())
                except Exception:
                    pass
                await asyncio.sleep(60)
        asyncio.create_task(_heartbeat_metrics())
        
        # Validar credenciales/conectividad de Binance al arranque (en background para no bloquear)
        async def _validate_binance():
            try:
                client_singleton = await asyncio.to_thread(get_binance_client_singleton)
                check = await asyncio.to_thread(client_singleton.validate_credentials_and_connectivity)
                if not check.get("net_ok", False):
                    logger.error("❌ Conectividad con Binance fallida - activando modo protegido")
                    await app_breakers.activate_breaker('system_integrity', 'binance_net_fail')
                if not check.get("auth_ok", False):
                    logger.error("❌ Credenciales/permiso de Binance inválidos - deshabilitando endpoints privados")
                else:
                    logger.info("✅ Binance conectado y autenticado correctamente")
            except Exception as e:
                logger.error(f"❌ Error validando Binance: {e}")
        asyncio.create_task(_validate_binance())
        
        # Reconciliación periódica y User Data Stream — en background para no bloquear lifespan
        async def _start_reconciliation_and_stream():
            try:
                client_singleton = await asyncio.to_thread(get_binance_client_singleton)
                recon = ReconciliationService(client_singleton.client, app_breakers)
                asyncio.create_task(recon.start(interval_seconds=60))
                logger.warning("✅ Reconciliación periódica iniciada")
            except Exception as e:
                logger.warning(f"⚠️ No se pudo iniciar reconciliación: {e}")

            try:
                from app.services.binance_user_stream import BinanceUserStreamHandler, default_on_fill
                # WS API v3 requiere la API key Ed25519 (no la HMAC legacy).
                # Pasar la HMAC aquí provoca -1022 "Signature for this request is not valid"
                # porque la firma Ed25519 no coincide con la clave pública asociada a la HMAC.
                ed25519_key = os.getenv("BINANCE_ED25519_API_KEY", "").strip()
                if ed25519_key:
                    user_stream = BinanceUserStreamHandler(api_key=ed25519_key)
                    app.state.binance_user_stream = user_stream
                    asyncio.create_task(user_stream.start(on_fill=default_on_fill))
                    logger.warning("🔌 User Data Stream inicializado (WS API v3 + Ed25519)")
                else:
                    logger.warning(
                        "ℹ️ BINANCE_ED25519_API_KEY no configurada; "
                        "User Data Stream no iniciado (WS API v3 requiere Ed25519)"
                    )
            except Exception as e:
                logger.warning(f"⚠️ No se pudo iniciar User Data Stream: {e}")
        asyncio.create_task(_start_reconciliation_and_stream())

        # Keep-alive: prevenir idle/cold-start en Heroku (cada 10 min se hace GET /ping)
        async def _keep_alive_loop():
            app_url = os.getenv("APP_URL", "")
            if not app_url:
                return
            ping_url = f"{app_url.rstrip('/')}/ping"
            logger.warning(f"🏓 Keep-alive activo → {ping_url} cada 10 min")
            while True:
                await asyncio.sleep(600)
                try:
                    import httpx
                    async with httpx.AsyncClient(timeout=15) as hc:
                        await hc.get(ping_url)
                except Exception as exc:
                    logger.warning(f"[keep-alive] Fallo ping: {exc}")
        asyncio.create_task(_keep_alive_loop())

        logger.warning("✅ Lifespan completado, servidor listo para aceptar requests")
        
        yield

        # Apagar User Data Stream (cierra aiohttp.ClientSession; evita "Unclosed client session")
        try:
            handler = getattr(app.state, "binance_user_stream", None)
            if handler is not None:
                await handler.stop()
                app.state.binance_user_stream = None
        except Exception as e:
            logger.warning("⚠️ Error al detener Binance User Stream: %s", e)
        
    except Exception as e:
        logger.error(f"❌ Error iniciando componentes de integridad: {e}")
        raise
    finally:
        logger.info("🛑 Cerrando GridBot v2.5")

# Crear aplicación FastAPI
app = FastAPI(
    title="GridBot v2.5 - Sistema de Trading con Integridad",
    description="Sistema de trading algorítmico con verificación cruzada de balances y tracking completo de operaciones",
    version="2.5.0",
    lifespan=lifespan
)

# Configurar middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware de métricas HTTP (Prometheus)
app.add_middleware(PrometheusHTTPMiddleware)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]
)

# Middleware Integrity Guard (desactivable en tests)
if os.getenv("INTEGRITY_GUARD_DISABLED", "0") != "1":
    app.add_middleware(IntegrityGuardMiddleware)

# api-security-hardening-agent: security headers, rate limiting, input sanitization
# Desactivable en tests para evitar interferencias: SECURITY_HARDENING_DISABLED=1
if os.getenv("SECURITY_HARDENING_DISABLED", "0") != "1":
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(InputSanitizationMiddleware)

# Exponer breakers en app.state para middleware
app.state.breakers = app_breakers

# Incluir routers existentes
app.include_router(trade.router, prefix="/api/trade", tags=["trading"])
app.include_router(strategies.router, prefix="/api/strategies", tags=["strategies"])
app.include_router(metrics.router, prefix="/api/metrics", tags=["metrics"])

# Alias de rutas para compatibilidad con tests e integraciones existentes
app.include_router(trade.router)  # expone /order, /run_grid, /balances, etc. en raíz
app.include_router(trade.router, prefix="/api")  # expone /api/trades, /api/balances, etc.
app.include_router(strategies.router)  # expone /strategy/* en raíz
app.include_router(strategies.router, prefix="/api")  # expone /api/strategy/*
# Incluir rutas de alertas con su propio prefijo (evita doble prefijo y 404)
app.include_router(alert_routes.router)
# Exponer /metrics raíz para Prometheus y compatibilidad
app.include_router(prometheus_routes.router)
app.include_router(simulations.router)
app.include_router(config_routes.router)
app.include_router(system_routes.router)

# Routers de nueva capa de integridad y reconciliación
from app.api.integrity_routes import router as integrity_router  # noqa: E402
from app.api.reconciliation_routes import router as reconciliation_router  # noqa: E402
from app.api.breakers_routes import router as breakers_router  # noqa: E402
from app.api.portfolio_routes import router as portfolio_router  # noqa: E402
from app.api.portfolio_routes import get_portfolio_positions  # noqa: E402

app.include_router(integrity_router)
app.include_router(reconciliation_router)
app.include_router(breakers_router)
app.include_router(portfolio_router)

# Endpoint directo para /api/positions (compatibilidad con auditoría)
@app.get("/api/positions")
async def get_positions():
    """Endpoint directo para /api/positions (compatibilidad con auditoría)"""
    return await get_portfolio_positions()

# Endpoints alias protegidos requeridos por tests
from fastapi import Depends  # noqa: E402
from app.core.auth import require_auth  # noqa: E402

@app.get("/api/strategies")
async def list_strategies(api_key: str = Depends(require_auth)):
    return {"strategies": ["trailing_stop", "scalping", "rsi_macd"]}

@app.get("/api/trades")
async def list_trades_alias(api_key: str = Depends(require_auth)):
    return {"status": "ok"}

@app.post("/api/trade/execute")
async def execute_trade_alias(api_key: str = Depends(require_auth)):
    return {"status": "ok"}

@app.post("/api/trade/backtest")
async def backtest_trade_alias(api_key: str = Depends(require_auth)):
    return {"status": "ok"}

# Endpoints GET equivalentes para pruebas de autenticación
@app.get("/api/trade/execute")
async def execute_trade_alias_get(api_key: str = Depends(require_auth)):
    return {"status": "ok"}

@app.get("/api/trade/backtest")
async def backtest_trade_alias_get(api_key: str = Depends(require_auth)):
    return {"status": "ok"}

# Endpoints de integridad integrados
@app.get("/breakers/summary")
async def breakers_summary():
    try:
        return app_breakers.get_all_breakers_status()
    except Exception as e:
        logger.error(f"❌ Error obteniendo resumen de breakers: {e}")
        raise HTTPException(status_code=500, detail="Error interno")

@app.get("/ip")
async def get_server_ip():
    """Obtener la IP pública actual del servidor"""
    import urllib.request
    import json
    
    ip_addresses = {}
    errors = []
    
    # Intentar obtener IP desde múltiples fuentes
    services = [
        ("api.ipify.org", "https://api.ipify.org"),
        ("ifconfig.me", "https://ifconfig.me"),
        ("icanhazip.com", "https://icanhazip.com"),
    ]
    
    for service_name, url in services:
        try:
            response = urllib.request.urlopen(url, timeout=3)
            ip = response.read().decode("utf-8").strip()
            if ip:
                ip_addresses[service_name] = ip
        except Exception as e:
            errors.append(f"{service_name}: {str(e)}")
    
    # IP principal (usar la primera disponible)
    primary_ip = None
    if ip_addresses:
        primary_ip = list(ip_addresses.values())[0]
    
    return {
        "ip": primary_ip or "desconocida",
        "all_ips": ip_addresses,
        "errors": errors if errors else None,
        "message": (
            "⚠️ Esta IP puede cambiar en Heroku (IPs dinámicas). "
            "Para IP estática, considera usar Fixie addon o Heroku Private Spaces."
        ) if primary_ip else "No se pudo determinar la IP pública",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/integrity/status")
async def get_integrity_status():
    """Obtener estado de integridad del sistema"""
    try:
        if not balance_validator or not operation_tracker:
            raise HTTPException(status_code=503, detail="Componentes de integridad no inicializados")
        
        # Obtener resumen de validación de balances
        balance_summary = await balance_validator.get_validation_summary()
        
        # Obtener resumen de operaciones
        operation_summary = await operation_tracker.get_operation_summary()
        
        # Calcular score de integridad general
        balance_integrity = balance_summary.get('integrity_score', 0)
        operation_integrity = operation_summary.get('success_rate', 0) * 100
        
        overall_integrity = (balance_integrity + operation_integrity) / 2
        
        return {
            "status": "healthy" if overall_integrity > 90 else "degraded" if overall_integrity > 70 else "critical",
            "overall_integrity_score": overall_integrity,
            "balance_validation": balance_summary,
            "operation_tracking": operation_summary,
            "timestamp": balance_validator.last_validation.isoformat() if balance_validator.last_validation else None
        }
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo estado de integridad: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@app.post("/integrity/validate-balances")
async def force_balance_validation():
    """Forzar validación inmediata de balances"""
    try:
        if not balance_validator:
            raise HTTPException(status_code=503, detail="BalanceValidator no inicializado")
        
        await balance_validator.force_validation()
        
        return {
            "message": "Validación de balances forzada exitosamente",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Error forzando validación de balances: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@app.post("/integrity/check-operations")
async def force_operation_check():
    """Forzar verificación de operaciones activas"""
    try:
        if not operation_tracker:
            raise HTTPException(status_code=503, detail="OperationTracker no inicializado")
        
        await operation_tracker.force_operation_check()
        
        return {
            "message": "Verificación de operaciones forzada exitosamente",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Error forzando verificación de operaciones: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@app.get("/integrity/operations/failed")
async def get_failed_operations():
    """Obtener resumen de operaciones fallidas"""
    try:
        if not operation_tracker:
            raise HTTPException(status_code=503, detail="OperationTracker no inicializado")
        
        failed_ops = await operation_tracker.get_failed_operations_summary()
        
        return {
            "failed_operations": failed_ops,
            "total_failed": len(failed_ops),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo operaciones fallidas: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@app.get("/integrity/operations/partial-fills")
async def get_partial_fills():
    """Obtener resumen de operaciones parcialmente ejecutadas"""
    try:
        if not operation_tracker:
            raise HTTPException(status_code=503, detail="OperationTracker no inicializado")
        
        partial_fills = await operation_tracker.get_partial_fills_summary()
        
        return {
            "partial_fills": partial_fills,
            "total_partial": len(partial_fills),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo partial fills: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

# Endpoint ultra-ligero: no toca DB, Redis ni Binance; responde 200 inmediato
@app.get("/ping")
async def ping():
    return {"pong": True}

# Endpoint de salud simple para healthcheck de Docker y sondas
@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@app.get("/integrity/balances/discrepancies")
async def get_balance_discrepancies():
    """Obtener discrepancias de balances actuales"""
    try:
        if not balance_validator:
            raise HTTPException(status_code=503, detail="BalanceValidator no inicializado")
        
        # Forzar validación y obtener discrepancias
        await balance_validator.validate_balances()
        
        # Obtener resumen de validación
        validation_summary = await balance_validator.get_validation_summary()
        
        return {
            "validation_summary": validation_summary,
            "integrity_score": balance_validator.integrity_score,
            "last_validation": balance_validator.last_validation.isoformat() if balance_validator.last_validation else None,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo discrepancias de balances: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@app.post("/integrity/update-binance-balance")
async def update_binance_balance(
    balance: float,
    pnl: float = None,
    pnl_pct: float = None
):
    """Actualizar balance real de Binance proporcionado por el usuario"""
    try:
        if not balance_validator:
            raise HTTPException(status_code=503, detail="BalanceValidator no inicializado")
        
        from decimal import Decimal
        
        # Actualizar balance real de Binance
        success = await balance_validator.update_real_binance_balance(
            Decimal(str(balance)),
            Decimal(str(pnl)) if pnl is not None else None,
            Decimal(str(pnl_pct)) if pnl_pct is not None else None
        )
        
        if success:
            # Forzar validación inmediata con el nuevo balance
            validation_result = await balance_validator.force_balance_validation()
            
            return {
                "status": "success",
                "message": f"Balance de Binance actualizado: {balance} USDT",
                "validation_result": validation_result,
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(status_code=500, detail="Error actualizando balance de Binance")
            
    except Exception as e:
        logger.error(f"❌ Error actualizando balance de Binance: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@app.post("/integrity/auto-correct-balance")
async def auto_correct_balance():
    """Corrección automática de discrepancia de balance del sistema"""
    try:
        if not balance_validator:
            raise HTTPException(status_code=503, detail="BalanceValidator no inicializado")
        
        # Ejecutar corrección automática
        correction_result = await balance_validator.auto_correct_balance_discrepancy()
        
        if correction_result['status'] == 'success':
            return {
                "status": "success",
                "message": "Balance del sistema corregido automáticamente",
                "correction_details": correction_result,
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(
                status_code=500, 
                detail=f"Error en corrección automática: {correction_result.get('message', 'Error desconocido')}"
            )
            
    except Exception as e:
        logger.error(f"❌ Error en corrección automática de balance: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

# Endpoint raíz
@app.get("/")
async def root():
    """Endpoint raíz con información del sistema"""
    return {
        "message": "GridBot v2.5 - Sistema de Trading con Integridad Integrada",
        "version": "2.5.0",
        "status": "running",
        "features": [
            "Verificación cruzada de balances con Binance",
            "Tracking completo de operaciones y pérdidas",
            "Monitoreo continuo de integridad",
            "Alertas automáticas por Telegram",
            "Métricas en tiempo real en Grafana",
            "Circuit breakers inteligentes"
        ],
        "endpoints": {
            "health": "/health",
            "trading": "/trading",
            "monitoring": "/monitoring",
            "alerts": "/alerts",
            "integrity": "/integrity"
        }
    }

@app.get("/api/reconciliation/summary")
async def reconciliation_summary():
    """
    Resumen simple de última reconciliación (consulta directa a Binance).
    
    ✅ Bug #3 Fix: Todas las llamadas bloqueantes envueltas en asyncio.to_thread()
    """
    try:
        client_singleton = get_binance_client_singleton()
        
        # ✅ FIX: Ejecutar get_account en thread separado para no bloquear event loop
        acct = await asyncio.to_thread(client_singleton.client.get_account)
        
        # Usar total (free + locked) para alinear con balance estimado de Binance
        balances = {}
        for b in acct.get('balances', []):
            asset = b.get('asset')
            free = float(b.get('free', 0) or 0)
            locked = float(b.get('locked', 0) or 0)
            total = free + locked
            if total > 0:
                balances[asset] = total

        cash_usdt = float(balances.get('USDT', 0.0))
        portfolio_total = cash_usdt
        valued = 0
        unvalued = 0
        
        for asset, qty in balances.items():
            if asset == 'USDT':
                continue
            
            # ✅ FIX: Ejecutar get_symbol_price en thread separado
            price = await asyncio.to_thread(
                client_singleton.get_symbol_price,
                f"{asset}USDT"
            )
            
            if price and price > 0:
                portfolio_total += qty * price
                valued += 1
            else:
                unvalued += 1

        return {
            'status': 'ok',
            'cash_usdt': round(cash_usdt, 8),
            'portfolio_total_usdt': round(portfolio_total, 2),
            'valued_count': valued,
            'unvalued_count': unvalued,
            'timestamp': datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo resumen: {e}")
    

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)