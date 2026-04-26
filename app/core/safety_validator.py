#!/usr/bin/env python3
"""
Sistema de Validación de Seguridad Integrado para GridBot V2.5
Combina circuit breakers, validación de precisión y monitoreo
"""

import logging
from typing import Dict, Tuple
from datetime import datetime

# Importar sistemas de seguridad
from app.core.circuit_breaker import check_trading_allowed, record_trade_result
from app.core.precision_validator import validate_trading_order
from app.core.monitoring import record_trade_event, get_monitoring_status

logger = logging.getLogger(__name__)


class SafetyValidator:
    """
    Sistema de validación de seguridad integrado
    """

    def __init__(self):
        self.validation_history = []

    def validate_trade_request(
        self, symbol: str, side: str, quantity: float, price: float
    ) -> Tuple[bool, Dict, str]:
        """
        Valida una solicitud de trade completa

        Args:
            symbol: Símbolo del trading pair
            side: Lado del trade (BUY/SELL)
            quantity: Cantidad
            price: Precio

        Returns:
            Tuple[bool, Dict, str]: (válido, datos_validados, mensaje)
        """
        logger.info(f"🔍 Validando trade: {symbol} {side} {quantity} @ {price}")

        # 1. Verificar circuit breaker
        circuit_ok, circuit_msg = check_trading_allowed()
        if not circuit_ok:
            logger.warning(f"❌ Circuit breaker bloqueó trade: {circuit_msg}")
            return False, {}, f"Circuit breaker: {circuit_msg}"

        # 2. Validar precisión y formato
        precision_ok, precision_data, precision_msg = validate_trading_order(
            symbol, quantity, price
        )
        if not precision_ok:
            logger.warning(f"❌ Validación de precisión falló: {precision_msg}")
            return False, {}, f"Precisión: {precision_msg}"

        # 3. Verificar balance suficiente (simulado)
        balance_ok, balance_msg = self._check_sufficient_balance(
            symbol, side, quantity, price
        )
        if not balance_ok:
            logger.warning(f"❌ Balance insuficiente: {balance_msg}")
            return False, {}, f"Balance: {balance_msg}"

        # 4. Verificar límites de riesgo
        risk_ok, risk_msg = self._check_risk_limits(symbol, quantity, price)
        if not risk_ok:
            logger.warning(f"❌ Límites de riesgo excedidos: {risk_msg}")
            return False, {}, f"Riesgo: {risk_msg}"

        # 5. Registrar validación exitosa
        validated_data = {
            "symbol": symbol,
            "side": side,
            "quantity": precision_data["quantity"],
            "price": precision_data["price"],
            "notional_value": precision_data["notional_value"],
            "timestamp": datetime.now().isoformat(),
            "validation_passed": True,
        }

        self.validation_history.append(validated_data)

        logger.info(f"✅ Trade validado exitosamente: {symbol} {side}")
        return True, validated_data, "Trade validado exitosamente"

    def _check_sufficient_balance(
        self, symbol: str, side: str, quantity: float, price: float
    ) -> Tuple[bool, str]:
        """
        Verifica si hay balance suficiente para el trade

        Args:
            symbol: Símbolo del trading pair
            side: Lado del trade (BUY/SELL)
            quantity: Cantidad
            price: Precio

        Returns:
            Tuple[bool, str]: (suficiente, mensaje)
        """
        # TODO: Implementar verificación real de balance
        # Por ahora, simular verificación

        notional_value = quantity * price

        if side == "BUY":
            # Para compra, necesitamos USDT
            required_usdt = notional_value
            # Simular balance de USDT
            available_usdt = 316.82  # Balance actual

            if required_usdt > available_usdt:
                return (
                    False,
                    f"USDT insuficiente: ${required_usdt:.2f} > ${available_usdt:.2f}",
                )

        elif side == "SELL":
            # Para venta, necesitamos el asset base
            # TODO: Verificar balance del asset base
            pass

        return True, "Balance suficiente"

    def _check_risk_limits(
        self, symbol: str, quantity: float, price: float
    ) -> Tuple[bool, str]:
        """
        Verifica límites de riesgo

        Args:
            symbol: Símbolo del trading pair
            quantity: Cantidad
            price: Precio

        Returns:
            Tuple[bool, str]: (dentro_limites, mensaje)
        """
        notional_value = quantity * price

        # Verificar valor notional mínimo
        if notional_value < 10:
            return False, f"Valor notional muy bajo: ${notional_value:.2f} < $10"

        # Verificar valor notional máximo (ejemplo: 50% del balance)
        max_notional = 316.82 * 0.5  # 50% del balance actual
        if notional_value > max_notional:
            return (
                False,
                f"Valor notional muy alto: ${notional_value:.2f} > ${max_notional:.2f}",
            )

        return True, "Dentro de límites de riesgo"

    def record_trade_execution(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        success: bool,
        profit_loss: float = 0.0,
    ):
        """
        Registra la ejecución de un trade

        Args:
            symbol: Símbolo del trading pair
            side: Lado del trade (BUY/SELL)
            quantity: Cantidad
            price: Precio
            success: Si el trade fue exitoso
            profit_loss: Ganancia/pérdida del trade
        """
        # Registrar en monitoreo
        record_trade_event(symbol, side, quantity, price, success, profit_loss)

        # Registrar en circuit breaker
        if success:
            record_trade_result(
                profit_loss, abs(profit_loss) / 316.82
            )  # Usar balance actual como referencia

        logger.info(
            f"📊 Trade registrado: {symbol} {side} - {'✅' if success else '❌'} ${profit_loss:.2f}"
        )

    def get_safety_status(self) -> Dict:
        """
        Obtiene el estado de seguridad del sistema

        Returns:
            Dict: Estado de seguridad
        """
        # Obtener estado del monitoreo
        monitoring_status = get_monitoring_status()

        # Obtener estado del circuit breaker
        circuit_ok, circuit_msg = check_trading_allowed()

        return {
            "circuit_breaker": {"is_open": not circuit_ok, "message": circuit_msg},
            "monitoring": monitoring_status,
            "validation_history": self.validation_history[
                -10:
            ],  # Últimas 10 validaciones
            "system_safe": circuit_ok
            and monitoring_status["system_status"] != "CRITICAL",
        }

    def emergency_stop(self, reason: str = "Manual"):
        """
        Activa parada de emergencia

        Args:
            reason: Razón de la parada de emergencia
        """
        from app.core.circuit_breaker import circuit_breaker

        circuit_breaker._open_circuit(f"Parada de emergencia: {reason}")

        logger.critical(f"🚨 PARADA DE EMERGENCIA ACTIVADA: {reason}")

    def reset_safety_systems(self, reason: str = "Manual"):
        """
        Resetea los sistemas de seguridad

        Args:
            reason: Razón del reset
        """
        from app.core.circuit_breaker import circuit_breaker

        circuit_breaker.close_circuit(f"Reset manual: {reason}")

        logger.info(f"✅ Sistemas de seguridad reseteados: {reason}")


# Instancia global del validador de seguridad
safety_validator = SafetyValidator()


def validate_and_execute_trade(
    symbol: str, side: str, quantity: float, price: float
) -> Tuple[bool, Dict, str]:
    """
    Función de conveniencia para validar y simular ejecución de trade

    Args:
        symbol: Símbolo del trading pair
        side: Lado del trade (BUY/SELL)
        quantity: Cantidad
        price: Precio

    Returns:
        Tuple[bool, Dict, str]: (éxito, resultado, mensaje)
    """
    # Validar trade
    valid, validated_data, validation_msg = safety_validator.validate_trade_request(
        symbol, side, quantity, price
    )

    if not valid:
        return False, {}, validation_msg

    # Simular ejecución (en producción, aquí iría la orden real)
    success = True  # Simular éxito
    profit_loss = 0.0  # Simular sin ganancia/pérdida

    # Registrar ejecución
    safety_validator.record_trade_execution(
        symbol, side, quantity, price, success, profit_loss
    )

    return True, validated_data, "Trade ejecutado exitosamente"


def get_system_safety_status() -> Dict:
    """
    Función de conveniencia para obtener estado de seguridad

    Returns:
        Dict: Estado de seguridad del sistema
    """
    return safety_validator.get_safety_status()


def trigger_emergency_stop(reason: str = "Manual"):
    """
    Función de conveniencia para activar parada de emergencia

    Args:
        reason: Razón de la parada
    """
    safety_validator.emergency_stop(reason)
