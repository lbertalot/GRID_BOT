"""
Trading consciente de comisiones para balance bajo
Asegura que las operaciones sean rentables después de comisiones
"""

import logging
from decimal import Decimal
from typing import Dict, Optional, Tuple
from app.services.commission import calculate_commission, validate_minimum_profit

logger = logging.getLogger(__name__)


class CommissionAwareTrading:
    """Trading que considera comisiones en todas las operaciones"""

    def __init__(self):
        self.min_profit_after_commission = 0.5  # 0.5%
        self.commission_rate = 0.001  # 0.1% por operación

    def validate_trade_profitability(
        self, symbol: str, buy_price: float, sell_price: float, quantity: float
    ) -> Tuple[bool, Dict]:
        """
        Valida si una operación será rentable después de comisiones

        Args:
            symbol: Símbolo de trading
            buy_price: Precio de compra
            sell_price: Precio de venta
            quantity: Cantidad

        Returns:
            (es_rentable, detalles)
        """
        try:
            # ✅ FIX: Convertir a Decimal para compatibilidad con funciones actualizadas
            buy_price_dec = Decimal(str(buy_price))
            sell_price_dec = Decimal(str(sell_price))
            quantity_dec = Decimal(str(quantity))
            min_profit_dec = Decimal(str(self.min_profit_after_commission))

            # Calcular ganancia con comisiones
            is_profitable, profit_data = validate_minimum_profit(
                buy_price=buy_price_dec,
                sell_price=sell_price_dec,
                quantity=quantity_dec,
                min_profit_percentage=min_profit_dec,
            )

            # Convertir Decimal a float para logging (compatibilidad)
            net_profit_float = float(profit_data["net_profit"])

            if is_profitable:
                logger.info(
                    f"✅ {symbol}: Operación rentable - Ganancia neta: ${net_profit_float:.4f}"
                )
            else:
                logger.warning(
                    f"⚠️ {symbol}: Operación no rentable - Pérdida neta: ${net_profit_float:.4f}"
                )

            # Convertir valores Decimal a float en el dict para compatibilidad
            profit_data_float = {
                k: float(v) if isinstance(v, Decimal) else v
                for k, v in profit_data.items()
            }
            return is_profitable, profit_data_float

        except Exception as e:
            logger.error(f"Error validando rentabilidad de {symbol}: {e}")
            return False, {"error": str(e)}

    def calculate_optimal_quantity(
        self,
        symbol: str,
        available_usdt: float,
        current_price: float,
        min_notional: float = 10.0,
    ) -> Tuple[float, Dict]:
        """
        Calcula la cantidad óptima considerando comisiones

        Args:
            symbol: Símbolo de trading
            available_usdt: USDT disponible
            current_price: Precio actual
            min_notional: Valor mínimo requerido

        Returns:
            (cantidad_óptima, detalles)
        """
        try:
            # ✅ FIX: Convertir a Decimal para cálculos precisos
            available_usdt_dec = Decimal(str(available_usdt))
            current_price_dec = Decimal(str(current_price))
            min_notional_dec = Decimal(str(min_notional))

            # Calcular cantidad máxima posible
            max_quantity = available_usdt_dec / current_price_dec

            # Calcular comisión para esta cantidad
            notional_value = max_quantity * current_price_dec
            commission = calculate_commission(notional_value, "MARKET", symbol)

            # Ajustar cantidad para incluir comisión
            adjusted_quantity = (
                available_usdt_dec - commission.commission_usdt
            ) / current_price_dec

            # Verificar mínimo notional
            if adjusted_quantity * current_price_dec < min_notional_dec:
                # Calcular cantidad mínima que cumple notional + comisión
                min_quantity = min_notional_dec / current_price_dec
                commission_for_min = calculate_commission(
                    min_notional_dec, "MARKET", symbol
                )
                total_required = min_notional_dec + commission_for_min.commission_usdt

                if total_required > available_usdt_dec:
                    return 0.0, {
                        "error": "Saldo insuficiente para cumplir mínimo notional + comisión",
                        "required": float(total_required),
                        "available": float(available_usdt_dec),
                    }

                adjusted_quantity = min_quantity

            # Convertir Decimal a float para retorno (compatibilidad)
            return float(adjusted_quantity), {
                "original_quantity": float(max_quantity),
                "adjusted_quantity": float(adjusted_quantity),
                "commission": float(commission.commission_usdt),
                "notional_value": float(adjusted_quantity * current_price_dec),
            }

        except Exception as e:
            logger.error(f"Error calculando cantidad óptima para {symbol}: {e}")
            return 0.0, {"error": str(e)}

    def should_execute_trade(
        self,
        symbol: str,
        action: str,
        price: float,
        quantity: float,
        grid_level: Optional[int] = None,
    ) -> Tuple[bool, str]:
        """
        Decide si debe ejecutar una operación

        Args:
            symbol: Símbolo de trading
            action: BUY o SELL
            price: Precio de la operación
            quantity: Cantidad
            grid_level: Nivel de grid (opcional)

        Returns:
            (debe_ejecutar, razón)
        """
        try:
            # Para operaciones de grid, validar rentabilidad
            if grid_level is not None:
                # Simular precio de salida (nivel siguiente)
                if action == "BUY":
                    # Estimar precio de venta en el siguiente nivel
                    estimated_sell_price = price * 1.02  # 2% de ganancia estimada
                    is_profitable, _ = self.validate_trade_profitability(
                        symbol, price, estimated_sell_price, quantity
                    )

                    if not is_profitable:
                        return False, "Operación no rentable después de comisiones"

                elif action == "SELL":
                    # Para ventas, verificar que ya tengamos ganancia
                    # Esto se validaría con el precio de compra original
                    return True, "Venta de posición existente"

            # Para operaciones fuera de grid, ser más conservador
            else:
                if action == "BUY":
                    return (
                        False,
                        "Operaciones fuera de grid deshabilitadas por seguridad",
                    )

            return True, "Operación válida"

        except Exception as e:
            logger.error(f"Error validando ejecución de {symbol}: {e}")
            return False, f"Error de validación: {e}"


# Instancia global
commission_aware_trading = CommissionAwareTrading()
