"""
OrderValidator — Validación estricta de órdenes contra filtros del exchange.

Contrato: CTR-001
Invariantes: INV-001 (Decimal obligatorio), INV-002 (filtros pre-orden)

Todos los valores monetarios (precios, cantidades, notional, filtros) son Decimal.
"""

from decimal import Decimal, ROUND_DOWN, getcontext, InvalidOperation
import logging
from typing import Dict, Any, Optional

from binance import Client
from binance.exceptions import BinanceAPIException

logger = logging.getLogger(__name__)

# Contexto de precisión global para cálculos monetarios
getcontext().prec = 28


def _to_decimal(value: Any) -> Decimal:
    """Convierte un valor a Decimal de forma segura, pasando por str para evitar imprecisión de float."""
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def _step_precision(step: Decimal) -> int:
    """Calcula la cantidad de decimales de un step (e.g., 0.0001 -> 4)."""
    if step <= 0:
        return 0
    sign, digits, exponent = step.normalize().as_tuple()
    return max(0, -exponent)


class OrderValidator:
    """Valida y ajusta parámetros de órdenes contra filtros del exchange (PRICE_FILTER, LOT_SIZE, MIN_NOTIONAL).

    Todos los valores internos y retornados son Decimal (INV-001).
    """

    def __init__(self, client: Client):
        self.client = client
        self._symbol_info_cache: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Cache de symbol info
    # ------------------------------------------------------------------

    def get_symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Obtiene info de un símbolo con filtros parseados como Decimal."""
        try:
            if symbol not in self._symbol_info_cache:
                try:
                    exchange_info = self.client.get_exchange_info(use_cache=True)
                except TypeError:
                    exchange_info = self.client.get_exchange_info()

                for s in exchange_info.get("symbols", []):
                    if s["symbol"] == symbol.upper():
                        filters = {f["filterType"]: f for f in s.get("filters", [])}

                        lot = filters.get("LOT_SIZE", {})
                        price_filter = filters.get("PRICE_FILTER", {})

                        # Usar notional filter (puede ser NOTIONAL o MIN_NOTIONAL según versión de API)
                        notional_filter = filters.get("NOTIONAL", filters.get("MIN_NOTIONAL", {}))

                        self._symbol_info_cache[symbol] = {
                            "symbol": s["symbol"],
                            "baseAsset": s.get("baseAsset", ""),
                            "quoteAsset": s.get("quoteAsset", ""),
                            "stepSize": _to_decimal(lot.get("stepSize", "0.001")),
                            "minQty": _to_decimal(lot.get("minQty", "0.001")),
                            "maxQty": _to_decimal(lot.get("maxQty", "1000000")),
                            "minNotional": _to_decimal(
                                notional_filter.get("minNotional", "5")
                            ),
                            "tickSize": _to_decimal(price_filter.get("tickSize", "0.01")),
                            "minPrice": _to_decimal(price_filter.get("minPrice", "0")),
                            "maxPrice": _to_decimal(price_filter.get("maxPrice", "0")),
                            "pricePrecision": s.get("quotePrecision", 8),
                            "quantityPrecision": s.get("baseAssetPrecision", 8),
                        }
                        break
            return self._symbol_info_cache.get(symbol)
        except Exception as e:
            logger.error(f"Error obteniendo información del símbolo {symbol}: {e}")
            return None

    # ------------------------------------------------------------------
    # Redondeo a step/tick
    # ------------------------------------------------------------------

    def _round_to_step(self, value: Any, step: Any) -> Decimal:
        """Redondea hacia abajo al múltiplo más cercano de step (INV-001).

        Acepta float o Decimal como entrada; retorna siempre Decimal.
        """
        v = _to_decimal(value)
        s = _to_decimal(step)
        if s <= 0:
            return v
        units = (v / s).to_integral_value(rounding=ROUND_DOWN)
        return units * s

    def _round_to_tick(self, price: Any, tick: Any) -> Decimal:
        """Redondea precio hacia abajo al múltiplo más cercano de tick (INV-001).

        Acepta float o Decimal como entrada; retorna siempre Decimal.
        """
        p = _to_decimal(price)
        t = _to_decimal(tick)
        if t <= 0:
            return p
        units = (p / t).to_integral_value(rounding=ROUND_DOWN)
        return units * t

    # ------------------------------------------------------------------
    # Ajuste de cantidad
    # ------------------------------------------------------------------

    def adjust_quantity_precision(self, quantity: Any, symbol: str) -> Dict[str, Any]:
        """Ajusta cantidad a la precisión del exchange. Retorna todo en Decimal."""
        try:
            qty = _to_decimal(quantity)
            symbol_info = self.get_symbol_info(symbol)

            if not symbol_info:
                step_size = Decimal("0.001")
                min_qty = Decimal("0.001")
                max_qty = Decimal("1000000")
                min_notional = Decimal("5")
            else:
                step_size = symbol_info["stepSize"]
                min_qty = symbol_info["minQty"]
                max_qty = symbol_info.get("maxQty", Decimal("1000000"))
                min_notional = symbol_info["minNotional"]

            adjusted = self._round_to_step(qty, step_size)

            if adjusted < min_qty:
                adjusted = min_qty
            if adjusted > max_qty:
                adjusted = max_qty

            precision = _step_precision(step_size)
            adjusted = adjusted.quantize(Decimal(10) ** -precision, rounding=ROUND_DOWN)

            return {
                "original_quantity": qty,
                "adjusted_quantity": adjusted,
                "step_size": step_size,
                "min_qty": min_qty,
                "max_qty": max_qty,
                "min_notional": min_notional,
                "precision": precision,
                "symbol_info": symbol_info,
            }
        except Exception as e:
            logger.error(f"Error ajustando precisión de cantidad: {e}")
            qty_fallback = _to_decimal(quantity)
            return {
                "original_quantity": qty_fallback,
                "adjusted_quantity": qty_fallback,
                "step_size": Decimal("0.001"),
                "min_qty": Decimal("0.001"),
                "max_qty": Decimal("1000000"),
                "min_notional": Decimal("5"),
                "precision": 3,
                "symbol_info": None,
                "error": str(e),
            }

    # ------------------------------------------------------------------
    # Validación completa de parámetros
    # ------------------------------------------------------------------

    def validate_order_parameters(
        self,
        symbol: str,
        quantity: Any,
        side: str,
        order_type: str = "MARKET",
        price: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Valida parámetros de una orden (CTR-001).

        - Ajusta cantidad a stepSize.
        - Ajusta precio (LIMIT) a tickSize y valida rangos.
        - Valida minQty/maxQty y minNotional.
        - Todos los campos monetarios son Decimal (INV-001).
        """
        try:
            quantity_info = self.adjust_quantity_precision(quantity, symbol)

            # Obtener precio actual del mercado
            ticker = self.client.get_symbol_ticker(symbol=symbol.upper())
            current_price = _to_decimal(ticker["price"])

            # Información del símbolo
            symbol_info = quantity_info["symbol_info"] or {}
            tick_size = _to_decimal(symbol_info.get("tickSize", "0.01") or "0.01")
            min_price = _to_decimal(symbol_info.get("minPrice", "0") or "0")
            max_price = _to_decimal(symbol_info.get("maxPrice", "0") or "0")

            adjusted_price: Optional[Decimal] = None

            if order_type.upper() == "LIMIT":
                if price is None:
                    raise ValueError("Precio requerido para órdenes LIMIT")
                raw_price = _to_decimal(price)
                adjusted_price = self._round_to_tick(raw_price, tick_size)
                if min_price > 0 and adjusted_price < min_price:
                    raise ValueError(
                        f"Precio {adjusted_price} menor que mínimo permitido {min_price}"
                    )
                if max_price > 0 and adjusted_price > max_price:
                    raise ValueError(
                        f"Precio {adjusted_price} mayor que máximo permitido {max_price}"
                    )
            else:
                adjusted_price = current_price

            # Calcular notional con Decimal (INV-001)
            notional_value = quantity_info["adjusted_quantity"] * adjusted_price

            errors: list[str] = []
            warnings: list[str] = []

            if quantity_info["adjusted_quantity"] < quantity_info["min_qty"]:
                errors.append(
                    f"Cantidad {quantity_info['adjusted_quantity']} menor al mínimo {quantity_info['min_qty']}"
                )
            if quantity_info["adjusted_quantity"] > quantity_info["max_qty"]:
                errors.append(
                    f"Cantidad {quantity_info['adjusted_quantity']} supera el máximo {quantity_info['max_qty']}"
                )
            # INV-002: validar minNotional DESPUÉS del redondeo
            if notional_value < quantity_info["min_notional"]:
                errors.append(
                    f"Valor notional {notional_value} menor al mínimo {quantity_info['min_notional']}"
                )

            if quantity_info["original_quantity"] != quantity_info["adjusted_quantity"]:
                warnings.append(
                    f"Cantidad ajustada de {quantity_info['original_quantity']} a {quantity_info['adjusted_quantity']} por stepSize"
                )
            if order_type.upper() == "LIMIT" and adjusted_price != _to_decimal(price):
                warnings.append(
                    f"Precio ajustado de {_to_decimal(price)} a {adjusted_price} por tickSize {tick_size}"
                )

            return {
                "is_valid": len(errors) == 0,
                "errors": errors,
                "warnings": warnings,
                "quantity_info": quantity_info,
                "current_price": current_price,
                "adjusted_price": adjusted_price,
                "notional_value": notional_value,
                "recommended_quantity": quantity_info["adjusted_quantity"],
            }
        except Exception as e:
            logger.error(f"Error validando parámetros de orden: {e}")
            return {
                "is_valid": False,
                "errors": [f"Error en validación: {e}"],
                "warnings": [],
                "quantity_info": None,
                "current_price": None,
                "adjusted_price": None,
                "notional_value": None,
                "recommended_quantity": None,
            }

    # ------------------------------------------------------------------
    # Orden de mercado con validación integrada
    # ------------------------------------------------------------------

    def place_market_order_with_validation(
        self, symbol: str, side: str, quantity: Any
    ) -> Dict[str, Any]:
        """Coloca orden de mercado solo si pasa validación completa (INV-002)."""
        try:
            qty = _to_decimal(quantity)
            validation = self.validate_order_parameters(symbol, qty, side, "MARKET")

            if not validation["is_valid"]:
                error_msg = f"Parámetros inválidos para {side} {qty} {symbol}: "
                error_msg += "; ".join(validation["errors"])
                raise ValueError(error_msg)

            adjusted_quantity = validation["quantity_info"]["adjusted_quantity"]

            # Convertir a float solo para la API de Binance (punto final de salida)
            qty_for_api = float(adjusted_quantity)

            if side.upper() == "BUY":
                result = self.client.order_market_buy(
                    symbol=symbol.upper(), quantity=qty_for_api
                )
            elif side.upper() == "SELL":
                result = self.client.order_market_sell(
                    symbol=symbol.upper(), quantity=qty_for_api
                )
            else:
                raise ValueError(f"Lado de orden inválido: {side}")

            return {
                "order": result,
                "validation": validation,
                "executed_quantity": adjusted_quantity,
                "action_details": {
                    "symbol": symbol.upper(),
                    "side": side.upper(),
                    "original_quantity": qty,
                    "adjusted_quantity": adjusted_quantity,
                    "current_price": validation["current_price"],
                    "notional_value": validation["notional_value"],
                },
            }

        except BinanceAPIException as e:
            error_details = self._format_binance_error(e, symbol, side, qty)
            raise ValueError(error_details)
        except Exception as e:
            logger.error(f"Error colocando orden de mercado: {e}")
            raise

    # ------------------------------------------------------------------
    # Formato de errores de Binance
    # ------------------------------------------------------------------

    def _format_binance_error(
        self, e: BinanceAPIException, symbol: str, side: str, quantity: Any
    ) -> str:
        """Formatea errores de Binance con sugerencias."""
        error_code = getattr(e, "code", "N/A")
        error_message = getattr(e, "message", str(e))

        if error_code == -1111:
            symbol_info = self.get_symbol_info(symbol)
            if symbol_info:
                step_size = symbol_info["stepSize"]
                min_qty = symbol_info["minQty"]
                qty = _to_decimal(quantity)
                recommended_qty = self._round_to_step(qty, step_size)
                if recommended_qty < min_qty:
                    recommended_qty = min_qty

                return (
                    f"Error de precisión: {symbol.upper()} {side.upper()} qty={quantity} | "
                    f"stepSize={step_size} minQty={min_qty} recomendado={recommended_qty} | "
                    f"code={error_code}: {error_message}"
                )

        error_labels = {
            -2010: "Balance insuficiente",
            -2011: "Error de precio",
        }
        label = error_labels.get(error_code, "Error de Binance API")

        return (
            f"{label}: {symbol.upper()} {side.upper()} qty={quantity} | "
            f"code={error_code}: {error_message}"
        )
