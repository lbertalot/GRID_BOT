#!/usr/bin/env python3
"""
Sistema de Circuit Breakers para GridBot V2.5
Protege el capital implementando límites de pérdida automáticos
"""

import logging
import json
import os
from datetime import datetime
from typing import Dict, Tuple

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """
    Sistema de circuit breakers para proteger el capital
    """

    def __init__(self, config_file: str = "grid_config_optimized.json"):
        self.config_file = config_file
        self.limits = {
            "daily_loss_limit": 0.05,  # 5% máximo pérdida diaria
            "total_loss_limit": 0.10,  # 10% máximo pérdida total
            "trade_loss_limit": 0.02,  # 2% máximo pérdida por trade
            "consecutive_losses": 3,  # Máximo 3 pérdidas consecutivas
            "hourly_loss_limit": 0.03,  # 3% máximo pérdida por hora
        }
        self.state = {
            "is_open": False,
            "reason": None,
            "opened_at": None,
            "daily_loss": 0.0,
            "total_loss": 0.0,
            "consecutive_losses": 0,
            "hourly_loss": 0.0,
            "last_reset": datetime.now(),
        }
        self.load_state()

    def load_state(self):
        """Carga el estado del circuit breaker"""
        try:
            if os.path.exists("circuit_breaker_state.json"):
                with open("circuit_breaker_state.json", "r") as f:
                    saved_state = json.load(f)
                    self.state.update(saved_state)
                    # Convertir string de fecha a datetime
                    if self.state["opened_at"]:
                        self.state["opened_at"] = datetime.fromisoformat(
                            self.state["opened_at"]
                        )
                    if self.state["last_reset"]:
                        self.state["last_reset"] = datetime.fromisoformat(
                            self.state["last_reset"]
                        )
        except Exception as e:
            logger.error(f"Error cargando estado del circuit breaker: {e}")

    def save_state(self):
        """Guarda el estado del circuit breaker"""
        try:
            state_to_save = self.state.copy()
            # Convertir datetime a string para JSON
            if state_to_save["opened_at"]:
                state_to_save["opened_at"] = state_to_save["opened_at"].isoformat()
            if state_to_save["last_reset"]:
                state_to_save["last_reset"] = state_to_save["last_reset"].isoformat()

            with open("circuit_breaker_state.json", "w") as f:
                json.dump(state_to_save, f, indent=2)
        except Exception as e:
            logger.error(f"Error guardando estado del circuit breaker: {e}")

    def reset_daily_limits(self):
        """Resetea los límites diarios"""
        now = datetime.now()
        if now.date() > self.state["last_reset"].date():
            self.state["daily_loss"] = 0.0
            self.state["hourly_loss"] = 0.0
            self.state["last_reset"] = now
            logger.info("🔄 Límites diarios reseteados")

    def check_limits(self, trade_loss: float = 0.0) -> Tuple[bool, str]:
        """
        Verifica si se han excedido los límites

        Args:
            trade_loss: Pérdida del trade actual (opcional)

        Returns:
            Tuple[bool, str]: (permitir_trading, razón)
        """
        # Resetear límites diarios si es necesario
        self.reset_daily_limits()

        # Si el circuit breaker está abierto, no permitir trading
        if self.state["is_open"]:
            return False, f"Circuit breaker abierto: {self.state['reason']}"

        # Verificar límite de pérdida por trade
        if trade_loss > self.limits["trade_loss_limit"]:
            self._open_circuit(
                f"Pérdida por trade excedida: {trade_loss:.2%} > {self.limits['trade_loss_limit']:.2%}"
            )
            return False, f"Pérdida por trade excedida: {trade_loss:.2%}"

        # Verificar límite de pérdida diaria
        if self.state["daily_loss"] > self.limits["daily_loss_limit"]:
            self._open_circuit(
                f"Límite de pérdida diaria excedido: {self.state['daily_loss']:.2%} > {self.limits['daily_loss_limit']:.2%}"
            )
            return (
                False,
                f"Límite de pérdida diaria excedido: {self.state['daily_loss']:.2%}",
            )

        # Verificar límite de pérdida total
        if self.state["total_loss"] > self.limits["total_loss_limit"]:
            self._open_circuit(
                f"Límite de pérdida total excedido: {self.state['total_loss']:.2%} > {self.limits['total_loss_limit']:.2%}"
            )
            return (
                False,
                f"Límite de pérdida total excedido: {self.state['total_loss']:.2%}",
            )

        # Verificar pérdidas consecutivas
        if self.state["consecutive_losses"] >= self.limits["consecutive_losses"]:
            self._open_circuit(
                f"Demasiadas pérdidas consecutivas: {self.state['consecutive_losses']}"
            )
            return (
                False,
                f"Demasiadas pérdidas consecutivas: {self.state['consecutive_losses']}",
            )

        # Verificar límite de pérdida por hora
        if self.state["hourly_loss"] > self.limits["hourly_loss_limit"]:
            self._open_circuit(
                f"Límite de pérdida por hora excedido: {self.state['hourly_loss']:.2%} > {self.limits['hourly_loss_limit']:.2%}"
            )
            return (
                False,
                f"Límite de pérdida por hora excedido: {self.state['hourly_loss']:.2%}",
            )

        return True, "OK"

    def _open_circuit(self, reason: str):
        """Abre el circuit breaker"""
        self.state["is_open"] = True
        self.state["reason"] = reason
        self.state["opened_at"] = datetime.now()
        self.save_state()

        logger.critical(f"🚨 CIRCUIT BREAKER ABIERTO: {reason}")

        # Enviar alerta (implementar según necesidad)
        self._send_alert(f"Circuit Breaker activado: {reason}")

    def close_circuit(self, reason: str = "Manual"):
        """Cierra el circuit breaker manualmente"""
        self.state["is_open"] = False
        self.state["reason"] = None
        self.state["opened_at"] = None
        self.save_state()

        logger.info(f"✅ Circuit breaker cerrado: {reason}")

    def record_loss(self, loss_amount: float, loss_percentage: float):
        """
        Registra una pérdida y actualiza los contadores

        Args:
            loss_amount: Cantidad perdida en USDT
            loss_percentage: Porcentaje perdido
        """
        # Actualizar pérdida diaria
        self.state["daily_loss"] += loss_percentage

        # Actualizar pérdida total
        self.state["total_loss"] += loss_percentage

        # Actualizar pérdida por hora
        self.state["hourly_loss"] += loss_percentage

        # Incrementar pérdidas consecutivas
        self.state["consecutive_losses"] += 1

        self.save_state()

        logger.warning(
            f"📉 Pérdida registrada: ${loss_amount:.2f} ({loss_percentage:.2%})"
        )
        logger.info(
            f"   Diaria: {self.state['daily_loss']:.2%}, Total: {self.state['total_loss']:.2%}"
        )

    def record_profit(self, profit_amount: float, profit_percentage: float):
        """
        Registra una ganancia y resetea contadores de pérdidas consecutivas

        Args:
            profit_amount: Cantidad ganada en USDT
            profit_percentage: Porcentaje ganado
        """
        # Resetear pérdidas consecutivas
        self.state["consecutive_losses"] = 0

        # Reducir pérdida diaria (pero no por debajo de 0)
        self.state["daily_loss"] = max(0, self.state["daily_loss"] - profit_percentage)

        # Reducir pérdida total (pero no por debajo de 0)
        self.state["total_loss"] = max(0, self.state["total_loss"] - profit_percentage)

        self.save_state()

        logger.info(
            f"📈 Ganancia registrada: ${profit_amount:.2f} ({profit_percentage:.2%})"
        )

    def get_status(self) -> Dict:
        """Obtiene el estado actual del circuit breaker"""
        return {
            "is_open": self.state["is_open"],
            "reason": self.state["reason"],
            "opened_at": self.state["opened_at"].isoformat()
            if self.state["opened_at"]
            else None,
            "limits": self.limits,
            "current_state": {
                "daily_loss": self.state["daily_loss"],
                "total_loss": self.state["total_loss"],
                "consecutive_losses": self.state["consecutive_losses"],
                "hourly_loss": self.state["hourly_loss"],
            },
        }

    def _send_alert(self, message: str):
        """Envía una alerta (implementar según necesidad)"""
        # TODO: Implementar alertas por email/SMS
        logger.critical(f"🚨 ALERTA: {message}")

    def reset_hourly_loss(self):
        """Resetea la pérdida por hora (llamar cada hora)"""
        self.state["hourly_loss"] = 0.0
        self.save_state()
        logger.info("🔄 Pérdida por hora reseteada")


# Instancia global del circuit breaker
circuit_breaker = CircuitBreaker()


def check_trading_allowed(trade_loss: float = 0.0) -> Tuple[bool, str]:
    """
    Función de conveniencia para verificar si se permite trading

    Args:
        trade_loss: Pérdida estimada del trade (opcional)

    Returns:
        Tuple[bool, str]: (permitir_trading, razón)
    """
    return circuit_breaker.check_limits(trade_loss)


def record_trade_result(profit_loss_usdt: float, profit_loss_percentage: float):
    """
    Función de conveniencia para registrar resultado de trade

    Args:
        profit_loss_usdt: Ganancia/pérdida en USDT
        profit_loss_percentage: Ganancia/pérdida en porcentaje
    """
    if profit_loss_usdt > 0:
        circuit_breaker.record_profit(profit_loss_usdt, profit_loss_percentage)
    else:
        circuit_breaker.record_loss(abs(profit_loss_usdt), abs(profit_loss_percentage))
