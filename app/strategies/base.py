#!/usr/bin/env python3
"""
⚠️ DEPRECATED — cleanup-archive-agent (2026-04-17)

Este directorio (`app/strategies/`) está reemplazado por `app/services/strategies/`,
que es el directorio activo con las estrategias en uso.

Migra todos los imports a:
    from app.services.strategies.base import BaseStrategy

---
Framework Base de Estrategias de Trading
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class StrategyType(Enum):
    """Tipos de estrategias disponibles"""

    GRID = "grid"
    DCA = "dca"
    SCALPING = "scalping"
    ARBITRAGE = "arbitrage"
    RSI_MACD = "rsi_macd"
    TRAILING_STOP = "trailing_stop"


class OrderSide(Enum):
    """Lados de las órdenes"""

    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(Enum):
    """Estados de las órdenes"""

    PENDING = "PENDING"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass
class Order:
    """Representa una orden de trading"""

    symbol: str
    side: OrderSide
    quantity: float
    price: float
    order_id: Optional[str] = None
    status: OrderStatus = OrderStatus.PENDING
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class TradingResult:
    """Resultado de una operación de trading"""

    orders: List[Order]
    strategy_type: StrategyType
    total_profit: float = 0.0
    total_volume: float = 0.0
    success: bool = True
    error_message: Optional[str] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class StrategyConfig(BaseModel):
    """Configuración base para estrategias"""

    symbol: str = Field(..., description="Símbolo del activo")
    strategy_type: StrategyType = Field(..., description="Tipo de estrategia")
    investment_amount: float = Field(gt=0, description="Cantidad a invertir en USDT")
    risk_tolerance: float = Field(
        ge=0.1, le=1.0, default=0.5, description="Tolerancia al riesgo"
    )
    enabled: bool = Field(default=True, description="Si la estrategia está habilitada")

    class Config:
        use_enum_values = True


class StrategyMetrics(BaseModel):
    """Métricas de rendimiento de una estrategia"""

    strategy_type: StrategyType
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_profit: float = 0.0
    total_volume: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    avg_trade_duration: float = 0.0
    last_trade_time: Optional[datetime] = None

    class Config:
        use_enum_values = True


class TradingStrategy(ABC):
    """
    Clase abstracta base para todas las estrategias de trading
    """

    def __init__(self, config: StrategyConfig):
        self.config = config
        self.metrics = StrategyMetrics(strategy_type=config.strategy_type)
        self.is_running = False
        self.last_execution = None

    @abstractmethod
    async def execute(self) -> TradingResult:
        """
        Ejecuta la estrategia de trading

        Returns:
            TradingResult con el resultado de la ejecución
        """
        pass

    @abstractmethod
    async def validate_config(self) -> bool:
        """
        Valida la configuración de la estrategia

        Returns:
            True si la configuración es válida
        """
        pass

    @abstractmethod
    async def get_current_position(self) -> Dict[str, Any]:
        """
        Obtiene la posición actual para el símbolo

        Returns:
            Dict con información de la posición actual
        """
        pass

    async def start(self) -> bool:
        """
        Inicia la estrategia

        Returns:
            True si se inició correctamente
        """
        if not await self.validate_config():
            return False

        self.is_running = True
        return True

    async def stop(self) -> bool:
        """
        Detiene la estrategia

        Returns:
            True si se detuvo correctamente
        """
        self.is_running = False
        return True

    async def update_metrics(self, result: TradingResult):
        """
        Actualiza las métricas de la estrategia

        Args:
            result: Resultado de la ejecución
        """
        if result.success:
            self.metrics.total_trades += len(result.orders)
            self.metrics.total_profit += result.total_profit
            self.metrics.total_volume += result.total_volume

            # Calcular win rate
            if result.total_profit > 0:
                self.metrics.winning_trades += 1
            elif result.total_profit < 0:
                self.metrics.losing_trades += 1

            if self.metrics.total_trades > 0:
                self.metrics.win_rate = (
                    self.metrics.winning_trades / self.metrics.total_trades
                )

        self.metrics.last_trade_time = datetime.now()
        self.last_execution = datetime.now()

    def get_metrics(self) -> StrategyMetrics:
        """
        Obtiene las métricas actuales de la estrategia

        Returns:
            StrategyMetrics con las métricas actuales
        """
        return self.metrics

    async def get_status(self) -> Dict[str, Any]:
        """
        Obtiene el estado actual de la estrategia

        Returns:
            Dict con el estado de la estrategia
        """
        return {
            "strategy_type": self.config.strategy_type.value,
            "symbol": self.config.symbol,
            "is_running": self.is_running,
            "enabled": self.config.enabled,
            "last_execution": self.last_execution.isoformat()
            if self.last_execution
            else None,
            "metrics": self.metrics.dict(),
            "config": self.config.dict(),
        }
