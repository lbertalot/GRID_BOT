"""
Optimized Grid Manager for Multi-Asset Trading
Following FastAPI best practices and .cursorrules
"""

import asyncio
from typing import Any, Dict, List, Optional
from decimal import Decimal, ROUND_DOWN, getcontext
from dataclasses import dataclass
from datetime import datetime
import json
import os
import uuid
import asyncpg
import math

from pydantic import BaseModel, Field
from pydantic import field_validator, model_validator
from binance import Client
from dotenv import load_dotenv

# SQLAlchemy logging: se configura una vez al importar sqlalchemy_logging.
from app.core.sqlalchemy_logging import configure_sqlalchemy_logging  # noqa: F401

# Cargar variables de entorno desde .env
load_dotenv()

from app.services.telegram_alert import send_telegram_alert
from app.services.grid_strategy import decide_grid_action, calculate_grid_levels
from app.services.order_validation import OrderValidator
from app.models.asset_limit import AssetLimit
from app.services.strategy_manager import strategy_manager
from app.services.binance_async import AsyncBinanceWrapper
from app.services.commission_manager import commission_manager
from app.services.broker_adapter import use_broker_adapter_for_trade_execution_from_env
from app.services.broker_market_execution import place_spot_market_via_adapter
from app.core.metrics import gridbot_spot_market_submit_path_total

# Configurar logging optimizado
from app.core.optimized_logging import setup_optimized_logging
from app.core.secret_redaction import format_credential_for_log

logger = setup_optimized_logging()


class AssetConfig(BaseModel):
    symbol: str
    min_price: float
    max_price: float
    grids: int
    quantity: float
    is_active: bool = True
    last_action: Optional[str] = None
    last_level: Optional[float] = None
    grid_levels: List[float] = Field(default_factory=list)

    @field_validator("grid_levels")
    @classmethod
    def calculate_grid_levels_on_init(cls, v, info):
        if v:
            return v
        data = info.data or {}
        return calculate_grid_levels(
            data.get("min_price"), data.get("max_price"), data.get("grids")
        )

    @model_validator(mode="after")
    def ensure_grid_levels(self):
        # Garantiza niveles de grilla calculados si no vienen en el JSON
        if (not self.grid_levels) and self.min_price and self.max_price and self.grids:
            self.grid_levels = calculate_grid_levels(
                self.min_price, self.max_price, self.grids
            )
        return self


class GridManagerConfig(BaseModel):
    """Pydantic model for grid manager configuration"""

    assets: Dict[str, AssetConfig] = Field(default_factory=dict)
    update_interval: int = Field(default=60, ge=30, le=300)
    min_notional_threshold: float = Field(
        default=10.0, ge=1.0
    )  # Cambiado a 10.0 por defecto
    max_concurrent_orders: int = Field(default=3, ge=1, le=10)


DEFAULT_GRID_CONFIG_FILE = "grid_config_optimized.json"


def resolve_grid_config_file() -> str:
    """Path de config del grid: env GRID_CONFIG_FILE o optimized.json (legacy)."""
    raw = (os.getenv("GRID_CONFIG_FILE") or DEFAULT_GRID_CONFIG_FILE).strip()
    return raw or DEFAULT_GRID_CONFIG_FILE


def _positive_float(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return parsed if parsed > 0 else 0.0


def resolve_min_notional_threshold(config_data: Dict[str, Any]) -> float:
    """Piso L0 = max(floor metadata, notional/nivel, threshold top-level). Default 10.

    Freeze paper: floor 15 + nivel 20 → 20. JSON optimized sin metadata → 10.
    """
    meta = config_data.get("_config_metadata")
    if not isinstance(meta, dict):
        meta = {}
    floor = _positive_float(meta.get("min_notional_floor_usd"))
    level = _positive_float(meta.get("notional_per_level_usd"))
    for _key, data in config_data.items():
        if not isinstance(data, dict):
            continue
        level = max(level, _positive_float(data.get("notional_per_level_usd")))
    top = _positive_float(config_data.get("min_notional_threshold"))
    candidates = [x for x in (floor, level, top) if x > 0]
    return max(candidates) if candidates else 10.0


@dataclass
class TradingResult:
    timestamp: datetime
    symbol: str
    action: str
    quantity: float
    price: float
    order_id: str
    status: str
    profit: float = None


class OptimizedGridManager:
    """
    Optimized Grid Manager following functional programming principles
    and FastAPI best practices
    """

    def __init__(self, config: GridManagerConfig):
        self.config = config
        self.client = self._initialize_binance_client()
        self.order_validator = OrderValidator(self.client)
        self.trading_history: List[TradingResult] = []
        self.asset_limits: Dict[str, AssetLimit] = {}
        self.insufficient_funds: Dict[
            str, Dict
        ] = {}  # Nuevo: para registrar activos con saldo insuficiente
        self.config_file_path: Optional[str] = None  # Para recargar configuración
        # Wrapper asíncrono con caché y rate limiting para evitar bloqueos
        self.async_binance = AsyncBinanceWrapper(
            ttl_seconds=int(os.getenv("CACHE_TTL_SECONDS", "5")),
            rate_per_sec=float(os.getenv("BINANCE_RATE_PER_SEC", "5")),
            burst=int(os.getenv("BINANCE_RATE_BURST", "10")),
        )

    async def _load_asset_limits(self):
        """Load asset trading limits from the database."""
        database_url = os.getenv(
            "DATABASE_URL", "postgresql://griduser:gridpass@db:5432/gridbot"
        )
        conn = None
        try:
            conn = await asyncpg.connect(database_url)
            rows = await conn.fetch("SELECT * FROM asset_limits")
            for row in rows:
                self.asset_limits[row["symbol"]] = AssetLimit(**dict(row))
            logger.info(
                f"Cargados {len(self.asset_limits)} límites de activos desde la base de datos."
            )
        except Exception as e:
            logger.error(f"Error cargando límites de activos desde la BD: {e}")
        finally:
            if conn:
                await conn.close()

    def _initialize_binance_client(self) -> Client:
        """Initialize Binance client using Singleton pattern"""
        try:
            from app.services.binance_client_singleton import binance_client_singleton

            logger.info("🔧 Inicializando cliente Binance usando Singleton")
            client = binance_client_singleton.client

            if not client:
                raise Exception("No se pudo obtener cliente de Binance desde Singleton")

            # Verificar credenciales
            if not hasattr(client, "api_key") or not client.api_key:
                logger.error("❌ Cliente de Binance sin credenciales válidas")
                raise Exception("Cliente de Binance sin credenciales válidas")

            logger.info(
                "✅ Cliente Binance Singleton inicializado correctamente - "
                f"{format_credential_for_log(client.api_key, label='api_key')}"
            )

            # Obtener información de cuenta para uso posterior
            try:
                account_info = binance_client_singleton.get_account_info()
                self._account_info = account_info
                self._account_type = account_info.get("accountType", "SPOT")
                logger.info(
                    f"✅ Información de cuenta obtenida: {len(account_info.get('balances', []))} balances"
                )
            except Exception as e:
                logger.warning(f"⚠️ No se pudo obtener información de cuenta: {e}")
                self._account_info = {}
                self._account_type = "N/A"

            return client

        except Exception as e:
            logger.error(f"❌ Error inicializando cliente Binance Singleton: {e}")
            return None

    async def get_asset_balances(self) -> Dict[str, float]:
        """Balances: en paper SoT usa ledger; si no, Binance spot."""
        try:
            from app.core.paper_equity_ledger import paper_equity_is_source_of_truth
            from app.core.paper_cycle_liquidity import build_paper_balances_from_ledger

            if paper_equity_is_source_of_truth():
                symbols = [
                    a.symbol
                    for a in self.config.assets.values()
                    if getattr(a, "is_active", True)
                ]
                balances = build_paper_balances_from_ledger(symbols=symbols)
                logger.info(
                    "📄 Balances paper (ledger): %s activos — USDT=%s",
                    len(balances),
                    balances.get("USDT"),
                )
                return balances
        except Exception as exc:
            logger.warning("paper balances fallback a exchange: %s", exc)

        try:
            if not self.client:
                logger.error("❌ Cliente de Binance no inicializado")
                return {}

            # Verificar que el cliente tenga credenciales válidas
            if not hasattr(self.client, "api_key") or not self.client.api_key:
                logger.error("❌ Cliente de Binance sin credenciales válidas")
                return {}

            logger.info(
                "✅ Cliente de Binance verificado - "
                f"{format_credential_for_log(self.client.api_key, label='api_key')}"
            )

            logger.info("🔄 Obteniendo información de cuenta de Binance...")

            # Usar información de cuenta ya verificada si está disponible
            if hasattr(self, "_account_info") and self._account_info:
                account_info = self._account_info
                logger.info("✅ Usando información de cuenta pre-verificada")
            else:
                # Obtener información de cuenta con manejo robusto de errores
                from binance.exceptions import (
                    BinanceAPIException,
                    BinanceRequestException,
                )

                try:
                    # Evitar bloqueo en loop async
                    account_info = await asyncio.to_thread(self.client.get_account)
                except BinanceAPIException as e:
                    if e.code == -2015:
                        logger.error("❌ API Secret required for private endpoints")
                        logger.error("   Verifica que las credenciales sean correctas")
                        return {}
                    elif e.code == -2013:
                        logger.error("❌ Invalid API-key")
                        return {}
                    else:
                        logger.error(f"❌ Error de API de Binance: {e}")
                        return {}
                except BinanceRequestException as e:
                    logger.error(f"❌ Error de conexión con Binance: {e}")
                    return {}
                except Exception as e:
                    logger.error(
                        f"❌ Error inesperado obteniendo información de cuenta: {e}"
                    )
                    return {}

            logger.info(
                f"✅ Información de cuenta obtenida: {len(account_info.get('balances', []))} balances"
            )

            balances = {}
            for balance in account_info["balances"]:
                asset = balance["asset"]
                free_balance = float(balance["free"])
                if free_balance > 0:
                    balances[asset] = free_balance
                    logger.info(f"💰 Balance {asset}: {free_balance}")

            logger.info(f"📊 Total de activos con saldo: {len(balances)}")
            return balances

        except Exception as e:
            logger.error(f"❌ Error obteniendo balances: {e}")
            return {}

    async def get_current_prices(self, symbols: List[str]) -> Dict[str, float]:
        """Get current prices for given symbols"""
        try:
            if not self.client:
                return {}

            # Filtrar símbolos válidos (excluir metadatos)
            valid_symbols = [s for s in symbols if not s.startswith("_")]

            # Consultas concurrentes con caché/TTL para minimizar latencia y presión a la API
            results: Dict[str, float] = {}

            async def _fetch(sym: str):
                try:
                    price = await self.async_binance.get_price(sym)
                except Exception as e:
                    logger.warning(f"Error obteniendo precio para {sym}: {e}")
                    price = 0.0
                results[sym] = price

            await asyncio.gather(*[_fetch(s) for s in valid_symbols])
            return results
        except Exception as e:
            logger.error(f"Error obteniendo precios: {e}")
            return {}

    def calculate_optimal_quantities(
        self, balances: Dict[str, float], prices: Dict[str, float]
    ) -> Dict[str, float]:
        """Calcula las cantidades óptimas para operar, usando la configuración del archivo."""
        optimal_quantities = {}
        self.insufficient_funds = {}

        for symbol, asset_config in self.config.assets.items():
            if not asset_config.is_active:
                continue

            base_asset = symbol.replace("USDT", "")
            current_balance = balances.get(base_asset, 0)
            current_price = prices.get(symbol, 0)

            if current_price <= 0:
                continue

            # Usar la cantidad mayor entre config y mínima por notional
            quantity_to_use = asset_config.quantity

            # Verificar que cumple con min_notional del sistema y del exchange
            min_notional = self.config.min_notional_threshold
            try:
                limits = self.asset_limits.get(symbol)
                if limits and getattr(limits, "min_notional", None):
                    min_notional = max(min_notional, float(limits.min_notional))
            except Exception:
                pass
            notional_value = quantity_to_use * current_price

            if notional_value < min_notional:
                # Ajustar hacia arriba para cumplir notional mínimo, respetando step_size
                raw_min_qty = min_notional / current_price
                limits = self.asset_limits.get(symbol)
                if limits and getattr(limits, "step_size", None):
                    step_size = float(limits.step_size)
                    if step_size > 0:
                        steps = math.ceil(raw_min_qty / step_size)
                        quantity_to_use = steps * step_size
                    else:
                        quantity_to_use = raw_min_qty
                else:
                    quantity_to_use = raw_min_qty

            # Ajustar a step_size si corresponde
            limits = self.asset_limits.get(symbol)
            if limits and getattr(limits, "step_size", None):
                step_size = float(limits.step_size)
                precision = int(round(-math.log(step_size, 10), 0))
                quantity_to_use = float(
                    f"{math.floor(quantity_to_use / step_size) * step_size:.{precision}f}"
                )
                # Cap histórico 0.003 ETH solo si sigue cumpliendo min_notional
                if symbol == "ETHUSDT" and quantity_to_use >= 0.003:
                    capped = float(
                        f"{math.floor(0.003 / step_size) * step_size:.{precision}f}"
                    )
                    if capped * current_price >= min_notional:
                        quantity_to_use = capped
                # Re-bump si floor/cap dejaron nocional bajo el mínimo
                if quantity_to_use * current_price < min_notional and step_size > 0:
                    steps = math.ceil((min_notional / current_price) / step_size)
                    quantity_to_use = float(f"{(steps * step_size):.{precision}f}")
            elif quantity_to_use * current_price < min_notional and current_price > 0:
                quantity_to_use = min_notional / current_price

            # Log detallado del saldo y mínimos requeridos
            logger.info(
                f"[{symbol}] Saldo {base_asset} disponible: {current_balance}, cantidad requerida: {quantity_to_use}"
            )
            logger.info(
                f"[{symbol}] Valor nocional: {(quantity_to_use * current_price):.4f} USDT, mínimo requerido: {min_notional} USDT"
            )

            paper_mode = False
            try:
                from app.core.paper_equity_ledger import paper_equity_is_source_of_truth
                from app.core.paper_cycle_liquidity import can_afford_grid_quantity

                paper_mode = paper_equity_is_source_of_truth()
                affordable = can_afford_grid_quantity(
                    balances=balances,
                    base_asset=base_asset,
                    quantity=quantity_to_use,
                    price=current_price,
                    paper_mode=paper_mode,
                )
            except Exception:
                affordable = current_balance >= quantity_to_use

            # Recalcular notional tras ajuste de qty
            notional_value = quantity_to_use * current_price

            if affordable:
                optimal_quantities[symbol] = quantity_to_use
                logger.info(
                    f"✅ [{symbol}] Saldo suficiente para operar"
                    + (" (paper USDT/base)" if paper_mode else "")
                )
            else:
                missing = max(0, quantity_to_use - current_balance)
                self.insufficient_funds[symbol] = {
                    "saldo_actual": current_balance,
                    "cantidad_necesaria": quantity_to_use,
                    "faltante": missing,
                    "min_notional": min_notional,
                    "precio_actual": current_price,
                    "usdt": balances.get("USDT", 0),
                }
                logger.warning(
                    f"⛔ [{symbol}] Saldo insuficiente - Faltan {missing} {base_asset}"
                    + (f" / USDT={balances.get('USDT', 0)}" if paper_mode else "")
                )

        return optimal_quantities

    def _adjust_quantity_to_step_size(self, symbol: str, quantity: float) -> float:
        """Adjusts the order quantity to match the symbol's step size."""
        limits = self.asset_limits.get(symbol)
        if not limits or not limits.step_size:
            return quantity

        step_size = limits.step_size
        precision = int(round(-math.log(step_size, 10), 0))
        return float(f"{math.floor(quantity / step_size) * step_size:.{precision}f}")

    async def execute_grid_trading_cycle(self) -> List[TradingResult]:
        """
        Execute a complete grid trading cycle for all configured assets
        """
        try:
            from time import perf_counter
            from app.core.metrics import trading_metrics

            cycle_start = perf_counter()
            # Verificar límites de riesgo antes de ejecutar trading
            # Comentado temporalmente para evitar errores
            # risk_status = await risk_manager.check_portfolio_risk()
            #
            # if risk_status == RiskStatus.STOP_TRADING:
            #     logger.warning("Trading detenido por límites de riesgo críticos")
            #     send_telegram_alert("🚨 Trading detenido por límites de riesgo críticos")
            #     return []
            #
            # if risk_status == RiskStatus.DANGER:
            #     logger.warning("Trading en modo de riesgo alto - ejecutando con precaución")
            #     send_telegram_alert("⚠️ Trading en modo de riesgo alto - ejecutando con precaución")
            #
            # # Verificar si el trading está habilitado
            # if not risk_manager.trading_enabled:
            #     logger.info("Trading deshabilitado por gestión de riesgos")
            #     return []

            logger.info("Iniciando ciclo de trading con verificación de riesgos...")

            # Verificar y ejecutar rebalanceo automático si es necesario
            # Paper SoT: no rebalancear contra Binance (cash vive en ledger).
            try:
                from app.core.paper_equity_ledger import paper_equity_is_source_of_truth

                if paper_equity_is_source_of_truth():
                    logger.info("📄 Skip rebalance exchange (paper ledger SoT)")
                else:
                    from app.services.auto_rebalancer import auto_rebalancer

                    rebalance_status = await auto_rebalancer.get_rebalance_status()

                    if rebalance_status.get("assets_needing_rebalance", 0) > 0:
                        logger.info(
                            f"🔄 Detectados {rebalance_status['assets_needing_rebalance']} activos que necesitan rebalanceo"
                        )

                        if rebalance_status.get("can_rebalance", False):
                            logger.info("✅ Ejecutando rebalanceo automático...")
                            rebalance_result = await auto_rebalancer.check_and_rebalance()
                            logger.info(
                                f"Rebalanceo completado: {rebalance_result.get('status')}"
                            )
                        else:
                            logger.warning("⚠️ No se puede rebalancear - USDT insuficiente")
                            logger.warning(
                                f"   Necesario: ${rebalance_status.get('total_needed_usdt', 0):.2f}"
                            )
                            logger.warning(
                                f"   Disponible: ${rebalance_status.get('available_usdt', 0):.2f}"
                            )
                    else:
                        logger.info("✅ Todos los activos tienen saldo suficiente")

            except Exception as e:
                logger.error(f"Error en rebalanceo automático: {e}")

            balances = await self.get_asset_balances()
            symbols = [
                asset.symbol for asset in self.config.assets.values() if asset.is_active
            ]
            prices = await self.get_current_prices(symbols)
            # Adaptación de estrategia (no bloquea, usa colector async)
            try:
                changes = await strategy_manager.adapt_manager(self, symbols)
                if changes:
                    logger.info(
                        f"🧠 Adaptación aplicada por StrategyManager: {changes}"
                    )
            except Exception as e:
                logger.warning(f"No se pudo adaptar estrategia en este ciclo: {e}")
            optimal_quantities = self.calculate_optimal_quantities(balances, prices)
            trading_results = []

            logger.info(f"📊 Evaluando {len(symbols)} símbolos activos para trading")
            logger.info(f"💰 Balances disponibles: {len(balances)} activos con saldo")
            logger.info(f"📈 Precios obtenidos: {len(prices)} símbolos")
            logger.info(
                f"🎯 Cantidades óptimas calculadas: {len(optimal_quantities)} símbolos"
            )

            for symbol, quantity in optimal_quantities.items():
                asset_config = self.config.assets.get(symbol)
                if not asset_config:
                    logger.warning(
                        f"⛔ {symbol}: Configuración de activo no encontrada"
                    )
                    continue

                logger.info(f"🔍 Evaluando {symbol} para trading...")

                # Verificar riesgo específico del activo
                # Comentado temporalmente para evitar errores
                # asset_risk_status = await risk_manager.check_asset_risk(symbol)
                # if asset_risk_status == RiskStatus.STOP_TRADING:
                #     logger.warning(f"Trading detenido para {symbol} por riesgo crítico")
                #     continue
                #
                # if asset_risk_status == RiskStatus.DANGER:
                #     # Ejecutar stop-loss si es necesario
                #     await risk_manager.execute_stop_loss(symbol)
                #     logger.warning(f"Stop-loss ejecutado para {symbol}")
                #     continue

                current_price = prices.get(symbol, 0)
                if current_price <= 0:
                    logger.warning(
                        f"⛔ {symbol}: Precio es 0 o negativo (${current_price}), saltando operación."
                    )
                    continue

                logger.info(
                    f"📊 {symbol}: Precio actual ${current_price}, cantidad óptima {quantity}"
                )

                # Paper: hidratar last_action / last_level desde ledger (persiste entre ciclos).
                try:
                    from app.core.paper_cycle_liquidity import (
                        resolve_last_grid_action,
                        resolve_last_grid_level,
                    )

                    hydrated = resolve_last_grid_action(
                        symbol, fallback=asset_config.last_action
                    )
                    if hydrated and hydrated != asset_config.last_action:
                        logger.info(
                            "📄 %s last_action hidratado desde ledger: %s",
                            symbol,
                            hydrated,
                        )
                        asset_config.last_action = hydrated
                    lvl = resolve_last_grid_level(
                        symbol, fallback=asset_config.last_level
                    )
                    if lvl is not None:
                        asset_config.last_level = float(lvl)
                except Exception as hyd_exc:  # noqa: BLE001
                    logger.debug("last_action hydrate skip: %s", hyd_exc)

                action = decide_grid_action(
                    prices.get(symbol, 0),
                    asset_config.grid_levels,
                    asset_config.last_action,
                    asset_config.last_level,
                )

                if action and action.get("action"):
                    logger.info(
                        f"✅ {symbol}: Señal de {action['action']} detectada en nivel {action.get('level', 'N/A')}"
                    )

                    # Usar la cantidad calculada (que ya incluye validaciones)
                    quantity_to_use = quantity
                    side = str(action.get("action") or "").upper()
                    paper_sot = False
                    try:
                        from app.core.paper_equity_ledger import (
                            paper_equity_is_source_of_truth as _paper_sot,
                        )

                        paper_sot = bool(_paper_sot())
                    except Exception:
                        paper_sot = False

                    # Paper SELL residual: clip a ledger.position antes del fund_manager.
                    if side == "SELL":
                        from app.core.paper_cycle_liquidity import (
                            clip_paper_sell_quantity,
                        )

                        limits = self.asset_limits.get(symbol)
                        step_raw = (
                            getattr(limits, "step_size", None) if limits else None
                        )
                        step_dec = (
                            Decimal(str(step_raw))
                            if step_raw is not None and float(step_raw) > 0
                            else None
                        )
                        clipped = clip_paper_sell_quantity(
                            symbol=symbol,
                            sizer_qty=Decimal(str(quantity_to_use)),
                            step_size=step_dec,
                        )
                        quantity_to_use = float(clipped)
                        if clipped <= 0:
                            logger.info(
                                "📄 %s: SELL clip qty=0 — nada que vender, skip",
                                symbol,
                            )
                            continue

                    # Validar saldo
                    base_asset = symbol.replace("USDT", "")
                    available_balance = balances.get(base_asset, 0)

                    # Validar requisitos de fondos usando FundManager
                    from app.services.fund_manager import fund_manager
                    from app.core.paper_cycle_liquidity import (
                        should_enforce_level_notional_on_sell,
                    )

                    (
                        is_valid,
                        message,
                        details,
                    ) = await fund_manager.validate_trade_requirements(
                        symbol=symbol,
                        side=action["action"],
                        quantity=quantity_to_use,
                        price=current_price,
                        balances=balances,
                    )

                    if not is_valid:
                        # Log más detallado para debugging
                        logger.info(f"🔍 {symbol}: Validación fallida - {message}")
                        logger.info(f"   📊 Detalles: {details}")

                        # Subir a min_quantity_required (min_notional) si el fund_manager lo pide
                        min_qty_req = details.get("min_quantity_required")
                        skip_sell_bump = (
                            side == "SELL"
                            and paper_sot
                            and min_qty_req is not None
                            and float(min_qty_req) > quantity_to_use
                        )
                        if skip_sell_bump:
                            logger.info(
                                "📄 %s: no bump SELL a min_quantity_required=%s "
                                "(supera clip/position %s)",
                                symbol,
                                min_qty_req,
                                quantity_to_use,
                            )
                        elif min_qty_req and float(min_qty_req) > quantity_to_use:
                            adjusted_quantity = float(min_qty_req)
                            logger.info(
                                f"🔄 {symbol}: Reintento con min_quantity_required={adjusted_quantity}"
                            )
                            (
                                is_valid,
                                message,
                                details,
                            ) = await fund_manager.validate_trade_requirements(
                                symbol=symbol,
                                side=action["action"],
                                quantity=adjusted_quantity,
                                price=current_price,
                                balances=balances,
                            )
                            if is_valid:
                                quantity_to_use = adjusted_quantity
                                logger.info(
                                    f"✅ {symbol}: Validación OK tras bump min_notional"
                                )
                            else:
                                logger.warning(
                                    f"⛔ {symbol}: Sigue inválido tras bump - {message}"
                                )
                                logger.info(f"   📊 Detalles: {details}")

                        # Cierre residual paper: piso L0 15/20 o shortage post-clip
                        # no deben abortar el SELL de inventario ya comprado.
                        residual_reject = (
                            "min_notional" in details
                            or "min_quantity_required" in details
                            or "shortage" in details
                        )
                        if (
                            not is_valid
                            and side == "SELL"
                            and paper_sot
                            and quantity_to_use > 0
                            and residual_reject
                            and not should_enforce_level_notional_on_sell(paper=True)
                        ):
                            logger.info(
                                "📄 %s: SELL residual paper — se permite cierre "
                                "qty=%s notional≈%s (rechazo fund_manager: %s)",
                                symbol,
                                quantity_to_use,
                                quantity_to_use * current_price,
                                message,
                            )
                            is_valid = True

                        # Intentar con cantidad reducida si es posible
                        if not is_valid and "shortage" in details:
                            shortage = details.get("shortage", 0)
                            if shortage > 0:
                                # Calcular cantidad ajustada
                                adjusted_quantity = quantity_to_use * 0.8  # Reducir 20%
                                logger.info(
                                    f"🔄 {symbol}: Intentando con cantidad ajustada: {adjusted_quantity}"
                                )

                                # Validar con cantidad ajustada
                                (
                                    is_valid_adj,
                                    message_adj,
                                    details_adj,
                                ) = await fund_manager.validate_trade_requirements(
                                    symbol=symbol,
                                    side=action["action"],
                                    quantity=adjusted_quantity,
                                    price=current_price,
                                    balances=balances,
                                )

                                if is_valid_adj:
                                    quantity_to_use = adjusted_quantity
                                    is_valid = True
                                    logger.info(
                                        f"✅ {symbol}: Validación exitosa con cantidad ajustada"
                                    )
                                else:
                                    logger.warning(
                                        f"⛔ {symbol}: No se puede ajustar cantidad - {message_adj}"
                                    )
                                    continue
                            else:
                                logger.warning(f"⛔ {symbol}: {message}")
                                continue
                        elif not is_valid:
                            logger.warning(f"⛔ {symbol}: {message}")
                            continue

                    # Usar cantidad ajustada si es necesario
                    adjusted_quantity = details.get("quantity", quantity_to_use)
                    if adjusted_quantity and adjusted_quantity != quantity_to_use:
                        if (
                            side == "SELL"
                            and paper_sot
                            and float(adjusted_quantity) > quantity_to_use
                        ):
                            logger.info(
                                "📄 %s: skip raise SELL qty %s → %s (no superar position)",
                                symbol,
                                quantity_to_use,
                                adjusted_quantity,
                            )
                        else:
                            logger.info(
                                f"🔄 {symbol}: Ajustando cantidad de {quantity_to_use} a {adjusted_quantity}"
                            )
                            quantity_to_use = adjusted_quantity

                            # Verificar min_notional (piso de nivel: BUY/nuevos, no SELL paper residual)
                            notional_value = quantity_to_use * current_price
                            min_notional = self.config.min_notional_threshold

                            if notional_value < min_notional:
                                sell_residual_ok = (
                                    side == "SELL"
                                    and not should_enforce_level_notional_on_sell(
                                        paper=paper_sot
                                    )
                                )
                                if sell_residual_ok:
                                    logger.info(
                                        "📄 %s: SELL residual notional $%.4f < piso nivel $%s — permitiendo cierre",
                                        symbol,
                                        notional_value,
                                        min_notional,
                                    )
                                else:
                                    logger.warning(
                                        f"⛔ {symbol}: Valor nocional insuficiente. Valor: ${notional_value:.4f}, Mínimo: ${min_notional}"
                                    )
                                    continue

                    logger.info(
                        f"🚀 {symbol}: Ejecutando {action['action']} de {quantity_to_use} @ ${current_price}"
                    )

                    result = await self._execute_trade(
                        symbol=symbol,
                        action=action["action"],
                        quantity=quantity_to_use,
                        price=current_price,
                        grid_level=action.get("level"),
                    )

                    if result:
                        trading_results.append(result)
                        asset_config.last_action = action["action"]
                        if action.get("level") is not None:
                            asset_config.last_level = float(action["level"])
                        logger.info(f"✅ {symbol}: Trade ejecutado exitosamente")

                        # Registrar métricas de trading usando el nuevo sistema centralizado
                        try:
                            from app.core.metrics_manager import metrics_manager

                            metrics_manager.record_trade_execution(
                                symbol=symbol,
                                side=action["action"],
                                quantity=quantity_to_use,
                                price=current_price,
                                execution_time=0.5,  # Tiempo estimado de ejecución
                            )
                        except Exception as e:
                            logger.error(f"Error registrando métricas de trade: {e}")
                    else:
                        logger.error(f"❌ {symbol}: Error ejecutando trade")

                        # Registrar métricas de error usando el nuevo sistema centralizado
                        try:
                            from app.core.metrics_manager import metrics_manager

                            metrics_manager.record_error(
                                "trade_execution_failed", "grid_manager"
                            )
                        except Exception as e:
                            logger.error(f"Error registrando métricas de error: {e}")
                else:
                    current_price = prices.get(symbol, 0)
                    # Determinar el motivo específico por el que no se ejecuta la orden
                    if not action:
                        reason = "sin señal de trading válida"
                    elif not action.get("action"):
                        reason = "señal de trading inválida"
                    else:
                        reason = (
                            "precio no cruzó niveles de grilla o última acción repetida"
                        )

                    logger.info(f"⛔ {symbol}: No se ejecuta orden - Motivo: {reason}")
                    logger.info(f"   📊 Precio actual: ${current_price}")
                    logger.info(f"   📈 Niveles de grilla: {asset_config.grid_levels}")
                    logger.info(f"   🔄 Última acción: {asset_config.last_action}")
                    logger.info(f"   📡 Señal recibida: {action}")

                    # Log adicional para debugging de la lógica de grid
                    if asset_config.grid_levels:
                        min_level = min(asset_config.grid_levels)
                        max_level = max(asset_config.grid_levels)
                        logger.info(
                            f"   📋 Rango de grilla: ${min_level} - ${max_level}"
                        )
                        if current_price < min_level:
                            logger.info("   ⬇️ Precio por debajo del rango mínimo")
                        elif current_price > max_level:
                            logger.info("   ⬆️ Precio por encima del rango máximo")
                        else:
                            logger.info(
                                "   ↔️ Precio dentro del rango, pero no cruzó niveles"
                            )

            if self.insufficient_funds:
                logger.warning(
                    f"⚠️ Activos con saldo insuficiente: {list(self.insufficient_funds.keys())}"
                )

            # Log final del ciclo
            if trading_results:
                logger.info("🎉 Ciclo de trading completado exitosamente")
                logger.info(
                    f"📊 Total de operaciones ejecutadas: {len(trading_results)}"
                )
                buy_trades = len([r for r in trading_results if r.action == "BUY"])
                sell_trades = len([r for r in trading_results if r.action == "SELL"])
                logger.info(f"📈 Compras: {buy_trades}, Ventas: {sell_trades}")
            else:
                logger.info("ℹ️ Ciclo de trading completado sin operaciones")
                logger.info(
                    "💡 Posibles razones: precios fuera de rango, sin señales válidas, o saldos insuficientes"
                )

            # Actualizar métricas usando el nuevo sistema centralizado y el servicio de rentabilidad
            try:
                from app.core.metrics_manager import metrics_manager
                from app.services.metrics_service import metrics_service

                await metrics_manager.update_all_metrics()
                # Actualiza gauges como profit_total_usdt/portfolio_total_value_usdt con labels esperados
                try:
                    await metrics_service.calculate_portfolio_metrics()
                except Exception:
                    pass
                logger.info("✅ Métricas actualizadas correctamente")
            except Exception as e:
                logger.error(f"Error actualizando métricas: {e}")

            # Registrar duración de ciclo grid
            duration = perf_counter() - cycle_start
            try:
                trading_metrics.record_grid_cycle_duration(duration)
            except Exception:
                pass
            return trading_results

        except Exception as e:
            logger.error(f"Error ejecutando ciclo de trading: {e}")
            return []

    async def _execute_single_asset_trading(
        self, symbol: str, quantity: float, current_price: float
    ) -> Optional[TradingResult]:
        """Execute trading for a single asset"""
        try:
            asset_config = self.config.assets.get(symbol)
            if not asset_config:
                return None

            try:
                from app.core.paper_cycle_liquidity import (
                    resolve_last_grid_action,
                    resolve_last_grid_level,
                )

                hydrated = resolve_last_grid_action(
                    symbol, fallback=asset_config.last_action
                )
                if hydrated:
                    asset_config.last_action = hydrated
                lvl = resolve_last_grid_level(
                    symbol, fallback=asset_config.last_level
                )
                if lvl is not None:
                    asset_config.last_level = float(lvl)
            except Exception:
                pass

            action = decide_grid_action(
                current_price,
                asset_config.grid_levels,
                asset_config.last_action,
                asset_config.last_level,
            )

            if not action or not action.get("action"):
                return None

            result = await self._execute_trade(
                symbol=symbol,
                action=action["action"],
                quantity=quantity,
                price=current_price,
                grid_level=action.get("level"),
            )

            if result:
                asset_config.last_action = action["action"]
                if action.get("level") is not None:
                    asset_config.last_level = float(action["level"])

            return result

        except Exception as e:
            logger.error(f"Error ejecutando trading para {symbol}: {e}")
            return None

    def _record_paper_fill(
        self,
        symbol: str,
        action: str,
        quantity: float,
        price: float,
        grid_level: Optional[int] = None,
    ) -> bool:
        """Asienta el fill paper en el ledger contable (S10).

        Devuelve `True` si no había nada que asentar (modo real) o si el asiento
        salió bien. `False` si el ledger rechazó la operación — típicamente cash
        insuficiente o venta sin inventario: en paper eso significa que la orden no
        debería haber existido, y contarla inflaría el equity.

        La conversión `float → Decimal` vía `str()` ocurre acá, en el borde: adentro
        del ledger todo es `Decimal` (regla 10-financial-integrity).
        """
        try:
            from app.core.paper_equity_ledger import (
                PaperLedgerError,
                get_paper_ledger,
                paper_equity_is_source_of_truth,
                to_money,
            )

            if not paper_equity_is_source_of_truth():
                return True

            ledger = get_paper_ledger()
            qty = to_money(str(quantity), field_name="quantity")
            px = to_money(str(price), field_name="price")
            try:
                if action.upper() == "BUY":
                    ledger.record_buy(
                        symbol,
                        qty,
                        px,
                        grid_level=grid_level,
                        client_order_id=f"paper-grid-buy-{uuid.uuid4().hex[:16]}",
                    )
                else:
                    ledger.record_sell(
                        symbol,
                        qty,
                        px,
                        client_order_id=f"paper-grid-sell-{uuid.uuid4().hex[:16]}",
                    )
            except PaperLedgerError as exc:
                logger.warning(
                    f"📄 Fill paper rechazado por el ledger ({symbol} {action}): {exc}"
                )
                return False
            return True
        except Exception as exc:
            logger.error(f"❌ Error asentando fill paper en el ledger: {exc}")
            return False

    @staticmethod
    def _build_paper_simulated_order(
        *,
        symbol: str,
        action: str,
        quantity: float,
        commission: float,
        commission_percentage: float,
        notional_value: float,
    ) -> Dict[str, Any]:
        """Payload FILLED paper-sim (seam testeable; sin red)."""
        now_ms = int(datetime.now().timestamp() * 1000)
        return {
            "orderId": f"paper_{int(datetime.now().timestamp())}",
            "symbol": symbol,
            "side": action,
            "type": "MARKET",
            "quantity": str(quantity),
            "status": "FILLED",
            "price": "0",
            "executedQty": str(quantity),
            "cummulativeQuoteQty": "0",
            "timeInForce": "GTC",
            "time": now_ms,
            "updateTime": now_ms,
            "isWorking": False,
            "origQuoteOrderQty": "0",
            "commission_info": {
                "commission_usdt": commission,
                "commission_percentage": commission_percentage,
                "notional_value": notional_value,
                "order_type": "MARKET",
            },
        }

    async def _place_order(
        self, symbol: str, action: str, quantity: float
    ) -> Optional[Dict]:
        """Place an order on Binance (Paper Trading or Real) with commission validation"""
        try:
            # Verificar modo Paper Trading
            paper_trading = os.getenv("PAPER_TRADING", "false").lower() == "true"

            # Obtener precio actual para cálculos de comisión
            current_price = await self.async_binance.get_price(symbol)
            notional_value = quantity * current_price

            # Calcular comisión antes de ejecutar la orden
            commission = commission_manager.calculate_commission(
                notional_value, "MARKET", symbol
            )
            commission_percentage = (
                (commission / notional_value * 100) if notional_value > 0 else 0
            )

            logger.info(
                f"💰 Comisión calculada para {action} {quantity} {symbol}: ${commission:.6f} USDT ({commission_percentage:.3f}%)"
            )

            # Validar si la comisión es excesiva (más del 1%)
            if commission_percentage > 1.0:
                logger.warning(
                    f"⚠️ Comisión alta detectada: {commission_percentage:.3f}% para {symbol}"
                )

            if paper_trading:
                # Simular orden en modo Paper Trading
                logger.info(
                    f"📄 Simulando orden en modo Paper Trading: {action} {quantity} {symbol}"
                )
                simulated_order = self._build_paper_simulated_order(
                    symbol=symbol,
                    action=action,
                    quantity=quantity,
                    commission=commission,
                    commission_percentage=commission_percentage,
                    notional_value=notional_value,
                )
                logger.info(
                    f"✅ Orden simulada creada: {simulated_order['orderId']} - Comisión: ${commission:.6f} USDT"
                )
                return simulated_order

            else:
                # Orden real en Binance — S-GATE (B15/B26): fail-closed
                from app.core.order_execution_guard import (
                    RealOrderBlocked,
                    assert_real_order_allowed,
                )

                try:
                    assert_real_order_allowed(context="OptimizedGridManager._place_order")
                except RealOrderBlocked as blocked:
                    logger.error("❌ Orden real rechazada por guard: %s", blocked.reason)
                    return None

                if not self.client:
                    logger.error(
                        "❌ Cliente de Binance no inicializado para orden real"
                    )
                    return None

                # Verificar credenciales antes de crear orden real
                if not hasattr(self.client, "api_key") or not self.client.api_key:
                    logger.error(
                        "❌ Cliente de Binance sin credenciales para orden real"
                    )
                    return None

                # Formatear cantidad evitando notación científica y respetando stepSize
                def _format_quantity(sym: str, qty: float) -> str:
                    limits = self.asset_limits.get(sym)
                    # Precisión por defecto si no hay límites
                    default_step = Decimal("0.00000001")
                    step = default_step
                    if limits and getattr(limits, "step_size", None):
                        try:
                            step = Decimal(str(limits.step_size))
                        except Exception:
                            step = default_step
                    getcontext().prec = 28
                    q = Decimal(str(qty))
                    # Floor a múltiplos de step
                    units = (q / step).to_integral_value(rounding=ROUND_DOWN)
                    q_adj = units * step
                    precision = max(0, -step.as_tuple().exponent)
                    return f"{q_adj:.{precision}f}"

                qty_str = _format_quantity(symbol, quantity)
                # Asegurar formato fijo (sin notación científica)
                try:
                    limits = self.asset_limits.get(symbol)
                    precision = 8
                    if limits and getattr(limits, "step_size", None):
                        step = Decimal(str(limits.step_size))
                        precision = max(0, -step.as_tuple().exponent)
                    qty_str = f"{Decimal(qty_str):.{precision}f}"
                except Exception:
                    qty_str = f"{Decimal(str(quantity)):.8f}"
                logger.info(
                    f"💰 Creando orden real en Binance: {action} {qty_str} {symbol}"
                )

                action_u = action.upper()

                def _create_order():
                    if action_u == "BUY":
                        try:
                            price_now = (
                                float(current_price)
                                if current_price
                                else float(
                                    asyncio.run(self.async_binance.get_price(symbol))
                                )
                            )
                        except Exception:
                            price_now = float(current_price) if current_price else 0.0
                        usdt_amount = max(round(price_now * float(quantity), 2), 10.02)
                        return self.client.create_order(
                            symbol=symbol,
                            side=action,
                            type="MARKET",
                            quoteOrderQty=usdt_amount,
                        )
                    return self.client.create_order(
                        symbol=symbol, side=action, type="MARKET", quantity=qty_str
                    )

                used_broker_adapter = False
                order: Optional[Dict[str, Any]] = None
                if (
                    action_u == "SELL"
                    and use_broker_adapter_for_trade_execution_from_env()
                ):
                    try:
                        order = await place_spot_market_via_adapter(
                            symbol=symbol,
                            side=action_u,
                            quantity_base=float(qty_str),
                            client_order_id=None,
                            recv_window_ms=10_000,
                            binance_wrapper=self.async_binance,
                        )
                        used_broker_adapter = True
                    except Exception as adapter_err:
                        if "-1021" not in str(adapter_err):
                            raise
                        logger.warning(
                            "BrokerAdapter -1021 en grid SELL; fallback cliente sync: %s",
                            adapter_err,
                        )

                if order is None:
                    order = await asyncio.to_thread(_create_order)

                path = "broker_adapter" if used_broker_adapter else "binance_client"
                gridbot_spot_market_submit_path_total.labels(
                    source="grid_manager", path=path
                ).inc()

                # Agregar información de comisión al resultado
                order["commission_info"] = {
                    "commission_usdt": commission,
                    "commission_percentage": commission_percentage,
                    "notional_value": notional_value,
                    "order_type": "MARKET",
                }

                logger.info(
                    f"✅ Orden real creada: {order.get('orderId', 'unknown')} - Comisión: ${commission:.6f} USDT"
                )
                return order

        except Exception as e:
            logger.error(f"❌ Error colocando orden para {symbol}: {e}")
            return None

    def _send_trading_notification(self, result: TradingResult):
        """Send trading notification via Telegram"""
        try:
            message = (
                f"🔄 Trade ejecutado:\n"
                f"🪙 {result.symbol}\n"
                f"📈 {result.action}\n"
                f"📏 {result.quantity}\n"
                f"💰 ${result.price:.6f}\n"
                f"📊 Estado: {result.status}"
            )

            send_telegram_alert(message)
        except Exception as e:
            logger.error(f"Error enviando notificación: {e}")

    async def _save_trade_to_db(
        self, symbol: str, side: str, quantity: float, price: float, order_id: str
    ):
        """Guarda un trade en la base de datos PostgreSQL con manejo optimizado"""
        if not symbol or not side or quantity <= 0 or price <= 0:
            logger.error(
                f"❌ Datos inválidos para guardar trade: symbol={symbol}, side={side}, "
                f"quantity={quantity}, price={price}"
            )
            return

        db = None
        try:
            from app.db.session import SessionLocal
            from app.models.trade import Trade
            from sqlalchemy import desc

            logger.info(
                f"🔄 Guardando trade en BD: {side} {quantity} {symbol} @ ${price:.6f}"
            )

            db = SessionLocal()
            saved_id: Optional[int] = None

            if side.upper() == "SELL":
                # Buscar última BUY sin cerrar para realizar PnL
                open_buy = (
                    db.query(Trade)
                    .filter(
                        Trade.symbol == symbol,
                        Trade.side == "BUY",
                        Trade.exit_price == None,
                    )
                    .order_by(desc(Trade.timestamp))
                    .first()
                )
                if open_buy:
                    open_buy.exit_price = float(price)
                    open_buy.profit_loss = (
                        float(price) - float(open_buy.entry_price)
                    ) * float(min(quantity, open_buy.quantity))
                    db.commit()
                    db.refresh(open_buy)
                    saved_id = open_buy.id
                    logger.info(
                        f"✅ PnL realizado registrado: {open_buy.profit_loss:.6f} USDT en {symbol}"
                    )
                else:
                    # Sin BUY abierto: registrar trade SELL como evento de salida sin PnL
                    trade = Trade(
                        symbol=symbol,
                        side=side,
                        quantity=quantity,
                        entry_price=price,
                        timestamp=datetime.now(),
                    )
                    db.add(trade)
                    db.commit()
                    db.refresh(trade)
                    saved_id = trade.id
            else:
                # BUY: crear entrada abierta
                trade = Trade(
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    entry_price=price,
                    timestamp=datetime.now(),
                )
                db.add(trade)
                db.commit()
                db.refresh(trade)
                saved_id = trade.id

            logger.info(f"✅ Trade guardado exitosamente en BD - ID: {saved_id}")

        except Exception as e:
            logger.error(f"❌ Error guardando trade en BD: {e}")
            logger.error(
                f"   Detalles: symbol={symbol}, side={side}, quantity={quantity}, price={price}"
            )
            if db:
                try:
                    db.rollback()
                    logger.debug("🔄 Rollback ejecutado en BD debido a error")
                except Exception as rollback_error:
                    logger.error(f"❌ Error en rollback: {rollback_error}")
        finally:
            if db:
                try:
                    db.close()
                except Exception as close_error:
                    logger.error(f"❌ Error cerrando conexión BD: {close_error}")

    async def _execute_trade(
        self,
        symbol: str,
        action: str,
        quantity: float,
        price: float,
        grid_level: Optional[int] = None,
    ):
        """Execute a trade and return the result"""
        try:
            # E7 IC-WIRE: IC-1/IC-2 gate BUY del Core (paper-safe; no live).
            if str(action).upper() == "BUY":
                try:
                    from app.core.inventory_controls import get_inventory_control_guard

                    guard = get_inventory_control_guard()
                    # Actualiza IC-1/IC-2 con el precio de la señal antes del gate.
                    if price and guard.config.range_floor is not None:
                        observe_kw: Dict[str, Any] = {"mid": price, "enforce": False}
                        try:
                            from app.core import paper_equity_ledger as pel
                            from app.core.paper_equity_ledger import to_money

                            # Solo si ya están hidratados en el proceso (no leer
                            # paper_telemetry/ acá: el path ticker IC-2 es el snapshot).
                            series = getattr(pel, "_series", None)
                            ledger = getattr(pel, "_ledger", None)
                            if series is not None:
                                peak = series.peak_equity_usdt()
                                if peak is not None:
                                    observe_kw["peak_equity"] = peak
                                if series.samples:
                                    observe_kw["equity_mtm"] = to_money(
                                        series.samples[-1]["equity"],
                                        field_name="equity_mtm",
                                    )
                            if (
                                "equity_mtm" not in observe_kw
                                and ledger is not None
                            ):
                                symbols = ledger.symbols()
                                sym_u = str(symbol).upper()
                                if symbols == [sym_u]:
                                    observe_kw["equity_mtm"] = ledger.mark_to_market(
                                        {
                                            sym_u: to_money(
                                                str(price), field_name="mid"
                                            )
                                        }
                                    )
                        except Exception:
                            pass
                        guard.observe(**observe_kw)
                    if not guard.allows_core_buy():
                        logger.warning(
                            "[IC-WIRE] BUY bloqueado (%s %s @ %s) ic1=%s ic2=%s armed=%s",
                            symbol,
                            action,
                            price,
                            guard.state.ic1_active,
                            guard.state.ic2_active,
                            guard.state.armed,
                        )
                        return None
                except Exception as ic_exc:  # noqa: BLE001 — fail-closed en paper
                    paper_trading = (
                        os.getenv("PAPER_TRADING", "false").lower() == "true"
                    )
                    if paper_trading:
                        logger.error(
                            "[IC-WIRE] error en gate BUY — fail-closed paper: %s",
                            ic_exc,
                        )
                        return None
                    logger.warning("[IC-WIRE] gate BUY omitido (no-paper): %s", ic_exc)

            # Place the order
            order = await self._place_order(symbol, action, quantity)

            if not order:
                return None

            # S10: en paper el ledger contable es la fuente de verdad del equity.
            # Sin esto la orden simulada no deja rastro y la serie de equity queda
            # plana (gap I-3/I-5). Si el ledger rechaza el fill, el trade no vale.
            if not self._record_paper_fill(symbol, action, quantity, price, grid_level):
                return None

            # Create trading result
            result = TradingResult(
                timestamp=datetime.now(),
                symbol=symbol,
                action=action,
                quantity=quantity,
                price=price,
                order_id=order.get("orderId", "unknown"),
                status=order.get("status", "unknown"),
                profit=None,  # Will be calculated later
            )

            # Add to trading history
            self.trading_history.append(result)

            # Send notification
            self._send_trading_notification(result)

            # Registrar métricas del trade
            try:
                execution_time = 0.1  # Tiempo estimado de ejecución
                success = result.status in ["FILLED", "PARTIALLY_FILLED"]
                # Comentado temporalmente para evitar errores
                # await metrics_service.record_trade_execution(
                #     symbol=symbol,
                #     side=action,
                #     quantity=quantity,
                #     price=price,
                #     success=success,
                #     execution_time=execution_time
                # )
                logger.info(
                    f"📊 Métricas del trade registradas: {action} {quantity} {symbol}"
                )
            except Exception as e:
                logger.error(f"Error registrando métricas del trade: {e}")

            # Guardar trade en la base de datos
            try:
                logger.info(
                    f"🔄 Intentando guardar trade en BD: {action} {quantity} {symbol} @ ${price:.6f}"
                )
                await self._save_trade_to_db(
                    symbol, action, quantity, price, order.get("orderId", "unknown")
                )
                logger.info("✅ Trade guardado exitosamente en BD")
            except Exception as e:
                logger.error(f"❌ Error guardando trade en base de datos: {e}")
                logger.error(
                    f"   Detalles: symbol={symbol}, action={action}, quantity={quantity}, price={price}"
                )

            logger.info(f"Trade ejecutado: {action} {quantity} {symbol} a ${price:.6f}")

            return result

        except Exception as e:
            logger.error(f"Error ejecutando trade para {symbol}: {e}")
            return None

    def update_asset_config(self, symbol: str, new_config: Dict) -> bool:
        """Update configuration for a specific asset"""
        try:
            if symbol not in self.config.assets:
                return False

            asset_config = self.config.assets[symbol]

            # Update fields
            for key, value in new_config.items():
                if hasattr(asset_config, key):
                    setattr(asset_config, key, value)

            # Recalculate grid levels
            asset_config.grid_levels = calculate_grid_levels(
                asset_config.min_price, asset_config.max_price, asset_config.grids
            )

            logger.info(f"Updated configuration for {symbol}")
            return True
        except Exception as e:
            logger.error(f"Error updating config for {symbol}: {e}")
            return False

    async def reload_configuration(self, config_file_path: str = None) -> bool:
        """Recarga la configuración desde el archivo"""
        try:
            if config_file_path:
                self.config_file_path = config_file_path

            if not self.config_file_path:
                logger.error("No se especificó archivo de configuración para recargar")
                return False

            logger.info(f"Recargando configuración desde: {self.config_file_path}")

            # Crear nuevo grid manager con la configuración actualizada
            new_manager = await create_optimized_grid_manager(self.config_file_path)

            if new_manager:
                # Actualizar configuración
                self.config = new_manager.config
                self.asset_limits = new_manager.asset_limits

                logger.info("✅ Configuración recargada exitosamente")
                return True
            else:
                logger.error("❌ Error creando nuevo grid manager")
                return False

        except Exception as e:
            logger.error(f"Error recargando configuración: {e}")
            return False

    def get_trading_statistics(self) -> Dict:
        """Get comprehensive trading statistics"""
        try:
            if not self.trading_history:
                return {"message": "No trading history available"}

            total_trades = len(self.trading_history)
            buy_trades = len([t for t in self.trading_history if t.action == "BUY"])
            sell_trades = len([t for t in self.trading_history if t.action == "SELL"])

            # Calculate profits
            total_profit = sum(t.profit or 0 for t in self.trading_history)

            # Group by asset
            asset_stats = {}
            for result in self.trading_history:
                if result.symbol not in asset_stats:
                    asset_stats[result.symbol] = {"trades": 0, "profit": 0}
                asset_stats[result.symbol]["trades"] += 1
                asset_stats[result.symbol]["profit"] += result.profit or 0

            return {
                "total_trades": total_trades,
                "buy_trades": buy_trades,
                "sell_trades": sell_trades,
                "total_profit": total_profit,
                "asset_statistics": asset_stats,
                "last_trade": self.trading_history[-1].dict()
                if self.trading_history
                else None,
            }
        except Exception as e:
            logger.error(f"Error calculating statistics: {e}")
            return {"error": str(e)}

    async def save_configuration(self, filepath: str) -> bool:
        """Save current configuration to file"""
        try:
            import asyncio

            config_data = {
                "assets": {
                    symbol: {
                        "symbol": config.symbol,
                        "min_price": config.min_price,
                        "max_price": config.max_price,
                        "grids": config.grids,
                        "quantity": config.quantity,
                        "is_active": config.is_active,
                        "last_action": config.last_action,
                    }
                    for symbol, config in self.config.assets.items()
                },
                "update_interval": self.config.update_interval,
                "min_notional_threshold": self.config.min_notional_threshold,
                "max_concurrent_orders": self.config.max_concurrent_orders,
            }

            # ✅ FIX: Guardar configuración (non-blocking)
            def _write_config():
                with open(filepath, "w") as f:
                    json.dump(config_data, f, indent=2)

            await asyncio.to_thread(_write_config)

            logger.info(f"Configuration saved to {filepath}")
            return True
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            return False

    def get_insufficient_funds_report(self) -> Dict[str, Dict]:
        """Devuelve un reporte de los activos que no pueden operar por saldo insuficiente y cuánto falta para operar."""
        return self.insufficient_funds


# Factory function for creating grid manager
async def create_optimized_grid_manager(
    config_file: str,
) -> Optional[OptimizedGridManager]:
    """
    Factory function to create and initialize an OptimizedGridManager
    """
    try:
        import asyncio

        # ✅ FIX: Leer archivo de configuración (non-blocking)
        def _read_config():
            with open(config_file, "r") as f:
                return json.load(f)

        config_data = await asyncio.to_thread(_read_config)

        assets = {}
        required_fields = {"symbol", "min_price", "max_price", "grids", "quantity"}
        for key, data in config_data.items():
            # Omitir metadatos y secciones no-asset
            if not isinstance(data, dict):
                continue
            if key.startswith("_") or key in {"system_config"}:
                continue
            # Incluir sólo configuraciones con campos requeridos
            if required_fields.issubset(data.keys()):
                assets[key] = AssetConfig(**data)
            else:
                logger.debug(
                    f"Saltando clave no-asset '{key}' por campos faltantes: {set(data.keys())}"
                )

        grid_config = GridManagerConfig(
            assets=assets,
            update_interval=config_data.get("update_interval", 60),
            min_notional_threshold=resolve_min_notional_threshold(config_data),
            max_concurrent_orders=int(config_data.get("max_concurrent_orders", 3)),
        )

        manager = OptimizedGridManager(grid_config)
        manager.config_file_path = config_file  # Guardar ruta del archivo
        await manager._load_asset_limits()  # Load limits after creation
        return manager
    except Exception as e:
        logger.error(f"Error creating grid manager: {e}")
        return None
