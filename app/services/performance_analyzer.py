"""
PerformanceAnalyzer Service - Análisis avanzado de rendimiento para Grid Trading Bot

Este servicio calcula métricas avanzadas de rendimiento como:
- Sharpe Ratio
- Maximum Drawdown
- Volatilidad
- Retornos totales y por período
- Métricas de riesgo
"""

import asyncio
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta, timezone
import logging
from dataclasses import dataclass

# ✅ FASE 4: Migrado a singleton
from app.services.binance_client_singleton import get_binance_client_singleton
# Compatibilidad: mantener variable 'client' para no romper código existente
_client_singleton = get_binance_client_singleton()
client = _client_singleton.client if _client_singleton.is_ready() else None

# portfolio-snapshot-agent: historial y trades reales desde PostgreSQL
from app.db.session import SessionLocal
from app.models.trade import Trade
from app.services.portfolio_snapshot_service import (
    get_portfolio_value_history as _snapshot_history,
    get_latest_snapshot,
)

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Métricas de rendimiento calculadas"""
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    volatility: float
    win_rate: float
    profit_factor: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_win: float
    avg_loss: float
    best_trade: float
    worst_trade: float
    current_balance: float
    initial_balance: float
    period_days: int


class PerformanceAnalyzer:
    """
    Analizador de rendimiento avanzado para Grid Trading Bot
    """
    
    def __init__(self):
        self.risk_free_rate = 0.02  # 2% anual (tasa libre de riesgo)
        self.min_trades_for_analysis = 5
        
    async def calculate_comprehensive_metrics(self, days: int = 30) -> PerformanceMetrics:
        """
        Calcula métricas comprehensivas de rendimiento
        
        Args:
            days: Número de días para el análisis
            
        Returns:
            PerformanceMetrics con todas las métricas calculadas
        """
        try:
            logger.info(f"Calculando métricas de rendimiento para {days} días")
            
            # Obtener datos históricos
            portfolio_values = await self.get_portfolio_value_history(days)
            trades = await self.get_trade_history(days)
            
            if not portfolio_values or len(portfolio_values) < 2:
                logger.warning("Datos insuficientes para análisis de rendimiento")
                return self._create_empty_metrics()
            
            # Calcular métricas básicas
            total_return = self._calculate_total_return(portfolio_values)
            volatility = self._calculate_volatility(portfolio_values)
            sharpe_ratio = self._calculate_sharpe_ratio(portfolio_values, volatility)
            max_drawdown = self._calculate_max_drawdown(portfolio_values)
            
            # Calcular métricas de trading
            win_rate, profit_factor, avg_win, avg_loss, best_trade, worst_trade = \
                self._calculate_trading_metrics(trades)
            
            # Obtener balances actuales
            current_balance = await self.get_current_portfolio_value()
            initial_balance = portfolio_values[0] if portfolio_values else current_balance
            
            return PerformanceMetrics(
                total_return=total_return,
                sharpe_ratio=sharpe_ratio,
                max_drawdown=max_drawdown,
                volatility=volatility,
                win_rate=win_rate,
                profit_factor=profit_factor,
                total_trades=len(trades),
                winning_trades=len([t for t in trades if t.get('realized_pnl', 0) > 0]),
                losing_trades=len([t for t in trades if t.get('realized_pnl', 0) < 0]),
                avg_win=avg_win,
                avg_loss=avg_loss,
                best_trade=best_trade,
                worst_trade=worst_trade,
                current_balance=current_balance,
                initial_balance=initial_balance,
                period_days=days
            )
            
        except Exception as e:
            logger.error(f"Error calculando métricas de rendimiento: {e}")
            return self._create_empty_metrics()
    
    async def get_portfolio_value_history(self, days: int) -> List[float]:
        """
        Obtiene el historial real de valores del portafolio desde PostgreSQL.

        Usa la tabla portfolio_snapshots (portfolio-snapshot-agent).
        Si no hay suficientes snapshots retorna lista vacía para activar fallback.
        """
        try:
            db = SessionLocal()
            try:
                values = _snapshot_history(db, days=days)
            finally:
                db.close()

            if len(values) < 2:
                logger.warning(
                    "[PerformanceAnalyzer] Solo %d snapshot(s) en los últimos %d días. "
                    "El agente portfolio-snapshot-agent necesita más tiempo de ejecución "
                    "(captura cada 15 min). Retornando lista vacía.",
                    len(values),
                    days,
                )
                return []

            logger.info(
                "[PerformanceAnalyzer] %d snapshots reales cargados para %d días",
                len(values),
                days,
            )
            return values

        except Exception as exc:
            logger.error("[PerformanceAnalyzer] Error obteniendo historial de snapshots: %s", exc)
            return []
    
    async def get_trade_history(self, days: int) -> List[Dict]:
        """
        Obtiene el historial real de trades cerrados desde PostgreSQL.

        Retorna solo trades con exit_price y profit_loss registrados
        (trades completamente cerrados).
        """
        try:
            since = datetime.now(timezone.utc) - timedelta(days=days)
            db = SessionLocal()
            try:
                rows = (
                    db.query(Trade)
                    .filter(
                        Trade.timestamp >= since,
                        Trade.exit_price.isnot(None),
                        Trade.profit_loss.isnot(None),
                    )
                    .order_by(Trade.timestamp.asc())
                    .all()
                )
            finally:
                db.close()

            trades = [
                {
                    "timestamp": row.timestamp,
                    "symbol": row.symbol,
                    "side": row.side,
                    "quantity": row.quantity,
                    "price": row.exit_price,
                    "realized_pnl": float(row.profit_loss),
                    "status": "FILLED",
                }
                for row in rows
            ]

            logger.info(
                "[PerformanceAnalyzer] %d trades reales cargados para %d días",
                len(trades),
                days,
            )
            return trades

        except Exception as exc:
            logger.error("[PerformanceAnalyzer] Error obteniendo historial de trades: %s", exc)
            return []
    
    async def get_current_portfolio_value(self) -> float:
        """
        Obtiene el valor actual del portafolio.

        performance-analyzer-realdata-agent: usa el snapshot más reciente de DB
        como primer intento (evita hammear Binance API). Si el snapshot tiene más
        de 20 minutos o no existe, cae al cálculo directo via Binance.
        """
        from datetime import timezone
        # Intentar desde snapshot reciente (< 20 min)
        try:
            db = SessionLocal()
            try:
                latest = get_latest_snapshot(db)
            finally:
                db.close()

            if latest and latest.captured_at:
                age_seconds = (
                    datetime.now(timezone.utc) - latest.captured_at
                ).total_seconds()
                if age_seconds < 1200:  # menos de 20 minutos
                    logger.debug(
                        "[PerformanceAnalyzer] Usando snapshot reciente: %.2f USDT (age=%.0fs)",
                        latest.total_value_usdt, age_seconds,
                    )
                    return float(latest.total_value_usdt)
        except Exception as exc:
            logger.warning(
                "[PerformanceAnalyzer] No se pudo usar snapshot: %s — usando Binance API", exc
            )

        # Fallback: calcular en tiempo real desde Binance
        try:
            account_info = await asyncio.to_thread(client.get_account)
            total_value = 0.0

            for balance in account_info["balances"]:
                asset = balance["asset"]
                free_balance = float(balance["free"])

                if free_balance > 0:
                    if asset == "USDT":
                        total_value += free_balance
                    else:
                        try:
                            symbol = f"{asset}USDT"
                            ticker = await asyncio.to_thread(
                                client.get_symbol_ticker, symbol=symbol
                            )
                            price = float(ticker["price"])
                            total_value += free_balance * price
                        except Exception:
                            continue

            return total_value

        except Exception as exc:
            logger.error("[PerformanceAnalyzer] Error obteniendo valor del portafolio: %s", exc)
            return 0.0
    
    def _calculate_total_return(self, portfolio_values: List[float]) -> float:
        """
        Calcula el retorno total
        
        Args:
            portfolio_values: Lista de valores del portafolio
            
        Returns:
            Retorno total como porcentaje
        """
        if len(portfolio_values) < 2:
            return 0.0
        
        initial_value = portfolio_values[0]
        final_value = portfolio_values[-1]
        
        if initial_value == 0:
            return 0.0
        
        return ((final_value - initial_value) / initial_value) * 100
    
    def _calculate_volatility(self, portfolio_values: List[float]) -> float:
        """
        Calcula la volatilidad (desviación estándar de retornos)
        
        Args:
            portfolio_values: Lista de valores del portafolio
            
        Returns:
            Volatilidad anualizada
        """
        if len(portfolio_values) < 2:
            return 0.0
        
        # Calcular retornos diarios
        returns = []
        for i in range(1, len(portfolio_values)):
            if portfolio_values[i-1] != 0:
                daily_return = (portfolio_values[i] - portfolio_values[i-1]) / portfolio_values[i-1]
                returns.append(daily_return)
        
        if not returns:
            return 0.0
        
        # Calcular volatilidad anualizada (asumiendo retornos diarios)
        daily_volatility = np.std(returns)
        annualized_volatility = daily_volatility * np.sqrt(365)
        
        return annualized_volatility * 100  # Convertir a porcentaje
    
    def _calculate_sharpe_ratio(self, portfolio_values: List[float], volatility: float) -> float:
        """
        Calcula el Sharpe Ratio
        
        Args:
            portfolio_values: Lista de valores del portafolio
            volatility: Volatilidad calculada
            
        Returns:
            Sharpe Ratio
        """
        if len(portfolio_values) < 2 or volatility == 0:
            return 0.0
        
        # Calcular retorno promedio anualizado
        total_return = self._calculate_total_return(portfolio_values)
        days = len(portfolio_values)
        annualized_return = total_return * (365 / days)
        
        # Calcular Sharpe Ratio
        excess_return = annualized_return - self.risk_free_rate
        sharpe_ratio = excess_return / volatility if volatility > 0 else 0
        
        return sharpe_ratio
    
    def _calculate_max_drawdown(self, portfolio_values: List[float]) -> float:
        """
        Calcula el máximo drawdown
        
        Args:
            portfolio_values: Lista de valores del portafolio
            
        Returns:
            Máximo drawdown como porcentaje
        """
        if len(portfolio_values) < 2:
            return 0.0
        
        peak = portfolio_values[0]
        max_dd = 0.0
        
        for value in portfolio_values:
            if value > peak:
                peak = value
            
            if peak > 0:
                drawdown = (peak - value) / peak
                max_dd = max(max_dd, drawdown)
        
        return max_dd * 100  # Convertir a porcentaje
    
    def _calculate_trading_metrics(self, trades: List[Dict]) -> Tuple[float, float, float, float, float, float]:
        """
        Calcula métricas de trading
        
        Args:
            trades: Lista de trades
            
        Returns:
            Tuple con (win_rate, profit_factor, avg_win, avg_loss, best_trade, worst_trade)
        """
        if not trades:
            return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
        
        # Separar trades ganadores y perdedores
        winning_trades = [t for t in trades if t.get('realized_pnl', 0) > 0]
        losing_trades = [t for t in trades if t.get('realized_pnl', 0) < 0]
        
        # Calcular métricas
        total_trades = len(trades)
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
        
        # Profit factor
        total_wins = sum(t.get('realized_pnl', 0) for t in winning_trades)
        total_losses = abs(sum(t.get('realized_pnl', 0) for t in losing_trades))
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
        
        # Promedios
        avg_win = np.mean([t.get('realized_pnl', 0) for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t.get('realized_pnl', 0) for t in losing_trades]) if losing_trades else 0
        
        # Mejor y peor trade
        pnls = [t.get('realized_pnl', 0) for t in trades]
        best_trade = max(pnls) if pnls else 0
        worst_trade = min(pnls) if pnls else 0
        
        return win_rate * 100, profit_factor, avg_win, avg_loss, best_trade, worst_trade
    
    def _create_empty_metrics(self) -> PerformanceMetrics:
        """Crea métricas vacías cuando no hay datos suficientes"""
        return PerformanceMetrics(
            total_return=0.0,
            sharpe_ratio=0.0,
            max_drawdown=0.0,
            volatility=0.0,
            win_rate=0.0,
            profit_factor=0.0,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            avg_win=0.0,
            avg_loss=0.0,
            best_trade=0.0,
            worst_trade=0.0,
            current_balance=0.0,
            initial_balance=0.0,
            period_days=0
        )
    
    async def get_asset_performance(self, symbol: str, days: int = 30) -> Dict:
        """
        Obtiene el rendimiento de un activo específico
        
        Args:
            symbol: Símbolo del activo (ej: BNBUSDT)
            days: Número de días para el análisis
            
        Returns:
            Diccionario con métricas del activo
        """
        try:
            # Obtener datos históricos del activo
            klines = client.get_historical_klines(
                symbol, 
                client.KLINE_INTERVAL_1DAY, 
                f"{days} days ago UTC"
            )
            
            if not klines:
                return {"error": "No hay datos históricos disponibles"}
            
            # Procesar datos
            prices = [float(k[4]) for k in klines]  # Precio de cierre
            volumes = [float(k[5]) for k in klines]  # Volumen
            
            # Calcular métricas
            initial_price = prices[0]
            final_price = prices[-1]
            price_change = ((final_price - initial_price) / initial_price) * 100
            
            # Volatilidad
            returns = []
            for i in range(1, len(prices)):
                if prices[i-1] != 0:
                    daily_return = (prices[i] - prices[i-1]) / prices[i-1]
                    returns.append(daily_return)
            
            volatility = np.std(returns) * np.sqrt(365) * 100 if returns else 0
            
            # Volumen promedio
            avg_volume = np.mean(volumes) if volumes else 0
            
            return {
                "symbol": symbol,
                "initial_price": initial_price,
                "final_price": final_price,
                "price_change_percent": price_change,
                "volatility_annualized": volatility,
                "avg_volume": avg_volume,
                "days_analyzed": days,
                "current_price": final_price
            }
            
        except Exception as e:
            logger.error(f"Error analizando rendimiento de {symbol}: {e}")
            return {"error": str(e)}
    
    async def get_portfolio_allocation(self) -> Dict:
        """
        Obtiene la distribución actual del portafolio
        
        Returns:
            Diccionario con distribución por activo
        """
        try:
            import asyncio
            
            # ✅ FIX: Obtener account info (non-blocking)
            account_info = await asyncio.to_thread(client.get_account)
            allocation = {}
            total_value = 0.0
            
            for balance in account_info['balances']:
                asset = balance['asset']
                free_balance = float(balance['free'])
                
                if free_balance > 0:
                    if asset == 'USDT':
                        value = free_balance
                        allocation[asset] = {
                            'balance': free_balance,
                            'value_usdt': value,
                            'percentage': 0  # Se calculará después
                        }
                        total_value += value
                    else:
                        try:
                            symbol = f"{asset}USDT"
                            # ✅ FIX: Obtener precio (non-blocking)
                            ticker = await asyncio.to_thread(client.get_symbol_ticker, symbol=symbol)
                            price = float(ticker['price'])
                            value = free_balance * price
                            
                            allocation[asset] = {
                                'balance': free_balance,
                                'value_usdt': value,
                                'price': price,
                                'percentage': 0  # Se calculará después
                            }
                            total_value += value
                        except:
                            continue
            
            # Calcular porcentajes
            for asset_data in allocation.values():
                if total_value > 0:
                    asset_data['percentage'] = (asset_data['value_usdt'] / total_value) * 100
            
            return {
                'allocation': allocation,
                'total_value': total_value,
                'assets_count': len(allocation)
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo distribución del portafolio: {e}")
            return {"error": str(e)}


# Instancia global del PerformanceAnalyzer
performance_analyzer = PerformanceAnalyzer() 