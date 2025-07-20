#!/usr/bin/env python3
"""
Script para probar directamente la API de Binance y diagnosticar errores
"""

import os
from binance import Client
import json

def test_binance_connection():
    """Prueba la conexión directa con Binance"""
    
    # Obtener credenciales del entorno
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")
    
    if not api_key or not api_secret:
        print("❌ Error: Credenciales de Binance no configuradas")
        return
    
    try:
        # Crear cliente
        client = Client(api_key, api_secret)
        print("✅ Cliente de Binance creado correctamente")
        
        # Probar conexión
        account_info = client.get_account()
        print(f"✅ Conexión exitosa - Tipo de cuenta: {account_info.get('accountType', 'N/A')}")
        
        # Verificar balance
        balances = {b["asset"]: float(b["free"]) for b in account_info["balances"] if float(b["free"]) > 0}
        print(f"💰 Balances: {balances}")
        
        # Verificar símbolo BNBUSDT
        exchange_info = client.get_exchange_info()
        bnb_symbol = None
        for symbol in exchange_info['symbols']:
            if symbol['symbol'] == 'BNBUSDT':
                bnb_symbol = symbol
                break
        
        if bnb_symbol:
            print(f"✅ Símbolo BNBUSDT encontrado - Estado: {bnb_symbol['status']}")
            
            # Mostrar filtros importantes
            for filter_info in bnb_symbol['filters']:
                if filter_info['filterType'] in ['LOT_SIZE', 'NOTIONAL', 'MIN_NOTIONAL']:
                    print(f"📋 Filtro {filter_info['filterType']}: {filter_info}")
        else:
            print("❌ Símbolo BNBUSDT no encontrado")
        
        # Probar precio actual
        ticker = client.get_symbol_ticker(symbol="BNBUSDT")
        current_price = float(ticker["price"])
        print(f"📊 Precio actual BNBUSDT: ${current_price}")
        
        # Calcular cantidad mínima para NOTIONAL
        min_notional = 5.0  # USDT
        min_quantity = min_notional / current_price
        print(f"🎯 Cantidad mínima para NOTIONAL: {min_quantity:.6f} BNB")
        
        # Probar orden de compra pequeña
        try:
            test_quantity = round(min_quantity + 0.001, 6)  # Un poco más del mínimo
            print(f"🧪 Probando orden de compra: {test_quantity} BNB")
            
            order = client.order_market_buy(symbol="BNBUSDT", quantity=test_quantity)
            print(f"✅ Orden exitosa: {order['orderId']}")
            print(f"   Cantidad ejecutada: {order['executedQty']}")
            print(f"   Precio promedio: {order['cummulativeQuoteQty']}")
            
        except Exception as e:
            print(f"❌ Error en orden de prueba: {e}")
            if hasattr(e, 'code'):
                print(f"   Código de error: {e.code}")
            if hasattr(e, 'message'):
                print(f"   Mensaje: {e.message}")
        
    except Exception as e:
        print(f"❌ Error general: {e}")
        if hasattr(e, 'code'):
            print(f"   Código de error: {e.code}")
        if hasattr(e, 'message'):
            print(f"   Mensaje: {e.message}")

if __name__ == "__main__":
    test_binance_connection() 