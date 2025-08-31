"""
Schemas simplificados para validación de datos
Versión sin dependencias externas para pruebas
"""

from typing import Literal, Optional, Dict, Any
from decimal import Decimal
import re
from datetime import datetime

class TradingSymbol:
    """Tipo personalizado para símbolos de trading"""
    
    def __init__(self, value: str):
        if not isinstance(value, str):
            raise ValueError('Símbolo debe ser una cadena')
        
        if not re.match(r'^[A-Z0-9]+$', value):
            raise ValueError('Símbolo debe contener solo letras mayúsculas y números')
        
        # Validar símbolos soportados
        supported_symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'DOTUSDT']
        if value not in supported_symbols:
            raise ValueError(f'Símbolo {value} no está soportado')
        
        self.value = value.upper()
    
    def __str__(self):
        return self.value
    
    def __eq__(self, other):
        return str(self) == str(other)

class TradingOrder:
    """Schema para órdenes de trading"""
    
    def __init__(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = 'MARKET',
        price: Optional[float] = None
    ):
        self.symbol = TradingSymbol(symbol)
        self.side = side
        self.quantity = quantity
        self.order_type = order_type
        self.price = price
        
        # Validaciones
        if side not in ['BUY', 'SELL']:
            raise ValueError('Side debe ser BUY o SELL')
        
        if order_type not in ['MARKET', 'LIMIT']:
            raise ValueError('Order type debe ser MARKET o LIMIT')
        
        if quantity <= 0:
            raise ValueError('Quantity debe ser positivo')
        
        if order_type == 'LIMIT' and price is None:
            raise ValueError('Precio requerido para órdenes LIMIT')
        
        if price is not None and price <= 0:
            raise ValueError('Precio debe ser positivo')

class GridConfiguration:
    """Schema para configuración de grid trading"""
    
    def __init__(
        self,
        symbol: str,
        min_price: float,
        max_price: float,
        num_levels: int,
        quantity_per_level: float,
        min_profit_percentage: float = 0.5
    ):
        self.symbol = TradingSymbol(symbol)
        self.min_price = min_price
        self.max_price = max_price
        self.num_levels = num_levels
        self.quantity_per_level = quantity_per_level
        self.min_profit_percentage = min_profit_percentage
        
        # Validaciones
        if min_price <= 0 or max_price <= 0:
            raise ValueError('Precios deben ser positivos')
        
        if max_price <= min_price:
            raise ValueError('Precio máximo debe ser mayor al precio mínimo')
        
        if num_levels < 2 or num_levels > 100:
            raise ValueError('Número de niveles debe estar entre 2 y 100')
        
        if quantity_per_level <= 0:
            raise ValueError('Cantidad por nivel debe ser positiva')
        
        if min_profit_percentage < 0.1 or min_profit_percentage > 10.0:
            raise ValueError('Porcentaje de ganancia mínima debe estar entre 0.1% y 10%')

class CommissionCalculation:
    """Schema para cálculos de comisión"""
    
    def __init__(
        self,
        notional_value: float,
        order_type: str = 'MARKET',
        symbol: str = 'BTCUSDT',
        commission_rate: float = 0.001
    ):
        self.notional_value = notional_value
        self.order_type = order_type
        self.symbol = TradingSymbol(symbol)
        self.commission_rate = commission_rate
        
        # Validaciones
        if notional_value <= 0:
            raise ValueError('Valor notional debe ser positivo')
        
        if order_type not in ['MARKET', 'LIMIT']:
            raise ValueError('Order type debe ser MARKET o LIMIT')
        
        if commission_rate < 0 or commission_rate > 1:
            raise ValueError('Tasa de comisión debe estar entre 0 y 1')

class TradingResult:
    """Schema para resultados de trading"""
    
    def __init__(
        self,
        success: bool,
        order_id: Optional[str] = None,
        executed_quantity: Optional[float] = None,
        executed_price: Optional[float] = None,
        commission_paid: Optional[float] = None,
        timestamp: Optional[str] = None,
        error_message: Optional[str] = None
    ):
        self.success = success
        self.order_id = order_id
        self.executed_quantity = executed_quantity
        self.executed_price = executed_price
        self.commission_paid = commission_paid
        self.timestamp = timestamp or datetime.now().isoformat()
        self.error_message = error_message

class PortfolioBalance:
    """Schema para balances de portafolio"""
    
    def __init__(
        self,
        asset: str,
        free: float,
        locked: float,
        total: float
    ):
        self.asset = asset
        self.free = free
        self.locked = locked
        self.total = total
        
        # Validaciones
        if not re.match(r'^[A-Z0-9]+$', asset):
            raise ValueError('Asset debe contener solo letras mayúsculas y números')
        
        if free < 0 or locked < 0 or total < 0:
            raise ValueError('Balances no pueden ser negativos')
        
        if abs(total - (free + locked)) > 0.000001:  # Tolerancia para floats
            raise ValueError('Total debe ser igual a free + locked')

# Schemas para respuestas de API
class APIResponse:
    """Schema base para respuestas de API"""
    
    def __init__(
        self,
        success: bool,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None
    ):
        self.success = success
        self.message = message
        self.data = data or {}
        self.timestamp = timestamp or datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "message": self.message,
            "data": self.data,
            "timestamp": self.timestamp
        }

class ErrorResponse:
    """Schema para respuestas de error"""
    
    def __init__(
        self,
        error_code: str,
        error_message: str,
        details: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None
    ):
        self.success = False
        self.error_code = error_code
        self.error_message = error_message
        self.details = details or {}
        self.timestamp = timestamp or datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "details": self.details,
            "timestamp": self.timestamp
        }
