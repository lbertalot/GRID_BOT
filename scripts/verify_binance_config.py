#!/usr/bin/env python3
"""
Script para verificar la configuración de Binance
Verifica las credenciales y la configuración del trading
"""

import os
import sys
from binance.client import Client
from binance.exceptions import BinanceAPIException

def verify_binance_config():
    """Verifica la configuración de Binance"""
    
    print("🔍 Verificando configuración de Binance...")
    print("=" * 50)
    
    # Obtener variables de entorno
    api_key = os.getenv('BINANCE_API_KEY')
    secret_key = os.getenv('BINANCE_SECRET_KEY')
    testnet = os.getenv('BINANCE_TESTNET', 'true').lower() == 'true'
    paper_trading = os.getenv('PAPER_TRADING', 'true').lower() == 'true'
    
    print(f"📊 Configuración detectada:")
    print(f"   • API Key: {'✅ Configurada' if api_key else '❌ No configurada'}")
    print(f"   • Secret Key: {'✅ Configurada' if secret_key else '❌ No configurada'}")
    print(f"   • Testnet: {'✅ Activado' if testnet else '❌ Desactivado'}")
    print(f"   • Paper Trading: {'✅ Activado' if paper_trading else '❌ Desactivado'}")
    
    if not api_key or not secret_key:
        print("\n❌ Error: Credenciales de Binance no configuradas")
        print("   Configura las variables de entorno:")
        print("   - BINANCE_API_KEY")
        print("   - BINANCE_SECRET_KEY")
        return False
    
    try:
        # Crear cliente de Binance
        if testnet:
            client = Client(api_key, secret_key, testnet=True)
            print(f"\n🔗 Conectando a Binance Testnet...")
        else:
            client = Client(api_key, secret_key)
            print(f"\n🔗 Conectando a Binance Mainnet...")
        
        # Verificar conexión
        server_time = client.get_server_time()
        print(f"✅ Conexión exitosa - Server time: {server_time}")
        
        # Verificar información de cuenta
        if not paper_trading:
            try:
                account_info = client.get_account()
                print(f"✅ Información de cuenta obtenida")
                print(f"   • Tipo de cuenta: {account_info.get('accountType', 'N/A')}")
                print(f"   • Permisos: {', '.join(account_info.get('permissions', []))}")
                
                # Verificar balances
                balances = account_info.get('balances', [])
                non_zero_balances = [b for b in balances if float(b['free']) > 0 or float(b['locked']) > 0]
                print(f"   • Balances con saldo: {len(non_zero_balances)}")
                
            except BinanceAPIException as e:
                if e.code == -2015:
                    print(f"❌ Error: API Secret required for private endpoints")
                    print(f"   Verifica que las credenciales sean correctas")
                    return False
                else:
                    print(f"❌ Error de API: {e}")
                    return False
        else:
            print(f"📄 Modo Paper Trading activado - No se verifican credenciales reales")
        
        # Verificar información del exchange
        exchange_info = client.get_exchange_info()
        print(f"✅ Información del exchange obtenida")
        print(f"   • Símbolos disponibles: {len(exchange_info['symbols'])}")
        
        # Verificar símbolos específicos
        test_symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
        available_symbols = [s['symbol'] for s in exchange_info['symbols'] if s['status'] == 'TRADING']
        
        print(f"   • Símbolos de prueba:")
        for symbol in test_symbols:
            status = "✅ Disponible" if symbol in available_symbols else "❌ No disponible"
            print(f"     - {symbol}: {status}")
        
        return True
        
    except BinanceAPIException as e:
        print(f"❌ Error de API de Binance: {e}")
        return False
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return False

def check_environment_variables():
    """Verifica las variables de entorno relacionadas con trading"""
    
    print("\n🔧 Verificando variables de entorno...")
    print("=" * 30)
    
    env_vars = {
        'BINANCE_API_KEY': 'Clave API de Binance',
        'BINANCE_SECRET_KEY': 'Clave secreta de Binance',
        'BINANCE_TESTNET': 'Usar testnet de Binance',
        'PAPER_TRADING': 'Modo paper trading',
        'TELEGRAM_BOT_TOKEN': 'Token del bot de Telegram',
        'TELEGRAM_CHAT_ID': 'ID del chat de Telegram',
        'DEBUG': 'Modo debug',
        'ENVIRONMENT': 'Entorno de ejecución'
    }
    
    for var, description in env_vars.items():
        value = os.getenv(var)
        if value:
            # Ocultar valores sensibles
            if 'KEY' in var or 'SECRET' in var or 'TOKEN' in var:
                display_value = f"{value[:8]}..." if len(value) > 8 else "***"
            else:
                display_value = value
            print(f"   ✅ {var}: {display_value}")
        else:
            print(f"   ⚠️  {var}: No configurada")
    
    return True

if __name__ == "__main__":
    print("🚀 Verificación de configuración de Binance")
    print("=" * 50)
    
    # Verificar variables de entorno
    check_environment_variables()
    
    # Verificar configuración de Binance
    if verify_binance_config():
        print("\n🎉 ¡Configuración de Binance verificada exitosamente!")
    else:
        print("\n❌ Problemas detectados en la configuración de Binance")
        sys.exit(1) 