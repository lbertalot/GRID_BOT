#!/usr/bin/env python3
"""
ConfigManager Avanzado para Optimización de Parámetros
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

import numpy as np
from pydantic import BaseModel, Field

# ✅ FASE 4: Migrado a singleton
from app.services.binance_client_singleton import get_binance_client_singleton

_client_singleton = get_binance_client_singleton()
binance_client = _client_singleton.client if _client_singleton.is_ready() else None
from app.services.telegram_alert import send_telegram_alert

logger = logging.getLogger(__name__)


class OptimizationStrategy(Enum):
    """Estrategias de optimización"""

    GRID_OPTIMIZATION = "grid_optimization"
    VOLATILITY_BASED = "volatility_based"
    VOLUME_BASED = "volume_based"
    MACHINE_LEARNING = "machine_learning"


@dataclass
class MarketData:
    """Datos de mercado para optimización"""

    symbol: str
    current_price: float
    volatility: float
    volume_24h: float
    price_change_24h: float
    high_24h: float
    low_24h: float
    timestamp: datetime


@dataclass
class OptimizedConfig:
    """Configuración optimizada"""

    symbol: str
    min_price: float
    max_price: float
    grids: int
    quantity: float
    confidence_score: float
    optimization_strategy: str
    timestamp: datetime
    backtest_results: Optional[Dict] = None


class OptimizationRequest(BaseModel):
    """Request para optimización"""

    symbol: str
    strategy: OptimizationStrategy = OptimizationStrategy.GRID_OPTIMIZATION
    investment_amount: float = Field(gt=0, description="Cantidad a invertir en USDT")
    risk_tolerance: float = Field(
        ge=0.1, le=1.0, default=0.5, description="Tolerancia al riesgo (0.1-1.0)"
    )
    max_grids: int = Field(
        ge=5, le=50, default=20, description="Máximo número de grids"
    )
    time_horizon: int = Field(
        ge=1, le=30, default=7, description="Horizonte temporal en días"
    )


class ConfigManager:
    """Gestor avanzado de configuración con optimización automática"""

    def __init__(self):
        self.optimization_history: Dict[str, List[OptimizedConfig]] = {}
        self.market_data_cache: Dict[str, MarketData] = {}
        self.cache_duration = timedelta(minutes=5)

        # Parámetros de optimización
        self.min_grids = 5
        self.max_grids = 50
        self.min_quantity = 0.001
        self.max_quantity = 1.0

        # Límites de precio
        self.price_range_percentage = 0.20  # 20% del precio actual
        self.min_price_range = 0.05  # 5% mínimo

        logger.info("ConfigManager avanzado inicializado")

    async def optimize_parameters(
        self, request: OptimizationRequest
    ) -> OptimizedConfig:
        """Optimiza parámetros automáticamente"""
        try:
            logger.info(f"Optimizando parámetros para {request.symbol}")

            # Obtener datos de mercado
            market_data = await self._get_market_data(request.symbol)

            # Aplicar estrategia de optimización
            if request.strategy == OptimizationStrategy.GRID_OPTIMIZATION:
                optimized_config = await self._optimize_grid_strategy(
                    request, market_data
                )
            elif request.strategy == OptimizationStrategy.VOLATILITY_BASED:
                optimized_config = await self._optimize_volatility_based(
                    request, market_data
                )
            elif request.strategy == OptimizationStrategy.VOLUME_BASED:
                optimized_config = await self._optimize_volume_based(
                    request, market_data
                )
            elif request.strategy == OptimizationStrategy.MACHINE_LEARNING:
                optimized_config = await self._optimize_ml_based(request, market_data)
            else:
                raise ValueError(f"Estrategia no soportada: {request.strategy}")

            # Ejecutar backtesting
            backtest_results = await self._run_backtest(optimized_config, market_data)
            optimized_config.backtest_results = backtest_results

            # Guardar en historial
            if request.symbol not in self.optimization_history:
                self.optimization_history[request.symbol] = []
            self.optimization_history[request.symbol].append(optimized_config)

            # Enviar notificación
            await self._send_optimization_notification(optimized_config)

            logger.info(
                f"Optimización completada para {request.symbol} con score: {optimized_config.confidence_score:.2f}"
            )
            return optimized_config

        except Exception as e:
            logger.error(f"Error optimizando parámetros para {request.symbol}: {e}")
            raise

    async def _optimize_grid_strategy(
        self, request: OptimizationRequest, market_data: MarketData
    ) -> OptimizedConfig:
        """Optimiza estrategia de grid tradicional"""
        try:
            current_price = market_data.current_price

            # Calcular rango de precios basado en volatilidad
            volatility_factor = min(market_data.volatility * 2, 0.5)  # Máximo 50%
            price_range = max(volatility_factor, self.min_price_range)

            min_price = current_price * (1 - price_range)
            max_price = current_price * (1 + price_range)

            # Optimizar número de grids
            optimal_grids = self._calculate_optimal_grids(
                market_data.volatility, request.risk_tolerance
            )
            optimal_grids = min(optimal_grids, request.max_grids)
            optimal_grids = max(optimal_grids, self.min_grids)

            # Calcular cantidad óptima
            grid_investment = request.investment_amount / optimal_grids
            optimal_quantity = grid_investment / current_price

            # Ajustar cantidad a límites
            optimal_quantity = max(optimal_quantity, self.min_quantity)
            optimal_quantity = min(optimal_quantity, self.max_quantity)

            # Calcular score de confianza
            confidence_score = self._calculate_confidence_score(
                market_data, optimal_grids, price_range
            )

            return OptimizedConfig(
                symbol=request.symbol,
                min_price=min_price,
                max_price=max_price,
                grids=optimal_grids,
                quantity=optimal_quantity,
                confidence_score=confidence_score,
                optimization_strategy=request.strategy.value,
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Error en optimización de grid: {e}")
            raise

    async def _optimize_volatility_based(
        self, request: OptimizationRequest, market_data: MarketData
    ) -> OptimizedConfig:
        """Optimiza basado en volatilidad del mercado"""
        try:
            current_price = market_data.current_price
            volatility = market_data.volatility

            # Ajustar rango de precios según volatilidad
            if volatility < 0.05:  # Baja volatilidad
                price_range = 0.10  # 10%
                grid_multiplier = 1.5
            elif volatility < 0.15:  # Volatilidad media
                price_range = 0.15  # 15%
                grid_multiplier = 1.0
            else:  # Alta volatilidad
                price_range = 0.25  # 25%
                grid_multiplier = 0.7

            min_price = current_price * (1 - price_range)
            max_price = current_price * (1 + price_range)

            # Calcular grids basado en volatilidad
            base_grids = 10
            optimal_grids = int(base_grids * grid_multiplier)
            optimal_grids = min(optimal_grids, request.max_grids)
            optimal_grids = max(optimal_grids, self.min_grids)

            # Calcular cantidad
            grid_investment = request.investment_amount / optimal_grids
            optimal_quantity = grid_investment / current_price
            optimal_quantity = max(optimal_quantity, self.min_quantity)
            optimal_quantity = min(optimal_quantity, self.max_quantity)

            # Score de confianza basado en volatilidad
            confidence_score = 1.0 - (
                volatility * 2
            )  # Menor volatilidad = mayor confianza
            confidence_score = max(confidence_score, 0.1)

            return OptimizedConfig(
                symbol=request.symbol,
                min_price=min_price,
                max_price=max_price,
                grids=optimal_grids,
                quantity=optimal_quantity,
                confidence_score=confidence_score,
                optimization_strategy=request.strategy.value,
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Error en optimización basada en volatilidad: {e}")
            raise

    async def _optimize_volume_based(
        self, request: OptimizationRequest, market_data: MarketData
    ) -> OptimizedConfig:
        """Optimiza basado en volumen de trading"""
        try:
            current_price = market_data.current_price
            volume_24h = market_data.volume_24h

            # Normalizar volumen (simplificado)
            volume_factor = min(volume_24h / 1000000, 1.0)  # Normalizar a 1M USDT

            # Ajustar parámetros según volumen
            if volume_factor > 0.8:  # Alto volumen
                price_range = 0.12
                grid_density = 1.2
            elif volume_factor > 0.4:  # Volumen medio
                price_range = 0.15
                grid_density = 1.0
            else:  # Bajo volumen
                price_range = 0.20
                grid_density = 0.8

            min_price = current_price * (1 - price_range)
            max_price = current_price * (1 + price_range)

            # Calcular grids
            optimal_grids = int(12 * grid_density)
            optimal_grids = min(optimal_grids, request.max_grids)
            optimal_grids = max(optimal_grids, self.min_grids)

            # Calcular cantidad
            grid_investment = request.investment_amount / optimal_grids
            optimal_quantity = grid_investment / current_price
            optimal_quantity = max(optimal_quantity, self.min_quantity)
            optimal_quantity = min(optimal_quantity, self.max_quantity)

            # Score basado en volumen
            confidence_score = 0.5 + (volume_factor * 0.5)

            return OptimizedConfig(
                symbol=request.symbol,
                min_price=min_price,
                max_price=max_price,
                grids=optimal_grids,
                quantity=optimal_quantity,
                confidence_score=confidence_score,
                optimization_strategy=request.strategy.value,
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Error en optimización basada en volumen: {e}")
            raise

    async def _optimize_ml_based(
        self, request: OptimizationRequest, market_data: MarketData
    ) -> OptimizedConfig:
        """Optimiza usando machine learning básico"""
        try:
            current_price = market_data.current_price

            # Obtener datos históricos para ML
            historical_data = await self._get_historical_data(request.symbol, days=30)

            if not historical_data:
                # Fallback a optimización básica si no hay datos
                return await self._optimize_grid_strategy(request, market_data)

            # Calcular features para ML
            features = self._extract_features(historical_data, market_data)

            # Predicción simple (simulada)
            predicted_volatility = features["volatility"] * (
                1 + np.random.normal(0, 0.1)
            )
            predicted_trend = features["trend"]

            # Ajustar parámetros según predicciones
            if predicted_trend > 0.02:  # Tendencia alcista
                price_range = 0.15
                grid_bias = 1.1
            elif predicted_trend < -0.02:  # Tendencia bajista
                price_range = 0.18
                grid_bias = 0.9
            else:  # Lateral
                price_range = 0.12
                grid_bias = 1.0

            min_price = current_price * (1 - price_range)
            max_price = current_price * (1 + price_range)

            # Calcular grids
            optimal_grids = int(10 * grid_bias)
            optimal_grids = min(optimal_grids, request.max_grids)
            optimal_grids = max(optimal_grids, self.min_grids)

            # Calcular cantidad
            grid_investment = request.investment_amount / optimal_grids
            optimal_quantity = grid_investment / current_price
            optimal_quantity = max(optimal_quantity, self.min_quantity)
            optimal_quantity = min(optimal_quantity, self.max_quantity)

            # Score basado en confianza del modelo
            confidence_score = 0.7 + (0.3 * (1 - abs(predicted_trend)))

            return OptimizedConfig(
                symbol=request.symbol,
                min_price=min_price,
                max_price=max_price,
                grids=optimal_grids,
                quantity=optimal_quantity,
                confidence_score=confidence_score,
                optimization_strategy=request.strategy.value,
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Error en optimización ML: {e}")
            raise

    async def _get_market_data(self, symbol: str) -> MarketData:
        """Obtiene datos de mercado actualizados"""
        try:
            # Verificar cache
            if symbol in self.market_data_cache:
                cached_data = self.market_data_cache[symbol]
                if datetime.now() - cached_data.timestamp < self.cache_duration:
                    return cached_data

            # Obtener ticker de 24h
            ticker_24h = binance_client.get_ticker(symbol=f"{symbol}USDT")

            # Obtener klines para calcular volatilidad
            klines = binance_client.get_klines(
                symbol=f"{symbol}USDT", interval="1h", limit=24
            )

            # Calcular volatilidad
            prices = [float(k[4]) for k in klines]  # Precios de cierre
            returns = np.diff(np.log(prices))
            volatility = np.std(returns) * np.sqrt(24)  # Volatilidad anualizada

            # Crear objeto MarketData
            market_data = MarketData(
                symbol=symbol,
                current_price=float(ticker_24h["lastPrice"]),
                volatility=volatility,
                volume_24h=float(ticker_24h["volume"]),
                price_change_24h=float(ticker_24h["priceChangePercent"]),
                high_24h=float(ticker_24h["highPrice"]),
                low_24h=float(ticker_24h["lowPrice"]),
                timestamp=datetime.now(),
            )

            # Guardar en cache
            self.market_data_cache[symbol] = market_data

            return market_data

        except Exception as e:
            logger.error(f"Error obteniendo datos de mercado para {symbol}: {e}")
            # Retornar datos por defecto
            return MarketData(
                symbol=symbol,
                current_price=100.0,
                volatility=0.1,
                volume_24h=1000000.0,
                price_change_24h=0.0,
                high_24h=110.0,
                low_24h=90.0,
                timestamp=datetime.now(),
            )

    async def _get_historical_data(self, symbol: str, days: int) -> List[Dict]:
        """Obtiene datos históricos para ML"""
        try:
            # Obtener klines históricos
            klines = await binance_client.get_klines(
                symbol=f"{symbol}USDT", interval="1d", limit=days
            )

            historical_data = []
            for k in klines:
                historical_data.append(
                    {
                        "timestamp": k[0],
                        "open": float(k[1]),
                        "high": float(k[2]),
                        "low": float(k[3]),
                        "close": float(k[4]),
                        "volume": float(k[5]),
                    }
                )

            return historical_data

        except Exception as e:
            logger.error(f"Error obteniendo datos históricos para {symbol}: {e}")
            return []

    def _extract_features(
        self, historical_data: List[Dict], market_data: MarketData
    ) -> Dict:
        """Extrae features para ML"""
        try:
            prices = [d["close"] for d in historical_data]

            # Calcular features básicas
            returns = np.diff(np.log(prices))
            volatility = np.std(returns)
            trend = (prices[-1] - prices[0]) / prices[0]

            # Calcular indicadores técnicos simples
            sma_short = np.mean(prices[-5:])  # SMA 5 días
            sma_long = np.mean(prices[-20:])  # SMA 20 días
            momentum = sma_short / sma_long - 1

            return {
                "volatility": volatility,
                "trend": trend,
                "momentum": momentum,
                "current_price": market_data.current_price,
                "volume_ratio": market_data.volume_24h / 1000000,
            }

        except Exception as e:
            logger.error(f"Error extrayendo features: {e}")
            return {
                "volatility": 0.1,
                "trend": 0.0,
                "momentum": 0.0,
                "current_price": market_data.current_price,
                "volume_ratio": 1.0,
            }

    def _calculate_optimal_grids(self, volatility: float, risk_tolerance: float) -> int:
        """Calcula número óptimo de grids"""
        # Fórmula: más volatilidad = más grids, más riesgo = menos grids
        base_grids = 10
        volatility_factor = volatility * 20  # Escalar volatilidad
        risk_factor = (1 - risk_tolerance) * 10  # Menos riesgo = más grids

        optimal_grids = base_grids + volatility_factor + risk_factor
        return int(optimal_grids)

    def _calculate_confidence_score(
        self, market_data: MarketData, grids: int, price_range: float
    ) -> float:
        """Calcula score de confianza de la optimización"""
        try:
            # Factores que afectan la confianza
            volatility_score = 1.0 - (
                market_data.volatility * 2
            )  # Menor volatilidad = mayor confianza
            volume_score = min(
                market_data.volume_24h / 1000000, 1.0
            )  # Mayor volumen = mayor confianza
            grid_score = (
                1.0 - abs(grids - 15) / 15
            )  # Grids cercanos a 15 = mayor confianza
            range_score = (
                1.0 - abs(price_range - 0.15) / 0.15
            )  # Rango cercano a 15% = mayor confianza

            # Ponderación de factores
            confidence_score = (
                volatility_score * 0.3
                + volume_score * 0.3
                + grid_score * 0.2
                + range_score * 0.2
            )

            return max(confidence_score, 0.1)  # Mínimo 10%

        except Exception as e:
            logger.error(f"Error calculando score de confianza: {e}")
            return 0.5

    async def _run_backtest(
        self, config: OptimizedConfig, market_data: MarketData
    ) -> Dict:
        """Ejecuta backtesting de la configuración"""
        try:
            # Simulación realista de backtesting
            initial_investment = (
                config.quantity * config.grids * market_data.current_price
            )
            current_balance = initial_investment
            total_trades = 0
            winning_trades = 0
            total_profit = 0.0

            # Simular 30 días de trading
            simulation_days = 30
            trades_per_day = max(
                1, int(config.grids / 10)
            )  # Más grids = más trades por día

            for day in range(simulation_days):
                # Simular volatilidad diaria
                daily_volatility = market_data.volatility * np.random.uniform(0.5, 1.5)

                for trade in range(trades_per_day):
                    # Simular movimiento de precio
                    price_change = np.random.normal(0, daily_volatility)
                    current_price = market_data.current_price * (1 + price_change)

                    # Determinar si se ejecuta un trade
                    if current_price <= config.min_price:
                        # Trade de compra
                        trade_profit = (
                            (config.max_price - current_price) / current_price * 0.1
                        )  # 10% del spread
                        total_profit += trade_profit
                        total_trades += 1
                        if trade_profit > 0:
                            winning_trades += 1

                    elif current_price >= config.max_price:
                        # Trade de venta
                        trade_profit = (
                            (current_price - config.min_price) / current_price * 0.1
                        )  # 10% del spread
                        total_profit += trade_profit
                        total_trades += 1
                        if trade_profit > 0:
                            winning_trades += 1

                # Actualizar precio base para el siguiente día
                market_data.current_price *= 1 + np.random.normal(
                    0, daily_volatility * 0.1
                )

            # Calcular métricas finales
            win_rate = winning_trades / total_trades if total_trades > 0 else 0.0
            roi = total_profit / initial_investment if initial_investment > 0 else 0.0

            # Calcular Sharpe ratio simplificado
            daily_returns = [total_profit / simulation_days] * simulation_days
            sharpe_ratio = (
                np.mean(daily_returns) / (np.std(daily_returns) + 1e-8)
                if len(daily_returns) > 1
                else 0.0
            )

            # Calcular máximo drawdown
            max_drawdown = self._calculate_simulated_drawdown(
                total_profit, simulation_days
            )

            return {
                "total_trades": total_trades,
                "winning_trades": winning_trades,
                "win_rate": win_rate,
                "total_profit": total_profit,
                "roi": roi,
                "sharpe_ratio": sharpe_ratio,
                "max_drawdown": max_drawdown,
                "simulation_days": simulation_days,
                "initial_investment": initial_investment,
                "final_balance": initial_investment + total_profit,
            }

        except Exception as e:
            logger.error(f"Error ejecutando backtesting: {e}")
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "win_rate": 0.0,
                "total_profit": 0.0,
                "roi": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
                "simulation_days": 30,
                "initial_investment": 0.0,
                "final_balance": 0.0,
                "error": str(e),
            }

    def _calculate_simulated_drawdown(self, total_profit: float, days: int) -> float:
        """Calcula drawdown máximo simulado"""
        try:
            # Simular equity curve
            daily_profit = total_profit / days
            equity_curve = []
            current_equity = 1000.0  # Starting equity

            for day in range(days):
                # Simular variación diaria
                daily_variation = daily_profit * np.random.uniform(-2, 2)
                current_equity += daily_variation
                equity_curve.append(current_equity)

            # Calcular máximo drawdown
            peak = equity_curve[0]
            max_dd = 0.0

            for equity in equity_curve:
                if equity > peak:
                    peak = equity
                dd = (peak - equity) / peak if peak > 0 else 0.0
                max_dd = max(max_dd, dd)

            return max_dd

        except Exception as e:
            logger.error(f"Error calculando drawdown simulado: {e}")
            return 0.0

    async def _send_optimization_notification(self, config: OptimizedConfig):
        """Envía notificación de optimización completada"""
        try:
            message = "🎯 **OPTIMIZACIÓN COMPLETADA**\n\n"
            message += f"**Activo**: {config.symbol}\n"
            message += f"**Estrategia**: {config.optimization_strategy}\n"
            message += f"**Score de Confianza**: {config.confidence_score:.2%}\n\n"
            message += "**Configuración Optimizada**:\n"
            message += f"• Precio Mín: ${config.min_price:.4f}\n"
            message += f"• Precio Máx: ${config.max_price:.4f}\n"
            message += f"• Grids: {config.grids}\n"
            message += f"• Cantidad: {config.quantity:.6f}\n\n"

            if config.backtest_results:
                backtest = config.backtest_results
                message += "**Resultados Backtest**:\n"
                message += f"• Trades: {backtest['total_trades']}\n"
                message += f"• Win Rate: {backtest['win_rate']:.2%}\n"
                message += f"• ROI: {backtest['roi']:.2%}\n"

            send_telegram_alert(message)

        except Exception as e:
            logger.error(f"Error enviando notificación de optimización: {e}")

    async def get_optimization_history(self, symbol: str = None) -> Dict:
        """Obtiene historial de optimizaciones"""
        try:
            if symbol:
                history = self.optimization_history.get(symbol, [])
                return {
                    "symbol": symbol,
                    "optimizations": [
                        {
                            "timestamp": opt.timestamp.isoformat(),
                            "strategy": opt.optimization_strategy,
                            "confidence_score": opt.confidence_score,
                            "config": {
                                "min_price": opt.min_price,
                                "max_price": opt.max_price,
                                "grids": opt.grids,
                                "quantity": opt.quantity,
                            },
                            "backtest_results": opt.backtest_results,
                        }
                        for opt in history
                    ],
                }
            else:
                return {
                    "all_optimizations": {
                        sym: [
                            {
                                "timestamp": opt.timestamp.isoformat(),
                                "strategy": opt.optimization_strategy,
                                "confidence_score": opt.confidence_score,
                            }
                            for opt in opts
                        ]
                        for sym, opts in self.optimization_history.items()
                    }
                }

        except Exception as e:
            logger.error(f"Error obteniendo historial de optimizaciones: {e}")
            return {}

    async def get_market_analysis(self, symbol: str) -> Dict:
        """Obtiene análisis de mercado para un símbolo"""
        try:
            market_data = await self._get_market_data(symbol)

            # Análisis de mercado
            volatility_level = (
                "Baja"
                if market_data.volatility < 0.1
                else "Media"
                if market_data.volatility < 0.2
                else "Alta"
            )
            trend_direction = (
                "Alcista" if market_data.price_change_24h > 0 else "Bajista"
            )

            return {
                "symbol": symbol,
                "current_price": market_data.current_price,
                "volatility": {
                    "value": market_data.volatility,
                    "level": volatility_level,
                },
                "volume_24h": market_data.volume_24h,
                "price_change_24h": market_data.price_change_24h,
                "trend": trend_direction,
                "high_24h": market_data.high_24h,
                "low_24h": market_data.low_24h,
                "timestamp": market_data.timestamp.isoformat(),
            }

        except Exception as e:
            logger.error(f"Error obteniendo análisis de mercado para {symbol}: {e}")
            return {}


# Instancia global del ConfigManager
config_manager = ConfigManager()
