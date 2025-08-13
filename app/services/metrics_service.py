"""
Servicio para integrar métricas de rentabilidad en el bot de trading
"""

import time
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from app.core.metrics import trading_metrics
from binance.client import Client
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()
from app.db.session import SessionLocal
from app.models.trade import Trade
from sqlalchemy import func
# from app.models.balance import Balance  # Modelo no implementado aún

logger = logging.getLogger(__name__)

class MetricsService:
    """
    Servicio para calcular y actualizar métricas de rentabilidad
    """
    
    def __init__(self):
        self.initial_portfolio_value = None
        self.last_calculation = None
        # Mantener conteo previo de trades por (symbol, side) para incrementar Counters
        self._last_trades_count_by_symbol_side: Dict[tuple, int] = {}
        
    async def calculate_portfolio_metrics(self) -> Dict:
        """
        Calcula todas las métricas de rentabilidad del portafolio
        """
        try:
            # Obtener balances actuales
            balances = await self._get_current_balances()
            
            # Calcular valor total del portafolio
            portfolio_value = await self._calculate_portfolio_value(balances)
            
            # Calcular ganancia total
            total_profit = await self._calculate_total_profit()
            
            # Calcular ganancia diaria
            daily_profit = await self._calculate_daily_profit()
            
            # Calcular ROI diario
            roi_daily = await self._calculate_daily_roi(daily_profit, portfolio_value)
            
            # Calcular métricas por activo
            asset_metrics = await self._calculate_asset_metrics(balances)
            
            # Actualizar métricas en Prometheus
            self._update_prometheus_metrics(
                total_profit=total_profit,
                portfolio_value=portfolio_value,
                daily_profit=daily_profit,
                roi_daily=roi_daily,
                asset_metrics=asset_metrics
            )
            
            return {
                "portfolio_value": portfolio_value,
                "total_profit": total_profit,
                "daily_profit": daily_profit,
                "roi_daily": roi_daily,
                "asset_metrics": asset_metrics,
                "last_update": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error calculando métricas del portafolio: {e}")
            trading_metrics.record_error("portfolio_calculation_error")
            return {}
    
    async def _get_current_balances(self) -> Dict[str, float]:
        """
        Obtiene los balances actuales de Binance usando Singleton
        """
        try:
            from app.services.binance_client_singleton import binance_client_singleton
            
            balances = binance_client_singleton.get_balances()
            return balances
            
        except Exception as e:
            logger.error(f"Error obteniendo balances: {e}")
            return {}
    
    async def _calculate_portfolio_value(self, balances: Dict[str, float]) -> float:
        """
        Calcula el valor total del portafolio en USDT
        """
        try:
            total_value = 0.0
            
            for asset, amount in balances.items():
                if asset == 'USDT':
                    total_value += amount
                elif amount > 0:
                    # Obtener precio actual del activo
                    try:
                        if asset in ['BTC', 'ETH', 'BNB']:
                            symbol = f"{asset}USDT"
                            try:
                                from app.services.binance_client_singleton import binance_client_singleton
                                price = binance_client_singleton.get_symbol_price(symbol)
                                asset_value = amount * price
                                total_value += asset_value
                            except Exception as e:
                                logger.warning(f"No se pudo obtener precio para {asset}: {e}")
                                # Usar precio estimado
                                if asset == 'BTC':
                                    total_value += amount * 114000
                                elif asset == 'ETH':
                                    total_value += amount * 3500
                                elif asset == 'BNB':
                                    total_value += amount * 500
                    except Exception as e:
                        logger.warning(f"No se pudo obtener precio para {asset}: {e}")
            
            return total_value
            
        except Exception as e:
            logger.error(f"Error calculando valor del portafolio: {e}")
            return 0.0
    
    async def _calculate_total_profit(self) -> float:
        """
        Calcula la ganancia total desde el inicio usando consulta optimizada
        """
        try:
            db = SessionLocal()
            try:
                # Consulta optimizada: sumar solo profit_loss no nulos
                from sqlalchemy import func
                result = db.query(func.sum(Trade.profit_loss)).filter(
                    Trade.profit_loss.isnot(None)
                ).scalar()
                
                total_profit = result or 0.0
                
                # Si no hay profit_loss calculados, calcular con trades completos
                if total_profit == 0.0:
                    completed_trades = db.query(Trade).filter(
                        Trade.side == 'SELL',
                        Trade.exit_price.isnot(None),
                        Trade.entry_price.isnot(None)
                    ).all()
                    
                    for trade in completed_trades:
                        profit = (trade.exit_price - trade.entry_price) * trade.quantity
                        total_profit += profit
                
                return total_profit
            finally:
                db.close()
            
        except Exception as e:
            logger.error(f"Error calculando ganancia total: {e}")
            return 0.0
    
    async def _calculate_daily_profit(self) -> float:
        """
        Calcula la ganancia del día actual usando consulta optimizada
        """
        try:
            db = SessionLocal()
            try:
                # Obtener trades del día actual
                today = datetime.now().date()
                
                # Consulta optimizada: sumar profit_loss del día
                from sqlalchemy import func
                result = db.query(func.sum(Trade.profit_loss)).filter(
                    Trade.timestamp >= today,
                    Trade.profit_loss.isnot(None)
                ).scalar()
                
                daily_profit = result or 0.0
                
                # Si no hay profit_loss calculados, calcular con trades completos del día
                if daily_profit == 0.0:
                    completed_today_trades = db.query(Trade).filter(
                        Trade.timestamp >= today,
                        Trade.side == 'SELL',
                        Trade.exit_price.isnot(None),
                        Trade.entry_price.isnot(None)
                    ).all()
                    
                    for trade in completed_today_trades:
                        profit = (trade.exit_price - trade.entry_price) * trade.quantity
                        daily_profit += profit
                
                return daily_profit
            finally:
                db.close()
            
        except Exception as e:
            logger.error(f"Error calculando ganancia diaria: {e}")
            return 0.0
    
    async def _calculate_daily_roi(self, daily_profit: float, portfolio_value: float) -> float:
        """
        Calcula el ROI diario en porcentaje
        """
        try:
            if portfolio_value > 0:
                # Establecer valor inicial del portafolio si no está definido
                if self.initial_portfolio_value is None:
                    self.initial_portfolio_value = portfolio_value
                    trading_metrics.set_initial_portfolio_value(portfolio_value)
                
                # Usar el valor inicial o el actual si es mayor
                base_value = max(self.initial_portfolio_value, portfolio_value)
                roi = (daily_profit / base_value) * 100
                
                # Limitar el ROI a un rango razonable (-100% a +100%)
                roi = max(-100.0, min(100.0, roi))
                return roi
            return 0.0
            
        except Exception as e:
            logger.error(f"Error calculando ROI diario: {e}")
            return 0.0
    
    async def _calculate_asset_metrics(self, balances: Dict[str, float]) -> Dict[str, Dict]:
        """
        Calcula métricas por activo usando consultas optimizadas
        """
        try:
            asset_metrics = {}
            db = SessionLocal()
            
            try:
                for asset in ['BTC', 'ETH', 'BNB']:
                    if asset in balances and balances[asset] > 0:
                        symbol = f"{asset}USDT"
                        
                        # Consulta optimizada: calcular métricas por activo en una sola consulta
                        from sqlalchemy import func
                        buy_trades = db.query(
                            func.sum(Trade.quantity * Trade.entry_price)
                        ).filter(
                            Trade.symbol == symbol,
                            Trade.side == 'BUY'
                        ).scalar() or 0.0
                        
                        sell_trades = db.query(
                            func.sum(Trade.quantity * Trade.entry_price)
                        ).filter(
                            Trade.symbol == symbol,
                            Trade.side == 'SELL'
                        ).scalar() or 0.0
                        
                        # Calcular métricas
                        asset_investment = buy_trades
                        asset_profit = sell_trades
                        net_profit = asset_profit - asset_investment
                        
                        # Calcular ROI del activo
                        asset_roi = 0.0
                        if asset_investment > 0:
                            asset_roi = (net_profit / asset_investment) * 100
                        
                        asset_metrics[asset] = {
                            "profit": net_profit,
                            "roi": asset_roi,
                            "balance": balances[asset]
                        }
                
                return asset_metrics
            finally:
                db.close()
            
        except Exception as e:
            logger.error(f"Error calculando métricas por activo: {e}")
            return {}
    
    def _update_prometheus_metrics(self, 
                                 total_profit: float,
                                 portfolio_value: float,
                                 daily_profit: float,
                                 roi_daily: float,
                                 asset_metrics: Dict[str, Dict]):
        """
        Actualiza todas las métricas en Prometheus
        """
        try:
            # Métricas principales
            trading_metrics.update_profit_metrics(
                total_profit=total_profit,
                portfolio_value=portfolio_value,
                strategy="grid"
            )
            
            # Métricas por activo
            for asset, metrics in asset_metrics.items():
                trading_metrics.update_asset_profit(
                    asset=f"{asset}USDT",
                    profit=metrics["profit"],
                    roi=metrics["roi"],
                    strategy="grid"
                )
            
            # Actualizar estado del bot
            trading_metrics.update_bot_status(is_active=True, strategy="grid")

            # Incrementar contador de trades en base a DB (diferencias)
            try:
                db = SessionLocal()
                rows = db.query(Trade.symbol, Trade.side, func.count(Trade.id)).group_by(Trade.symbol, Trade.side).all()
                total_trades = 0
                successful_trades = 0
                for symbol, side, count in rows:
                    total_trades += int(count)
                    # Delta contra último valor
                    key = (symbol, side)
                    previous = self._last_trades_count_by_symbol_side.get(key, 0)
                    delta = int(count) - int(previous)
                    if delta > 0:
                        trading_metrics.trades_executed_total.labels(side=side, asset=symbol, strategy="grid").inc(delta)
                        self._last_trades_count_by_symbol_side[key] = int(count)

                # Calcular tasa de éxito global (0-1)
                successful_trades = db.query(func.count(Trade.id)).filter(Trade.profit_loss.isnot(None), Trade.profit_loss > 0).scalar() or 0
                if total_trades > 0:
                    trading_metrics.trades_success_rate.labels(strategy="grid").set(successful_trades / total_trades)
                db.close()
            except Exception as e:
                logger.warning(f"No se pudo actualizar trades_executed_total/trades_success_rate: {e}")
            
            logger.info(f"✅ Métricas actualizadas: Profit=${total_profit:.2f}, Portfolio=${portfolio_value:.2f}, ROI={roi_daily:.2f}%")
            
        except Exception as e:
            logger.error(f"Error actualizando métricas de Prometheus: {e}")
            trading_metrics.record_error("prometheus_update_error")
    
    async def record_trade_execution(self, 
                                   symbol: str,
                                   side: str,
                                   quantity: float,
                                   price: float,
                                   success: bool,
                                   execution_time: float):
        """
        Registra la ejecución de un trade
        """
        try:
            volume_usdt = quantity * price
            
            trading_metrics.record_trade(
                side=side,
                asset=symbol,
                success=success,
                volume_usdt=volume_usdt,
                execution_time=execution_time,
                strategy="grid"
            )
            
            logger.info(f"📊 Trade registrado: {side} {quantity} {symbol} @ ${price} - {'✅' if success else '❌'}")
            
        except Exception as e:
            logger.error(f"Error registrando trade: {e}")
            trading_metrics.record_error("trade_recording_error")
    
    async def update_balance_metrics(self, balances: Dict[str, float]):
        """
        Actualiza métricas de saldos
        """
        try:
            trading_metrics.update_balances(balances, strategy="grid")
            
            # Contar posiciones activas (activos con saldo > 0)
            active_positions = sum(1 for balance in balances.values() if balance > 0)
            trading_metrics.update_active_positions(active_positions, strategy="grid")
            
        except Exception as e:
            logger.error(f"Error actualizando métricas de saldos: {e}")
            trading_metrics.record_error("balance_metrics_error")

# Instancia global del servicio
metrics_service = MetricsService() 