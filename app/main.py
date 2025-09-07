"""
GridBot v2.5 - FastAPI Application
Sistema de Trading Algorítmico con Integridad Integrada
"""

import asyncio
import logging
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

# Importar routers existentes
from app.api import trade, strategies, metrics, alert_routes, simulations
from app.api import prometheus as prometheus_routes
from app.core.circuit_breakers import CircuitBreakers

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    
    try:
        # Inicializar componentes de integridad
        balance_validator = BalanceValidator()
        operation_tracker = OperationTracker()
        integrity_monitor = IntegrityMonitor()
        
        # Conectar componentes entre sí
        integrity_monitor.set_components(balance_validator, operation_tracker)
        
        # Iniciar monitoreo de integridad en background
        asyncio.create_task(balance_validator.start_validation_loop())
        asyncio.create_task(operation_tracker.start_periodic_cleanup())
        asyncio.create_task(integrity_monitor.start_monitoring())
        
        # Validar credenciales/conectividad de Binance al arranque
        try:
            client_singleton = get_binance_client_singleton()
            check = client_singleton.validate_credentials_and_connectivity()
            if not check.get("net_ok", False):
                logger.error("❌ Conectividad con Binance fallida - activando modo protegido")
                await app_breakers.activate_breaker('system_integrity', 'binance_net_fail')
            if not check.get("auth_ok", False):
                logger.error("❌ Credenciales/permiso de Binance inválidos - deshabilitando endpoints privados")
                await app_breakers.activate_breaker('system_integrity', 'binance_auth_fail')
            # Reconciliación periódica
            try:
                recon = ReconciliationService(client_singleton.client, app_breakers)
                asyncio.create_task(recon.start(interval_seconds=60))
            except Exception:
                pass

        except Exception as e:
            logger.error(f"❌ Error validando Binance al arranque: {e}")

        logger.info("✅ Componentes de integridad iniciados correctamente")
        
        yield
        
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

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]
)

# Incluir routers existentes
app.include_router(trade.router, prefix="/api/trade", tags=["trading"])
app.include_router(strategies.router, prefix="/api/strategies", tags=["strategies"])
app.include_router(metrics.router, prefix="/api/metrics", tags=["metrics"])
# Incluir rutas de alertas con su propio prefijo (evita doble prefijo y 404)
app.include_router(alert_routes.router)
# Exponer /metrics raíz para Prometheus y compatibilidad
app.include_router(prometheus_routes.router)
app.include_router(simulations.router)

# Endpoints de integridad integrados
@app.get("/breakers/summary")
async def breakers_summary():
    try:
        return app_breakers.get_all_breakers_status()
    except Exception as e:
        logger.error(f"❌ Error obteniendo resumen de breakers: {e}")
        raise HTTPException(status_code=500, detail="Error interno")

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

@app.get("/api/reconciliation/summary")
async def reconciliation_summary():
    """Resumen simple de última reconciliación (consulta directa a Binance)."""
    try:
        client_singleton = get_binance_client_singleton()
        acct = client_singleton.client.get_account()
        ext_balances = {b['asset']: float(b['free']) for b in acct.get('balances', [])}
        return {
            'status': 'ok',
            'usdt': ext_balances.get('USDT', 0.0),
            'timestamp': datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo resumen: {e}")
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)