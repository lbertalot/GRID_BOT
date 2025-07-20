#!/usr/bin/env python3
"""
Script simple para verificar P&L actual
"""

import json
import os
from datetime import datetime

def check_current_pnl():
    """Verifica el P&L actual"""
    
    print("🎯 Verificación de P&L Actual")
    print("=" * 40)
    
    # Verificar si existe el archivo de datos
    pnl_file = "profit_loss_data.json"
    
    if not os.path.exists(pnl_file):
        print("❌ No hay datos de P&L disponibles")
        print("   Ejecuta primero: python3 profit_loss_tracker.py")
        return
    
    try:
        with open(pnl_file, 'r') as f:
            data = json.load(f)
        
        # Verificar datos iniciales
        if not data.get("initial_balance"):
            print("❌ No hay datos iniciales")
            return
        
        # Verificar datos actuales
        if not data.get("current_balance"):
            print("❌ No hay datos actuales")
            print("   Ejecuta: python3 profit_loss_tracker.py")
            return
        
        # Obtener valores
        initial_value = data["initial_balance"]["portfolio_value"]["total_value_usdt"]
        current_value = data["current_balance"]["portfolio_value"]["total_value_usdt"]
        
        # Calcular P&L
        pnl_absolute = current_value - initial_value
        pnl_percentage = (pnl_absolute / initial_value * 100) if initial_value > 0 else 0.0
        
        # Mostrar resultados
        print(f"📊 RESUMEN DE P&L:")
        print(f"   💰 Valor inicial: ${initial_value:.2f} USDT")
        print(f"   💰 Valor actual: ${current_value:.2f} USDT")
        print(f"   📊 P&L absoluto: ${pnl_absolute:.2f} USDT")
        print(f"   📈 P&L porcentual: {pnl_percentage:.2f}%")
        
        # Determinar estado
        if pnl_absolute > 0:
            status = "🟢 GANANDO"
            emoji = "📈"
        elif pnl_absolute < 0:
            status = "🔴 PERDIENDO"
            emoji = "📉"
        else:
            status = "🟡 NEUTRAL"
            emoji = "➡️"
        
        print(f"   {emoji} Estado: {status}")
        
        # Mostrar desglose por asset
        print(f"\n📋 DESGLOSE POR ASSET:")
        initial_assets = data["initial_balance"]["portfolio_value"]["asset_values"]
        current_assets = data["current_balance"]["portfolio_value"]["asset_values"]
        
        for asset in set(initial_assets.keys()) | set(current_assets.keys()):
            initial_val = initial_assets.get(asset, {}).get("value_usdt", 0.0)
            current_val = current_assets.get(asset, {}).get("value_usdt", 0.0)
            
            if initial_val > 0 or current_val > 0:
                asset_pnl = current_val - initial_val
                asset_pnl_pct = (asset_pnl / initial_val * 100) if initial_val > 0 else 0.0
                
                status_emoji = "🟢" if asset_pnl > 0 else "🔴" if asset_pnl < 0 else "🟡"
                print(f"   {status_emoji} {asset}: ${asset_pnl:.2f} ({asset_pnl_pct:.2f}%)")
        
        # Mostrar P&L diario
        if data.get("daily_pnl"):
            print(f"\n📅 P&L DIARIO:")
            for date, entries in data["daily_pnl"].items():
                if entries:
                    latest = entries[-1]
                    print(f"   📅 {date}: ${latest['pnl_absolute']:.2f} ({latest['pnl_percentage']:.2f}%)")
        
        # Mostrar timestamp
        if data.get("current_balance", {}).get("timestamp"):
            timestamp = data["current_balance"]["timestamp"]
            print(f"\n🕒 Última actualización: {timestamp}")
        
    except Exception as e:
        print(f"❌ Error leyendo datos: {e}")

def main():
    """Función principal"""
    check_current_pnl()

if __name__ == "__main__":
    main() 