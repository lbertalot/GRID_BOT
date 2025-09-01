#!/usr/bin/env python3
"""
Script para actualizar métricas directamente en el contenedor de la API
"""

import os
import sys
import asyncio
import logging
from datetime import datetime, timedelta

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.metrics import (
    profit_total_usdt, profit_daily_usdt, portfolio_total_value_usdt,
    roi_daily_percent, profit_by_asset_usdt, roi_by_asset_percent,
    trades_executed_total, trades_success_rate, trades_successful_total,
    trades_failed_total, bot_status, bot_last_execution_timestamp,
    balance_by_asset, active_positions_count, trading_volume_usdt,
    grid_cycle_duration_seconds, bot_errors_total
)
from app.services.binance_async import AsyncBinanceWrapper
from app.db.database import SessionLocal
from app.models.trade import Trade
from sqlalchemy import func

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def update_metrics_direct():
    """Actualiza las métricas directamente"""
    try:
        logger.info("🚀 Actualizando métricas directamente...")
        
        # Obtener datos de la base de datos
        db = SessionLocal()
        
        # Total de trades
        total_trades = db.query(func.count(Trade.id)).scalar() or 0
        
        # Trades exitosos y fallidos
        successful_trades = db.query(func.count(Trade.id)).filter(
            Trade.profit_loss.isnot(None),
            Trade.profit_loss > 0
        ).scalar() or 0
        
        failed_trades = db.query(func.count(Trade.id)).filter(
            Trade.profit_loss.isnot(None),
            Trade.profit_loss < 0
        ).scalar() or 0
        
        # Profit total y diario
        total_profit = db.query(func.sum(Trade.profit_loss)).filter(
            Trade.profit_loss.isnot(None)
        ).scalar() or 0.0
        
        yesterday = datetime.now() - timedelta(days=1)
        daily_profit = db.query(func.sum(Trade.profit_loss)).filter(
            Trade.profit_loss.isnot(None),
            Trade.created_at >= yesterday
        ).scalar() or 0.0
        
        # Volumen total
        total_volume = db.query(func.sum(Trade.quantity * Trade.price)).filter(
            Trade.quantity.isnot(None),
            Trade.price.isnot(None)
        ).scalar() or 0.0
        
        # Trades por símbolo
        trades_by_symbol = db.query(
            Trade.symbol,
            func.count(Trade.id).label('count'),
            func.sum(Trade.profit_loss).label('profit')
        ).group_by(Trade.symbol).all()
        
        db.close()
        
        # Obtener valor del portafolio
        binance = AsyncBinanceWrapper()
        balances = await binance.get_balances()
        
        portfolio_value = 0.0
        for asset, balance in balances.items():
            if balance > 0:
                if asset == 'USDT':
                    portfolio_value += balance
                else:
                    try:
                        price = await binance.get_price(f"{asset}USDT")
                        portfolio_value += balance * price
                    except:
                        pass
        
        logger.info(f"📊 Datos obtenidos:")
        logger.info(f"   Total trades: {total_trades}")
        logger.info(f"   Successful: {successful_trades}")
        logger.info(f"   Failed: {failed_trades}")
        logger.info(f"   Total profit: ${total_profit:.2f}")
        logger.info(f"   Daily profit: ${daily_profit:.2f}")
        logger.info(f"   Portfolio value: ${portfolio_value:.2f}")
        
        # Actualizar métricas
        profit_total_usdt.labels(strategy="grid").set(float(total_profit))
        profit_daily_usdt.labels(strategy="grid").set(float(daily_profit))
        portfolio_total_value_usdt.labels(strategy="grid").set(portfolio_value)
        
        # ROI diario
        if portfolio_value > 0:
            roi_daily = (daily_profit / portfolio_value) * 100
            roi_daily_percent.labels(strategy="grid").set(roi_daily)
        
        # Métricas de trades
        if total_trades > 0:
            success_rate = successful_trades / total_trades
            trades_success_rate.labels(strategy="grid").set(success_rate)
        
        # Estado del bot
        bot_status.labels(strategy="grid").set(1)
        bot_last_execution_timestamp.labels(strategy="grid").set(datetime.now().timestamp())
        
        # Métricas por activo
        for symbol, count, profit in trades_by_symbol:
            profit_by_asset_usdt.labels(asset=symbol, strategy="grid").set(float(profit or 0))
            
            if portfolio_value > 0:
                roi = ((profit or 0) / portfolio_value) * 100
                roi_by_asset_percent.labels(asset=symbol, strategy="grid").set(roi)
        
        # Duración del ciclo grid
        grid_cycle_duration_seconds.labels().observe(20.0)
        
        logger.info("✅ Métricas actualizadas exitosamente")
        
    except Exception as e:
        logger.error(f"Error actualizando métricas: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(update_metrics_direct())
