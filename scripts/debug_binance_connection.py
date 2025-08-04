#!/usr/bin/env python3
"""
Script para diagnosticar la conexión con Binance API
"""

import asyncio
import sys
import os
from binance.client import Client
from binance.exceptions import BinanceAPIException
from dotenv import load_dotenv

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Cargar variables de entorno desde .env
load_dotenv()

async def debug_binance_connection():
    """Diagnostica la conexión con Binance API"""
    try:
        print("🔍 Diagnóstico de Conexión Binance API")
        print("=" * 50)
        
        # 1. Verificar variables de entorno
        print("\n🔐 Verificando credenciales...")
        api_key = os.getenv("BINANCE_API_KEY")
        api_secret = os.getenv("BINANCE_SECRET_KEY")
        testnet = os.getenv("BINANCE_TESTNET", "false").lower() == "true"
        
        print(f"• API Key configurada: {'✅' if api_key else '❌'}")
        print(f"• API Secret configurada: {'✅' if api_secret else '❌'}")
        print(f"• Testnet: {testnet}")
        
        if not api_key or not api_secret:
            print("❌ Credenciales no configuradas")
            return
        
        # 2. Crear cliente Binance
        print("\n🔗 Creando cliente Binance...")
        client = Client(api_key, api_secret, testnet=testnet)
        
        # 3. Verificar conexión
        print("\n📡 Probando conexión...")
        try:
            # Test básico de conexión
            server_time = client.get_server_time()
            print(f"✅ Conexión exitosa - Server time: {server_time}")
            
            # Obtener información de cuenta
            print("\n📊 Obteniendo información de cuenta...")
            account_info = client.get_account()
            print(f"✅ Información de cuenta obtenida")
            print(f"• Tipo de cuenta: {account_info.get('accountType', 'N/A')}")
            print(f"• Permisos: {account_info.get('permissions', [])}")
            
            # 4. Mostrar balances reales
            print("\n💰 Balances reales de tu cuenta:")
            print("-" * 40)
            
            balances_with_value = []
            total_usdt_value = 0
            
            for balance in account_info['balances']:
                asset = balance['asset']
                free_balance = float(balance['free'])
                locked_balance = float(balance['locked'])
                total_balance = free_balance + locked_balance
                
                if total_balance > 0:
                    # Obtener precio en USDT si no es USDT
                    usdt_value = 0
                    if asset == 'USDT':
                        usdt_value = total_balance
                    else:
                        try:
                            ticker = client.get_symbol_ticker(symbol=f"{asset}USDT")
                            price = float(ticker['price'])
                            usdt_value = total_balance * price
                        except:
                            try:
                                ticker = client.get_symbol_ticker(symbol=f"USDT{asset}")
                                price = float(ticker['price'])
                                usdt_value = total_balance / price
                            except:
                                usdt_value = 0
                    
                    balances_with_value.append({
                        'asset': asset,
                        'free': free_balance,
                        'locked': locked_balance,
                        'total': total_balance,
                        'usdt_value': usdt_value
                    })
                    
                    if asset == 'USDT':
                        total_usdt_value += total_balance
                    else:
                        total_usdt_value += usdt_value
            
            # Ordenar por valor USDT descendente
            balances_with_value.sort(key=lambda x: x['usdt_value'], reverse=True)
            
            for balance in balances_with_value:
                print(f"• {balance['asset']}: {balance['total']:.6f} (${balance['usdt_value']:.2f})")
                if balance['locked'] > 0:
                    print(f"  - Libre: {balance['free']:.6f}, Bloqueado: {balance['locked']:.6f}")
            
            print(f"\n💵 Valor total en USDT: ${total_usdt_value:.2f}")
            
            # 5. Verificar activos configurados
            print("\n🎯 Verificando activos configurados...")
            import json
            try:
                with open('grid_config_optimized.json', 'r') as f:
                    config = json.load(f)
                
                configured_assets = []
                for symbol, asset_config in config.items():
                    if symbol != "_optimization_metadata" and asset_config.get('is_active', True):
                        base_asset = symbol.replace('USDT', '')
                        configured_assets.append(base_asset)
                
                print(f"• Activos configurados: {configured_assets}")
                
                # Verificar saldo de activos configurados
                print("\n📋 Estado de activos configurados:")
                for asset in configured_assets:
                    balance_info = next((b for b in balances_with_value if b['asset'] == asset), None)
                    if balance_info:
                        print(f"✅ {asset}: {balance_info['total']:.6f} (${balance_info['usdt_value']:.2f})")
                    else:
                        print(f"❌ {asset}: Sin saldo")
                        
            except Exception as e:
                print(f"❌ Error leyendo configuración: {e}")
            
        except BinanceAPIException as e:
            print(f"❌ Error de API Binance: {e}")
            print(f"• Código: {e.code}")
            print(f"• Mensaje: {e.message}")
        except Exception as e:
            print(f"❌ Error de conexión: {e}")
            
    except Exception as e:
        print(f"❌ Error general: {e}")

if __name__ == "__main__":
    asyncio.run(debug_binance_connection()) 