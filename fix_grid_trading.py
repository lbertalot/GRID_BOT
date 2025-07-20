#!/usr/bin/env python3
"""
Script para solucionar el problema del grid trading
"""

import requests
import json

def fix_grid_trading():
    """Soluciona el problema del grid trading"""
    
    base_url = "http://localhost:8000"
    headers = {
        "Authorization": "Bearer aPZGos-2ok2Cb9t0OeOMPzUqtMU0GPk0",
        "Content-Type": "application/json"
    }
    
    # 1. Verificar balance actual
    print("🔍 Verificando balance actual...")
    response = requests.get(f"{base_url}/api/trade/balances")
    balances = response.json()
    print(f"💰 USDT: {balances.get('USDT', 0)}")
    print(f"💰 BNB: {balances.get('BNB', 0)}")
    
    # 2. Calcular cantidad correcta para grid trading
    # Precio actual aproximado de BNB
    current_price = 733.0
    min_notional = 5.0  # USDT mínimo
    step_size = 0.001   # Step size de BNBUSDT
    
    # Calcular cantidad mínima
    min_quantity = min_notional / current_price
    # Ajustar al step size
    correct_quantity = round(min_quantity / step_size) * step_size
    
    print(f"🎯 Cantidad calculada: {correct_quantity:.6f} BNB")
    print(f"💵 Valor en USDT: ${correct_quantity * current_price:.2f}")
    
    # 3. Ejecutar grid trading con cantidad correcta
    grid_params = {
        "symbol": "BNBUSDT",
        "min_price": 703.39,
        "max_price": 762.01,
        "grids": 8,
        "quantity": correct_quantity
    }
    
    print("🚀 Ejecutando grid trading...")
    response = requests.post(
        f"{base_url}/api/trade/run_grid",
        headers=headers,
        json=grid_params
    )
    
    if response.status_code == 200:
        result = response.json()
        print("✅ Grid trading ejecutado exitosamente!")
        print(f"📊 Decisión: {result.get('decision', {})}")
        if 'order_result' in result:
            order = result['order_result']
            print(f"📋 Orden ID: {order.get('orderId')}")
            print(f"💰 Cantidad: {order.get('executedQty')}")
            print(f"💵 Valor: ${order.get('cummulativeQuoteQty')}")
    else:
        error = response.json()
        print(f"❌ Error: {error.get('message', 'Error desconocido')}")
    
    # 4. Verificar balance final
    print("\n🔍 Verificando balance final...")
    response = requests.get(f"{base_url}/api/trade/balances")
    balances = response.json()
    print(f"💰 USDT: {balances.get('USDT', 0)}")
    print(f"💰 BNB: {balances.get('BNB', 0)}")

if __name__ == "__main__":
    fix_grid_trading() 