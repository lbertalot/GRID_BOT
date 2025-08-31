"""
Excepciones personalizadas para el módulo de exchanges.
"""

from typing import Optional, Dict, Any


class ExchangeError(Exception):
    """Excepción base para errores de exchange."""
    
    def __init__(self, message: str, exchange: str = "unknown", details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.exchange = exchange
        self.details = details or {}
        super().__init__(self.message)


class SymbolFilterError(ExchangeError):
    """Error cuando los parámetros de orden no cumplen con los filtros del símbolo."""
    
    def __init__(self, symbol: str, reason: str, filter_type: str, 
                 provided_value: Any, required_value: Any, exchange: str = "binance"):
        self.symbol = symbol
        self.reason = reason
        self.filter_type = filter_type
        self.provided_value = provided_value
        self.required_value = required_value
        
        message = f"Symbol filter validation failed for {symbol}: {reason}"
        super().__init__(message, exchange, {
            "symbol": symbol,
            "reason": reason,
            "filter_type": filter_type,
            "provided_value": provided_value,
            "required_value": required_value
        })


class RateLimitError(ExchangeError):
    """Error cuando se excede el límite de rate de la API."""
    
    def __init__(self, endpoint: str, retry_after: Optional[int] = None, exchange: str = "binance"):
        self.endpoint = endpoint
        self.retry_after = retry_after
        
        message = f"Rate limit exceeded for endpoint: {endpoint}"
        if retry_after:
            message += f" (retry after {retry_after}s)"
            
        super().__init__(message, exchange, {
            "endpoint": endpoint,
            "retry_after": retry_after
        })


class WebSocketError(ExchangeError):
    """Error relacionado con WebSocket."""
    
    def __init__(self, message: str, symbol: Optional[str] = None, 
                 ws_type: str = "unknown", exchange: str = "binance"):
        self.symbol = symbol
        self.ws_type = ws_type
        
        super().__init__(message, exchange, {
            "symbol": symbol,
            "ws_type": ws_type
        })


class ConnectionError(ExchangeError):
    """Error de conexión con el exchange."""
    
    def __init__(self, message: str, endpoint: str, exchange: str = "binance"):
        self.endpoint = endpoint
        
        super().__init__(message, exchange, {
            "endpoint": endpoint
        })
