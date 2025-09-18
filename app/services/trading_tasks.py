"""
Tareas de trading mejoradas con logging detallado y validaciones robustas
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from celery import shared_task
from app.core.celery_app import celery_app
import os

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
from app.core.metrics import dust_assets_count, dust_value_usd, dust_swept_usd_total, last_dust_sweep_timestamp

logger = logging.getLogger(__name__)

# Estado de ciclo (cache en Redis/memoria)
_CACHE = get_async_cache()
_CYCLE_KEY = "cycle:state"
_CYCLE_TTL = 600  # 10 minutos por seguridad

# Parámetros de decisión/ejecución
MIN_DECISION_CONFIDENCE = 0.55
MIN_NOTIONAL_USDT = 10.5
SAFE_MIN_USDT = 20.0  # Guarda dura para evitar operar con liquidez insuficiente
BALANCES_CACHE_KEY = "balances:last"
BALANCES_TTL = 300

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

async def _get_cached_balances() -> Optional[Dict]:
    raw = await _CACHE.get(BALANCES_CACHE_KEY)
    if not raw:
        return None
    import json
    try:
        return json.loads(raw)
    except Exception:
        return None

async def _set_cached_balances(balances: Dict) -> None:
    await _CACHE.set(BALANCES_CACHE_KEY, balances, ttl_seconds=BALANCES_TTL)

async def _fetch_balances_with_retry(manager, retries: int = 3, delay_seconds: float = 1.0) -> Dict:
    last_err: Optional[Exception] = None
    for i in range(retries):
        try:
            b = await manager.get_asset_balances()
            if isinstance(b, dict) and len(b) > 0:
                await _set_cached_balances(b)
                return b
        except Exception as e:
            last_err = e
            logger.warning(f"[Cycle] Fallo obteniendo balances (intento {i+1}/{retries}): {e}")
        await asyncio.sleep(delay_seconds)
    # Fallback a caché
    cached = await _get_cached_balances()
    if cached:
        logger.warning("[Cycle] Usando balances en caché por fallos consecutivos")
        return cached
    if last_err:
        raise last_err
    return {}

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
                # Universo temporal restringido para ejecuciones seguras
                symbols = ["ETHUSDT"]
                decisions = state.get("decision") or {}
                # Estado de cuenta (equity, balance, exposición)
                total_equity = 0.0
                available_balance = 0.0
                total_exposure = 0.0
                try:
                    mgr = await create_optimized_grid_manager('grid_config_optimized.json')
                    balances = await _fetch_balances_with_retry(mgr, retries=3, delay_seconds=1.5)
                    summary = await fund_manager.get_trading_summary(balances)
                    total_equity = float(summary.get("total_value_usdt", 0.0) or 0.0)
                    available_balance = float(summary.get("usdt_balance", 0.0) or 0.0)
                    total_exposure = max(0.0, total_equity - available_balance)
                except Exception as e:
                    logger.warning(f"[Cycle] No se pudo obtener estado de cuenta: {e}")
                # Verificar breakers antes de preparar decisiones
                breakers_block = False
                try:
                    ck = CircuitBreakers()
                    breakers = ck.get_all_breakers_status() if hasattr(ck, 'get_all_breakers_status') else {}
                    if breakers.get('critical_mode') or ('system_integrity' in breakers.get('active_breakers', [])):
                        breakers_block = True
                except Exception:
                    breakers_block = False

                # Si estamos en PAPER_TRADING, usar balance del sistema de paper en lugar de Binance
                try:
                    paper_mode = os.getenv("PAPER_TRADING", "false").lower() == "true"
                    if paper_mode:
                        from app.core.paper_trading import get_paper_portfolio_summary
                        paper_summary = get_paper_portfolio_summary()
                        available_balance = float(paper_summary.get("current_balance", available_balance) or available_balance)
                except Exception:
                    pass

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
                        conf = float(getattr(spec, 'confidence', 0.6))
                        # Requisitos de readiness: confianza, liquidez mínima y breakers inactivos
                        # En PAPER_TRADING relajamos el mínimo a MIN_NOTIONAL
                        min_cash = (MIN_NOTIONAL_USDT if (os.getenv("PAPER_TRADING", "false").lower() == "true") else max(MIN_NOTIONAL_USDT, SAFE_MIN_USDT))
                        ready = (conf >= MIN_DECISION_CONFIDENCE) and (available_balance >= min_cash) and (not breakers_block)
                        decisions[sym] = {
                            "strategy": getattr(spec.strategy_name, 'value', str(spec.strategy_name)),
                            "confidence": conf,
                            "price": float(price),
                            "ready": ready
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
                        if d.get("ready"):
                            cycle_decision_ready.labels(symbol=sym, strategy=d.get("strategy","grid")).set(_now_ts())
                return

            # 240–300s: ejecución
            if elapsed < 300:
                cycle_phase.labels(phase="execution").set(_now_ts())
                decisions = state.get("decision") or {}
                # Considerar listo si hay decisión y breakers inactivos; en tests se fuerza con PYTEST_CURRENT_TEST
                ready_symbols = [s for s, d in (decisions or {}).items() if d and d.get("ready")]
                if not ready_symbols:
                    logger.info("[Cycle] Sin decisión lista (ready=false); se omite ejecución en minuto 5")
                    return
                # Breakers
                try:
                    ck = CircuitBreakers()
                    breakers = ck.get_all_breakers_status() if hasattr(ck, 'get_all_breakers_status') else {}
                    if breakers.get('critical_mode') or ('system_integrity' in breakers.get('active_breakers', [])):
                        logger.warning("[Cycle] Ciclo protegido por breakers activos; sin ejecución")
                        return
                except Exception:
                    pass
                # Ejecutar una orden por símbolo según decisión (enviar tarea Celery fuera del event loop)
                try:
                    execute_trading_cycle.delay()
                    for sym in ready_symbols:
                        cycle_order_executed.labels(symbol=sym, status="sent").set(_now_ts())
                    logger.info(f"[Cycle] ✅ Ejecución enviada (fase ejecución) symbols={ready_symbols}")
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
            # Auto-recovery: si pasó el check, intentar desactivar breaker de integridad de red
            try:
                asyncio.run(CircuitBreakers().deactivate_breaker('system_integrity'))
            except Exception:
                pass
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

        # Guardas: evitar operar si liquidez es insuficiente o breakers activos
        try:
            balances = {}
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                balances = loop.run_until_complete(manager.get_asset_balances())
            finally:
                asyncio.set_event_loop(None)
                loop.close()
            summary = fund_manager.get_trading_summary_sync(balances) if hasattr(fund_manager, 'get_trading_summary_sync') else None
            if not summary:
                # fallback async
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    summary = loop.run_until_complete(fund_manager.get_trading_summary(balances))
                finally:
                    asyncio.set_event_loop(None)
                    loop.close()
            available_usdt = float((summary or {}).get("usdt_balance", 0.0) or 0.0)
            if available_usdt < SAFE_MIN_USDT:
                logger.warning(f"[Cycle] Liquidez insuficiente USDT={available_usdt:.2f} < {SAFE_MIN_USDT}, omitiendo ejecución")
                return {"status": "skipped", "message": "Insufficient USDT"}
            ck = CircuitBreakers()
            bs = ck.get_all_breakers_status() if hasattr(ck, 'get_all_breakers_status') else {}
            if bs.get('critical_mode') or ('system_integrity' in bs.get('active_breakers', [])):
                logger.warning("[Cycle] Breakers activos; omitiendo ejecución")
                return {"status": "skipped", "message": "Breakers active"}
        except Exception as e:
            logger.warning(f"[Cycle] No se pudo evaluar guardas previas: {e}")

        # Limitar universo a ETHUSDT temporalmente y ajustar grilla a entorno actual
        try:
            for sym, asset in manager.config.assets.items():
                asset.is_active = (sym == "ETHUSDT")
            # Ajuste dinámico de grilla basado en precio actual (±1% del spot)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                spot = loop.run_until_complete(AsyncBinanceWrapper().get_price("ETHUSDT"))
            finally:
                asyncio.set_event_loop(None)
                loop.close()
            if spot and spot > 0:
                asset = manager.config.assets.get("ETHUSDT")
                if asset:
                    low = float(spot) * 0.99
                    high = float(spot) * 1.01
                    asset.min_price = low
                    asset.max_price = high
                    # Generar 3 niveles equidistantes dentro del rango
                    step = (high - low) / 3.0
                    asset.grids = [round(low + step * i, 8) for i in range(1, 4)]
        except Exception as e:
            logger.warning(f"[Cycle] No se pudo ajustar universo/grilla dinámica: {e}")
        
        # Ejecutar ciclo de trading
        logger.info("🔄 Ejecutando ciclo de grid trading...")
        # Comprobación rápida de conectividad y ejecución
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            try:
                price = loop.run_until_complete(AsyncBinanceWrapper().get_price("ETHUSDT"))
                logger.info(f"🔎 ETH precio pre-ciclo: {price}")
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


@shared_task
def dust_sweep(dry_run: bool = True) -> dict:
    """
    Barre saldos pequeños (< 1 USDT) según política:
    - Si existe par ASSETUSDT y supera MIN_NOTIONAL: vender MARKET a USDT
    - Si no, intentar Convert/Dust to BNB (no implementado por API pública): registrar recomendación
    - Respetar whitelist y límites
    """
    try:
        logger.info("🧹 Iniciando barrido de polvo (dry_run=%s)", dry_run)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        from app.services.binance_client_singleton import get_binance_client_singleton
        client_singleton = get_binance_client_singleton()

        async def _run() -> dict:
            # Obtener balances actuales (dict asset -> qty)
            balances = client_singleton.get_balances() or {}
            # Precios helper
            def px(sym: str) -> float:
                return client_singleton.get_symbol_price(sym)

            whitelist = set(os.getenv("DUST_WHITELIST", "").split(",")) if os.getenv("DUST_WHITELIST") else set()
            min_notional = float(os.getenv("DUST_MIN_NOTIONAL", "10"))
            dust_threshold = float(os.getenv("DUST_THRESHOLD_USD", "1"))

            items = []
            total_dust = 0.0
            for asset, qty in balances.items():
                if asset in ("USDT", "BUSD", "USDC", "TUSD", "FDUSD", "DAI"):
                    continue
                if asset in whitelist:
                    continue
                price = 1.0 if asset == "USD" else px(f"{asset}USDT") or 0.0
                value = float(qty) * float(price)
                if 0.0 < value < dust_threshold:
                    items.append({"asset": asset, "qty": float(qty), "price": float(price), "value": value})
                    total_dust += value

            dust_assets_count.set(len(items))
            dust_value_usd.set(total_dust)

            actions = []
            swept_total = 0.0
            for it in items:
                symbol = f"{it['asset']}USDT"
                if it["value"] >= min_notional:
                    action = {"asset": it["asset"], "symbol": symbol, "qty": it["qty"], "type": "SELL_MARKET"}
                    actions.append({**action, "executed": not dry_run})
                    if not dry_run:
                        try:
                            client_singleton.create_order(symbol=symbol, side="SELL", order_type="MARKET", quantity=str(it["qty"]))
                            swept_total += it["value"]
                        except Exception as e:
                            logger.warning(f"Dust sell fallo {symbol}: {e}")
                else:
                    actions.append({"asset": it["asset"], "symbol": symbol, "qty": it["qty"], "type": "RECOMMEND_DUST_TO_BNB", "executed": False})

            if swept_total > 0:
                dust_swept_usd_total.inc(swept_total)
            last_dust_sweep_timestamp.set(time.time())

            return {"count": len(items), "total_value": round(total_dust, 4), "actions": actions, "dry_run": dry_run}

        try:
            result = loop.run_until_complete(_run())
        finally:
            asyncio.set_event_loop(None)
            loop.close()

        logger.info("🧹 Barrido de polvo: %s", result)
        return result
    except Exception as e:
        logger.error(f"❌ Error en dust_sweep: {e}")
        return {"status": "error", "message": str(e)}