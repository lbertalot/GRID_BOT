#!/usr/bin/env python3
"""
Script para monitorear transacciones de BNB/USDT y verificar el funcionamiento del grid
"""

import requests
import json
import time
from datetime import datetime
import os

def get_balances():
    """Obtiene los balances actuales"""
    try:
        response = requests.get("http://localhost:8000/api/trade/balances", timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Error obteniendo balances: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def get_bnb_trades(limit=10):
    """Obtiene las transacciones recientes de BNB/USDT"""
    try:
        response = requests.get(f"http://localhost:8000/api/trade/trades?symbol=BNBUSDT&limit={limit}", timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Error obteniendo trades: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def get_bnb_price():
    """Obtiene el precio actual de BNB/USDT"""
    try:
        response = requests.get("http://localhost:8000/api/trade/price/BNBUSDT", timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Error obteniendo precio: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def get_grid_config():
    """Obtiene la configuración del grid para BNB/USDT"""
    try:
        response = requests.get("http://localhost:8000/api/trade/grid_config?symbol=BNBUSDT", timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Error obteniendo configuración: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def run_grid_manual():
    """Ejecuta el grid manualmente para BNB/USDT"""
    try:
        api_key = "aPZGos-2ok2Cb9t0OeOMPzUqtMU0GPk0"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        data = {
            "symbol": "BNBUSDT",
            "min_price": 706.58,
            "max_price": 780.96,
            "grids": 8,
            "quantity": 0.007,
            "last_action": None
        }
        
        response = requests.post("http://localhost:8000/api/trade/run_grid", 
                               headers=headers, json=data, timeout=30)
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Error ejecutando grid: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def analyze_grid_decision(price, min_price, max_price):
    """Analiza si el precio actual está en rango para el grid"""
    if price < min_price:
        return "COMPRAR (precio bajo del rango)"
    elif price > max_price:
        return "VENDER (precio alto del rango)"
    else:
        return "EN RANGO (esperar movimiento)"

def main():
    """Función principal de monitoreo"""
    print("🔍 MONITOREO DE TRANSACCIONES BNB/USDT")
    print("=" * 50)
    
    # Obtener datos actuales
    balances = get_balances()
    trades = get_bnb_trades(5)
    price_data = get_bnb_price()
    grid_config = get_grid_config()
    
    if not all([balances, trades, price_data, grid_config]):
        print("❌ No se pudieron obtener todos los datos")
        return
    
    # Mostrar información actual
    print(f"\n💰 BALANCES ACTUALES:")
    print(f"   BNB: {balances.get('BNB', 0):.6f}")
    print(f"   USDT: {balances.get('USDT', 0):.2f}")
    
    current_price = price_data.get('price', 0)
    print(f"\n📈 PRECIO ACTUAL BNB/USDT: ${current_price:.2f}")
    
    # Analizar configuración del grid
    bnb_config = grid_config.get('BNBUSDT', {})
    min_price = bnb_config.get('min_price', 0)
    max_price = bnb_config.get('max_price', 0)
    quantity = bnb_config.get('quantity', 0)
    
    print(f"\n⚙️ CONFIGURACIÓN GRID:")
    print(f"   Rango: ${min_price:.2f} - ${max_price:.2f}")
    print(f"   Cantidad: {quantity}")
    print(f"   Decisión: {analyze_grid_decision(current_price, min_price, max_price)}")
    
    # Mostrar transacciones recientes
    print(f"\n📊 ÚLTIMAS TRANSACCIONES BNB/USDT:")
    for trade in trades:
        timestamp = trade.get('timestamp', '')
        side = trade.get('side', '')
        quantity = trade.get('quantity', 0)
        price = trade.get('entry_price', 0)
        value = quantity * price
        
        print(f"   {timestamp[:19]} | {side} {quantity} BNB @ ${price:.2f} = ${value:.2f}")
    
    # Verificar si hay suficientes fondos para operar
    bnb_balance = balances.get('BNB', 0)
    usdt_balance = balances.get('USDT', 0)
    
    print(f"\n🔍 ANÁLISIS DE OPERABILIDAD:")
    
    # Verificar si puede vender
    if bnb_balance >= quantity:
        print(f"   ✅ Puede VENDER: {bnb_balance:.6f} BNB disponible")
    else:
        print(f"   ❌ No puede VENDER: necesita {quantity} BNB, tiene {bnb_balance:.6f}")
    
    # Verificar si puede comprar
    usdt_needed = quantity * current_price
    if usdt_balance >= usdt_needed:
        print(f"   ✅ Puede COMPRAR: ${usdt_balance:.2f} USDT disponible")
    else:
        print(f"   ❌ No puede COMPRAR: necesita ${usdt_needed:.2f} USDT, tiene ${usdt_balance:.2f}")
    
    # Ejecutar grid manualmente si es necesario
    print(f"\n🤖 EJECUTANDO GRID MANUALMENTE...")
    grid_result = run_grid_manual()
    
    if grid_result:
        if 'error' in grid_result:
            print(f"   ❌ Error: {grid_result['error']}")
        else:
            decision = grid_result.get('decision', {})
            order_result = grid_result.get('order_result', {})
            
            if decision.get('action'):
                print(f"   ✅ Acción ejecutada: {decision['action']} en nivel {decision['level']}")
                if order_result.get('orderId'):
                    print(f"   📋 Order ID: {order_result['orderId']}")
                    print(f"   💰 Cantidad: {order_result.get('executedQty', 0)}")
                    print(f"   💵 Precio: ${order_result.get('fills', [{}])[0].get('price', 0)}")
            else:
                print(f"   ⏸️ No se ejecutó acción: precio en rango")
    else:
        print(f"   ❌ Error ejecutando grid")
    
    print(f"\n🎯 RESUMEN:")
    print(f"   • BNB disponible: {bnb_balance:.6f}")
    print(f"   • USDT disponible: ${usdt_balance:.2f}")
    print(f"   • Precio actual: ${current_price:.2f}")
    print(f"   • Grid activo: {bnb_config.get('is_active', False)}")
    print(f"   • Última transacción: {trades[0].get('timestamp', '')[:19] if trades else 'N/A'}")
    
    print(f"\n✅ Monitoreo completado - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main() 