"""
Servicio para integrar métricas de rentabilidad en el bot de trading
"""

import asyncio
import logging
from typing import Dict, Optional
from datetime import datetime

from app.core.metrics import trading_metrics
from app.core.metrics import portfolio_change_usdt
from app.core.metrics import (
    roi_daily_percent,
    profit_daily_usdt,
    roi_total_percent,
    profit_total_usdt,
)
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()
from app.db.session import SessionLocal
from app.models.system_setting import SystemSetting
from app.models.trade import Trade
from sqlalchemy import func

# from app.models.balance import Balance  # Modelo no implementado aún
from app.services.cache import get_async_cache

logger = logging.getLogger(__name__)


class MetricsService:
    """
    Servicio para calcular y actualizar métricas de rentabilidad
    """

    def __init__(self):
        self.initial_portfolio_value = None
        self.last_calculation = None
        # Mantener conteo previo de trades por (symbol, side) para incrementar Counters
        self._last_trades_count_by_symbol_side: Dict[tuple, int] = {}
        # Cache async para snapshots diarios (ROI base)
        self._cache = get_async_cache()
        self._allowed_symbols = {"BTCUSDT", "ETHUSDT", "BNBUSDT"}
        self._profit_baseline_key = "profit:baseline_iso"

    async def calculate_portfolio_metrics(self) -> Dict:
        """
        Calcula todas las métricas de rentabilidad del portafolio
        """
        try:
            # Obtener balances actuales
            balances = await self._get_current_balances()

            # Calcular valor total del portafolio
            portfolio_value = await self._calculate_portfolio_value(balances)

            # Calcular ganancia total
            total_profit = await self._calculate_total_profit()

            # Calcular ganancia diaria
            daily_profit = await self._calculate_daily_profit()

            # Calcular ROI diario
            roi_daily = await self._calculate_daily_roi(daily_profit, portfolio_value)

            # Calcular métricas por activo
            asset_metrics = await self._calculate_asset_metrics(balances)

            # Actualizar métricas en Prometheus
            self._update_prometheus_metrics(
                total_profit=total_profit,
                portfolio_value=portfolio_value,
                daily_profit=daily_profit,
                roi_daily=roi_daily,
                asset_metrics=asset_metrics,
            )

            # Delta vs baseline de portafolio (persistente en BD si existe)
            try:
                db = SessionLocal()
                base_val = None
                try:
                    s = (
                        db.query(SystemSetting)
                        .filter(SystemSetting.key == "portfolio:baseline_value_usdt")
                        .first()
                    )
                    if s and s.value:
                        base_val = float(s.value)
                except Exception:
                    base_val = None
                finally:
                    db.close()
                if base_val is None:
                    base_val = portfolio_value
                delta = float(portfolio_value) - float(base_val)
                portfolio_change_usdt.labels(strategy="grid").set(delta)
            except Exception:
                pass

            return {
                "portfolio_value": portfolio_value,
                "total_profit": total_profit,
                "daily_profit": daily_profit,
                "roi_daily": roi_daily,
                "asset_metrics": asset_metrics,
                "last_update": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error calculando métricas del portafolio: {e}")
            trading_metrics.record_error("portfolio_calculation_error")
            return {}

    async def update_binance_pnl_metrics(self) -> Dict:
        """
        Obtiene trades 'puros' de Binance, calcula PnL/ROI y publica métricas:
        - profit_total_usdt{strategy}
        - roi_total_percent{strategy}
        """
        try:
            from app.services.binance_trades_pnl import compute_binance_pnl_and_roi

            symbols = list(self._allowed_symbols)
            total_profit, total_invested, roi_pct = compute_binance_pnl_and_roi(symbols)
            # Publicar métricas totales
            profit_total_usdt.labels(strategy="grid").set(float(total_profit))
            roi_total_percent.labels(strategy="grid").set(float(roi_pct))
            logger.info(
                "📈 PnL/ROI Binance OPS/histórico (≠ SoT paper Capa A; "
                "equity paper = ledger ~999, no invested Binance): "
                "profit=%.6f USDT, invested=%.6f USDT, roi=%.4f%%",
                total_profit,
                total_invested,
                roi_pct,
            )
            return {
                "profit_total_usdt": total_profit,
                "invested_usdt": total_invested,
                "roi_total_percent": roi_pct,
            }
        except Exception as e:
            logger.error(f"Error actualizando métricas PnL/ROI Binance: {e}")
            return {"error": str(e)}

    async def _get_current_balances(self) -> Dict[str, float]:
        """
        Obtiene los balances actuales de Binance usando Singleton
        """
        try:
            from app.services.binance_client_singleton import (
                get_binance_client_singleton,
            )

            client = get_binance_client_singleton()
            # Reintentos simples + fallback caché
            for i in range(3):
                try:
                    balances = client.get_balances()
                    if balances:
                        await self._cache.set(
                            "balances:last", str(balances), ttl_seconds=180
                        )
                        return balances
                except Exception as e:
                    logger.warning(f"Retry balances ({i+1}/3) failed: {e}")
                    await asyncio.sleep(
                        0.5
                    )  # ✅ FIX: asyncio.sleep en lugar de time.sleep
            cached = await self._cache.get("balances:last")
            if cached:
                import ast

                try:
                    return ast.literal_eval(cached)
                except Exception:
                    pass
            return {}

        except Exception as e:
            logger.error(f"Error obteniendo balances: {e}")
            return {}

    async def _calculate_portfolio_value(self, balances: Dict[str, float]) -> float:
        """
        Calcula el valor total del portafolio en USDT
        """
        try:
            total_value = 0.0

            from app.services.binance_client_singleton import (
                STABLECOIN_ASSETS,
                binance_earn_underlying_asset,
                get_binance_client_singleton,
            )

            client_singleton = get_binance_client_singleton()

            def price_usdt_for(asset_symbol: str) -> float:
                if asset_symbol in STABLECOIN_ASSETS:
                    return 1.0
                # Intentar par directo a USDT
                direct = client_singleton.get_symbol_price(f"{asset_symbol}USDT")
                if direct and direct > 0:
                    return direct
                # Intentar BUSD (≈ USDT)
                busd = client_singleton.get_symbol_price(f"{asset_symbol}BUSD")
                if busd and busd > 0:
                    return busd  # Tratar BUSD≈USDT
                # Intentar vía BTC
                via_btc = client_singleton.get_symbol_price(f"{asset_symbol}BTC")
                if via_btc and via_btc > 0:
                    btc_usdt = client_singleton.get_symbol_price("BTCUSDT")
                    return via_btc * btc_usdt if btc_usdt else 0.0
                # Intentar vía ETH
                via_eth = client_singleton.get_symbol_price(f"{asset_symbol}ETH")
                if via_eth and via_eth > 0:
                    eth_usdt = client_singleton.get_symbol_price("ETHUSDT")
                    return via_eth * eth_usdt if eth_usdt else 0.0
                # Intentar vía BNB
                via_bnb = client_singleton.get_symbol_price(f"{asset_symbol}BNB")
                if via_bnb and via_bnb > 0:
                    bnb_usdt = client_singleton.get_symbol_price("BNBUSDT")
                    return via_bnb * bnb_usdt if bnb_usdt else 0.0
                return 0.0

            for asset, amount in balances.items():
                if amount <= 0:
                    continue
                # Binance Earn (LD*): valuár el subyacente; LDUSDT ≈ USDT 1:1.
                underlying = binance_earn_underlying_asset(asset)
                if underlying is not None:
                    asset = underlying
                if asset in STABLECOIN_ASSETS:
                    total_value += amount  # 1:1 USDT
                    continue
                price = price_usdt_for(asset)
                if price and price > 0:
                    total_value += amount * price
                else:
                    # Si no hay precio, omitir para no sesgar; opcional: log de depuración
                    logger.debug(f"Sin precio para {asset}, omitido en valoración")

            return total_value

        except Exception as e:
            logger.error(f"Error calculando valor del portafolio: {e}")
            return 0.0

    async def _calculate_total_profit(self) -> float:
        """
        Calcula la ganancia total desde el inicio en USDT
        """
        try:
            db = SessionLocal()
            try:
                # Determinar baseline temporal (BD > caché)
                baseline = None
                try:
                    s = (
                        db.query(SystemSetting)
                        .filter(SystemSetting.key == self._profit_baseline_key)
                        .first()
                    )
                    if s and s.value:
                        from datetime import datetime

                        baseline = datetime.fromisoformat(s.value)
                except Exception:
                    baseline = None
                if baseline is None:
                    try:
                        b = await self._cache.get(self._profit_baseline_key)
                        if b:
                            from datetime import datetime

                            baseline = datetime.fromisoformat(b)
                    except Exception:
                        baseline = None

                q = db.query(
                    Trade.symbol,
                    Trade.profit_loss,
                    Trade.entry_price,
                    Trade.exit_price,
                    Trade.quantity,
                ).filter(Trade.symbol.in_(self._allowed_symbols))
                if baseline is not None:
                    q = q.filter(Trade.timestamp >= baseline)
                rows = q.all()

                from app.services.binance_client_singleton import (
                    get_binance_client_singleton,
                )

                client_singleton = get_binance_client_singleton()

                def detect_quote(symbol: Optional[str]) -> Optional[str]:
                    if not symbol:
                        return None
                    quotes = [
                        "USDT",
                        "BUSD",
                        "USDC",
                        "TUSD",
                        "FDUSD",
                        "DAI",
                        "BTC",
                        "ETH",
                        "BNB",
                    ]
                    for q in quotes:
                        if symbol.upper().endswith(q):
                            return q
                    return None

                def to_usdt(amount_in_quote: float, quote: Optional[str]) -> float:
                    if amount_in_quote == 0.0 or not quote:
                        return amount_in_quote
                    if quote in {"USDT", "BUSD", "USDC", "TUSD", "FDUSD", "DAI"}:
                        return amount_in_quote  # 1:1 aproximado
                    if quote == "BTC":
                        px = client_singleton.get_symbol_price("BTCUSDT")
                        return amount_in_quote * (px or 0.0)
                    if quote == "ETH":
                        px = client_singleton.get_symbol_price("ETHUSDT")
                        return amount_in_quote * (px or 0.0)
                    if quote == "BNB":
                        px = client_singleton.get_symbol_price("BNBUSDT")
                        return amount_in_quote * (px or 0.0)
                    return 0.0

                total_profit_usdt = 0.0
                for symbol, profit_loss, entry_price, exit_price, qty in rows:
                    # Usar sólo PnL realizado provisto por la DB; evitar reconstrucciones ruidosas
                    if profit_loss is None:
                        continue
                    quote = detect_quote(symbol)
                    total_profit_usdt += to_usdt(float(profit_loss), quote)
                return total_profit_usdt
            finally:
                db.close()

        except Exception as e:
            logger.error(f"Error calculando ganancia total: {e}")
            return 0.0

    async def _calculate_daily_profit(self) -> float:
        """
        Calcula la ganancia del día actual en USDT
        """
        try:
            db = SessionLocal()
            try:
                today = datetime.now().date()

                rows = (
                    db.query(
                        Trade.symbol,
                        Trade.profit_loss,
                        Trade.entry_price,
                        Trade.exit_price,
                        Trade.quantity,
                        Trade.timestamp,
                    )
                    .filter(
                        Trade.timestamp >= today,
                        Trade.symbol.in_(self._allowed_symbols),
                    )
                    .all()
                )

                from app.services.binance_client_singleton import (
                    get_binance_client_singleton,
                )

                client_singleton = get_binance_client_singleton()

                def detect_quote(symbol: Optional[str]) -> Optional[str]:
                    if not symbol:
                        return None
                    quotes = [
                        "USDT",
                        "BUSD",
                        "USDC",
                        "TUSD",
                        "FDUSD",
                        "DAI",
                        "BTC",
                        "ETH",
                        "BNB",
                    ]
                    for q in quotes:
                        if symbol.upper().endswith(q):
                            return q
                    return None

                def to_usdt(amount_in_quote: float, quote: Optional[str]) -> float:
                    if amount_in_quote == 0.0 or not quote:
                        return amount_in_quote
                    if quote in {"USDT", "BUSD", "USDC", "TUSD", "FDUSD", "DAI"}:
                        return amount_in_quote
                    if quote == "BTC":
                        px = client_singleton.get_symbol_price("BTCUSDT")
                        return amount_in_quote * (px or 0.0)
                    if quote == "ETH":
                        px = client_singleton.get_symbol_price("ETHUSDT")
                        return amount_in_quote * (px or 0.0)
                    if quote == "BNB":
                        px = client_singleton.get_symbol_price("BNBUSDT")
                        return amount_in_quote * (px or 0.0)
                    return 0.0

                daily_profit_usdt = 0.0
                for symbol, profit_loss, entry_price, exit_price, qty, _ in rows:
                    if profit_loss is None:
                        continue
                    quote = detect_quote(symbol)
                    daily_profit_usdt += to_usdt(float(profit_loss), quote)
                return daily_profit_usdt
            finally:
                db.close()

        except Exception as e:
            logger.error(f"Error calculando ganancia diaria: {e}")
            return 0.0

    async def _calculate_daily_roi(
        self, daily_profit: float, portfolio_value: float
    ) -> float:
        """
        Calcula el ROI diario en porcentaje
        """
        try:
            if portfolio_value <= 0:
                return 0.0
            # ROI base: snapshot al inicio de día (UTC), persistido en cache
            date_key = datetime.utcnow().date().isoformat()
            cache_key = f"roi:base:{date_key}"
            try:
                base_raw = await self._cache.get(cache_key)
                if not base_raw:
                    await self._cache.set(
                        cache_key, str(portfolio_value), ttl_seconds=60 * 60 * 30
                    )  # 30h
                    base_value = portfolio_value
                    trading_metrics.set_initial_portfolio_value(portfolio_value)
                else:
                    try:
                        base_value = float(base_raw)
                    except Exception:
                        base_value = portfolio_value
            except Exception:
                # Fallback si cache falla
                if self.initial_portfolio_value is None:
                    self.initial_portfolio_value = portfolio_value
                base_value = self.initial_portfolio_value
            if base_value <= 0:
                return 0.0
            roi = (daily_profit / base_value) * 100.0
            roi = max(-100.0, min(100.0, roi))
            return roi

        except Exception as e:
            logger.error(f"Error calculando ROI diario: {e}")
            return 0.0

    async def _calculate_asset_metrics(
        self, balances: Dict[str, float]
    ) -> Dict[str, Dict]:
        """
        Calcula métricas por activo usando consultas optimizadas
        """
        try:
            asset_metrics = {}
            db = SessionLocal()

            try:
                # ✅ FASE 5: Optimización - Query combinada para todos los assets en una sola consulta
                from sqlalchemy import func

                # Obtener símbolos de assets que tienen balance
                symbols_to_query = [
                    f"{asset}USDT"
                    for asset in ["BTC", "ETH", "BNB"]
                    if asset in balances and balances[asset] > 0
                ]

                if not symbols_to_query:
                    return asset_metrics

                # Query combinada: obtener sumas de BUY y SELL por símbolo en una sola consulta
                results = (
                    db.query(
                        Trade.symbol,
                        Trade.side,
                        func.sum(Trade.quantity * Trade.entry_price).label(
                            "total_value"
                        ),
                    )
                    .filter(Trade.symbol.in_(symbols_to_query))
                    .group_by(Trade.symbol, Trade.side)
                    .all()
                )

                # Procesar resultados
                asset_data = {}
                for symbol, side, total_value in results:
                    asset = symbol.replace("USDT", "")
                    if asset not in asset_data:
                        asset_data[asset] = {"buy": 0.0, "sell": 0.0}
                    asset_data[asset][side.lower()] = float(total_value or 0.0)

                # Calcular métricas para cada asset
                for asset in ["BTC", "ETH", "BNB"]:
                    if asset in balances and balances[asset] > 0:
                        data = asset_data.get(asset, {"buy": 0.0, "sell": 0.0})
                        asset_investment = data["buy"]
                        asset_profit = data["sell"]
                        net_profit = asset_profit - asset_investment

                        # Calcular ROI del activo
                        asset_roi = 0.0
                        if asset_investment > 0:
                            asset_roi = (net_profit / asset_investment) * 100

                        asset_metrics[asset] = {
                            "profit": net_profit,
                            "roi": asset_roi,
                            "balance": balances[asset],
                        }

                return asset_metrics
            finally:
                db.close()

        except Exception as e:
            logger.error(f"Error calculando métricas por activo: {e}")
            return {}

    def _update_prometheus_metrics(
        self,
        total_profit: float,
        portfolio_value: float,
        daily_profit: float,
        roi_daily: float,
        asset_metrics: Dict[str, Dict],
    ):
        """
        Actualiza todas las métricas en Prometheus
        """
        try:
            # Métricas principales
            trading_metrics.update_profit_metrics(
                total_profit=total_profit,
                portfolio_value=portfolio_value,
                strategy="grid",
            )
            # Forzar publicación de ROI diario y ganancia diaria (evitar "No data")
            try:
                profit_daily_usdt.labels(strategy="grid").set(float(daily_profit))
                roi_daily_percent.labels(strategy="grid").set(float(roi_daily))
            except Exception:
                pass

            # Métricas por activo
            for asset, metrics in asset_metrics.items():
                trading_metrics.update_asset_profit(
                    asset=f"{asset}USDT",
                    profit=metrics["profit"],
                    roi=metrics["roi"],
                    strategy="grid",
                )

            # Actualizar estado del bot
            trading_metrics.update_bot_status(is_active=True, strategy="grid")

            # Incrementar contador de trades en base a DB (diferencias)
            try:
                db = SessionLocal()
                rows = (
                    db.query(Trade.symbol, Trade.side, func.count(Trade.id))
                    .group_by(Trade.symbol, Trade.side)
                    .all()
                )
                total_trades = 0
                successful_trades = 0
                for symbol, side, count in rows:
                    total_trades += int(count)
                    # Delta contra último valor
                    key = (symbol, side)
                    previous = self._last_trades_count_by_symbol_side.get(key, 0)
                    delta = int(count) - int(previous)
                    if delta > 0:
                        trading_metrics.trades_executed_total.labels(
                            side=side, asset=symbol, strategy="grid"
                        ).inc(delta)
                        self._last_trades_count_by_symbol_side[key] = int(count)

                # Calcular tasa de éxito global (0-1)
                successful_trades = (
                    db.query(func.count(Trade.id))
                    .filter(Trade.profit_loss.isnot(None), Trade.profit_loss > 0)
                    .scalar()
                    or 0
                )
                if total_trades > 0:
                    trading_metrics.trades_success_rate.labels(strategy="grid").set(
                        successful_trades / total_trades
                    )
                db.close()
            except Exception as e:
                logger.warning(
                    f"No se pudo actualizar trades_executed_total/trades_success_rate: {e}"
                )

            logger.info(
                f"✅ Métricas actualizadas: Profit=${total_profit:.2f}, Portfolio=${portfolio_value:.2f}, ROI={roi_daily:.2f}%"
            )

        except Exception as e:
            logger.error(f"Error actualizando métricas de Prometheus: {e}")
            trading_metrics.record_error("prometheus_update_error")

    async def record_trade_execution(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        success: bool,
        execution_time: float,
    ):
        """
        Registra la ejecución de un trade
        """
        try:
            volume_usdt = quantity * price

            trading_metrics.record_trade(
                side=side,
                asset=symbol,
                success=success,
                volume_usdt=volume_usdt,
                execution_time=execution_time,
                strategy="grid",
            )

            logger.info(
                f"📊 Trade registrado: {side} {quantity} {symbol} @ ${price} - {'✅' if success else '❌'}"
            )

        except Exception as e:
            logger.error(f"Error registrando trade: {e}")
            trading_metrics.record_error("trade_recording_error")

    async def update_balance_metrics(self, balances: Dict[str, float]):
        """
        Actualiza métricas de saldos
        """
        try:
            trading_metrics.update_balances(balances, strategy="grid")

            # Contar posiciones activas (activos con saldo > 0)
            active_positions = sum(1 for balance in balances.values() if balance > 0)
            trading_metrics.update_active_positions(active_positions, strategy="grid")

        except Exception as e:
            logger.error(f"Error actualizando métricas de saldos: {e}")
            trading_metrics.record_error("balance_metrics_error")


# Instancia global del servicio
metrics_service = MetricsService()
