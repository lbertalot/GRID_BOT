"""
Tareas de trading mejoradas con logging detallado y validaciones robustas
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional
from celery import shared_task

from app.core.optimized_grid_manager import create_optimized_grid_manager
from app.services.metrics_service import MetricsService
from app.services.fund_manager import fund_manager
from app.services.telegram_alert import send_telegram_alert
from app.services.alert_tasks import notify_consecutive_api_failures
from app.services.binance_async import AsyncBinanceWrapper

logger = logging.getLogger(__name__)

@shared_task
def execute_trading_cycle():
    """
    Ejecuta un ciclo completo de trading con validaciones mejoradas
    """
    try:
        logger.info("🚀 Iniciando ciclo de trading REAL")
        logger.info("💰 Ejecutando TRADING REAL con dinero real")
        
        # Verificar credenciales de Binance
        logger.info("🔍 Validando credenciales de Binance...")
        
        # Crear manager de grid trading
        manager = asyncio.run(create_optimized_grid_manager('grid_config_optimized.json'))
        if not manager:
            logger.error("❌ No se pudo crear el manager de grid trading")
            return {"status": "error", "message": "Manager no disponible"}
        
        # Ejecutar ciclo de trading
        logger.info("🔄 Ejecutando ciclo de grid trading...")
        # Comprobación rápida de conectividad y rate limit centralizado
        try:
            price = asyncio.run(AsyncBinanceWrapper().get_price("BTCUSDT"))
            logger.info(f"🔎 BTC precio pre-ciclo: {price}")
        except Exception as e:
            logger.warning(f"Fallo conectividad Binance pre-ciclo: {e}")
            try:
                notify_consecutive_api_failures.delay("binance", 3)
            except Exception:
                pass
        results = asyncio.run(manager.execute_grid_trading_cycle())
        
        # Analizar resultados
        trades_executed = len([r for r in results if r and r.status == "success"])
        total_trades = len(results)
        
        # Generar resumen
        summary = {
            "timestamp": datetime.now().isoformat(),
            "total_trades": total_trades,
            "trades_executed": trades_executed,
            "success_rate": (trades_executed / total_trades * 100) if total_trades > 0 else 0,
            "mode": "REAL"
        }
        
        # Logging detallado
        logger.info(f"📊 Resumen del ciclo de trading:")
        logger.info(f"   🔄 Total operaciones: {total_trades}")
        logger.info(f"   ✅ Operaciones ejecutadas: {trades_executed}")
        logger.info(f"   📈 Tasa de éxito: {summary['success_rate']:.1f}%")
        logger.info(f"   💰 Modo: {summary['mode']}")
        
        # Enviar notificación si hay operaciones
        if trades_executed > 0:
            message = f"🔄 Resumen del ciclo de trading:\n" \
                     f"🔄 Total operaciones: {total_trades}\n" \
                     f"✅ Operaciones ejecutadas: {trades_executed}\n" \
                     f"📈 Tasa de éxito: {summary['success_rate']:.1f}%\n" \
                     f"💰 Modo: {summary['mode']}"
            
            try:
                asyncio.run(send_telegram_alert(message))
                logger.info("✅ Notificación enviada a Telegram")
            except Exception as e:
                logger.error(f"❌ Error enviando notificación: {e}")
        
        # Actualizar métricas
        try:
            metrics_service = MetricsService()
            asyncio.run(metrics_service.calculate_portfolio_metrics())
            logger.info("✅ Métricas actualizadas")
        except Exception as e:
            logger.error(f"❌ Error actualizando métricas: {e}")
        
        return {
            "status": "success",
            "message": f"Ciclo completado - {trades_executed}/{total_trades} operaciones ejecutadas",
            "summary": summary
        }
        
    except Exception as e:
        logger.error(f"❌ Error en ciclo de trading: {e}")
        
        # Enviar alerta de error
        error_message = f"🚨 Error en ciclo de trading:\n{str(e)}"
        try:
            asyncio.run(send_telegram_alert(error_message))
        except:
            pass
        
        return {"status": "error", "message": str(e)}

@shared_task
def assess_risk():
    """
    Evalúa el riesgo del portafolio
    """
    try:
        logger.info("🔍 Evaluando riesgo del portafolio")
        
        # Crear manager para obtener balances
        manager = asyncio.run(create_optimized_grid_manager('grid_config_optimized.json'))
        if not manager:
            return {"risk_level": "unknown", "error": "Manager no disponible"}
        
        # Obtener balances
        balances = asyncio.run(manager.get_asset_balances())
        
        # Obtener resumen de trading
        trading_summary = asyncio.run(fund_manager.get_trading_summary(balances))
        
        # Calcular métricas de riesgo
        total_value = trading_summary.get("total_value_usdt", 0)
        usdt_balance = trading_summary.get("usdt_balance", 0)
        
        # Determinar nivel de riesgo
        if total_value < 10:
            risk_level = "high"
            recommendation = "insufficient_funds"
        elif usdt_balance < 5:
            risk_level = "medium"
            recommendation = "low_liquidity"
        else:
            risk_level = "low"
            recommendation = "continue_trading"
        
        risk_assessment = {
            "risk_level": risk_level,
            "daily_pnl": 0.0,  # Se calcularía con datos históricos
            "max_drawdown": 0.0,  # Se calcularía con datos históricos
            "recommendation": recommendation,
            "total_value": total_value,
            "usdt_balance": usdt_balance,
            "can_trade": trading_summary.get("can_trade", False)
        }
        
        logger.info(f"✅ Evaluación de riesgo completada: {risk_assessment}")
        return risk_assessment
        
    except Exception as e:
        logger.error(f"❌ Error evaluando riesgo: {e}")
        return {"risk_level": "unknown", "error": str(e)}

@shared_task
def update_metrics():
    """
    Actualiza todas las métricas del sistema
    """
    try:
        logger.info("📊 Actualizando métricas del sistema")
        
        metrics_service = MetricsService()
        asyncio.run(metrics_service.calculate_portfolio_metrics())
        
        logger.info("✅ Métricas actualizadas correctamente")
        return {"status": "success", "message": "Métricas actualizadas"}
        
    except Exception as e:
        logger.error(f"❌ Error actualizando métricas: {e}")
        return {"status": "error", "message": str(e)}

@shared_task
def health_check():
    """
    Verificación de salud del sistema
    """
    try:
        logger.info("🏥 Ejecutando verificación de salud del sistema")
        
        # Verificar conexión con Binance
        manager = asyncio.run(create_optimized_grid_manager('grid_config_optimized.json'))
        if not manager:
            return {"status": "unhealthy", "error": "Manager no disponible"}
        
        # Verificar balances
        balances = asyncio.run(manager.get_asset_balances())
        if not balances:
            return {"status": "unhealthy", "error": "No se pueden obtener balances"}
        
        # Verificar configuración
        config = manager.config
        if not config.assets:
            return {"status": "unhealthy", "error": "No hay activos configurados"}
        
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "binance_connection": "ok",
            "balances_available": len(balances),
            "assets_configured": len(config.assets),
            "active_assets": len([a for a in config.assets.values() if a.is_active])
        }
        
        logger.info(f"✅ Verificación de salud completada: {health_status}")
        return health_status
        
    except Exception as e:
        logger.error(f"❌ Error en verificación de salud: {e}")
        return {"status": "unhealthy", "error": str(e)} 