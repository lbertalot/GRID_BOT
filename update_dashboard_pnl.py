#!/usr/bin/env python3
"""
Script para actualizar dashboard_pnl.json con datos reales
"""

import json
import os
import sys
from datetime import datetime

# Agregar el directorio del proyecto al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from binance import Client
from dotenv import load_dotenv

def update_dashboard_pnl():
    """Actualizar dashboard_pnl.json con datos reales"""
    
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
                
                total_value_usdt += value_usdt
        
        # Calcular P&L (asumiendo inversión inicial de $100)
        initial_investment = 100.0
        pnl_absolute = total_value_usdt - initial_investment
        pnl_percentage = (pnl_absolute / initial_investment * 100) if initial_investment > 0 else 0.0
        
        # Determinar estado
        if pnl_absolute > 0:
            status = "🟢 GANANDO"
        elif pnl_absolute < 0:
            status = "🔴 PERDIENDO"
        else:
            status = "🟡 NEUTRAL"
        
        # Crear datos del dashboard
        dashboard_data = {
            "pnl_absolute": round(pnl_absolute, 2),
            "pnl_percentage": round(pnl_percentage, 2),
            "current_value": round(total_value_usdt, 2),
            "initial_value": initial_investment,
            "status": status,
            "timestamp": datetime.now().isoformat()
        }
        
        # Guardar en archivo
        with open("dashboard_pnl.json", "w") as f:
            json.dump(dashboard_data, f, indent=2)
        
        # Mostrar resultados
        print(f"🔄 Actualizando dashboard_pnl.json - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"💰 Current Value: ${dashboard_data['current_value']:.2f} USDT")
        print(f"📈 P&L Absolute: ${dashboard_data['pnl_absolute']:.2f} USDT")
        print(f"📊 P&L Percentage: {dashboard_data['pnl_percentage']:.2f}%")
        print(f"🎯 Status: {dashboard_data['status']}")
        print(f"✅ Datos guardados en dashboard_pnl.json")
        
        return dashboard_data
        
    except Exception as e:
        print(f"❌ Error actualizando P&L: {e}")
        return None

if __name__ == "__main__":
    update_dashboard_pnl() 