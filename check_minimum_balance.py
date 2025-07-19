#!/usr/bin/env python3
"""
Script para verificar requisitos mínimos de balance para operar en Binance
"""

import os
import sys
from binance import Client
from dotenv import load_dotenv

def get_minimum_requirements():
    """Obtiene los requisitos mínimos de Binance"""
    print("🔍 Verificando Requisitos Mínimos de Binance")
    print("=" * 50)
    
    # Cargar credenciales
    load_dotenv()
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")
    
    if not api_key or not api_secret:
        print("❌ Credenciales de Binance no encontradas")
        return False
    
    try:
        client = Client(api_key, api_secret)
        
        # Obtener información del exchange
        exchange_info = client.get_exchange_info()
        
        print("📋 Requisitos Mínimos por Símbolo:")
        print("-" * 30)
        
        # Analizar símbolos populares
        popular_symbols = ['BNBUSDT', 'BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'DOTUSDT']
        
        for symbol in popular_symbols:
            symbol_info = None
            for s in exchange_info['symbols']:
                if s['symbol'] == symbol:
                    symbol_info = s
                    break
            
            if symbol_info:
                print(f"\n🔸 {symbol}:")
                
                # Filtros de cantidad mínima
                for filter_info in symbol_info['filters']:
                    if filter_info['filterType'] == 'LOT_SIZE':
                        min_qty = float(filter_info['minQty'])
                        step_size = float(filter_info['stepSize'])
                        print(f"   Cantidad mínima: {min_qty}")
                        print(f"   Tamaño de paso: {step_size}")
                    
                    elif filter_info['filterType'] == 'MIN_NOTIONAL':
                        min_notional = float(filter_info['minNotional'])
                        print(f"   Valor mínimo: ${min_notional} USDT")
                
                # Obtener precio actual
                try:
                    ticker = client.get_symbol_ticker(symbol=symbol)
                    current_price = float(ticker['price'])
                    min_qty_usd = min_qty * current_price
                    print(f"   Precio actual: ${current_price}")
                    print(f"   Cantidad mínima en USD: ${min_qty_usd:.4f}")
                except Exception as e:
                    print(f"   Error obteniendo precio: {e}")
        
        # Obtener balance actual
        print(f"\n💰 Balance Actual:")
        print("-" * 20)
        
        account = client.get_account()
        balances = account['balances']
        
        # Filtrar balances con saldo
        non_zero_balances = [b for b in balances if float(b['free']) > 0]
        
        total_usdt_value = 0
        
        for balance in non_zero_balances:
            asset = balance['asset']
            free_amount = float(balance['free'])
            
            if asset == 'USDT':
                total_usdt_value += free_amount
                print(f"   {asset}: {free_amount:.8f}")
            else:
                # Obtener precio en USDT
                try:
                    if asset != 'USDT':
                        ticker = client.get_symbol_ticker(symbol=f"{asset}USDT")
                        price = float(ticker['price'])
                        usdt_value = free_amount * price
                        total_usdt_value += usdt_value
                        print(f"   {asset}: {free_amount:.8f} (≈ ${usdt_value:.4f})")
                except:
                    print(f"   {asset}: {free_amount:.8f} (precio no disponible)")
        
        print(f"\n💵 Total estimado en USDT: ${total_usdt_value:.4f}")
        
        # Recomendaciones
        print(f"\n📋 Recomendaciones:")
        print("-" * 20)
        
        if total_usdt_value < 10:
            print("❌ Balance insuficiente para trading")
            print("   - Mínimo recomendado: $10 USDT")
            print("   - Para grid trading: $50-100 USDT")
            print("   - Para operaciones seguras: $100+ USDT")
        elif total_usdt_value < 50:
            print("⚠️ Balance bajo para trading")
            print("   - Puedes operar con cuidado")
            print("   - Recomendado: $50+ USDT")
        else:
            print("✅ Balance suficiente para trading")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def get_trading_limits():
    """Obtiene límites de trading específicos"""
    print(f"\n🔍 Límites de Trading Específicos:")
    print("=" * 40)
    
    load_dotenv()
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")
    
    try:
        client = Client(api_key, api_secret)
        
        # Obtener límites de cuenta
        account_status = client.get_account_status()
        print(f"Estado de cuenta: {account_status}")
        
        # Obtener información de comisiones
        commission_info = client.get_commission_info()
        print(f"Comisiones:")
        for info in commission_info:
            print(f"   {info['symbol']}: Maker {info['makerCommissionRate']}, Taker {info['takerCommissionRate']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error obteniendo límites: {e}")
        return False

def main():
    print("🤖 Análisis de Balance Mínimo para GridBot")
    print("=" * 50)
    
    # Verificar requisitos mínimos
    success1 = get_minimum_requirements()
    
    # Verificar límites de trading
    success2 = get_trading_limits()
    
    print(f"\n📊 Resumen:")
    print("-" * 15)
    print(f"Requisitos mínimos: {'✅' if success1 else '❌'}")
    print(f"Límites de trading: {'✅' if success2 else '❌'}")
    
    if success1 and success2:
        print(f"\n🎯 Próximos pasos:")
        print("1. Depositar fondos en USDT")
        print("2. Verificar balance mínimo")
        print("3. Configurar estrategia de grid")
        print("4. Iniciar trading")
    
    return success1 and success2

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 