#!/usr/bin/env python3
"""
Script para verificar las credenciales de Binance API
"""

import os
import sys
from binance import Client
from binance.exceptions import BinanceAPIException
from dotenv import load_dotenv

def main():
    print("🔍 Verificación de Credenciales de Binance API")
    print("=" * 50)
    
    # Cargar variables de entorno
    load_dotenv()
    
    # Obtener credenciales
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")
    
    print(f"📋 Credenciales encontradas:")
    print(f"   API Key: {api_key[:20] + '...' if api_key else 'NO ENCONTRADA'}")
    print(f"   API Secret: {api_secret[:20] + '...' if api_secret else 'NO ENCONTRADA'}")
    print()
    
    if not api_key or not api_secret:
        print("❌ ERROR: Credenciales no configuradas")
        print("   Verifica que BINANCE_API_KEY y BINANCE_API_SECRET estén en el archivo .env")
        return False
    
    # Paso 1: Verificar conexión sin autenticación
    print("🔗 Paso 1: Verificando conexión a Binance (sin autenticación)")
    try:
        client_public = Client()
        server_time = client_public.get_server_time()
        print(f"   ✅ Conexión exitosa")
        print(f"   Tiempo del servidor: {server_time}")
    except Exception as e:
        print(f"   ❌ Error de conexión: {e}")
        return False
    
    # Paso 2: Verificar credenciales
    print("\n🔐 Paso 2: Verificando credenciales")
    try:
        client = Client(api_key, api_secret)
        
        # Intentar obtener información de la cuenta
        account_info = client.get_account()
        
        print(f"   ✅ Credenciales válidas")
        print(f"   Tipo de cuenta: {account_info.get('accountType', 'N/A')}")
        print(f"   Comisión maker: {account_info.get('makerCommission', 'N/A')}")
        print(f"   Comisión taker: {account_info.get('takerCommission', 'N/A')}")
        
        # Verificar balances
        balances = account_info['balances']
        non_zero_balances = [b for b in balances if float(b['free']) > 0 or float(b['locked']) > 0]
        
        print(f"   Balances con saldo: {len(non_zero_balances)}")
        for balance in non_zero_balances[:5]:
            print(f"     {balance['asset']}: Libre={balance['free']}, Bloqueado={balance['locked']}")
        
        return True
        
    except BinanceAPIException as e:
        print(f"   ❌ Error de Binance API: {e}")
        print(f"   Código: {e.code}")
        print(f"   Mensaje: {e.message}")
        
        if e.code == -1022:
            print(f"\n🔍 DIAGNÓSTICO DEL ERROR 1022:")
            print(f"   El error -1022 indica un problema con la firma de la API.")
            print(f"   Posibles causas y soluciones:")
            print(f"\n   1. 🔑 API Key inválida:")
            print(f"      - Verifica que la API Key sea correcta")
            print(f"      - Copia la API Key exactamente desde Binance")
            print(f"      - No incluyas espacios extra")
            
            print(f"\n   2. 🔒 API Secret incorrecto:")
            print(f"      - Verifica que el API Secret sea correcto")
            print(f"      - Copia el API Secret exactamente desde Binance")
            print(f"      - No incluyas espacios extra")
            
            print(f"\n   3. 🚫 Permisos insuficientes:")
            print(f"      - Ve a Binance > API Management")
            print(f"      - Verifica que la API Key tenga permisos de 'Read Info'")
            print(f"      - Para trading, necesita permisos de 'Enable Trading'")
            
            print(f"\n   4. 🌐 Restricciones de IP:")
            print(f"      - Verifica que tu IP esté en la lista blanca")
            print(f"      - Ve a Binance > API Management > Restrict Access")
            print(f"      - Agrega tu IP actual a la lista blanca")
            
            print(f"\n   5. ⚠️ API Key deshabilitada:")
            print(f"      - Verifica que la API Key esté activa")
            print(f"      - Ve a Binance > API Management")
            print(f"      - Asegúrate de que el estado sea 'Active'")
            
            print(f"\n   6. 🔄 Problema de sincronización de tiempo:")
            print(f"      - Verifica que el tiempo del sistema sea correcto")
            print(f"      - Los timestamps deben estar sincronizados con Binance")
        
        return False
        
    except Exception as e:
        print(f"   ❌ Error inesperado: {e}")
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print(f"\n✅ Verificación completada exitosamente")
        sys.exit(0)
    else:
        print(f"\n❌ Verificación falló")
        sys.exit(1) 