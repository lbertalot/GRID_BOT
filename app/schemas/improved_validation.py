"""
Schemas mejorados para validación de datos
Siguiendo mejores prácticas de Pydantic v2
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Literal, Optional, Dict, Any
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
            raise ValueError("Símbolo debe ser una cadena")

        if not re.match(r"^[A-Z0-9]+$", v):
            raise ValueError("Símbolo debe contener solo letras mayúsculas y números")

        # Validar símbolos soportados
        supported_symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT", "DOTUSDT"]
        if v not in supported_symbols:
            raise ValueError(f"Símbolo {v} no está soportado")

        return v.upper()


class TradingOrder(BaseModel):
    """Schema para órdenes de trading"""

    symbol: TradingSymbol
    side: Literal["BUY", "SELL"]
    quantity: Decimal = Field(..., gt=0, decimal_places=8)
    order_type: Literal["MARKET", "LIMIT"] = "MARKET"
    price: Optional[Decimal] = Field(None, gt=0, decimal_places=8)

    @field_validator("quantity")
    @classmethod
    def validate_min_quantity(cls, v: Decimal) -> Decimal:
        min_quantity = Decimal("0.001")
        if v < min_quantity:
            raise ValueError(f"Cantidad debe ser al menos {min_quantity}")
        return v

    @field_validator("price")
    @classmethod
    def validate_price_for_limit(cls, v: Optional[Decimal], info) -> Optional[Decimal]:
        data = info.data or {}
        if data.get("order_type") == "LIMIT" and v is None:
            raise ValueError("Precio requerido para órdenes LIMIT")
        return v

    @model_validator(mode="after")
    def validate_order_consistency(self):
        """Validación adicional del modelo"""
        if self.order_type == "LIMIT" and self.price is None:
            raise ValueError("Precio requerido para órdenes LIMIT")
        return self


class GridConfiguration(BaseModel):
    """Schema para configuración de grid trading"""

    symbol: TradingSymbol
    min_price: Decimal = Field(..., gt=0)
    max_price: Decimal = Field(..., gt=0)
    num_levels: int = Field(..., ge=2, le=100)
    quantity_per_level: Decimal = Field(..., gt=0)
    min_profit_percentage: Decimal = Field(default=Decimal("0.5"), ge=0.1, le=10.0)

    @field_validator("max_price")
    @classmethod
    def validate_max_price(cls, v: Decimal, info) -> Decimal:
        data = info.data or {}
        if "min_price" in data and v <= data["min_price"]:
            raise ValueError("Precio máximo debe ser mayor al precio mínimo")
        return v

    @field_validator("num_levels")
    @classmethod
    def validate_reasonable_levels(cls, v: int) -> int:
        if v > 50:
            raise ValueError(
                "Número de niveles no debe exceder 50 para evitar sobrecarga"
            )
        return v


class CommissionCalculation(BaseModel):
    """Schema para cálculos de comisión"""

    notional_value: Decimal = Field(..., gt=0)
    order_type: Literal["MARKET", "LIMIT"] = "MARKET"
    symbol: TradingSymbol
    commission_rate: Decimal = Field(default=Decimal("0.001"), ge=0, le=1)

    @field_validator("commission_rate")
    @classmethod
    def validate_reasonable_commission(cls, v: Decimal) -> Decimal:
        if v > Decimal("0.01"):  # 1%
            raise ValueError("Tasa de comisión parece excesiva")
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

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        from datetime import datetime

        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
            return v
        except ValueError:
            raise ValueError("Timestamp debe estar en formato ISO")


class PortfolioBalance(BaseModel):
    """Schema para balances de portafolio"""

    asset: str = Field(..., pattern=r"^[A-Z0-9]+$")
    free: Decimal = Field(..., ge=0)
    locked: Decimal = Field(..., ge=0)
    total: Decimal = Field(..., ge=0)

    @model_validator(mode="after")
    def validate_balance_consistency(self):
        """Valida que total = free + locked"""
        if self.total != self.free + self.locked:
            raise ValueError("Total debe ser igual a free + locked")
        return self


# Schemas para respuestas de API
class APIResponse(BaseModel):
    """Schema base para respuestas de API"""

    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    timestamp: str

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        from datetime import datetime

        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
            return v
        except ValueError:
            raise ValueError("Timestamp debe estar en formato ISO")


class ErrorResponse(BaseModel):
    """Schema para respuestas de error"""

    success: bool = False
    error_code: str
    error_message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: str
