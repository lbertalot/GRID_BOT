"""
Tareas de trading mejoradas con logging detallado y validaciones robustas
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from celery import shared_task
from app.core.celery_app import celery_app

from app.core.optimized_grid_manager import create_optimized_grid_manager
from app.services.metrics_service import MetricsService
from app.services.fund_manager import fund_manager
from app.services.telegram_alert import send_telegram_alert
from app.services.alert_tasks import notify_consecutive_api_failures
from app.services.binance_async import AsyncBinanceWrapper
from app.services.binance_client_singleton import get_binance_client_singleton
from app.core.circuit_breakers import CircuitBreakers
from app.core.metrics import cycle_phase, cycle_decision_ready, cycle_order_executed
from app.services.market_data_collector import MarketDataCollector
from app.services.ml_engine import MLEngine
from app.services.strategy_selector import StrategySelector, AccountState
from app.core.risk_manager import RiskManager, PositionSizeParams
from app.services.cache import get_async_cache

logger = logging.getLogger(__name__)

# Estado de ciclo (cache en Redis/memoria)
_CACHE = get_async_cache()
_CYCLE_KEY = "cycle:state"
_CYCLE_TTL = 600  # 10 minutos por seguridad

async def _get_cycle_state() -> Dict:
    raw = await _CACHE.get(_CYCLE_KEY)
    if not raw:
        return {"started_at": None, "decision": None}
    import json
    try:
        return json.loads(raw)
    except Exception:
        return {"started_at": None, "decision": None}

async def _set_cycle_state(state: Dict) -> None:
    await _CACHE.set(_CYCLE_KEY, state, ttl_seconds=_CYCLE_TTL)

def _now_ts() -> float:
    return datetime.utcnow().timestamp()

@celery_app.task
def trading_cycle_tick():
    """Tick cada 60s que orquesta un ciclo de 5 minutos (4m evaluación, 1m ejecución)."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def _run():
            state = await _get_cycle_state()
            now = datetime.utcnow()
            start = state.get("started_at")

            # Iniciar ciclo si no hay o si pasaron >=5m
            if not start:
                state = {"started_at": now.isoformat(), "decision": None}
                await _set_cycle_state(state)
                cycle_phase.labels(phase="evaluation").set(_now_ts())
                logger.info("[Cycle] ▶️ Nueva fase: evaluation (t=0m)")
                return

            started_at = datetime.fromisoformat(start)
            elapsed = (now - started_at).total_seconds()

            # 0–240s: evaluación
            if elapsed < 240:
                cycle_phase.labels(phase="evaluation").set(_now_ts())
                # Recolectar datos y actualizar ML/selector
                mdc = MarketDataCollector(ttl_seconds=5)
                ml = MLEngine()
                symbols = ["BTCUSDT","ETHUSDT","BNBUSDT"]
                decisions = state.get("decision") or {}
                # Estado de cuenta (equity, balance, exposición)
                total_equity = 0.0
                available_balance = 0.0
                total_exposure = 0.0
                try:
                    mgr = await create_optimized_grid_manager('grid_config_optimized.json')
                    balances = await mgr.get_asset_balances()
                    summary = await fund_manager.get_trading_summary(balances)
                    total_equity = float(summary.get("total_value_usdt", 0.0) or 0.0)
                    available_balance = float(summary.get("usdt_balance", 0.0) or 0.0)
                    total_exposure = max(0.0, total_equity - available_balance)
                except Exception as e:
                    logger.warning(f"[Cycle] No se pudo obtener estado de cuenta: {e}")
                for sym in symbols:
                    try:
                        price = await mdc.get_price(sym)
                        kl = await mdc.get_klines(sym, interval="1m", limit=60)
                        features = {"price": float(price), "vol": float(kl[-1][5]) if kl else 0.0}
                        # Predicción corta (mock con ml_engine si disponible)
                        # Aquí podríamos usar ml.predict_regime real; mantenemos compatibilidad
                        regime = await ml.compute_features_from_klines(kl) if hasattr(ml, 'compute_features_from_klines') else {"rsi": 50.0}
                        # Selección de estrategia (solo registrar)
                        risk = RiskManager()
                        selector = StrategySelector(risk)
                        account = AccountState(
                            total_equity=total_equity or 300.0,
                            available_balance=available_balance or 50.0,
                            total_exposure=total_exposure if total_equity > 0 else 250.0,
                            daily_pnl=0.0,
                            max_drawdown=0.0,
                            risk_score=0.1
                        )
                        # Usamos un wrapper simple si ml_engine real no da RegimePrediction
                        from app.core.risk_manager import RegimePrediction, MarketRegime
                        rp = RegimePrediction(long_regime=MarketRegime.RANGE, short_regime=MarketRegime.RANGE,
                                              long_conf=0.6, short_conf=0.6)
                        spec = selector.select_strategy(rp, sym, account)
                        decisions[sym] = {
                            "strategy": getattr(spec.strategy_name, 'value', str(spec.strategy_name)),
                            "confidence": float(getattr(spec, 'confidence', 0.6)),
                            "price": float(price)
                        }
                    except Exception as e:
                        logger.warning(f"[Cycle] Eval fallo {sym}: {e}")
                        continue
                state["decision"] = decisions
                await _set_cycle_state(state)
                logger.info("[Cycle] 📝 Decisión parcial registrada (fase evaluación)")
                # Si estamos cerca de 4 minutos, marcar decision_ready
                if 210 <= elapsed < 240 and decisions:
                    for sym, d in decisions.items():
                        cycle_decision_ready.labels(symbol=sym, strategy=d.get("strategy","grid")).set(_now_ts())
                return

            # 240–300s: ejecución
            if elapsed < 300:
                cycle_phase.labels(phase="execution").set(_now_ts())
                decisions = state.get("decision") or {}
                if not decisions:
                    logger.info("[Cycle] Sin decisión lista; se omite ejecución")
                    return
                # Breakers
                try:
                    ck = CircuitBreakers()
                    breakers = asyncio.get_event_loop().run_until_complete(ck.get_breakers_state())
                    if breakers.get('critical_mode') or breakers.get('system_integrity'):
                        logger.warning("[Cycle] Ciclo protegido por breakers activos; sin ejecución")
                        return
                except Exception:
                    pass
                # Ejecutar una orden por símbolo según decisión (enviar tarea Celery fuera del event loop)
                try:
                    execute_trading_cycle.delay()
                    for sym in decisions.keys():
                        cycle_order_executed.labels(symbol=sym, status="sent").set(_now_ts())
                    logger.info("[Cycle] ✅ Ejecución enviada (fase ejecución)")
                except Exception as e:
                    logger.error(f"[Cycle] Error en ejecución: {e}")
                return

            # >=300s: cerrar ciclo y reiniciar
            logger.info("[Cycle] 🔁 Reiniciando ciclo 5m")
            state = {"started_at": now.isoformat(), "decision": None}
            await _set_cycle_state(state)
            cycle_phase.labels(phase="evaluation").set(_now_ts())

        loop.run_until_complete(_run())
        loop.close()
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"❌ trading_cycle_tick error: {e}")
        return {"status": "error", "message": str(e)}

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
        try:
            client_singleton = get_binance_client_singleton()
            check = client_singleton.validate_credentials_and_connectivity()
            if not check.get("net_ok", False):
                logger.error("❌ Conectividad con Binance fallida - abortando ciclo")
                notify_consecutive_api_failures.delay("binance", 1)
                try:
                    asyncio.run(CircuitBreakers().activate_breaker('system_integrity', 'binance_net_fail'))
                except Exception:
                    pass
                return {"status": "error", "message": "Binance net check failed"}
            if not check.get("auth_ok", False):
                logger.error("❌ Credenciales/permiso de Binance inválidos - abortando ciclo")
                notify_consecutive_api_failures.delay("binance_auth", 1)
                try:
                    asyncio.run(CircuitBreakers().activate_breaker('system_integrity', 'binance_auth_fail'))
                except Exception:
                    pass
                return {"status": "error", "message": "Binance auth check failed"}
        except Exception as e:
            logger.error(f"❌ Error validando Binance pre-ciclo: {e}")
            return {"status": "error", "message": str(e)}
        
        # Crear manager de grid trading (usar loop local para evitar nested run)
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            manager = loop.run_until_complete(create_optimized_grid_manager('grid_config_optimized.json'))
        finally:
            asyncio.set_event_loop(None)
            loop.close()
        if not manager:
            logger.error("❌ No se pudo crear el manager de grid trading")
            return {"status": "error", "message": "Manager no disponible"}
        
        # Ejecutar ciclo de trading
        logger.info("🔄 Ejecutando ciclo de grid trading...")
        # Comprobación rápida de conectividad y ejecución
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            try:
                price = loop.run_until_complete(AsyncBinanceWrapper().get_price("BTCUSDT"))
                logger.info(f"🔎 BTC precio pre-ciclo: {price}")
            except Exception as e:
                logger.warning(f"Fallo conectividad Binance pre-ciclo: {e}")
                try:
                    notify_consecutive_api_failures.delay("binance", 3)
                except Exception:
                    pass
            results = loop.run_until_complete(manager.execute_grid_trading_cycle())
        finally:
            asyncio.set_event_loop(None)
            loop.close()
        
        # Analizar resultados
        trades_executed = len([r for r in results if r and r.status == "success"])
        total_trades = len(results)
        
        # Generar resumen con modo según flag PAPER_TRADING
        import os
        mode = "PAPER" if os.getenv("PAPER_TRADING", "false").lower() == "true" else "REAL"
        summary = {
            "timestamp": datetime.now().isoformat(),
            "total_trades": total_trades,
            "trades_executed": trades_executed,
            "success_rate": (trades_executed / total_trades * 100) if total_trades > 0 else 0,
            "mode": mode
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
                send_telegram_alert.delay(message)
                logger.info("✅ Notificación a Telegram encolada")
            except Exception as e:
                logger.error(f"❌ Error encolando notificación: {e}")
        
        # Actualizar métricas
        try:
            metrics_service = MetricsService()
            loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(loop)
                loop.run_until_complete(metrics_service.calculate_portfolio_metrics())
            finally:
                asyncio.set_event_loop(None)
                loop.close()
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
            send_telegram_alert.delay(error_message)
        except Exception:
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
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            manager = loop.run_until_complete(create_optimized_grid_manager('grid_config_optimized.json'))
        finally:
            asyncio.set_event_loop(None)
            loop.close()
        if not manager:
            return {"risk_level": "unknown", "error": "Manager no disponible"}
        
        # Obtener balances
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            balances = loop.run_until_complete(manager.get_asset_balances())
        finally:
            asyncio.set_event_loop(None)
            loop.close()
        
        # Obtener resumen de trading
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            trading_summary = loop.run_until_complete(fund_manager.get_trading_summary(balances))
        finally:
            asyncio.set_event_loop(None)
            loop.close()
        
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
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            loop.run_until_complete(metrics_service.calculate_portfolio_metrics())
        finally:
            asyncio.set_event_loop(None)
            loop.close()
        
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
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            manager = loop.run_until_complete(create_optimized_grid_manager('grid_config_optimized.json'))
        finally:
            asyncio.set_event_loop(None)
            loop.close()
        if not manager:
            return {"status": "unhealthy", "error": "Manager no disponible"}
        
        # Verificar balances
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            balances = loop.run_until_complete(manager.get_asset_balances())
        finally:
            asyncio.set_event_loop(None)
            loop.close()
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