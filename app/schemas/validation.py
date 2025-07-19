from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any
from decimal import Decimal
import re

class OrderRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20, description="Símbolo del par de trading")
    side: str = Field(..., description="Lado de la orden")
    quantity: float = Field(..., gt=0, le=1000, description="Cantidad a operar")
    type: str = Field(default="MARKET", description="Tipo de orden")
    price: Optional[float] = Field(None, gt=0, description="Precio para órdenes LIMIT")
    
    @validator('symbol')
    def validate_symbol(cls, v):
        if not re.match(r'^[A-Z0-9]+$', v):
            raise ValueError('Símbolo debe contener solo letras mayúsculas y números')
        return v.upper()
    
    @validator('side')
    def validate_side(cls, v):
        if v not in ['BUY', 'SELL']:
            raise ValueError('Lado debe ser BUY o SELL')
        return v
    
    @validator('type')
    def validate_type(cls, v):
        if v not in ['MARKET', 'LIMIT']:
            raise ValueError('Tipo debe ser MARKET o LIMIT')
        return v
    
    @validator('price')
    def validate_price_for_limit(cls, v, values):
        if values.get('type') == 'LIMIT' and v is None:
            raise ValueError('Precio requerido para órdenes LIMIT')
        return v

class GridParams(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    min_price: float = Field(..., gt=0, le=1000000)
    max_price: float = Field(..., gt=0, le=1000000)
    grids: int = Field(..., gt=1, le=100)
    quantity: float = Field(..., gt=0, le=1000)
    last_action: Optional[str] = Field(None)
    
    @validator('symbol')
    def validate_symbol(cls, v):
        if not re.match(r'^[A-Z0-9]+$', v):
            raise ValueError('Símbolo debe contener solo letras mayúsculas y números')
        return v.upper()
    
    @validator('max_price')
    def validate_max_price(cls, v, values):
        if 'min_price' in values and v <= values['min_price']:
            raise ValueError('Precio máximo debe ser mayor al precio mínimo')
        return v
    
    @validator('last_action')
    def validate_last_action(cls, v):
        if v is not None and v not in ['BUY', 'SELL']:
            raise ValueError('Última acción debe ser BUY, SELL o None')
        return v

class StrategyParams(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    interval: str = Field(..., description="Intervalo de tiempo")
    limit: int = Field(..., gt=0, le=1000)
    balances: Dict[str, float] = Field(..., description="Balances disponibles")
    params: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('symbol')
    def validate_symbol(cls, v):
        if not re.match(r'^[A-Z0-9]+$', v):
            raise ValueError('Símbolo debe contener solo letras mayúsculas y números')
        return v.upper()
    
    @validator('interval')
    def validate_interval(cls, v):
        valid_intervals = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '3d', '1w', '1M']
        if v not in valid_intervals:
            raise ValueError(f'Intervalo debe ser uno de: {valid_intervals}')
        return v
    
    @validator('balances')
    def validate_balances(cls, v):
        for asset, amount in v.items():
            if amount < 0:
                raise ValueError(f'Balance de {asset} no puede ser negativo')
        return v 