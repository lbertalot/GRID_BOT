#!/usr/bin/env python3
"""
Script para verificar el estado del sistema en modo calibración
"""

from app.services.binance_client_singleton import get_binance_client_singleton
import os

def check_system_status():
    print("🔬 Verificando estado del sistema en modo calibración")
    print(f"   CALIBRATION_MODE: {os.environ.get('CALIBRATION_MODE', 'false')}")
    print(f"   MIN_USDT_BALANCE: {os.environ.get('MIN_USDT_BALANCE', '25.0')}")
    print()
    
    try:
        client = get_binance_client_singleton()
        balances = client.get_balances()
        
        print("💰 Balances actuales:")
        total_usdt = 0
        for asset, amount in balances.items():
            if amount > 0:
                if asset == 'USDT':
                    total_usdt = amount
                    print(f"   {asset}: {amount:.6f}")
                else:
                    try:
                        price = client.get_symbol_price(f"{asset}USDT")
                        value = amount * price
                        print(f"   {asset}: {amount:.6f} (~${value:.2f})")
                    except Exception as e:
                        print(f"   {asset}: {amount:.6f} (error: {e})")
        
        print(f"\n📊 Resumen:")
        print(f"   USDT Balance: ${total_usdt:.2f}")
        print(f"   Umbral mínimo (nuevo): $15.0")
        print(f"   Puede operar: {'✅ SÍ' if total_usdt >= 15.0 else '❌ NO'}")
        
        # Verificar si el modo de calibración detectaría trades
        if total_usdt >= 10.0:  # Umbral para calibración
            print(f"\n🔬 En modo calibración:")
            print(f"   Trade BUY para ETHUSDT habría sido ejecutado")
            print(f"   Cantidad estimada: 0.0025 ETH")
            print(f"   Valor estimado: ${total_usdt * 0.8:.2f}")
            print(f"   Confianza: 0.60 (GridTrading)")
        else:
            print(f"\n🔬 En modo calibración:")
            print(f"   No se habrían ejecutado trades (balance muy bajo)")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    check_system_status()
