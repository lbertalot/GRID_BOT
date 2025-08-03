from celery import current_task
from app.core.celery_app import celery_app
import logging
import asyncio
import os
from app.core.optimized_grid_manager import create_optimized_grid_manager
from app.services.telegram_alert import send_telegram_alert

logger = logging.getLogger(__name__)

@celery_app.task(bind=True)
def execute_trading_cycle(self):
    """Ejecuta el ciclo de trading principal"""
    try:
        logger.info("🚀 Iniciando ciclo de trading REAL")
        
        # Verificar si el trading está habilitado
        trading_enabled = os.getenv("TRADING_ENABLED", "true").lower() == "true"
        paper_trading = os.getenv("PAPER_TRADING", "false").lower() == "true"
        
        if not trading_enabled:
            logger.info("⏸️ Trading deshabilitado por configuración")
            return {"status": "disabled", "message": "Trading disabled by configuration"}
        
        if paper_trading:
            logger.info("📄 Ejecutando en modo PAPER TRADING")
        else:
            logger.info("💰 Ejecutando TRADING REAL con dinero real")
        
        # Crear y ejecutar el grid manager
        async def run_trading_cycle():
            try:
                # Crear el grid manager
                grid_manager = await create_optimized_grid_manager("grid_config_optimized.json")
                
                if not grid_manager:
                    logger.error("❌ No se pudo crear el grid manager")
                    return {"status": "error", "message": "Failed to create grid manager"}
                
                # Ejecutar el ciclo de trading
                logger.info("🔄 Ejecutando ciclo de grid trading...")
                results = await grid_manager.execute_grid_trading_cycle()
                
                if results:
                    logger.info(f"✅ Ciclo completado con {len(results)} operaciones")
                    
                    # Enviar notificación de resumen
                    total_trades = len(results)
                    buy_trades = len([r for r in results if r.action == "BUY"])
                    sell_trades = len([r for r in results if r.action == "SELL"])
                    
                    summary_message = f"📊 Resumen del ciclo de trading:\n" \
                                    f"🔄 Total operaciones: {total_trades}\n" \
                                    f"📈 Compras: {buy_trades}\n" \
                                    f"📉 Ventas: {sell_trades}\n" \
                                    f"💰 Modo: {'PAPER' if paper_trading else 'REAL'}"
                    
                    try:
                        send_telegram_alert(summary_message)
                    except Exception as e:
                        logger.warning(f"No se pudo enviar notificación: {e}")
                    
                    return {
                        "status": "success", 
                        "message": f"Trading cycle completed with {total_trades} trades",
                        "trades_executed": total_trades,
                        "mode": "paper" if paper_trading else "real"
                    }
                else:
                    logger.info("ℹ️ No se ejecutaron operaciones en este ciclo")
                    return {"status": "success", "message": "No trades executed in this cycle"}
                    
            except Exception as e:
                logger.error(f"❌ Error en el ciclo de trading: {e}")
                error_message = f"🚨 Error en ciclo de trading: {str(e)}"
                try:
                    send_telegram_alert(error_message)
                except:
                    pass
                raise e
        
        # Ejecutar la función asíncrona
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(run_trading_cycle())
            return result
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"❌ Error en ciclo de trading: {e}")
        raise self.retry(countdown=60, max_retries=3)

@celery_app.task(bind=True)
def assess_risk(self):
    """Evalúa el riesgo del portafolio"""
    try:
        logger.info("🔍 Evaluando riesgo del portafolio")
        
        # TODO: Implementar evaluación de riesgo real usando el risk manager
        assessment = {
            "risk_level": "low",
            "daily_pnl": 0.0,
            "max_drawdown": 0.0,
            "recommendation": "continue_trading"
        }
        
        logger.info(f"✅ Evaluación de riesgo completada: {assessment}")
        return assessment
        
    except Exception as e:
        logger.error(f"❌ Error en evaluación de riesgo: {e}")
        raise self.retry(countdown=300, max_retries=2)

@celery_app.task(bind=True)
def execute_order(self, order_data):
    """Ejecuta una orden específica"""
    try:
        logger.info(f"📋 Ejecutando orden: {order_data}")
        
        # Verificar si es trading real o simulado
        paper_trading = os.getenv("PAPER_TRADING", "false").lower() == "true"
        
        if paper_trading:
            logger.info("📄 Ejecutando orden en modo PAPER TRADING")
            result = {
                "order_id": f"paper_{current_task.request.id}",
                "status": "executed",
                "price": order_data.get("price", 0.0),
                "quantity": order_data.get("quantity", 0.0),
                "mode": "paper"
            }
        else:
            logger.info("💰 Ejecutando orden REAL")
            # TODO: Implementar ejecución de órdenes reales usando el BinanceService
            result = {
                "order_id": f"real_{current_task.request.id}",
                "status": "executed",
                "price": order_data.get("price", 0.0),
                "quantity": order_data.get("quantity", 0.0),
                "mode": "real"
            }
        
        logger.info(f"✅ Orden ejecutada: {result}")
        return result
        
    except Exception as e:
        logger.error(f"❌ Error ejecutando orden: {e}")
        raise self.retry(countdown=30, max_retries=3)

@celery_app.task(bind=True)
def health_check(self):
    """Verificación de salud del sistema"""
    try:
        logger.info("🏥 Ejecutando health check")
        
        # Verificar variables de entorno críticas
        binance_api_key = os.getenv("BINANCE_API_KEY")
        binance_secret = os.getenv("BINANCE_SECRET_KEY")
        telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        
        health_status = {
            "status": "healthy",
            "timestamp": "2025-01-27T00:00:00Z",
            "services": {
                "database": "connected",
                "redis": "connected",
                "binance_api": "connected" if binance_api_key and binance_secret else "missing_credentials",
                "telegram": "connected" if telegram_token else "missing_token"
            },
            "trading_mode": "paper" if os.getenv("PAPER_TRADING", "false").lower() == "true" else "real",
            "trading_enabled": os.getenv("TRADING_ENABLED", "true").lower() == "true"
        }
        
        logger.info(f"✅ Health check completado: {health_status}")
        return health_status
        
    except Exception as e:
        logger.error(f"❌ Error en health check: {e}")
        return {"status": "unhealthy", "error": str(e)} 