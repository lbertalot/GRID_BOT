#!/usr/bin/env python3
"""
Script para aplicar optimizaciones de mejores prácticas
Basado en el análisis de .cursorrules y la API de Binance
"""

import os
import sys
import shutil
from pathlib import Path
from typing import List, Dict, Any

def apply_functional_refactoring():
    """Aplica refactoring funcional a los servicios principales"""
    print("🔄 Aplicando refactoring funcional...")
    
    # 1. Crear versión funcional de CommissionManager
    commission_funcional = '''
"""
Servicio de comisiones refactorizado a funciones puras
Siguiendo principios de programación funcional
"""

import logging
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from binance import Client
from binance.exceptions import BinanceAPIException

logger = logging.getLogger(__name__)

@dataclass
class CommissionRates:
    """Tasas de comisión para un símbolo"""
    maker: float
    taker: float
    symbol: Optional[str] = None

@dataclass
class CommissionResult:
    """Resultado del cálculo de comisión"""
    commission_usdt: float
    commission_percentage: float
    notional_value: float
    order_type: str

def get_default_commission_rates() -> CommissionRates:
    """Obtiene tasas de comisión por defecto"""
    return CommissionRates(
        maker=0.001,  # 0.1%
        taker=0.001   # 0.1%
    )

def calculate_commission(
    notional_value: float,
    order_type: str = 'MARKET',
    commission_rates: Optional[CommissionRates] = None
) -> CommissionResult:
    """
    Calcula comisión para una operación (función pura)
    
    Args:
        notional_value: Valor notional de la operación
        order_type: Tipo de orden (MARKET/LIMIT)
        commission_rates: Tasas de comisión (opcional)
        
    Returns:
        CommissionResult con detalles de la comisión
    """
    if notional_value <= 0:
        raise ValueError("Valor notional debe ser positivo")
    
    rates = commission_rates or get_default_commission_rates()
    commission_rate = rates.taker if order_type == 'MARKET' else rates.maker
    commission_usdt = notional_value * commission_rate
    
    return CommissionResult(
        commission_usdt=round(commission_usdt, 8),
        commission_percentage=commission_rate * 100,
        notional_value=notional_value,
        order_type=order_type
    )

def calculate_profit_with_commissions(
    buy_price: float,
    sell_price: float,
    quantity: float,
    buy_order_type: str = 'MARKET',
    sell_order_type: str = 'MARKET',
    commission_rates: Optional[CommissionRates] = None
) -> Dict[str, float]:
    """
    Calcula ganancia/pérdida considerando comisiones (función pura)
    """
    if any(price <= 0 for price in [buy_price, sell_price, quantity]):
        raise ValueError("Precios y cantidad deben ser positivos")
    
    # Calcular valores notionales
    buy_notional = quantity * buy_price
    sell_notional = quantity * sell_price
    
    # Calcular comisiones
    buy_commission = calculate_commission(buy_notional, buy_order_type, commission_rates)
    sell_commission = calculate_commission(sell_notional, sell_order_type, commission_rates)
    
    # Calcular ganancias
    gross_profit = sell_notional - buy_notional
    total_commission = buy_commission.commission_usdt + sell_commission.commission_usdt
    net_profit = gross_profit - total_commission
    
    return {
        'gross_profit': gross_profit,
        'buy_commission': buy_commission.commission_usdt,
        'sell_commission': sell_commission.commission_usdt,
        'total_commission': total_commission,
        'net_profit': net_profit,
        'profit_percentage': (net_profit / buy_notional * 100) if buy_notional > 0 else 0
    }

def validate_minimum_profit(
    buy_price: float,
    sell_price: float,
    quantity: float,
    min_profit_percentage: float = 0.5,
    buy_order_type: str = 'MARKET',
    sell_order_type: str = 'MARKET',
    commission_rates: Optional[CommissionRates] = None
) -> Tuple[bool, Dict[str, Any]]:
    """
    Valida si una operación generará ganancia mínima (función pura)
    """
    profit_data = calculate_profit_with_commissions(
        buy_price, sell_price, quantity, buy_order_type, sell_order_type, commission_rates
    )
    
    is_profitable = profit_data['profit_percentage'] >= min_profit_percentage
    
    return is_profitable, profit_data

# Función para actualizar tasas desde Binance (opcional)
async def update_commission_rates_from_binance(
    api_key: str,
    api_secret: str
) -> Optional[CommissionRates]:
    """
    Actualiza tasas de comisión desde Binance (función pura)
    """
    try:
        client = Client(api_key, api_secret)
        account_info = client.get_account()
        
        maker_commission = float(account_info.get('makerCommission', 15)) / 10000
        taker_commission = float(account_info.get('takerCommission', 15)) / 10000
        
        return CommissionRates(
            maker=maker_commission,
            taker=taker_commission
        )
    except Exception as e:
        logger.warning(f"No se pudieron actualizar comisiones desde Binance: {e}")
        return None
'''
    
    # Escribir el archivo refactorizado
    with open('app/services/commission.py', 'w') as f:
        f.write(commission_funcional)
    
    print("✅ CommissionManager refactorizado a funciones puras")

def apply_error_types():
    """Implementa tipos de error específicos"""
    print("🛡️ Implementando tipos de error específicos...")
    
    error_types = '''
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
    notional_value: float
    commission_rate: float
    
    def __post_init__(self):
        if not self.timestamp:
            from datetime import datetime
            self.timestamp = datetime.now().isoformat()

@dataclass
class ValidationError(TradingError):
    """Error de validación de datos"""
    field: str
    value: Any
    expected_type: str

@dataclass
class BinanceAPIError(TradingError):
    """Error de la API de Binance"""
    binance_code: Optional[int] = None
    binance_message: Optional[str] = None
    endpoint: Optional[str] = None

@dataclass
class InsufficientFundsError(TradingError):
    """Error de fondos insuficientes"""
    required_amount: float
    available_amount: float
    asset: str

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
'''
    
    with open('app/core/trading_errors.py', 'w') as f:
        f.write(error_types)
    
    print("✅ Tipos de error específicos implementados")

def apply_improved_schemas():
    """Implementa schemas mejorados con Pydantic"""
    print("📊 Implementando schemas mejorados...")
    
    improved_schemas = '''
"""
Schemas mejorados para validación de datos
Siguiendo mejores prácticas de Pydantic v2
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Literal, Optional, Dict, Any, List
from decimal import Decimal
import re

class TradingSymbol(str):
    """Tipo personalizado para símbolos de trading"""
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v):
        if not isinstance(v, str):
            raise ValueError('Símbolo debe ser una cadena')
        
        if not re.match(r'^[A-Z0-9]+$', v):
            raise ValueError('Símbolo debe contener solo letras mayúsculas y números')
        
        # Validar símbolos soportados
        supported_symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'DOTUSDT']
        if v not in supported_symbols:
            raise ValueError(f'Símbolo {v} no está soportado')
        
        return v.upper()

class TradingOrder(BaseModel):
    """Schema para órdenes de trading"""
    symbol: TradingSymbol
    side: Literal['BUY', 'SELL']
    quantity: Decimal = Field(..., gt=0, decimal_places=8)
    order_type: Literal['MARKET', 'LIMIT'] = 'MARKET'
    price: Optional[Decimal] = Field(None, gt=0, decimal_places=8)
    
    @field_validator('quantity')
    @classmethod
    def validate_min_quantity(cls, v: Decimal) -> Decimal:
        min_quantity = Decimal('0.001')
        if v < min_quantity:
            raise ValueError(f'Cantidad debe ser al menos {min_quantity}')
        return v
    
    @field_validator('price')
    @classmethod
    def validate_price_for_limit(cls, v: Optional[Decimal], info) -> Optional[Decimal]:
        data = info.data or {}
        if data.get('order_type') == 'LIMIT' and v is None:
            raise ValueError('Precio requerido para órdenes LIMIT')
        return v
    
    @model_validator(mode='after')
    def validate_order_consistency(self):
        """Validación adicional del modelo"""
        if self.order_type == 'LIMIT' and self.price is None:
            raise ValueError('Precio requerido para órdenes LIMIT')
        return self

class GridConfiguration(BaseModel):
    """Schema para configuración de grid trading"""
    symbol: TradingSymbol
    min_price: Decimal = Field(..., gt=0)
    max_price: Decimal = Field(..., gt=0)
    num_levels: int = Field(..., ge=2, le=100)
    quantity_per_level: Decimal = Field(..., gt=0)
    min_profit_percentage: Decimal = Field(default=Decimal('0.5'), ge=0.1, le=10.0)
    
    @field_validator('max_price')
    @classmethod
    def validate_max_price(cls, v: Decimal, info) -> Decimal:
        data = info.data or {}
        if 'min_price' in data and v <= data['min_price']:
            raise ValueError('Precio máximo debe ser mayor al precio mínimo')
        return v
    
    @field_validator('num_levels')
    @classmethod
    def validate_reasonable_levels(cls, v: int) -> int:
        if v > 50:
            raise ValueError('Número de niveles no debe exceder 50 para evitar sobrecarga')
        return v

class CommissionCalculation(BaseModel):
    """Schema para cálculos de comisión"""
    notional_value: Decimal = Field(..., gt=0)
    order_type: Literal['MARKET', 'LIMIT'] = 'MARKET'
    symbol: TradingSymbol
    commission_rate: Decimal = Field(default=Decimal('0.001'), ge=0, le=1)
    
    @field_validator('commission_rate')
    @classmethod
    def validate_reasonable_commission(cls, v: Decimal) -> Decimal:
        if v > Decimal('0.01'):  # 1%
            raise ValueError('Tasa de comisión parece excesiva')
        return v

class TradingResult(BaseModel):
    """Schema para resultados de trading"""
    success: bool
    order_id: Optional[str] = None
    executed_quantity: Optional[Decimal] = None
    executed_price: Optional[Decimal] = None
    commission_paid: Optional[Decimal] = None
    timestamp: str
    error_message: Optional[str] = None
    
    @field_validator('timestamp')
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        from datetime import datetime
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
            return v
        except ValueError:
            raise ValueError('Timestamp debe estar en formato ISO')

class PortfolioBalance(BaseModel):
    """Schema para balances de portafolio"""
    asset: str = Field(..., pattern=r'^[A-Z0-9]+$')
    free: Decimal = Field(..., ge=0)
    locked: Decimal = Field(..., ge=0)
    total: Decimal = Field(..., ge=0)
    
    @model_validator(mode='after')
    def validate_balance_consistency(self):
        """Valida que total = free + locked"""
        if self.total != self.free + self.locked:
            raise ValueError('Total debe ser igual a free + locked')
        return self

# Schemas para respuestas de API
class APIResponse(BaseModel):
    """Schema base para respuestas de API"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    timestamp: str
    
    @field_validator('timestamp')
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        from datetime import datetime
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
            return v
        except ValueError:
            raise ValueError('Timestamp debe estar en formato ISO')

class ErrorResponse(BaseModel):
    """Schema para respuestas de error"""
    success: bool = False
    error_code: str
    error_message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: str
'''
    
    with open('app/schemas/improved_validation.py', 'w') as f:
        f.write(improved_schemas)
    
    print("✅ Schemas mejorados implementados")

def apply_performance_optimizations():
    """Aplica optimizaciones de performance"""
    print("🚀 Aplicando optimizaciones de performance...")
    
    performance_utils = '''
"""
Utilidades de performance optimizadas
Siguiendo mejores prácticas de FastAPI y asyncio
"""

import asyncio
import functools
from typing import Any, Callable, Dict, Optional, TypeVar
from contextlib import asynccontextmanager
import asyncpg
import os

T = TypeVar('T')

# Cache en memoria con TTL
class MemoryCache:
    """Cache simple en memoria con TTL"""
    
    def __init__(self):
        self._cache: Dict[str, tuple[Any, float]] = {}
    
    def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            value, expiry = self._cache[key]
            if asyncio.get_event_loop().time() < expiry:
                return value
            else:
                del self._cache[key]
        return None
    
    def set(self, key: str, value: Any, ttl: float = 300):
        expiry = asyncio.get_event_loop().time() + ttl
        self._cache[key] = (value, expiry)
    
    def clear(self):
        self._cache.clear()

# Cache global
_memory_cache = MemoryCache()

def cached(ttl: float = 300):
    """Decorador para cachear resultados de funciones"""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            # Crear clave única para la función y argumentos
            key = f"{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"
            
            # Intentar obtener del cache
            cached_result = _memory_cache.get(key)
            if cached_result is not None:
                return cached_result
            
            # Ejecutar función y cachear resultado
            result = await func(*args, **kwargs)
            _memory_cache.set(key, result, ttl)
            return result
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            key = f"{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"
            
            cached_result = _memory_cache.get(key)
            if cached_result is not None:
                return cached_result
            
            result = func(*args, **kwargs)
            _memory_cache.set(key, result, ttl)
            return result
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

# Connection pooling para PostgreSQL
_db_pool: Optional[asyncpg.Pool] = None

async def get_db_pool() -> asyncpg.Pool:
    """Obtiene el pool de conexiones a la base de datos"""
    global _db_pool
    if _db_pool is None:
        _db_pool = await asyncpg.create_pool(
            os.getenv("DATABASE_URL", "postgresql://griduser:gridpass@db:5432/gridbot"),
            min_size=5,
            max_size=20,
            command_timeout=60
        )
    return _db_pool

@asynccontextmanager
async def get_db_connection():
    """Context manager para obtener conexión de la base de datos"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        yield conn

# Rate limiting funcional
class RateLimiter:
    """Rate limiter funcional"""
    
    def __init__(self, max_calls: int, time_window: float):
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls: List[float] = []
    
    async def acquire(self) -> bool:
        """Intenta adquirir un slot de rate limit"""
        now = asyncio.get_event_loop().time()
        
        # Limpiar llamadas antiguas
        self.calls = [call_time for call_time in self.calls if now - call_time < self.time_window]
        
        if len(self.calls) >= self.max_calls:
            return False
        
        self.calls.append(now)
        return True

# Lazy loading para datos pesados
class LazyLoader:
    """Cargador lazy para datos pesados"""
    
    def __init__(self, loader_func: Callable[[], Any]):
        self.loader_func = loader_func
        self._data: Optional[Any] = None
        self._loaded = False
    
    async def get_data(self) -> Any:
        """Obtiene los datos, cargándolos si es necesario"""
        if not self._loaded:
            self._data = await self.loader_func()
            self._loaded = True
        return self._data
    
    def reset(self):
        """Resetea el loader para forzar recarga"""
        self._data = None
        self._loaded = False

# Optimización de consultas
async def batch_query(
    queries: List[Callable],
    batch_size: int = 10
) -> List[Any]:
    """Ejecuta consultas en lotes para optimizar performance"""
    results = []
    
    for i in range(0, len(queries), batch_size):
        batch = queries[i:i + batch_size]
        batch_results = await asyncio.gather(*batch, return_exceptions=True)
        results.extend(batch_results)
    
    return results

# Decorador para medir performance
def measure_performance(func: Callable[..., T]) -> Callable[..., T]:
    """Decorador para medir tiempo de ejecución"""
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs) -> T:
        start_time = asyncio.get_event_loop().time()
        try:
            result = await func(*args, **kwargs)
            return result
        finally:
            end_time = asyncio.get_event_loop().time()
            print(f"{func.__name__} ejecutado en {end_time - start_time:.4f} segundos")
    
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs) -> T:
        start_time = asyncio.get_event_loop().time()
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            end_time = asyncio.get_event_loop().time()
            print(f"{func.__name__} ejecutado en {end_time - start_time:.4f} segundos")
    
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper
'''
    
    with open('app/core/performance_utils.py', 'w') as f:
        f.write(performance_utils)
    
    print("✅ Optimizaciones de performance implementadas")

def create_optimization_script():
    """Crea script para aplicar todas las optimizaciones"""
    print("📝 Creando script de optimización...")
    
    optimization_script = '''#!/bin/bash
# Script para aplicar optimizaciones de mejores prácticas

echo "🚀 Aplicando optimizaciones de mejores prácticas..."

# 1. Hacer backup del código actual
echo "1️⃣ Haciendo backup del código actual..."
cp -r app app.backup.$(date +%Y%m%d_%H%M%S)

# 2. Aplicar refactoring funcional
echo "2️⃣ Aplicando refactoring funcional..."
python3 scripts/apply_best_practices_optimization.py

# 3. Actualizar imports en archivos existentes
echo "3️⃣ Actualizando imports..."
find app -name "*.py" -exec sed -i '' 's/from app.services.commission_manager import/from app.services.commission import/g' {} \\;
find app -name "*.py" -exec sed -i '' 's/from app.core.error_handler import/from app.core.trading_errors import/g' {} \\;

# 4. Reiniciar servicios
echo "4️⃣ Reiniciando servicios..."
docker-compose restart api celery_worker

# 5. Ejecutar tests
echo "5️⃣ Ejecutando tests..."
python3 -m pytest tests/ -v

# 6. Verificar funcionamiento
echo "6️⃣ Verificando funcionamiento..."
sleep 10
curl -s http://localhost:8000/health

echo "✅ Optimizaciones aplicadas exitosamente"
echo "💡 Revisar logs para verificar que todo funciona correctamente"
'''
    
    with open('scripts/apply_optimizations.sh', 'w') as f:
        f.write(optimization_script)
    
    # Hacer el script ejecutable
    os.chmod('scripts/apply_optimizations.sh', 0o755)
    
    print("✅ Script de optimización creado")

def main():
    """Función principal"""
    print("🔧 Aplicando optimizaciones de mejores prácticas...")
    print("=" * 60)
    
    try:
        # Aplicar refactoring funcional
        apply_functional_refactoring()
        
        # Implementar tipos de error específicos
        apply_error_types()
        
        # Aplicar schemas mejorados
        apply_improved_schemas()
        
        # Aplicar optimizaciones de performance
        apply_performance_optimizations()
        
        # Crear script de optimización
        create_optimization_script()
        
        print("\n✅ Todas las optimizaciones aplicadas exitosamente!")
        print("\n📋 Resumen de cambios:")
        print("   🔄 CommissionManager → funciones puras")
        print("   🛡️ Tipos de error específicos implementados")
        print("   📊 Schemas mejorados con Pydantic")
        print("   🚀 Utilidades de performance agregadas")
        print("   📝 Script de optimización creado")
        
        print("\n🎯 Próximos pasos:")
        print("   1. Ejecutar: ./scripts/apply_optimizations.sh")
        print("   2. Revisar logs para verificar funcionamiento")
        print("   3. Ejecutar tests para validar cambios")
        print("   4. Monitorear performance del sistema")
        
    except Exception as e:
        print(f"\n❌ Error aplicando optimizaciones: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
