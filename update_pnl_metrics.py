#!/usr/bin/env python3
"""
Script para actualizar métricas de P&L en tiempo real
"""

import asyncio
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import argparse

# Agregar el directorio del proyecto al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from binance import Client
from app.core.metrics import (
    profit_loss,
    update_balance,
    update_strategy_status
)
from app.core.config import settings
import os
from dotenv import load_dotenv

class PnLMetricsUpdater:
    """Actualizador de métricas de P&L"""
    
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("BINANCE_API_KEY")
        self.api_secret = os.getenv("BINANCE_API_SECRET")
        self.client = Client(self.api_key, self.api_secret)
        self.last_portfolio_value = 0.0
        self.initial_portfolio_value = None
        
    def get_account_balances(self) -> Dict[str, Dict[str, float]]:
        """Obtener balances de la cuenta"""
        try:
            account = self.client.get_account()
            balances = {}
            
            for balance in account['balances']:
                asset = balance['asset']
                free = float(balance['free'])
                locked = float(balance['locked'])
                total = free + locked
                
                if total > 0:
                    balances[asset] = {
                        'free': free,
                        'locked': locked,
                        'total': total
                    }
            
            return balances
        except Exception as e:
            print(f"❌ Error obteniendo balances: {e}")
            return {}
    
    def get_current_prices(self, symbols: List[str]) -> Dict[str, float]:
        """Obtener precios actuales"""
        try:
            prices = {}
            for symbol in symbols:
                ticker = self.client.get_symbol_ticker(symbol=symbol)
                prices[symbol] = float(ticker['price'])
            return prices
        except Exception as e:
            print(f"❌ Error obteniendo precios: {e}")
            return {}
    
    def calculate_portfolio_value(self, balances: Dict[str, Dict[str, float]], prices: Dict[str, float]) -> float:
        """Calcular valor total del portfolio en USDT"""
        total_value = 0.0
        
        for asset, balance_data in balances.items():
            total_balance = balance_data['total']
            
            if asset == 'USDT':
                total_value += total_balance
            elif asset == 'BUSD':
                total_value += total_balance  # BUSD ≈ USDT
            else:
                # Buscar precio en USDT
                symbol = f"{asset}USDT"
                if symbol in prices:
                    total_value += total_balance * prices[symbol]
        
        return total_value
    
    def calculate_pnl(self, current_value: float) -> Dict[str, float]:
        """Calcular P&L"""
        if self.initial_portfolio_value is None:
            self.initial_portfolio_value = current_value
            return {
                'absolute': 0.0,
                'percentage': 0.0
            }
        
        absolute_pnl = current_value - self.initial_portfolio_value
        percentage_pnl = (absolute_pnl / self.initial_portfolio_value * 100) if self.initial_portfolio_value > 0 else 0.0
        
        return {
            'absolute': absolute_pnl,
            'percentage': percentage_pnl
        }
    
    def determine_trading_status(self, pnl_percentage: float) -> int:
        """Determinar estado de trading basado en P&L"""
        if pnl_percentage > 1.0:  # Ganando más del 1%
            return 2  # GANANDO
        elif pnl_percentage < -1.0:  # Perdiendo más del 1%
            return 0  # PERDIENDO
        else:
            return 1  # NEUTRAL
    
    def update_metrics(self):
        """Actualizar todas las métricas de P&L"""
        try:
            print(f"🔄 Actualizando métricas de P&L - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 1. Obtener balances
            balances = self.get_account_balances()
            if not balances:
                print("   ⚠️  No se pudieron obtener balances")
                return
            
            # 2. Obtener precios para assets no-USDT
            non_usdt_assets = [asset for asset in balances.keys() if asset not in ['USDT', 'BUSD']]
            symbols = [f"{asset}USDT" for asset in non_usdt_assets]
            prices = self.get_current_prices(symbols)
            
            # 3. Calcular valor del portfolio
            portfolio_value = self.calculate_portfolio_value(balances, prices)
            
            # 4. Calcular P&L
            pnl_data = self.calculate_pnl(portfolio_value)
            
            # 5. Determinar estado de trading
            trading_status = self.determine_trading_status(pnl_data['percentage'])
            
            # 6. Actualizar métricas
            profit_loss.labels(symbol="PORTFOLIO", strategy="overall").set(pnl_data['absolute'])
            
            # Registrar métricas adicionales usando el sistema de métricas
            update_balance("PORTFOLIO", portfolio_value)
            update_strategy_status("overall", trading_status)
            
            # 7. Mostrar resultados
            print(f"   💰 Portfolio Value: ${portfolio_value:.2f} USDT")
            print(f"   📈 P&L Absoluto: ${pnl_data['absolute']:.2f} USDT")
            print(f"   📊 P&L Porcentual: {pnl_data['percentage']:.2f}%")
            print(f"   🎯 Estado: {'GANANDO' if trading_status == 2 else 'PERDIENDO' if trading_status == 0 else 'NEUTRAL'}")
            
            # 8. Mostrar top assets
            asset_values = []
            for asset, balance_data in balances.items():
                if asset == 'USDT':
                    asset_values.append((asset, balance_data['total']))
                elif asset == 'BUSD':
                    asset_values.append((asset, balance_data['total']))
                else:
                    symbol = f"{asset}USDT"
                    if symbol in prices:
                        value = balance_data['total'] * prices[symbol]
                        asset_values.append((asset, value))
            
            asset_values.sort(key=lambda x: x[1], reverse=True)
            print(f"   🏆 Top Assets:")
            for asset, value in asset_values[:5]:
                print(f"      {asset}: ${value:.2f} USDT")
            
            self.last_portfolio_value = portfolio_value
            
        except Exception as e:
            print(f"❌ Error actualizando métricas: {e}")
    
    def run_continuous(self, interval: int = 60):
        """Ejecutar actualización continua"""
        print(f"🚀 Iniciando monitoreo continuo de P&L (intervalo: {interval}s)")
        print(f"📊 Métricas disponibles en: http://localhost:8000/api/metrics/metrics/")
        print(f"📈 Dashboard: http://localhost:3000")
        print(f"🔍 Prometheus: http://localhost:9090")
        print("-" * 60)
        
        while True:
            self.update_metrics()
            time.sleep(interval)
    
    def run_once(self):
        """Ejecutar una sola actualización"""
        self.update_metrics()

def main():
    """Función principal"""
    parser = argparse.ArgumentParser(description='Actualizar métricas de P&L')
    parser.add_argument('--continuous', action='store_true', help='Ejecutar en modo continuo')
    parser.add_argument('--interval', type=int, default=60, help='Intervalo en segundos (default: 60)')
    
    args = parser.parse_args()
    
    updater = PnLMetricsUpdater()
    
    if args.continuous:
        updater.run_continuous(args.interval)
    else:
        updater.run_once()

if __name__ == "__main__":
    main() 