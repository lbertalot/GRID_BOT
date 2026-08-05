"""
Trade Executor con actualización automática de balances
Wrapper around Binance orders que integra BalanceService
"""

import logging
import time
import asyncio
import requests
import concurrent.futures
from decimal import Decimal
from typing import Dict, Any, Optional, Union
from sqlalchemy.orm import Session
from app.core.binance_proxy import get_binance_proxies
from app.core.metrics import gridbot_trade_executor_order_path_total
from app.services.binance_client_singleton import get_binance_client_singleton
from app.services.balance_service import BalanceService
from app.services.broker_adapter import (
    BrokerMarketOrderRequest,
    create_broker_adapter_from_env,
    use_broker_adapter_for_trade_execution_from_env,
)
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


def _sync_run_async_coroutine(coroutine):
    """Ejecuta una corrutina en un hilo con loop propio (evita conflictos si hay loop activo)."""

    def _runner():
        return asyncio.run(coroutine)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_runner).result(timeout=180)


def _trade_executor_adapter_kwargs_ok(kwargs: Dict[str, Any]) -> bool:
    allowed = {"recvWindow", "newClientOrderId"}
    return set(kwargs.keys()).issubset(allowed)


class TradeExecutor:
    """
    Ejecutor de trades que mantiene sincronizados los balances internos
    """

    def __init__(self):
        self.binance_client = get_binance_client_singleton()
        self.balance_service = BalanceService()

    def _finalize_order(
        self,
        symbol: str,
        side: str,
        quantity: str,
        order_result: Dict[str, Any],
        db: Optional[Session] = None,
        update_balance: bool = True,
    ) -> Dict[str, Any]:
        if not order_result or order_result.get("status") not in [
            "FILLED",
            "PARTIALLY_FILLED",
        ]:
            logger.warning(f"⚠️ Orden no ejecutada completamente: {order_result}")
            return order_result

        if update_balance:
            self._update_balances_after_trade(
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_result=order_result,
                db=db,
            )

        logger.info(
            f"✅ Orden ejecutada: {side} {quantity} {symbol} - OrderID: {order_result.get('orderId')}"
        )
        return order_result

    def _execute_market_via_broker_adapter(
        self,
        *,
        symbol: str,
        side: str,
        quantity: str,
        recv_window: int,
        client_order_id: str | None,
    ) -> Dict[str, Any]:
        side_u = side.upper()
        if side_u not in ("BUY", "SELL"):
            raise ValueError(f"Lado inválido para BrokerAdapter: {side!r}")

        async def _run() -> Dict[str, Any]:
            adapter = create_broker_adapter_from_env()
            req = BrokerMarketOrderRequest(
                symbol_code=symbol.upper(),
                side=side_u,  # type: ignore[arg-type]
                quantity_base=Decimal(str(quantity)),
                client_order_id=client_order_id,
                recv_window_ms=recv_window,
            )
            ack = await adapter.place_market_order(req)
            raw = ack.raw
            if not isinstance(raw, dict):
                raise TypeError("BrokerAdapter devolvió raw inválido")
            return raw

        return _sync_run_async_coroutine(_run())

    def execute_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Union[Decimal, str],
        db: Optional[Session] = None,
        update_balance: bool = True,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Ejecuta una orden y actualiza balances automáticamente

        Args:
            symbol: Par de trading (ej: "BTCUSDT")
            side: "BUY" o "SELL"
            order_type: "MARKET", "LIMIT", etc.
            quantity: Cantidad a comprar/vender
            db: Sesión de BD (opcional, se crea una si no se provee)
            update_balance: Si True, actualiza balances automáticamente
            **kwargs: Parámetros adicionales para la orden (price, etc.)

        Returns:
            Respuesta de Binance con información de la orden

        Raises:
            Exception si la orden falla
        """
        try:
            # ── GUARD DE SEGURIDAD: verificar Circuit Breakers antes de enviar ──
            # Si cualquier breaker está activo, rechazar la orden inmediatamente.
            # Esto es la última línea de defensa antes de Binance.
            try:
                from app.core.circuit_breakers import CircuitBreakers as _CB

                _cb = _CB()
                if _cb.is_trading_halted():
                    active = _cb.get_all_breakers_status().get("active_breakers", [])
                    logger.error(
                        f"🚨 ORDEN BLOQUEADA por Circuit Breakers activos {active}: "
                        f"{side} {quantity} {symbol}"
                    )
                    raise ValueError(
                        f"Circuit Breaker activo {active}: trading detenido por seguridad"
                    )
            except ValueError:
                raise
            except Exception as cb_err:
                logger.warning(
                    f"[Guard] No se pudo verificar circuit breakers: {cb_err}"
                )

            merged_kwargs: Dict[str, Any] = dict(kwargs)
            merged_kwargs.setdefault("recvWindow", 10000)

            if (
                order_type == "MARKET"
                and "timestamp" not in merged_kwargs
                and use_broker_adapter_for_trade_execution_from_env()
                and _trade_executor_adapter_kwargs_ok(merged_kwargs)
            ):
                try:
                    order_result = self._execute_market_via_broker_adapter(
                        symbol=symbol,
                        side=side,
                        quantity=quantity,
                        recv_window=int(merged_kwargs["recvWindow"]),
                        client_order_id=merged_kwargs.get("newClientOrderId"),
                    )
                    gridbot_trade_executor_order_path_total.labels(
                        path="broker_adapter"
                    ).inc()
                    return self._finalize_order(
                        symbol,
                        side,
                        quantity,
                        order_result,
                        db,
                        update_balance,
                    )
                except Exception as adapter_err:
                    if "-1021" not in str(adapter_err):
                        raise
                    logger.warning(
                        "BrokerAdapter falló con desfase -1021; "
                        "reintento vía cliente legacy: %s",
                        adapter_err,
                    )

            logger.info(
                f"🔄 Ejecutando orden: {side} {quantity} {symbol} ({order_type})"
            )
            try:
                order_result = self.binance_client.create_order(
                    symbol=symbol,
                    side=side,
                    order_type=order_type,
                    quantity=quantity,
                    **merged_kwargs,
                )
            except Exception as e:
                # Mitigación de error -1021: reintentar sincronizando tiempo
                if "-1021" in str(e):
                    try:
                        try:
                            asyncio.get_running_loop()
                            import concurrent.futures as _cf

                            _proxies = get_binance_proxies()
                            _kw: Dict[str, Any] = {"timeout": 3}
                            if _proxies:
                                _kw["proxies"] = _proxies
                            with _cf.ThreadPoolExecutor() as executor:
                                future = executor.submit(
                                    lambda: requests.get(
                                        "https://api.binance.com/api/v3/time", **_kw
                                    ).json()["serverTime"]
                                )
                                srv_time = future.result()
                        except RuntimeError:
                            _proxies = get_binance_proxies()
                            _kw = {"timeout": 3}
                            if _proxies:
                                _kw["proxies"] = _proxies
                            srv_time = requests.get(
                                "https://api.binance.com/api/v3/time", **_kw
                            ).json()["serverTime"]

                        now_ms = int(time.time() * 1000)
                        drift = abs(now_ms - int(srv_time))
                        if drift > 1000:
                            time.sleep(1.0)
                        merged_kwargs["timestamp"] = int(time.time() * 1000)
                        order_result = self.binance_client.create_order(
                            symbol=symbol,
                            side=side,
                            order_type=order_type,
                            quantity=quantity,
                            **merged_kwargs,
                        )
                    except Exception as ee:
                        logger.error(f"❌ Reintento tras -1021 falló: {ee}")
                        raise
                else:
                    raise

            gridbot_trade_executor_order_path_total.labels(path="legacy").inc()
            return self._finalize_order(
                symbol, side, quantity, order_result, db, update_balance
            )

        except Exception as e:
            logger.error(f"❌ Error ejecutando orden {side} {quantity} {symbol}: {e}")
            raise

    def _update_balances_after_trade(
        self,
        symbol: str,
        side: str,
        quantity: str,
        order_result: Dict[str, Any],
        db: Optional[Session] = None,
    ):
        """
        Actualiza balances internos después de un trade exitoso

        Args:
            symbol: Par de trading (ej: "BTCUSDT")
            side: "BUY" o "SELL"
            quantity: Cantidad ejecutada
            order_result: Respuesta de Binance
            db: Sesión de BD (opcional)
        """
        try:
            # Crear sesión si no existe
            close_db = False
            if db is None:
                db = SessionLocal()
                close_db = True

            try:
                # Extraer información de la orden
                executed_qty = Decimal(str(order_result.get("executedQty", quantity)))

                # Calcular precio promedio ponderado
                fills = order_result.get("fills", [])
                if fills:
                    total_cost = Decimal("0")
                    total_qty = Decimal("0")
                    for fill in fills:
                        qty = Decimal(str(fill.get("qty", "0")))
                        price = Decimal(str(fill.get("price", "0")))
                        total_cost += qty * price
                        total_qty += qty
                    avg_price = (
                        total_cost / total_qty if total_qty > 0 else Decimal("0")
                    )
                else:
                    # Si no hay fills, usar el precio de la respuesta
                    avg_price = Decimal(str(order_result.get("price", "0")))
                    if avg_price == 0:
                        # Si no hay precio, intentar obtenerlo del mercado
                        ticker = self.binance_client.get_symbol_ticker(symbol)
                        avg_price = Decimal(str(ticker.get("price", "0")))

                # Extraer activos del símbolo (ej: BTCUSDT -> base=BTC, quote=USDT)
                base_asset = symbol[
                    :-4
                ]  # Asume que quote es siempre USDT de 4 caracteres
                quote_asset = symbol[-4:]  # USDT

                # Calcular costo total (incluyendo comisión)
                commission = Decimal("0")
                commission_asset = quote_asset

                if fills:
                    for fill in fills:
                        comm = Decimal(str(fill.get("commission", "0")))
                        comm_asset = fill.get("commissionAsset", quote_asset)
                        if comm_asset == commission_asset:
                            commission += comm

                total_cost = executed_qty * avg_price

                # Actualizar balances según el lado
                if side == "BUY":
                    # BUY: -USDT, +Asset
                    cost_with_commission = total_cost + commission
                    BalanceService.update_balance(
                        db, quote_asset, -cost_with_commission
                    )
                    BalanceService.update_balance(db, base_asset, executed_qty)
                    logger.info(
                        f"💰 Balances actualizados (BUY): "
                        f"{quote_asset} -{cost_with_commission:.8f}, "
                        f"{base_asset} +{executed_qty:.8f}"
                    )

                elif side == "SELL":
                    # SELL: +USDT, -Asset
                    proceeds = total_cost - commission
                    BalanceService.update_balance(db, base_asset, -executed_qty)
                    BalanceService.update_balance(db, quote_asset, proceeds)
                    logger.info(
                        f"💰 Balances actualizados (SELL): "
                        f"{base_asset} -{executed_qty:.8f}, "
                        f"{quote_asset} +{proceeds:.8f}"
                    )

            finally:
                if close_db:
                    db.close()

        except Exception as e:
            logger.error(f"❌ Error actualizando balances después del trade: {e}")
            # No re-raise: la orden ya se ejecutó en Binance
            # Solo loguear el error para investigar
            import traceback

            traceback.print_exc()

    def execute_market_buy(
        self, symbol: str, quantity: Union[Decimal, str], db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Shortcut para orden MARKET BUY"""
        return self.execute_order(symbol, "BUY", "MARKET", quantity, db=db)

    def execute_market_sell(
        self, symbol: str, quantity: Union[Decimal, str], db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Shortcut para orden MARKET SELL"""
        return self.execute_order(symbol, "SELL", "MARKET", quantity, db=db)

    def execute_limit_buy(
        self,
        symbol: str,
        quantity: Union[Decimal, str],
        price: Union[Decimal, str],
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Shortcut para orden LIMIT BUY"""
        return self.execute_order(
            symbol, "BUY", "LIMIT", quantity, price=price, db=db, timeInForce="GTC"
        )

    def execute_limit_sell(
        self,
        symbol: str,
        quantity: Union[Decimal, str],
        price: Union[Decimal, str],
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Shortcut para orden LIMIT SELL"""
        return self.execute_order(
            symbol, "SELL", "LIMIT", quantity, price=price, db=db, timeInForce="GTC"
        )


# Instancia global
trade_executor = TradeExecutor()


def get_trade_executor() -> TradeExecutor:
    """Obtiene la instancia global del trade executor"""
    return trade_executor
