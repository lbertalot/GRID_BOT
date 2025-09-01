#!/usr/bin/env python3
"""
Script para generar métricas reales de trading para Grafana
"""

import os
import sys
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

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

async def get_real_trading_data() -> Dict[str, Any]:
    """Obtiene datos reales de trading desde la base de datos"""
    try:
        db = SessionLocal()
        
        # Obtener trades de las últimas 24 horas
        yesterday = datetime.now() - timedelta(days=1)
        
        # Total de trades
        total_trades = db.query(func.count(Trade.id)).scalar() or 0
        
        # Trades exitosos (con profit > 0)
        successful_trades = db.query(func.count(Trade.id)).filter(
            Trade.profit_loss.isnot(None),
            Trade.profit_loss > 0
        ).scalar() or 0
        
        # Trades fallidos (con profit < 0)
        failed_trades = db.query(func.count(Trade.id)).filter(
            Trade.profit_loss.isnot(None),
            Trade.profit_loss < 0
        ).scalar() or 0
        
        # Profit total
        total_profit = db.query(func.sum(Trade.profit_loss)).filter(
            Trade.profit_loss.isnot(None)
        ).scalar() or 0.0
        
        # Profit diario
        daily_profit = db.query(func.sum(Trade.profit_loss)).filter(
            Trade.profit_loss.isnot(None),
            Trade.created_at >= yesterday
        ).scalar() or 0.0
        
        # Volumen total
        total_volume = db.query(func.sum(Trade.quantity * Trade.price)).filter(
            Trade.quantity.isnot(None),
            Trade.price.isnot(None)
        ).scalar() or 0.0
        
        # Último trade
        last_trade = db.query(Trade).order_by(Trade.created_at.desc()).first()
        
        # Trades por símbolo
        trades_by_symbol = db.query(
            Trade.symbol,
            func.count(Trade.id).label('count'),
            func.sum(Trade.profit_loss).label('profit')
        ).group_by(Trade.symbol).all()
        
        db.close()
        
        return {
            'total_trades': total_trades,
            'successful_trades': successful_trades,
            'failed_trades': failed_trades,
            'total_profit': float(total_profit),
            'daily_profit': float(daily_profit),
            'total_volume': float(total_volume),
            'last_trade': last_trade.created_at if last_trade else None,
            'trades_by_symbol': [
                {
                    'symbol': symbol,
                    'count': int(count),
                    'profit': float(profit or 0)
                }
                for symbol, count, profit in trades_by_symbol
            ]
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo datos de trading: {e}")
        return {
            'total_trades': 0,
            'successful_trades': 0,
            'failed_trades': 0,
            'total_profit': 0.0,
            'daily_profit': 0.0,
            'total_volume': 0.0,
            'last_trade': None,
            'trades_by_symbol': []
        }

async def get_portfolio_value() -> float:
    """Obtiene el valor actual del portafolio"""
    try:
        binance = AsyncBinanceWrapper()
        balances = await binance.get_balances()
        
        total_value = 0.0
        for asset, balance in balances.items():
            if balance > 0:
                if asset == 'USDT':
                    total_value += balance
                else:
                    try:
                        price = await binance.get_price(f"{asset}USDT")
                        total_value += balance * price
                    except:
                        # Si no se puede obtener el precio, usar 0
                        pass
        
        return total_value
        
    except Exception as e:
        logger.error(f"Error obteniendo valor del portafolio: {e}")
        return 0.0

def update_metrics(trading_data: Dict[str, Any], portfolio_value: float):
    """Actualiza las métricas de Prometheus"""
    try:
        # Métricas de profit
        profit_total_usdt.labels(strategy="grid").set(trading_data['total_profit'])
        profit_daily_usdt.labels(strategy="grid").set(trading_data['daily_profit'])
        portfolio_total_value_usdt.labels(strategy="grid").set(portfolio_value)
        
        # ROI diario
        if portfolio_value > 0:
            roi_daily = (trading_data['daily_profit'] / portfolio_value) * 100
            roi_daily_percent.labels(strategy="grid").set(roi_daily)
        
        # Métricas de trades
        trades_executed_total.labels(side="BUY", asset="BTCUSDT", strategy="grid").inc(0)
        trades_executed_total.labels(side="SELL", asset="BTCUSDT", strategy="grid").inc(0)
        
        if trading_data['total_trades'] > 0:
            success_rate = trading_data['successful_trades'] / trading_data['total_trades']
            trades_success_rate.labels(strategy="grid").set(success_rate)
        
        trades_successful_total.labels(asset="BTCUSDT", strategy="grid").inc(0)
        trades_failed_total.labels(asset="BTCUSDT", strategy="grid").inc(0)
        
        # Volumen de trading
        trading_volume_usdt.labels(asset="BTCUSDT", strategy="grid").inc(0)
        
        # Estado del bot
        bot_status.labels(strategy="grid").set(1)  # Activo
        bot_last_execution_timestamp.labels(strategy="grid").set(datetime.now().timestamp())
        
        # Métricas por activo
        for symbol_data in trading_data['trades_by_symbol']:
            symbol = symbol_data['symbol']
            profit = symbol_data['profit']
            
            profit_by_asset_usdt.labels(asset=symbol, strategy="grid").set(profit)
            
            if portfolio_value > 0:
                roi = (profit / portfolio_value) * 100
                roi_by_asset_percent.labels(asset=symbol, strategy="grid").set(roi)
        
        # Duración del ciclo grid (simulado)
        grid_cycle_duration_seconds.labels().observe(20.0)  # 20 segundos promedio
        
        logger.info(f"✅ Métricas actualizadas: Profit=${trading_data['total_profit']:.2f}, Portfolio=${portfolio_value:.2f}")
        
    except Exception as e:
        logger.error(f"Error actualizando métricas: {e}")

async def main():
    """Función principal"""
    logger.info("🚀 Iniciando generación de métricas reales...")
    
    # Obtener datos reales
    trading_data = await get_real_trading_data()
    portfolio_value = await get_portfolio_value()
    
    logger.info(f"📊 Datos obtenidos:")
    logger.info(f"   Total trades: {trading_data['total_trades']}")
    logger.info(f"   Successful: {trading_data['successful_trades']}")
    logger.info(f"   Failed: {trading_data['failed_trades']}")
    logger.info(f"   Total profit: ${trading_data['total_profit']:.2f}")
    logger.info(f"   Daily profit: ${trading_data['daily_profit']:.2f}")
    logger.info(f"   Portfolio value: ${portfolio_value:.2f}")
    
    # Actualizar métricas
    update_metrics(trading_data, portfolio_value)
    
    logger.info("✅ Métricas generadas exitosamente")

if __name__ == "__main__":
    asyncio.run(main()) 