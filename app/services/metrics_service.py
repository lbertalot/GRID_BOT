"""
Servicio para integrar métricas de rentabilidad en el bot de trading
"""

import time
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from app.core.metrics import trading_metrics
from app.services.binance_client import client
from app.db.session import SessionLocal
from app.models.trade import Trade
# from app.models.balance import Balance  # Modelo no implementado aún

logger = logging.getLogger(__name__)

class MetricsService:
    """
    Servicio para calcular y actualizar métricas de rentabilidad
    """
    
    def __init__(self):
        self.initial_portfolio_value = None
        self.last_calculation = None
        
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
        Obtiene los balances actuales de Binance
        """
        try:
            account = client.get_account()
            balances = {}
            
            for balance in account['balances']:
                asset = balance['asset']
                free = float(balance['free'])
                locked = float(balance['locked'])
                total = free + locked
                
                if total > 0:
                    balances[asset] = total
            
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
                            ticker = client.get_symbol_ticker(symbol=symbol)
                            price = float(ticker['price'])
                            asset_value = amount * price
                            total_value += asset_value
                    except Exception as e:
                        logger.warning(f"No se pudo obtener precio para {asset}: {e}")
            
            return total_value
            
        except Exception as e:
            logger.error(f"Error calculando valor del portafolio: {e}")
            return 0.0
    
    async def _calculate_total_profit(self) -> float:
        """
        Calcula la ganancia total desde el inicio
        """
        try:
            db = SessionLocal()
            
            # Obtener todos los trades
            trades = db.query(Trade).all()
            
            total_profit = 0.0
            
            for trade in trades:
                if trade.side == 'BUY':
                    # Compra: gasto de USDT
                    total_profit -= trade.quantity * trade.entry_price
                else:
                    # Venta: ingreso de USDT
                    total_profit += trade.quantity * trade.entry_price
            
            db.close()
            return total_profit
            
        except Exception as e:
            logger.error(f"Error calculando ganancia total: {e}")
            return 0.0
    
    async def _calculate_daily_profit(self) -> float:
        """
        Calcula la ganancia del día actual
        """
        try:
            db = SessionLocal()
            
            # Obtener trades del día actual
            today = datetime.now().date()
            today_trades = db.query(Trade).filter(
                Trade.timestamp >= today
            ).all()
            
            daily_profit = 0.0
            
            for trade in today_trades:
                if trade.side == 'BUY':
                    daily_profit -= trade.quantity * trade.entry_price
                else:
                    daily_profit += trade.quantity * trade.entry_price
            
            db.close()
            return daily_profit
            
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
                
                roi = (daily_profit / self.initial_portfolio_value) * 100
                return roi
            return 0.0
            
        except Exception as e:
            logger.error(f"Error calculando ROI diario: {e}")
            return 0.0
    
    async def _calculate_asset_metrics(self, balances: Dict[str, float]) -> Dict[str, Dict]:
        """
        Calcula métricas por activo
        """
        try:
            asset_metrics = {}
            
            for asset in ['BTC', 'ETH', 'BNB']:
                if asset in balances and balances[asset] > 0:
                    # Obtener trades del activo
                    db = SessionLocal()
                    asset_trades = db.query(Trade).filter(
                        Trade.symbol == f"{asset}USDT"
                    ).all()
                    
                    asset_profit = 0.0
                    asset_investment = 0.0
                    
                    for trade in asset_trades:
                        if trade.side == 'BUY':
                            asset_investment += trade.quantity * trade.entry_price
                        else:
                            asset_profit += trade.quantity * trade.entry_price
                    
                    # Calcular ROI del activo
                    asset_roi = 0.0
                    if asset_investment > 0:
                        asset_roi = ((asset_profit - asset_investment) / asset_investment) * 100
                    
                    asset_metrics[asset] = {
                        "profit": asset_profit - asset_investment,
                        "roi": asset_roi,
                        "balance": balances[asset]
                    }
                    
                    db.close()
            
            return asset_metrics
            
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