"""
StrategySelector para V2.5 "Low-Risk, Predictive & Adaptive Grid".
Selecciona estrategias basado en predicciones de régimen y estado de la cuenta.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

from pydantic import BaseModel, Field
from prometheus_client import Counter, Gauge, REGISTRY

from app.core.risk_manager import MarketRegime, RegimePrediction, RiskManager, PositionSizeParams


class StrategyType(Enum):
    """Tipos de estrategias disponibles"""
    GRID_TRADING = "GridTrading"
    DCA = "DCA"
    SCALPING = "Scalping"
    HOLD = "HOLD"
    HEDGING = "Hedging"


class VolatilityLevel(Enum):
    """Niveles de volatilidad"""
    LOW = "LOW_VOL"
    MODERATE = "MODERATE_VOL"
    HIGH = "HIGH_VOL"


@dataclass
class StrategyParams:
    """Parámetros específicos de estrategia"""
    grid_spacing_bps: Optional[int] = None
    grid_levels: Optional[int] = None
    order_size_usdt: Optional[float] = None
    tranche_size: Optional[float] = None
    interval: Optional[int] = None
    take_profit: Optional[float] = None
    stop_loss: Optional[float] = None
    max_exposure: Optional[float] = None


class StrategySpec(BaseModel):
    """Especificación completa de estrategia"""
    strategy_name: StrategyType
    params: StrategyParams
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    regime_prediction: RegimePrediction
    timestamp: datetime = Field(default_factory=datetime.now)


class AccountState(BaseModel):
    """Estado de la cuenta"""
    total_equity: float
    available_balance: float
    total_exposure: float
    daily_pnl: float
    max_drawdown: float
    risk_score: float


class StrategySelector:
    """
    Selector de estrategias basado en régimen de mercado y estado de la cuenta.
    """
    
    def __init__(self, risk_manager: RiskManager):
        self.risk_manager = risk_manager
        
        # Configuración de estrategias por régimen
        self.strategy_configs = {
            # RANGE + LOW_VOL
            (MarketRegime.RANGE, VolatilityLevel.LOW): {
                "strategy": StrategyType.GRID_TRADING,
                "default_params": {
                    "grid_spacing_bps": 50,
                    "grid_levels": 10,
                    "order_size_usdt": 50.0
                }
            },
            
            # BULL_TREND + MODERATE_VOL
            (MarketRegime.BULL_TREND, VolatilityLevel.MODERATE): {
                "strategy": StrategyType.DCA,
                "default_params": {
                    "tranche_size": 100.0,
                    "interval": 3600,  # 1 hora
                    "take_profit": 0.05  # 5%
                }
            },
            
            # BULL_TREND + HIGH_VOL
            (MarketRegime.BULL_TREND, VolatilityLevel.HIGH): {
                "strategy": StrategyType.SCALPING,
                "default_params": {
                    "order_size_usdt": 25.0,
                    "take_profit": 0.02,  # 2%
                    "stop_loss": 0.01,    # 1%
                    "max_exposure": 0.3   # 30%
                }
            },
            
            # BEAR_TREND
            (MarketRegime.BEAR_TREND, None): {
                "strategy": StrategyType.HOLD,
                "default_params": {}
            },
            
            # HIGH_VOLATILITY_BEAR
            (MarketRegime.HIGH_VOLATILITY_BEAR, None): {
                "strategy": StrategyType.HEDGING,
                "default_params": {
                    "max_exposure": 0.2,  # 20%
                    "stop_loss": 0.03     # 3%
                }
            },
            
            # CRASH_IMMINENT
            (MarketRegime.CRASH_IMMINENT, None): {
                "strategy": StrategyType.HOLD,
                "default_params": {}
            }
        }
        
        # Métricas: crear o reutilizar colectores ya registrados
        existing_collectors = getattr(REGISTRY, '_names_to_collectors', {})
        try:
            self.strategy_selections = existing_collectors.get('strategy_selections_total')
            if self.strategy_selections is None:
                self.strategy_selections = Counter(
                    'strategy_selections_total',
                    'Total strategy selections',
                    ['strategy', 'regime', 'volatility']
                )
        except ValueError:
            # Duplicado: reutilizar colector existente
            self.strategy_selections = getattr(REGISTRY, '_names_to_collectors', {}).get('strategy_selections_total')

        try:
            self.strategy_confidence = existing_collectors.get('strategy_confidence')
            if self.strategy_confidence is None:
                self.strategy_confidence = Gauge(
                    'strategy_confidence',
                    'Strategy selection confidence',
                    ['strategy', 'regime']
                )
        except ValueError:
            self.strategy_confidence = getattr(REGISTRY, '_names_to_collectors', {}).get('strategy_confidence')
        
        self.logger = logging.getLogger(__name__)
    
    def _determine_volatility_level(self, regime_prediction: RegimePrediction, 
                                   account_state: AccountState) -> VolatilityLevel:
        """
        Determina el nivel de volatilidad basado en predicción y estado de cuenta.
        
        Args:
            regime_prediction: Predicción de régimen
            account_state: Estado de la cuenta
            
        Returns:
            Nivel de volatilidad
        """
        # Usar predicción de régimen para determinar volatilidad
        if regime_prediction.short_regime == MarketRegime.HIGH_VOL:
            return VolatilityLevel.HIGH
        
        # Usar métricas de la cuenta como fallback
        if account_state.risk_score > 0.7:
            return VolatilityLevel.HIGH
        elif account_state.risk_score > 0.4:
            return VolatilityLevel.MODERATE
        else:
            return VolatilityLevel.LOW
    
    def _calculate_dynamic_params(self, strategy_type: StrategyType, 
                                 regime_prediction: RegimePrediction,
                                 account_state: AccountState) -> StrategyParams:
        """
        Calcula parámetros dinámicos para la estrategia.
        
        Args:
            strategy_type: Tipo de estrategia
            regime_prediction: Predicción de régimen
            account_state: Estado de la cuenta
            
        Returns:
            Parámetros de estrategia
        """
        params = StrategyParams()
        
        # Calcular tamaño de orden basado en Kelly
        if account_state.total_equity > 0:
            # Usar RiskManager para calcular tamaño dinámico
            position_params = PositionSizeParams(
                symbol="GENERIC",
                account_equity=account_state.total_equity,
                atr=0.02,  # ATR estimado
                winrate_estimate=0.6,
                avg_win_loss_ratio=1.5,
                price=1.0
            )
            
            dynamic_size = self.risk_manager.calculate_dynamic_position_size(position_params)
        else:
            dynamic_size = 50.0  # Tamaño por defecto
        
        if strategy_type == StrategyType.GRID_TRADING:
            # Ajustar spacing basado en volatilidad
            if regime_prediction.short_regime == MarketRegime.HIGH_VOL:
                spacing_bps = 100
            elif regime_prediction.short_regime == MarketRegime.RANGE:
                spacing_bps = 50
            else:
                spacing_bps = 30
            
            params.grid_spacing_bps = spacing_bps
            params.grid_levels = min(15, int(account_state.available_balance / dynamic_size))
            params.order_size_usdt = dynamic_size
            
        elif strategy_type == StrategyType.DCA:
            params.tranche_size = dynamic_size
            params.interval = 3600  # 1 hora
            params.take_profit = 0.05  # 5%
            
        elif strategy_type == StrategyType.SCALPING:
            params.order_size_usdt = dynamic_size * 0.5  # Mitad del tamaño normal
            params.take_profit = 0.02  # 2%
            params.stop_loss = 0.01    # 1%
            params.max_exposure = 0.3  # 30%
            
        elif strategy_type == StrategyType.HEDGING:
            params.max_exposure = 0.2  # 20%
            params.stop_loss = 0.03    # 3%
        
        return params
    
    def _get_strategy_config(self, regime: MarketRegime, 
                           volatility: VolatilityLevel) -> Optional[Dict[str, Any]]:
        """
        Obtiene configuración de estrategia para régimen y volatilidad.
        
        Args:
            regime: Régimen de mercado
            volatility: Nivel de volatilidad
            
        Returns:
            Configuración de estrategia
        """
        # Intentar con volatilidad específica
        key = (regime, volatility)
        if key in self.strategy_configs:
            return self.strategy_configs[key]
        
        # Fallback a configuración sin volatilidad
        key = (regime, None)
        if key in self.strategy_configs:
            return self.strategy_configs[key]
        
        # Configuración por defecto
        return {
            "strategy": StrategyType.HOLD,
            "default_params": {}
        }
    
    def select_strategy(self, regime_prediction: RegimePrediction, 
                       symbol: str, account_state: AccountState) -> StrategySpec:
        """
        Selecciona estrategia basada en predicción de régimen y estado de cuenta.
        
        Args:
            regime_prediction: Predicción de régimen
            symbol: Símbolo del trading pair
            account_state: Estado de la cuenta
            
        Returns:
            Especificación de estrategia
        """
        try:
            # Safety check: verificar si hay stop de emergencia
            if self.risk_manager.emergency_stop:
                return StrategySpec(
                    strategy_name=StrategyType.HOLD,
                    params=StrategyParams(),
                    confidence=1.0,
                    reasoning="Emergency stop active - holding all positions",
                    regime_prediction=regime_prediction
                )
            
            # Determinar volatilidad
            volatility = self._determine_volatility_level(regime_prediction, account_state)
            
            # Obtener configuración de estrategia
            config = self._get_strategy_config(regime_prediction.short_regime, volatility)
            
            if not config:
                # Fallback a HOLD
                return StrategySpec(
                    strategy_name=StrategyType.HOLD,
                    params=StrategyParams(),
                    confidence=0.5,
                    reasoning="No strategy configuration found - holding",
                    regime_prediction=regime_prediction
                )
            
            strategy_type = config["strategy"]
            
            # Calcular parámetros dinámicos
            params = self._calculate_dynamic_params(
                strategy_type, regime_prediction, account_state
            )
            
            # Calcular confianza basada en predicciones
            confidence = (regime_prediction.long_conf + regime_prediction.short_conf) / 2
            
            # Ajustar confianza basada en estado de la cuenta
            if account_state.risk_score > 0.8:
                confidence *= 0.69  # Reducir confianza si riesgo alto (estrictamente menor)
            
            if account_state.daily_pnl < -0.05:  # Pérdida diaria > 5%
                confidence *= 0.49  # Reducir confianza si pérdidas (estrictamente menor)

            # Si el régimen es BULL_TREND en ambos horizontes con confianza suficiente, preferir DCA
            if (regime_prediction.long_regime == MarketRegime.BULL_TREND and 
                regime_prediction.short_regime == MarketRegime.BULL_TREND and 
                confidence >= 0.7):
                strategy_type = StrategyType.DCA
                params = self._calculate_dynamic_params(strategy_type, regime_prediction, account_state)
            
            # Generar reasoning
            reasoning = self._generate_reasoning(
                strategy_type, regime_prediction, volatility, 
                account_state, confidence
            )
            
            # Crear especificación de estrategia
            strategy_spec = StrategySpec(
                strategy_name=strategy_type,
                params=params,
                confidence=confidence,
                reasoning=reasoning,
                regime_prediction=regime_prediction
            )
            
            # Actualizar métricas (tolerante a entornos donde no se registren)
            try:
                if hasattr(self.strategy_selections, 'labels'):
                    self.strategy_selections.labels(
                        strategy=strategy_type.value,
                        regime=regime_prediction.short_regime.value,
                        volatility=volatility.value
                    ).inc()
            except Exception:
                pass
            
            try:
                if hasattr(self.strategy_confidence, 'labels'):
                    self.strategy_confidence.labels(
                        strategy=strategy_type.value,
                        regime=regime_prediction.short_regime.value
                    ).set(confidence)
            except Exception:
                pass
            
            self.logger.info(f"Strategy selected for {symbol}: {strategy_type.value} "
                           f"(confidence: {confidence:.2f}, reasoning: {reasoning})")
            
            return strategy_spec
            
        except Exception as e:
            self.logger.error(f"Error selecting strategy for {symbol}: {e}")
            
            # Retornar estrategia segura por defecto
            return StrategySpec(
                strategy_name=StrategyType.HOLD,
                params=StrategyParams(),
                confidence=0.5,
                reasoning=f"Error in strategy selection: {str(e)} - holding for safety",
                regime_prediction=regime_prediction
            )
    
    def _generate_reasoning(self, strategy_type: StrategyType,
                          regime_prediction: RegimePrediction,
                          volatility: VolatilityLevel,
                          account_state: AccountState,
                          confidence: float) -> str:
        """
        Genera explicación del razonamiento para la selección de estrategia.
        
        Args:
            strategy_type: Tipo de estrategia seleccionada
            regime_prediction: Predicción de régimen
            volatility: Nivel de volatilidad
            account_state: Estado de la cuenta
            confidence: Confianza de la selección
            
        Returns:
            Explicación del razonamiento
        """
        reasoning_parts = []
        
        # Régimen de mercado
        reasoning_parts.append(
            f"Market regime: {regime_prediction.short_regime.value} "
            f"(confidence: {regime_prediction.short_conf:.2f})"
        )
        
        # Volatilidad
        reasoning_parts.append(f"Volatility level: {volatility.value}")
        
        # Estado de la cuenta
        if account_state.risk_score > 0.7:
            reasoning_parts.append("High risk score - conservative approach")
        elif account_state.daily_pnl < -0.03:
            reasoning_parts.append("Daily losses detected - reducing exposure")
        
        # Justificación de estrategia
        if strategy_type == StrategyType.GRID_TRADING:
            reasoning_parts.append(
                "Range-bound market with low volatility - optimal for grid trading"
            )
        elif strategy_type == StrategyType.DCA:
            reasoning_parts.append(
                "Bull trend with moderate volatility - DCA strategy for trend following"
            )
        elif strategy_type == StrategyType.SCALPING:
            reasoning_parts.append(
                "Bull trend with high volatility - scalping for quick profits"
            )
        elif strategy_type == StrategyType.HOLD:
            reasoning_parts.append(
                "Bear market or high risk conditions - holding positions"
            )
        elif strategy_type == StrategyType.HEDGING:
            reasoning_parts.append(
                "High volatility bear market - hedging for risk management"
            )
        
        # Confianza
        if confidence > 0.8:
            reasoning_parts.append("High confidence in prediction")
        elif confidence < 0.6:
            reasoning_parts.append("Low confidence - conservative parameters")
        else:
            reasoning_parts.append("High confidence")
        # Añadir mensaje explícito de pérdidas diarias si aplica
        if account_state.daily_pnl < 0:
            reasoning_parts.append("Daily losses detected")
        
        return " | ".join(reasoning_parts)
    
    def get_strategy_history(self, symbol: str, limit: int = 10) -> List[StrategySpec]:
        """
        Obtiene historial de selecciones de estrategia para un símbolo.
        
        Args:
            symbol: Símbolo del trading pair
            limit: Número máximo de entradas
            
        Returns:
            Lista de especificaciones de estrategia
        """
        # TODO: Implementar persistencia de historial
        # Por ahora, retornar lista vacía
        return []
    
    def get_strategy_performance(self, strategy_type: StrategyType, 
                               timeframe_days: int = 30) -> Dict[str, Any]:
        """
        Obtiene métricas de rendimiento de una estrategia.
        
        Args:
            strategy_type: Tipo de estrategia
            timeframe_days: Período de tiempo en días
            
        Returns:
            Métricas de rendimiento
        """
        # TODO: Implementar cálculo de métricas de rendimiento
        return {
            "strategy": strategy_type.value,
            "timeframe_days": timeframe_days,
            "total_trades": 0,
            "win_rate": 0.0,
            "avg_profit": 0.0,
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0
        }
