#!/usr/bin/env python3
"""
Script para vender BTC y obtener USDT para operar
"""

import asyncio
import sys
import os
from dotenv import load_dotenv

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Cargar variables de entorno
load_dotenv()

async def sell_btc_for_usdt():
    """Vende una pequeña cantidad de BTC para obtener USDT"""
    try:
        print("💰 Convirtiendo BTC a USDT para operar")
        print("=" * 40)
        
        from binance.client import Client
        
        # Crear cliente Binance
        api_key = os.getenv("BINANCE_API_KEY")
        api_secret = os.getenv("BINANCE_SECRET_KEY")
        testnet = os.getenv("BINANCE_TESTNET", "false").lower() == "true"
        
        client = Client(api_key, api_secret, testnet=testnet)
        
        # Obtener precio actual de BTC
        ticker = client.get_symbol_ticker(symbol='BTCUSDT')
        btc_price = float(ticker['price'])
        print(f"📊 Precio actual de BTC: ${btc_price:.2f}")
        
        # Obtener balance actual de BTC
        account_info = client.get_account()
        btc_balance = 0.0
        usdt_balance = 0.0
        
        for balance in account_info['balances']:
            if balance['asset'] == 'BTC':
                btc_balance = float(balance['free'])
            elif balance['asset'] == 'USDT':
                usdt_balance = float(balance['free'])
        
        print(f"💰 Balance actual BTC: {btc_balance}")
        print(f"💰 Balance actual USDT: {usdt_balance}")
        
        # Calcular cantidad a vender para obtener 10 USDT
        usdt_target = 10.0
        btc_to_sell = usdt_target / btc_price
        
        print(f"🎯 Objetivo: Obtener {usdt_target} USDT")
        print(f"📏 Cantidad BTC a vender: {btc_to_sell:.8f}")
        
        # Verificar que tenemos suficiente BTC
        if btc_balance < btc_to_sell:
            print(f"❌ Error: No hay suficiente BTC. Disponible: {btc_balance}, Necesario: {btc_to_sell}")
            return
        
        # Verificar límites de la orden
        symbol_info = client.get_symbol_info('BTCUSDT')
        
        # Encontrar el filtro LOT_SIZE
        lot_size_filter = None
        for filter_info in symbol_info['filters']:
            if filter_info['filterType'] == 'LOT_SIZE':
                lot_size_filter = filter_info
                break
        
        if lot_size_filter:
            min_qty = float(lot_size_filter['minQty'])
            step_size = float(lot_size_filter['stepSize'])
        else:
            min_qty = 0.00001  # Valor por defecto
            step_size = 0.00001  # Valor por defecto
        
        print(f"📋 Límites de orden:")
        print(f"   Mínimo: {min_qty} BTC")
        print(f"   Step size: {step_size} BTC")
        
        # Ajustar cantidad al step size
        precision = len(str(step_size).split('.')[-1].rstrip('0'))
        btc_to_sell = round(btc_to_sell, precision)
        
        # Convertir a string con el formato correcto
        btc_to_sell_str = f"{btc_to_sell:.{precision}f}"
        
        print(f"📏 Cantidad ajustada: {btc_to_sell:.8f} BTC")
        
        # Confirmar la operación
        print(f"\n¿Confirmas vender {btc_to_sell_str} BTC por aproximadamente {usdt_target} USDT? (s/n): ", end="")
        response = input().lower().strip()
        
        if response != 's':
            print("❌ Operación cancelada")
            return
        
        # Ejecutar la venta
        print(f"\n🚀 Ejecutando venta de {btc_to_sell_str} BTC...")
        
        order = client.create_order(
            symbol='BTCUSDT',
            side='SELL',
            type='MARKET',
            quantity=btc_to_sell_str
        )
        
        print(f"✅ Orden ejecutada exitosamente!")
        print(f"📋 Order ID: {order.get('orderId')}")
        print(f"💰 Cantidad vendida: {order.get('executedQty')} BTC")
        print(f"💵 Precio promedio: ${float(order.get('cummulativeQuoteQty', 0)) / float(order.get('executedQty', 1)):.2f}")
        print(f"💵 USDT obtenido: {order.get('cummulativeQuoteQty')}")
        
        # Verificar balance actualizado
        print(f"\n🔄 Verificando balance actualizado...")
        account_info = client.get_account()
        
        for balance in account_info['balances']:
            if balance['asset'] == 'BTC':
                new_btc_balance = float(balance['free'])
                print(f"💰 Nuevo balance BTC: {new_btc_balance}")
            elif balance['asset'] == 'USDT':
                new_usdt_balance = float(balance['free'])
                print(f"💰 Nuevo balance USDT: {new_usdt_balance}")
        
        print(f"\n🎉 Conversión completada exitosamente!")
        print(f"💡 Ahora puedes ejecutar el ciclo de trading con USDT disponible")
        
    except Exception as e:
        print(f"❌ Error ejecutando conversión: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(sell_btc_for_usdt()) 