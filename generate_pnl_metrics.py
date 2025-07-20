#!/usr/bin/env python3
"""
Script para generar métricas de P&L en formato Prometheus
"""

import os
import sys
from datetime import datetime

# Agregar el directorio del proyecto al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from binance import Client
from dotenv import load_dotenv

def generate_pnl_metrics():
    """Generar métricas de P&L en formato Prometheus"""
    
    # Cargar variables de entorno
    load_dotenv()
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")
    
    if not api_key or not api_secret:
        print("❌ Error: BINANCE_API_KEY y BINANCE_API_SECRET no configurados")
        return
    
    try:
        # Conectar a Binance
        client = Client(api_key, api_secret)
        
        # Obtener información de la cuenta
        account = client.get_account()
        
        # Calcular valor total del portfolio
        total_value_usdt = 0.0
        asset_values = {}
        
        for balance in account['balances']:
            asset = balance['asset']
            free = float(balance['free'])
            locked = float(balance['locked'])
            total = free + locked
            
            if total > 0:
                if asset == 'USDT':
                    value_usdt = total
                elif asset == 'BUSD':
                    value_usdt = total  # BUSD ≈ USDT
                else:
                    # Obtener precio en USDT
                    try:
                        ticker = client.get_symbol_ticker(symbol=f"{asset}USDT")
                        price_usdt = float(ticker['price'])
                        value_usdt = total * price_usdt
                    except:
                        value_usdt = 0.0
                
                asset_values[asset] = {
                    'amount': total,
                    'value_usdt': value_usdt
                }
                total_value_usdt += value_usdt
        
        # Calcular P&L aproximado (asumiendo que empezaste con $100)
        initial_investment = 100.0  # Ajusta según tu inversión inicial
        pnl_absolute = total_value_usdt - initial_investment
        pnl_percentage = (pnl_absolute / initial_investment * 100) if initial_investment > 0 else 0.0
        
        # Determinar estado de trading
        status = 2 if pnl_absolute > 0 else 0 if pnl_absolute < 0 else 1
        
        # Generar métricas en formato Prometheus
        metrics = []
        metrics.append(f"# HELP gridbot_total_pnl_usdt Total P&L in USDT")
        metrics.append(f"# TYPE gridbot_total_pnl_usdt gauge")
        metrics.append(f"gridbot_total_pnl_usdt {pnl_absolute}")
        
        metrics.append(f"# HELP gridbot_pnl_percentage P&L percentage")
        metrics.append(f"# TYPE gridbot_pnl_percentage gauge")
        metrics.append(f"gridbot_pnl_percentage {pnl_percentage}")
        
        metrics.append(f"# HELP gridbot_portfolio_value_usdt Portfolio value in USDT")
        metrics.append(f"# TYPE gridbot_portfolio_value_usdt gauge")
        metrics.append(f"gridbot_portfolio_value_usdt {total_value_usdt}")
        
        metrics.append(f"# HELP gridbot_trading_status Trading status (0=losing, 1=neutral, 2=winning)")
        metrics.append(f"# TYPE gridbot_trading_status gauge")
        metrics.append(f"gridbot_trading_status {status}")
        
        # Agregar métricas por asset
        for asset, data in asset_values.items():
            if data['value_usdt'] > 1.0:  # Solo assets con valor > $1
                metrics.append(f"# HELP gridbot_asset_value_usdt Asset value in USDT")
                metrics.append(f"# TYPE gridbot_asset_value_usdt gauge")
                metrics.append(f'gridbot_asset_value_usdt{{asset="{asset}"}} {data["value_usdt"]}')
        
        # Guardar métricas en archivo
        metrics_file = "gridbot_pnl_metrics.txt"
        with open(metrics_file, 'w') as f:
            f.write('\n'.join(metrics))
        
        # Mostrar resultados
        print(f"🔄 P&L Metrics - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"💰 Portfolio Value: ${total_value_usdt:.2f} USDT")
        print(f"📈 P&L Absolute: ${pnl_absolute:.2f} USDT")
        print(f"📊 P&L Percentage: {pnl_percentage:.2f}%")
        print(f"🎯 Status: {'GANANDO' if status == 2 else 'PERDIENDO' if status == 0 else 'NEUTRAL'}")
        
        # Mostrar top assets
        sorted_assets = sorted(asset_values.items(), key=lambda x: x[1]['value_usdt'], reverse=True)
        print(f"\n🏆 Top Assets:")
        for asset, data in sorted_assets[:5]:
            if data['value_usdt'] > 1.0:
                print(f"   {asset}: {data['amount']:.6f} (${data['value_usdt']:.2f} USDT)")
        
        print(f"\n✅ Métricas guardadas en {metrics_file}")
        print(f"📊 Para ver métricas: curl http://localhost:8000/api/metrics/metrics/")
        print(f"📈 Dashboard: http://localhost:3000")
        
        return {
            'total_value': total_value_usdt,
            'pnl_absolute': pnl_absolute,
            'pnl_percentage': pnl_percentage,
            'status': status,
            'metrics_file': metrics_file
        }
        
    except Exception as e:
        print(f"❌ Error generando métricas: {e}")
        return None

if __name__ == "__main__":
    generate_pnl_metrics() 