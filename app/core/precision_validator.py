#!/usr/bin/env python3
"""
Sistema de Validación de Precisión para GridBot V2.5
Evita errores de cantidad en órdenes de Binance
"""

import logging
from decimal import Decimal
from typing import Dict, Optional, Tuple, Union
import json
import os

logger = logging.getLogger(__name__)


class PrecisionValidator:
    """
    Valida y ajusta la precisión de cantidades para Binance
    """

    def __init__(self):
        self.symbol_info_cache = {}
        self.precision_cache = {}
        self.load_precision_cache()

    def load_precision_cache(self):
        """Carga cache de precisión desde archivo"""
        try:
            if os.path.exists("precision_cache.json"):
                with open("precision_cache.json", "r") as f:
                    self.precision_cache = json.load(f)
                logger.info(
                    f"✅ Cache de precisión cargado: {len(self.precision_cache)} símbolos"
                )
        except Exception as e:
            logger.error(f"Error cargando cache de precisión: {e}")

    def save_precision_cache(self):
        """Guarda cache de precisión en archivo"""
        try:
            with open("precision_cache.json", "w") as f:
                json.dump(self.precision_cache, f, indent=2)
        except Exception as e:
            logger.error(f"Error guardando cache de precisión: {e}")

    def get_symbol_precision(self, symbol: str) -> Dict:
        """
        Obtiene la precisión de un símbolo

        Args:
            symbol: Símbolo del trading pair (ej: BTCUSDT)

        Returns:
            Dict con información de precisión
        """
        # Verificar cache primero
        if symbol in self.precision_cache:
            return self.precision_cache[symbol]

        # Precisión por defecto basada en símbolos conocidos
        default_precision = self._get_default_precision(symbol)

        # Guardar en cache
        self.precision_cache[symbol] = default_precision
        self.save_precision_cache()

        return default_precision

    def _get_default_precision(self, symbol: str) -> Dict:
        """
        Obtiene precisión por defecto basada en el símbolo

        Args:
            symbol: Símbolo del trading pair

        Returns:
            Dict con precisión por defecto
        """
        # Precisión conocida para símbolos principales
        precision_map = {
            "BTCUSDT": {"quantity": 5, "price": 2, "step_size": 0.00001},
            "ETHUSDT": {"quantity": 4, "price": 2, "step_size": 0.0001},
            "BNBUSDT": {"quantity": 4, "price": 2, "step_size": 0.0001},
            "ADAUSDT": {"quantity": 0, "price": 4, "step_size": 1},
            "DOTUSDT": {"quantity": 1, "price": 3, "step_size": 0.1},
            "LINKUSDT": {"quantity": 1, "price": 3, "step_size": 0.1},
            "AVAXUSDT": {"quantity": 2, "price": 2, "step_size": 0.01},
            "HOMEUSDT": {"quantity": 0, "price": 5, "step_size": 1},
            "SIGNUSDT": {"quantity": 0, "price": 5, "step_size": 1},
            "SPKUSDT": {"quantity": 0, "price": 5, "step_size": 1},
        }

        if symbol in precision_map:
            return precision_map[symbol]

        # Precisión por defecto para símbolos desconocidos
        return {"quantity": 2, "price": 2, "step_size": 0.01}

    def validate_quantity(
        self, symbol: str, quantity: Decimal | float
    ) -> Tuple[bool, Optional[Decimal], str]:
        """
        Valida y ajusta la cantidad para un símbolo

        Args:
            symbol: Símbolo del trading pair
            quantity: Cantidad a validar

        Returns:
            Tuple[bool, Optional[Decimal], str]: (válido, cantidad_ajustada, mensaje)
        """
        try:
            # Asegurar que la cantidad sea Decimal
            if not isinstance(quantity, Decimal):
                quantity = Decimal(str(quantity))

            # Obtener precisión del símbolo
            precision_info = self.get_symbol_precision(symbol)
            step_size = Decimal(str(precision_info["step_size"]))
            quantity_precision = precision_info["quantity"]

            # Validar que la cantidad sea positiva
            if quantity <= 0:
                return False, None, f"Cantidad debe ser mayor a 0: {quantity}"

            # Ajustar cantidad usando step_size
            adjusted_quantity = self._adjust_to_step_size(quantity, step_size)

            # Validar que la cantidad ajustada sea válida
            if adjusted_quantity <= 0:
                return (
                    False,
                    None,
                    f"Cantidad ajustada es 0 o negativa: {adjusted_quantity}",
                )

            # Validar formato de precisión
            if not self._is_valid_precision_format(
                adjusted_quantity, quantity_precision
            ):
                return False, None, f"Formato de precisión inválido para {symbol}"

            return True, adjusted_quantity, "OK"

        except Exception as e:
            logger.error(f"Error validando cantidad para {symbol}: {e}")
            return False, None, f"Error de validación: {str(e)}"

    def _adjust_to_step_size(self, quantity: Decimal, step_size: Decimal) -> Decimal:
        """
        Ajusta la cantidad al step_size más cercano

        Args:
            quantity: Cantidad original (Decimal)
            step_size: Tamaño del paso (Decimal)

        Returns:
            Decimal: Cantidad ajustada
        """
        try:
            # Redondear hacia abajo al step_size más cercano
            adjusted = (quantity // step_size) * step_size

            return adjusted

        except Exception as e:
            logger.error(f"Error ajustando step_size: {e}")
            # Fallback seguro
            return quantity

    def _is_valid_precision_format(self, quantity: Decimal, precision: int) -> bool:
        """
        Valida que la cantidad tenga el formato de precisión correcto

        Args:
            quantity: Cantidad a validar
            precision: Número de decimales permitidos

        Returns:
            bool: True si el formato es válido
        """
        try:
            # Normalizar Decimal para evitar formatos científicos y contar decimales reales
            normalized = quantity.normalize()
            sign, digits, exponent = normalized.as_tuple()
            
            if exponent >= 0:
                return True # No hay decimales
            
            return abs(exponent) <= precision

        except Exception as e:
            logger.error(f"Error validando formato de precisión: {e}")
            return False

    def validate_price(
        self, symbol: str, price: Decimal | float
    ) -> Tuple[bool, Optional[Decimal], str]:
        """
        Valida y ajusta el precio para un símbolo

        Args:
            symbol: Símbolo del trading pair
            price: Precio a validar

        Returns:
            Tuple[bool, Optional[Decimal], str]: (válido, precio_ajustado, mensaje)
        """
        try:
            # Asegurar que el precio sea Decimal
            if not isinstance(price, Decimal):
                price = Decimal(str(price))

            # Obtener precisión del símbolo
            precision_info = self.get_symbol_precision(symbol)
            price_precision = precision_info["price"]

            # Validar que el precio sea positivo
            if price <= 0:
                return False, None, f"Precio debe ser mayor a 0: {price}"

            # Ajustar precio a la precisión correcta
            # Rounding mode HALF_DOWN para ser conservadores
            from decimal import ROUND_HALF_DOWN
            format_str = f"0.{'0' * price_precision}" if price_precision > 0 else "0"
            adjusted_price = price.quantize(Decimal(format_str), rounding=ROUND_HALF_DOWN)

            return True, adjusted_price, "OK"

        except Exception as e:
            logger.error(f"Error validando precio para {symbol}: {e}")
            return False, None, f"Error de validación: {str(e)}"

    def validate_order(
        self, symbol: str, quantity: Decimal | float, price: Decimal | float
    ) -> Tuple[bool, Dict, str]:
        """
        Valida una orden completa

        Args:
            symbol: Símbolo del trading pair
            quantity: Cantidad
            price: Precio

        Returns:
            Tuple[bool, Dict, str]: (válido, datos_ajustados, mensaje)
        """
        # Validar cantidad
        quantity_valid, adjusted_quantity, quantity_msg = self.validate_quantity(
            symbol, quantity
        )
        if not quantity_valid:
            return False, {}, f"Error en cantidad: {quantity_msg}"

        # Validar precio
        price_valid, adjusted_price, price_msg = self.validate_price(symbol, price)
        if not price_valid:
            return False, {}, f"Error en precio: {price_msg}"

        # Calcular valor notional usando Decimal
        notional_value = adjusted_quantity * adjusted_price

        # Validar valor notional mínimo (Binance standard: $10)
        if notional_value < Decimal("10.0"):
            return False, {}, f"Valor notional muy bajo: ${notional_value:.2f} < $10"

        return (
            True,
            {
                "symbol": symbol,
                "quantity": adjusted_quantity,
                "price": adjusted_price,
                "notional_value": notional_value,
            },
            "OK",
        )

    def get_validation_summary(self, symbol: str) -> Dict:
        """
        Obtiene un resumen de validación para un símbolo

        Args:
            symbol: Símbolo del trading pair

        Returns:
            Dict: Resumen de validación
        """
        precision_info = self.get_symbol_precision(symbol)

        return {
            "symbol": symbol,
            "precision_info": precision_info,
            "min_quantity": precision_info["step_size"],
            "quantity_precision": precision_info["quantity"],
            "price_precision": precision_info["price"],
            "min_notional": 10.0,  # Valor mínimo en USDT
        }


# Instancia global del validador
precision_validator = PrecisionValidator()


def validate_trading_order(
    symbol: str, quantity: Union[Decimal, str], price: Union[Decimal, str]
) -> Tuple[bool, Dict, str]:
    """
    Función de conveniencia para validar una orden de trading

    Args:
        symbol: Símbolo del trading pair
        quantity: Cantidad
        price: Precio

    Returns:
        Tuple[bool, Dict, str]: (válido, datos_ajustados, mensaje)
    """
    return precision_validator.validate_order(symbol, quantity, price)


def get_symbol_precision_info(symbol: str) -> Dict:
    """
    Función de conveniencia para obtener información de precisión

    Args:
        symbol: Símbolo del trading pair

    Returns:
        Dict: Información de precisión
    """
    return precision_validator.get_validation_summary(symbol)
