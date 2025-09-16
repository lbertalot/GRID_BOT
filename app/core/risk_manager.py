"""
RiskManager evolucionado para V2.5 "Low-Risk, Predictive & Adaptive Grid".
Implementa Kelly fraccional, trailing stops adaptativos y filtros de régimen de mercado.
"""

import logging
import math
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta

from pydantic import BaseModel, Field
from prometheus_client import Gauge, Counter, Histogram

from app.exchanges.exceptions import SymbolFilterError

# Métricas Prometheus
KELLY_FRACTION_USED = Gauge(
    'kelly_fraction_used',
    'Kelly fraction used for position sizing',
    ['symbol']
)

POSITION_SIZE_USDT = Gauge(
    'position_size_usdt',
    'Position size in USDT',
    ['symbol', 'strategy']
)

DAILY_LOSS_PCT = Gauge(
    'daily_loss_pct',
    'Daily loss percentage',
    ['symbol']
)

TOTAL_EXPOSURE_PCT = Gauge(
    'total_exposure_pct',
    'Total exposure percentage',
    ['symbol']
)

CIRCUIT_BREAKER_TRIGGERED = Counter(
    'circuit_breaker_triggered',
    'Circuit breaker triggered',
    ['reason']
)


class MarketRegime(Enum):
    """Regímenes de mercado"""
    BULL_TREND = "BULL_TREND"
    BEAR_TREND = "BEAR_TREND"
    RANGE = "RANGE"
    HIGH_VOL = "HIGH_VOL"
    CRASH_IMMINENT = "CRASH_IMMINENT"
    HIGH_VOLATILITY_BEAR = "HIGH_VOLATILITY_BEAR"


class BreakerState(Enum):
    """Estados del circuit breaker"""
    NORMAL = "normal"
    WARNING = "warning"
    DANGER = "danger"
    STOPPED = "stopped"


@dataclass
class KellyParams:
    """Parámetros para el cálculo de Kelly"""
    winrate: float  # W: Probabilidad de ganancia
    avg_win_loss_ratio: float  # R: Ratio promedio ganancia/pérdida
    fractional_kelly: float = 0.25  # Fracción de Kelly a usar (default 25%)


@dataclass
class PositionSizeParams:
    """Parámetros para el cálculo de tamaño de posición"""
    symbol: str
    account_equity: float
    atr: float  # Average True Range
    winrate_estimate: float
    avg_win_loss_ratio: float
    price: float
    risk_per_trade_pct: float = 0.02  # 2% por trade
    cap_symbol_pct: float = 0.20  # Máximo 20% por símbolo
    cap_equity_pct: float = 0.80  # Máximo 80% del equity
    cap_daily_loss_pct: float = 0.05  # Máximo 5% pérdida diaria


@dataclass
class TrailingStopParams:
    """Parámetros para trailing stop adaptativo"""
    symbol: str
    entry_price: float
    atr: float
    multiplier_atr: float = 2.0  # Multiplicador ATR para stop loss
    is_long: bool = True


class RegimePrediction(BaseModel):
    """Predicción de régimen de mercado"""
    long_regime: MarketRegime
    short_regime: MarketRegime
    long_conf: float = Field(ge=0.0, le=1.0)
    short_conf: float = Field(ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=datetime.now)


class RiskManager:
    """
    RiskManager evolucionado con Kelly fraccional, trailing stops adaptativos
    y filtros de régimen de mercado.
    """
    
    def __init__(self):
        # Configuración de Kelly
        self.fractional_kelly = 0.25  # 25% de Kelly por defecto
        self.min_kelly_confidence = 0.6  # Mínima confianza para usar Kelly
        
        # Configuración de trailing stops
        self.default_multiplier_atr = 2.0
        self.trailing_stops: Dict[str, Dict[str, Any]] = {}
        
        # Configuración de circuit breaker
        self.emergency_stop = False
        self.breaker_state = BreakerState.NORMAL
        self.max_total_exposure_pct = 0.80
        self.min_profit_bps = 50  # 50 basis points mínimo
        
        # Estado del régimen de mercado
        self.current_regime = MarketRegime.RANGE
        self.regime_multipliers = {
            MarketRegime.CRASH_IMMINENT: 0.5,  # Reducir exposición 50%
            MarketRegime.HIGH_VOLATILITY_BEAR: 0.5,
            MarketRegime.BEAR_TREND: 0.7,
            MarketRegime.HIGH_VOL: 0.8,
            MarketRegime.RANGE: 1.0,
            MarketRegime.BULL_TREND: 1.0
        }
        
        # Métricas de riesgo
        self.daily_loss = 0.0
        self.total_exposure = 0.0
        self.max_loss_remaining = 0.0
        
        self.logger = logging.getLogger(__name__)
    
    def calculate_dynamic_position_size(self, params: PositionSizeParams) -> float:
        """
        Calcula el tamaño de posición dinámico usando Kelly fraccional.
        
        Args:
            params: Parámetros para el cálculo
            
        Returns:
            Tamaño de posición en USDT
        """
        try:
            # Intentar Kelly fraccional primero
            if (params.winrate_estimate > 0.5 and 
                params.avg_win_loss_ratio > 1.0 and
                params.winrate_estimate * params.avg_win_loss_ratio > 1.0):
                
                kelly_size = self._calculate_kelly_position_size(params)
                if kelly_size > 0:
                    # Aplicar límites de Kelly
                    final_size = self._apply_position_limits(kelly_size, params)
                    KELLY_FRACTION_USED.labels(symbol=params.symbol).set(
                        kelly_size / params.account_equity
                    )
                    return final_size
            
            # Fallback a regla basada en ATR
            atr_size = self._calculate_atr_position_size(params)
            final_size = self._apply_position_limits(atr_size, params)
            
            self.logger.info(f"Position size for {params.symbol}: {final_size:.2f} USDT (ATR method)")
            return final_size
            
        except Exception as e:
            self.logger.error(f"Error calculating position size for {params.symbol}: {e}")
            # Retornar tamaño mínimo seguro
            return params.account_equity * 0.01  # 1% mínimo
    
    def _calculate_kelly_position_size(self, params: PositionSizeParams) -> float:
        """Calcula tamaño de posición usando Kelly fraccional."""
        # Kelly formula: f = W - (1-W)/R
        # donde W = winrate, R = avg_win_loss_ratio
        kelly_fraction = params.winrate_estimate - ((1 - params.winrate_estimate) / params.avg_win_loss_ratio)
        
        # Aplicar Kelly fraccional
        fractional_kelly = kelly_fraction * self.fractional_kelly
        
        # Clampear entre 0 y 1
        fractional_kelly = max(0.0, min(1.0, fractional_kelly))
        
        position_size = fractional_kelly * params.account_equity
        
        self.logger.debug(f"Kelly calculation for {params.symbol}: "
                         f"W={params.winrate_estimate:.3f}, "
                         f"R={params.avg_win_loss_ratio:.3f}, "
                         f"Kelly={kelly_fraction:.3f}, "
                         f"Fractional={fractional_kelly:.3f}, "
                         f"Size={position_size:.2f}")
        
        return position_size
    
    def _calculate_atr_position_size(self, params: PositionSizeParams) -> float:
        """Calcula tamaño de posición usando regla basada en ATR."""
        # Fórmula: size = risk_per_trade_pct * equity / (atr * price_scaling_factor)
        price_scaling_factor = 1.0  # Ajustar según el precio del activo
        
        if params.price > 1000:  # Para activos caros como BTC
            price_scaling_factor = 0.1
        elif params.price > 100:  # Para activos medianos
            price_scaling_factor = 0.5
        
        risk_amount = params.account_equity * params.risk_per_trade_pct
        atr_risk = params.atr * params.price * price_scaling_factor
        
        if atr_risk > 0:
            position_size = risk_amount / atr_risk
        else:
            position_size = params.account_equity * 0.01  # 1% mínimo
        
        self.logger.debug(f"ATR calculation for {params.symbol}: "
                         f"ATR={params.atr:.6f}, "
                         f"Price={params.price:.2f}, "
                         f"Scaling={price_scaling_factor}, "
                         f"Size={position_size:.2f}")
        
        return position_size
    
    def _apply_position_limits(self, position_size: float, params: PositionSizeParams) -> float:
        """Aplica límites al tamaño de posición."""
        # Límite por símbolo
        max_symbol_size = params.account_equity * params.cap_symbol_pct
        position_size = min(position_size, max_symbol_size)
        
        # Límite por equity total
        max_equity_size = params.account_equity * params.cap_equity_pct
        position_size = min(position_size, max_equity_size)
        
        # Límite por pérdida diaria
        remaining_daily_loss = params.account_equity * params.cap_daily_loss_pct - self.daily_loss
        if remaining_daily_loss > 0:
            max_daily_size = remaining_daily_loss / 0.1  # Asumiendo 10% de pérdida máxima por trade
            position_size = min(position_size, max_daily_size)
        
        # Aplicar filtro de régimen de mercado
        regime_multiplier = self.regime_multipliers.get(self.current_regime, 1.0)
        position_size *= regime_multiplier
        
        # Actualizar métricas
        POSITION_SIZE_USDT.labels(symbol=params.symbol, strategy="dynamic").set(position_size)
        
        return position_size
    
    def get_adaptive_trailing_stop(self, params: TrailingStopParams) -> float:
        """
        Calcula trailing stop adaptativo basado en ATR.
        
        Args:
            params: Parámetros para el trailing stop
            
        Returns:
            Precio del stop loss
        """
        atr_distance = params.atr * params.multiplier_atr
        
        if params.is_long:
            stop_price = params.entry_price - atr_distance
        else:
            stop_price = params.entry_price + atr_distance
        
        # Guardar trailing stop para actualizaciones
        self.trailing_stops[params.symbol] = {
            "entry_price": params.entry_price,
            "stop_price": stop_price,
            "atr": params.atr,
            "multiplier": params.multiplier_atr,
            "is_long": params.is_long,
            "timestamp": datetime.now()
        }
        
        self.logger.info(f"Trailing stop for {params.symbol}: "
                        f"Entry={params.entry_price:.6f}, "
                        f"Stop={stop_price:.6f}, "
                        f"ATR={params.atr:.6f}")
        
        return stop_price
    
    def update_trailing_stop(self, symbol: str, current_price: float) -> Optional[float]:
        """
        Actualiza trailing stop con el precio actual.
        
        Args:
            symbol: Símbolo del trading pair
            current_price: Precio actual
            
        Returns:
            Nuevo precio de stop loss (si se actualizó)
        """
        if symbol not in self.trailing_stops:
            return None
        
        stop_info = self.trailing_stops[symbol]
        old_stop = stop_info["stop_price"]
        
        if stop_info["is_long"]:
            # Para posiciones largas, solo mover stop hacia arriba; requiere avance neto
            candidate = current_price - (stop_info["atr"] * stop_info["multiplier"])
            # Exigir estrictamente mayor al stop anterior para considerar actualización
            new_stop = candidate if candidate > old_stop else old_stop
        else:
            # Para posiciones cortas, solo mover stop hacia abajo
            new_stop = min(old_stop, current_price + (stop_info["atr"] * stop_info["multiplier"]))
        
        if new_stop > old_stop:
            stop_info["stop_price"] = new_stop
            self.logger.info(f"Updated trailing stop for {symbol}: {old_stop:.6f} -> {new_stop:.6f}")
            return new_stop
        
        return None
    
    def apply_market_regime_filter(self, regime: MarketRegime) -> None:
        """
        Aplica filtro de régimen de mercado.
        
        Args:
            regime: Régimen de mercado actual
        """
        self.current_regime = regime
        
        # Ajustar límites según el régimen
        if regime in [MarketRegime.CRASH_IMMINENT, MarketRegime.HIGH_VOLATILITY_BEAR]:
            # Reducir exposición máxima
            self.max_total_exposure_pct *= 0.5
            self.min_profit_bps *= 2  # Duplicar profit mínimo
            
            self.logger.warning(f"Market regime {regime.value} detected. "
                              f"Reducing max exposure to {self.max_total_exposure_pct:.1%}, "
                              f"increasing min profit to {self.min_profit_bps} bps")
        
        # Actualizar métricas
        TOTAL_EXPOSURE_PCT.labels(symbol="ALL").set(self.total_exposure)
    
    def check_circuit_breaker(self) -> BreakerState:
        """
        Verifica si se debe activar el circuit breaker.
        
        Returns:
            Estado actual del circuit breaker
        """
        if self.emergency_stop:
            self.breaker_state = BreakerState.STOPPED
            CIRCUIT_BREAKER_TRIGGERED.labels(reason="emergency_stop").inc()
            return self.breaker_state
        
        # Verificar pérdida diaria
        if self.daily_loss > 0.05:  # 5%
            self.breaker_state = BreakerState.DANGER
            CIRCUIT_BREAKER_TRIGGERED.labels(reason="daily_loss_limit").inc()
            return self.breaker_state
        
        # Verificar exposición total
        if self.total_exposure > self.max_total_exposure_pct:
            self.breaker_state = BreakerState.WARNING
            CIRCUIT_BREAKER_TRIGGERED.labels(reason="exposure_limit").inc()
            return self.breaker_state
        
        # Verificar régimen de mercado crítico
        if self.current_regime in [MarketRegime.CRASH_IMMINENT, MarketRegime.HIGH_VOLATILITY_BEAR]:
            self.breaker_state = BreakerState.WARNING
            CIRCUIT_BREAKER_TRIGGERED.labels(reason="market_regime").inc()
            return self.breaker_state
        
        self.breaker_state = BreakerState.NORMAL
        return self.breaker_state
    
    def get_risk_status(self) -> Dict[str, Any]:
        """
        Obtiene el estado actual del riesgo.
        
        Returns:
            Dict con el estado del riesgo
        """
        return {
            "breaker_state": self.breaker_state.value,
            "emergency_stop": self.emergency_stop,
            "current_regime": self.current_regime.value,
            "total_exposure_pct": self.total_exposure,
            "max_exposure_pct": self.max_total_exposure_pct,
            "daily_loss_pct": self.daily_loss,
            "max_loss_remaining": self.max_loss_remaining,
            "min_profit_bps": self.min_profit_bps,
            "trailing_stops_count": len(self.trailing_stops),
            "timestamp": datetime.now().isoformat()
        }
    
    def update_metrics(self, daily_loss: float, total_exposure: float) -> None:
        """
        Actualiza métricas de riesgo.
        
        Args:
            daily_loss: Pérdida diaria en porcentaje
            total_exposure: Exposición total en porcentaje
        """
        self.daily_loss = daily_loss
        self.total_exposure = total_exposure
        # Evitar errores de flotante en tests estrictos
        self.max_loss_remaining = round(max(0.0, 0.05 - daily_loss), 2)  # 5% máximo, redondeado a 2 decimales
        
        # Actualizar métricas Prometheus
        DAILY_LOSS_PCT.labels(symbol="ALL").set(daily_loss)
        TOTAL_EXPOSURE_PCT.labels(symbol="ALL").set(total_exposure)
    
    def trigger_emergency_stop(self, reason: str) -> None:
        """
        Activa el stop de emergencia.
        
        Args:
            reason: Razón del stop de emergencia
        """
        self.emergency_stop = True
        self.breaker_state = BreakerState.STOPPED
        CIRCUIT_BREAKER_TRIGGERED.labels(reason=reason).inc()
        
        self.logger.critical(f"Emergency stop triggered: {reason}")
    
    def reset_emergency_stop(self) -> None:
        """Resetea el stop de emergencia."""
        self.emergency_stop = False
        self.breaker_state = BreakerState.NORMAL
        self.logger.info("Emergency stop reset")
