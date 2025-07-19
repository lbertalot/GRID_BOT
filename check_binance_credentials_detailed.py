#!/usr/bin/env python3
"""
Script detallado para verificar credenciales de Binance API
"""

import os
import sys
import time
from binance import Client
from binance.exceptions import BinanceAPIException
from dotenv import load_dotenv

def main():
    print("🔍 Verificación Detallada de Credenciales de Binance API")
    print("=" * 60)
    
    # Cargar variables de entorno
    load_dotenv()
    
    # Obtener credenciales
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")
    
    print(f"📋 Análisis de Credenciales:")
    print(f"   API Key encontrada: {'✅' if api_key else '❌'}")
    print(f"   API Secret encontrado: {'✅' if api_secret else '❌'}")
    
    if api_key:
        print(f"   Longitud API Key: {len(api_key)} caracteres")
        print(f"   API Key comienza con: {api_key[:10]}...")
        print(f"   API Key termina con: ...{api_key[-10:]}")
    
    if api_secret:
        print(f"   Longitud API Secret: {len(api_secret)} caracteres")
        print(f"   API Secret comienza con: {api_secret[:10]}...")
        print(f"   API Secret termina con: ...{api_secret[-10:]}")
    
    print()
    
    if not api_key or not api_secret:
        print("❌ ERROR: Credenciales incompletas")
        return False
    
    # Verificar caracteres especiales o espacios
    print(f"🔍 Verificación de Formato:")
    print(f"   API Key tiene espacios: {'❌' if ' ' in api_key else '✅'}")
    print(f"   API Secret tiene espacios: {'❌' if ' ' in api_secret else '✅'}")
    has_newline_key = '\n' in api_key
    has_newline_secret = '\n' in api_secret
    print(f"   API Key tiene saltos de línea: {'❌' if has_newline_key else '✅'}")
    print(f"   API Secret tiene saltos de línea: {'❌' if has_newline_secret else '✅'}")
    
    # Limpiar credenciales
    api_key_clean = api_key.strip()
    api_secret_clean = api_secret.strip()
    
    if api_key != api_key_clean or api_secret != api_secret_clean:
        print(f"   ⚠️ Se detectaron espacios extra, limpiando...")
        api_key = api_key_clean
        api_secret = api_secret_clean
    
    print()
    
    # Paso 1: Verificar conexión sin autenticación
    print("🔗 Paso 1: Verificando conexión a Binance (sin autenticación)")
    try:
        client_public = Client()
        server_time = client_public.get_server_time()
        print(f"   ✅ Conexión exitosa")
        print(f"   Tiempo del servidor: {server_time}")
        
        # Verificar diferencia de tiempo
        local_time = int(time.time() * 1000)
        time_diff = abs(server_time['serverTime'] - local_time)
        print(f"   Diferencia de tiempo: {time_diff}ms")
        
        if time_diff > 5000:  # 5 segundos
            print(f"   ⚠️ ADVERTENCIA: Diferencia de tiempo significativa")
            print(f"      Esto puede causar errores de firma")
        
    except Exception as e:
        print(f"   ❌ Error de conexión: {e}")
        return False
    
    print()
    
    # Paso 2: Verificar credenciales con diferentes métodos
    print("🔐 Paso 2: Verificando credenciales")
    
    # Método 1: get_account (requiere autenticación)
    print(f"   🔍 Probando get_account()...")
    try:
        client = Client(api_key, api_secret)
        start_time = time.time()
        account_info = client.get_account()
        duration = time.time() - start_time
        
        print(f"   ✅ get_account() exitoso ({duration:.3f}s)")
        print(f"   Tipo de cuenta: {account_info.get('accountType', 'N/A')}")
        print(f"   Permisos de trading: {account_info.get('canTrade', 'N/A')}")
        
        # Verificar balances
        balances = account_info['balances']
        non_zero_balances = [b for b in balances if float(b['free']) > 0 or float(b['locked']) > 0]
        print(f"   Balances con saldo: {len(non_zero_balances)}")
        
        return True
        
    except BinanceAPIException as e:
        print(f"   ❌ get_account() falló: {e}")
        print(f"   Código: {e.code}")
        print(f"   Mensaje: {e.message}")
        
        # Análisis específico del error
        if e.code == -1022:
            print(f"\n🔍 ANÁLISIS DEL ERROR 1022:")
            print(f"   El error -1022 indica un problema con la firma de la API.")
            print(f"   Esto puede deberse a:")
            print(f"   1. API Key o Secret incorrectos")
            print(f"   2. Restricciones de IP")
            print(f"   3. API Key deshabilitada")
            print(f"   4. Permisos insuficientes")
            print(f"   5. Problema de sincronización de tiempo")
            
            # Probar con diferentes métodos
            print(f"\n🔍 Probando métodos alternativos...")
            
            # Método 2: get_exchange_info (no requiere autenticación)
            try:
                print(f"   🔍 Probando get_exchange_info()...")
                exchange_info = client.get_exchange_info()
                print(f"   ✅ get_exchange_info() exitoso")
                print(f"   Símbolos disponibles: {len(exchange_info['symbols'])}")
            except Exception as e2:
                print(f"   ❌ get_exchange_info() falló: {e2}")
            
            # Método 3: get_server_time (no requiere autenticación)
            try:
                print(f"   🔍 Probando get_server_time()...")
                server_time = client.get_server_time()
                print(f"   ✅ get_server_time() exitoso")
            except Exception as e3:
                print(f"   ❌ get_server_time() falló: {e3}")
        
        return False
        
    except Exception as e:
        print(f"   ❌ Error inesperado: {e}")
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print(f"\n✅ Verificación completada exitosamente")
        print(f"🎉 Las credenciales de Binance son válidas")
        sys.exit(0)
    else:
        print(f"\n❌ Verificación falló")
        print(f"🔧 Revisa la guía SOLUCION_ERROR_1022.md")
        sys.exit(1) 