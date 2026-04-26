from pydantic import BaseModel, Field
from pydantic import field_validator
from typing import Optional, Dict, Any
import re


class OrderRequest(BaseModel):
    symbol: str = Field(
        ..., min_length=1, max_length=20, description="Símbolo del par de trading"
    )
    side: str = Field(..., description="Lado de la orden")
    quantity: float = Field(..., gt=0, le=1000, description="Cantidad a operar")
    type: str = Field(default="MARKET", description="Tipo de orden")
    price: Optional[float] = Field(None, gt=0, description="Precio para órdenes LIMIT")

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        if not re.match(r"^[A-Z0-9]+$", v):
            raise ValueError("Símbolo debe contener solo letras mayúsculas y números")
        return v.upper()

    @field_validator("side")
    @classmethod
    def validate_side(cls, v: str) -> str:
        if v not in ["BUY", "SELL"]:
            raise ValueError("Lado debe ser BUY o SELL")
        return v

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in ["MARKET", "LIMIT"]:
            raise ValueError("Tipo debe ser MARKET o LIMIT")
        return v

    @field_validator("price")
    @classmethod
    def validate_price_for_limit(cls, v: Optional[float], info):
        data = info.data or {}
        if data.get("type") == "LIMIT" and v is None:
            raise ValueError("Precio requerido para órdenes LIMIT")
        return v


class GridParams(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    min_price: float = Field(..., gt=0, le=1000000)
    max_price: float = Field(..., gt=0, le=1000000)
    grids: int = Field(..., gt=1, le=100)
    quantity: float = Field(..., gt=0, le=1000)
    last_action: Optional[str] = Field(None)

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        if not re.match(r"^[A-Z0-9]+$", v):
            raise ValueError("Símbolo debe contener solo letras mayúsculas y números")
        return v.upper()

    @field_validator("max_price")
    @classmethod
    def validate_max_price(cls, v: float, info):
        data = info.data or {}
        if "min_price" in data and v <= data["min_price"]:
            raise ValueError("Precio máximo debe ser mayor al precio mínimo")
        return v

    @field_validator("last_action")
    @classmethod
    def validate_last_action(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ["BUY", "SELL"]:
            raise ValueError("Última acción debe ser BUY, SELL o None")
        return v


class StrategyParams(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    interval: str = Field(..., description="Intervalo de tiempo")
    limit: int = Field(..., gt=0, le=1000)
    balances: Dict[str, float] = Field(..., description="Balances disponibles")
    params: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        if not re.match(r"^[A-Z0-9]+$", v):
            raise ValueError("Símbolo debe contener solo letras mayúsculas y números")
        return v.upper()

    @field_validator("interval")
    @classmethod
    def validate_interval(cls, v: str) -> str:
        valid_intervals = [
            "1m",
            "3m",
            "5m",
            "15m",
            "30m",
            "1h",
            "2h",
            "4h",
            "6h",
            "8h",
            "12h",
            "1d",
            "3d",
            "1w",
            "1M",
        ]
        if v not in valid_intervals:
            raise ValueError(f"Intervalo debe ser uno de: {valid_intervals}")
        return v

    @field_validator("balances")
    @classmethod
    def validate_balances(cls, v: Dict[str, float]) -> Dict[str, float]:
        for asset, amount in v.items():
            if amount < 0:
                raise ValueError(f"Balance de {asset} no puede ser negativo")
        return v
