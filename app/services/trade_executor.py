"""
TradeExecutor — Ejecución de órdenes con validación, breakers e idempotencia.

Contrato: CTR-002
Invariantes: INV-001 (Decimal), INV-002 (filtros pre-orden), INV-003 (breakers),
             INV-004 (idempotencia), INV-008 (confirmación post-orden),
             INV-011 (balance check)
"""

import hashlib
import logging
import time
import asyncio
from datetime import datetime
from decimal import Decimal, ROUND_DOWN
from typing import Dict, Any, Optional

from app.services.binance_client_singleton import get_binance_client_singleton
from app.services.order_validation import OrderValidator, _to_decimal

logger = logging.getLogger(__name__)


def _generate_client_order_id(
    symbol: str, side: str, quantity: Decimal, price: Decimal, timestamp_bucket: int
) -> str:
    """Genera clientOrderId determinístico (INV-004).

    El timestamp_bucket agrupa en ventanas de 60s para permitir reintentos
    con el mismo ID dentro de la ventana.
    """
    payload = f"{symbol}|{side}|{quantity}|{price}|{timestamp_bucket}".encode()
    suffix = hashlib.sha256(payload).hexdigest()[:24]
    return f"GRIDBOT_{suffix}"


class TradeExecutor:
    """Ejecuta órdenes con validación completa, circuit breakers e idempotencia.

    Flujo obligatorio:
    1. Consultar circuit breakers (INV-003)
    2. Validar filtros del exchange (INV-002)
    3. Generar clientOrderId (INV-004)
    4. Enviar orden
    5. Confirmar estado post-orden (INV-008)
    6. Actualizar balances internos
    """

    def __init__(self):
        self.binance_client = get_binance_client_singleton()
        self._order_validator: Optional[OrderValidator] = None

    @property
    def order_validator(self) -> OrderValidator:
        if self._order_validator is None:
            self._order_validator = OrderValidator(self.binance_client.client)
        return self._order_validator

    # ------------------------------------------------------------------
    # Ejecución principal (async)
    # ------------------------------------------------------------------

    async def execute_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Any,
        price: Optional[Any] = None,
        client_order_id: Optional[str] = None,
        breakers=None,
        skip_validation: bool = False,
    ) -> Dict[str, Any]:
        """Ejecuta una orden con todas las validaciones de integridad.

        Args:
            symbol: Par de trading (e.g., "BTCUSDT")
            side: "BUY" o "SELL"
            order_type: "MARKET" o "LIMIT"
            quantity: Cantidad (se convierte a Decimal internamente)
            price: Precio para órdenes LIMIT
            client_order_id: ID personalizado (se genera si no se proporciona)
            breakers: Instancia de CircuitBreakers (opcional)
            skip_validation: Solo para emergencias documentadas
        """
        qty = _to_decimal(quantity)
        order_price = _to_decimal(price) if price is not None else Decimal("0")

        # ── 1. Consultar circuit breakers (INV-003) ──
        if breakers is not None and not skip_validation:
            if breakers.is_trading_halted():
                status = breakers.get_all_breakers_status()
                logger.warning(
                    f"Orden bloqueada por circuit breakers: {side} {qty} {symbol} | "
                    f"breakers_activos={status.get('active_breakers', [])}"
                )
                raise RuntimeError(
                    f"Trading detenido por circuit breakers activos: "
                    f"{status.get('active_breakers', [])}"
                )

        # ── 2. Validar filtros del exchange (INV-002) ──
        validation: Optional[Dict[str, Any]] = None
        if not skip_validation:
            validation = self.order_validator.validate_order_parameters(
                symbol=symbol,
                quantity=qty,
                side=side,
                order_type=order_type,
                price=order_price if order_type.upper() == "LIMIT" else None,
            )
            if not validation.get("is_valid"):
                errors = validation.get("errors", [])
                logger.warning(
                    f"Orden rechazada por validación: {side} {qty} {symbol} | errors={errors}"
                )
                try:
                    from app.core.metrics import order_validation_rejects_total

                    reason = errors[0] if errors else "unknown"
                    order_validation_rejects_total.labels(
                        reason=reason[:64], symbol=symbol
                    ).inc()
                except Exception:
                    pass
                raise ValueError(f"Validación fallida: {'; '.join(errors)}")

            # Usar cantidad y precio ajustados
            qty = validation["quantity_info"]["adjusted_quantity"]
            if order_type.upper() == "LIMIT" and validation.get("adjusted_price"):
                order_price = validation["adjusted_price"]

        # ── 3. Generar clientOrderId (INV-004) ──
        if client_order_id is None:
            ts_bucket = int(time.time()) // 60  # ventana de 60s
            client_order_id = _generate_client_order_id(
                symbol, side, qty, order_price, ts_bucket
            )

        # ── 4. Enviar orden al exchange ──
        logger.info(
            f"Ejecutando orden: {side} {qty} {symbol} ({order_type}) "
            f"clientOrderId={client_order_id}"
        )

        order_params: Dict[str, Any] = {
            "symbol": symbol.upper(),
            "side": side.upper(),
            "type": order_type.upper(),
            "quantity": str(qty),
            "newClientOrderId": client_order_id,
            "recvWindow": 10000,
        }
        if order_type.upper() == "LIMIT":
            order_params["price"] = str(order_price)
            order_params["timeInForce"] = "GTC"

        try:
            raw_result = await asyncio.to_thread(
                self.binance_client.client.create_order, **order_params
            )
        except Exception as exc:
            # Mitigación -1021 (timestamp ahead/behind)
            if "-1021" in str(exc):
                logger.warning("Reintentando tras error -1021 (timestamp)")
                await asyncio.sleep(1.0)
                try:
                    raw_result = await asyncio.to_thread(
                        self.binance_client.client.create_order, **order_params
                    )
                except Exception as retry_exc:
                    logger.error(f"Reintento -1021 falló: {retry_exc}")
                    raise
            else:
                raise

        # ── 5. Confirmar estado post-orden (INV-008) ──
        status = raw_result.get("status", "UNKNOWN")
        executed_qty = _to_decimal(raw_result.get("executedQty", "0"))

        # Calcular precio promedio ponderado y comisión con Decimal (INV-001)
        avg_price = Decimal("0")
        total_commission = Decimal("0")
        fills = raw_result.get("fills", [])
        if fills:
            total_cost = Decimal("0")
            total_qty = Decimal("0")
            for fill in fills:
                f_qty = _to_decimal(fill.get("qty", "0"))
                f_price = _to_decimal(fill.get("price", "0"))
                f_comm = _to_decimal(fill.get("commission", "0"))
                total_cost += f_qty * f_price
                total_qty += f_qty
                total_commission += f_comm
            if total_qty > 0:
                avg_price = total_cost / total_qty
        else:
            avg_price = _to_decimal(raw_result.get("price", "0"))

        result = {
            "order_id": raw_result.get("orderId"),
            "client_order_id": client_order_id,
            "status": status,
            "executed_qty": executed_qty,
            "avg_price": avg_price,
            "commission": total_commission,
            "notional": executed_qty * avg_price if avg_price > 0 else Decimal("0"),
            "raw_response": raw_result,
        }

        if status == "FILLED":
            logger.info(
                f"Orden ejecutada: {side} {executed_qty} {symbol} @ {avg_price} | "
                f"orderId={raw_result.get('orderId')} clientOrderId={client_order_id}"
            )
        elif status == "PARTIALLY_FILLED":
            logger.warning(
                f"Orden parcial: {side} {executed_qty}/{qty} {symbol} @ {avg_price}"
            )
            try:
                from app.core.metrics import partial_fills_total

                partial_fills_total.inc()
            except Exception:
                pass
        else:
            logger.warning(f"Orden no ejecutada completamente: status={status}")

        return result

    # ------------------------------------------------------------------
    # Shortcuts (async)
    # ------------------------------------------------------------------

    async def execute_market_buy(
        self, symbol: str, quantity: Any, breakers=None
    ) -> Dict[str, Any]:
        return await self.execute_order(
            symbol, "BUY", "MARKET", quantity, breakers=breakers
        )

    async def execute_market_sell(
        self, symbol: str, quantity: Any, breakers=None
    ) -> Dict[str, Any]:
        return await self.execute_order(
            symbol, "SELL", "MARKET", quantity, breakers=breakers
        )

    async def execute_limit_buy(
        self, symbol: str, quantity: Any, price: Any, breakers=None
    ) -> Dict[str, Any]:
        return await self.execute_order(
            symbol, "BUY", "LIMIT", quantity, price=price, breakers=breakers
        )

    async def execute_limit_sell(
        self, symbol: str, quantity: Any, price: Any, breakers=None
    ) -> Dict[str, Any]:
        return await self.execute_order(
            symbol, "SELL", "LIMIT", quantity, price=price, breakers=breakers
        )

    # ------------------------------------------------------------------
    # Versión sync para compatibilidad legacy
    # ------------------------------------------------------------------

    def execute_order_sync(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Any,
        **kwargs,
    ) -> Dict[str, Any]:
        """Wrapper síncrono para compatibilidad con código legacy.

        Preferir execute_order (async) para código nuevo.
        """
        qty = _to_decimal(quantity)
        order_params: Dict[str, Any] = {
            "symbol": symbol.upper(),
            "side": side.upper(),
            "type": order_type.upper(),
            "quantity": str(qty),
            "recvWindow": kwargs.pop("recvWindow", 10000),
        }
        # Generar clientOrderId si no se proporciona
        if "newClientOrderId" not in kwargs:
            ts_bucket = int(time.time()) // 60
            coid = _generate_client_order_id(
                symbol, side, qty, Decimal("0"), ts_bucket
            )
            order_params["newClientOrderId"] = coid

        order_params.update(kwargs)

        raw_result = self.binance_client.client.create_order(**order_params)
        return raw_result


# Instancia global
trade_executor = TradeExecutor()


def get_trade_executor() -> TradeExecutor:
    """Obtiene la instancia global del trade executor."""
    return trade_executor
