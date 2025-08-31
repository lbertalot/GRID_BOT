
"""
Tipos de error específicos para el sistema de trading
Siguiendo mejores prácticas de manejo de errores
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, Union
from enum import Enum

class ErrorSeverity(Enum):
    """Severidad de los errores"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class TradingError:
    """Error base para operaciones de trading"""
    code: str
    message: str
    severity: ErrorSeverity
    context: Dict[str, Any]
    retryable: bool = False
    timestamp: Optional[str] = None

@dataclass
class CommissionError(TradingError):
    """Error específico para cálculos de comisión"""
    notional_value: float = 0.0
    commission_rate: float = 0.0
    
    def __post_init__(self):
        if not self.timestamp:
            from datetime import datetime
            self.timestamp = datetime.now().isoformat()

@dataclass
class ValidationError(TradingError):
    """Error de validación de datos"""
    field: str = ""
    value: Any = None
    expected_type: str = ""

@dataclass
class BinanceAPIError(TradingError):
    """Error de la API de Binance"""
    binance_code: Optional[int] = None
    binance_message: Optional[str] = None
    endpoint: Optional[str] = None

@dataclass
class InsufficientFundsError(TradingError):
    """Error de fondos insuficientes"""
    required_amount: float = 0.0
    available_amount: float = 0.0
    asset: str = ""

# Funciones de utilidad para crear errores
def create_commission_error(
    notional_value: float,
    message: str,
    context: Dict[str, Any] = None
) -> CommissionError:
    """Crea un error de comisión"""
    return CommissionError(
        code="INVALID_COMMISSION_CALCULATION",
        message=message,
        severity=ErrorSeverity.MEDIUM,
        context=context or {},
        retryable=False,
        notional_value=notional_value,
        commission_rate=0.0
    )

def create_validation_error(
    field: str,
    value: Any,
    expected_type: str,
    message: str
) -> ValidationError:
    """Crea un error de validación"""
    return ValidationError(
        code="VALIDATION_ERROR",
        message=message,
        severity=ErrorSeverity.LOW,
        context={"field": field, "value": value},
        retryable=False,
        field=field,
        value=value,
        expected_type=expected_type
    )

def create_binance_api_error(
    binance_code: int,
    binance_message: str,
    endpoint: str,
    context: Dict[str, Any] = None
) -> BinanceAPIError:
    """Crea un error de API de Binance"""
    return BinanceAPIError(
        code="BINANCE_API_ERROR",
        message=f"Error de Binance API: {binance_message}",
        severity=ErrorSeverity.HIGH,
        context=context or {},
        retryable=binance_code in [-1003, -1015, 429],  # Rate limit errors
        binance_code=binance_code,
        binance_message=binance_message,
        endpoint=endpoint
    )

# Función para manejar errores de forma funcional
def handle_trading_error(error: TradingError) -> Dict[str, Any]:
    """
    Maneja un error de trading de forma funcional
    """
    return {
        "error": True,
        "code": error.code,
        "message": error.message,
        "severity": error.severity.value,
        "retryable": error.retryable,
        "timestamp": error.timestamp,
        "context": error.context
    }
