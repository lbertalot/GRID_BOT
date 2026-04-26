# Sistema de logging estructurado para trading
import json
import logging
from datetime import datetime
from typing import Dict, Any


class StructuredLogger:
    """Logger estructurado para eventos de trading"""

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.correlation_id = None

    def set_correlation_id(self, correlation_id: str):
        """Establece ID de correlación para seguimiento"""
        self.correlation_id = correlation_id

    def _format_message(self, message: str, extra: Dict[str, Any] = None) -> str:
        """Formatea mensaje como JSON estructurado"""
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "message": message,
            "correlation_id": self.correlation_id,
        }

        if extra:
            log_data.update(extra)

        return json.dumps(log_data, ensure_ascii=False)

    def info(self, message: str, extra: Dict[str, Any] = None):
        """Log de información estructurado"""
        self.logger.info(self._format_message(message, extra))

    def warning(self, message: str, extra: Dict[str, Any] = None):
        """Log de advertencia estructurado"""
        self.logger.warning(self._format_message(message, extra))

    def error(self, message: str, extra: Dict[str, Any] = None):
        """Log de error estructurado"""
        self.logger.error(self._format_message(message, extra))

    def trading_event(
        self,
        event_type: str,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        extra: Dict[str, Any] = None,
    ):
        """Log específico para eventos de trading"""
        trading_data = {
            "event_type": event_type,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            "total_value": quantity * price,
        }

        if extra:
            trading_data.update(extra)

        self.info(f"Trading event: {event_type}", trading_data)

    def trading_summary(self, summary: Dict[str, Any]):
        """Log de resumen de trading"""
        self.info("Trading cycle summary", summary)

    def error_event(
        self, error_type: str, error_message: str, context: Dict[str, Any] = None
    ):
        """Log específico para errores"""
        error_data = {"error_type": error_type, "error_message": error_message}

        if context:
            error_data.update(context)

        self.error(f"Error: {error_type}", error_data)


# Instancia global para uso en toda la aplicación
trading_logger = StructuredLogger("trading_system")
