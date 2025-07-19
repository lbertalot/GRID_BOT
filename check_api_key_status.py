#!/usr/bin/env python3
"""
Script para verificar el estado específico de la API Key de Binance
"""

import os
import sys
import time
import hashlib
import hmac
import requests
from binance import Client
from binance.exceptions import BinanceAPIException
from dotenv import load_dotenv

def test_api_key_directly():
    """Prueba directa de la API Key usando requests"""
    load_dotenv()
    
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")
    
    if not api_key or not api_secret:
        print("❌ Credenciales no encontradas")
        return False
    
    # URL base de Binance
    base_url = "https://api.binance.com"
    
    # Endpoint para obtener información de la cuenta
    endpoint = "/api/v3/account"
    
    # Timestamp actual
    timestamp = int(time.time() * 1000)
    
    # Parámetros de la consulta
    params = {
        'timestamp': timestamp
    }
    
    # Crear la firma
    query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
    signature = hmac.new(
        api_secret.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # Agregar la firma a los parámetros
    params['signature'] = signature
    
    # Headers
    headers = {
        'X-MBX-APIKEY': api_key
    }
    
    # URL completa
    url = f"{base_url}{endpoint}"
    
    print(f"🔍 Probando API Key directamente...")
    print(f"   URL: {url}")
    print(f"   API Key: {api_key[:10]}...")
    print(f"   Timestamp: {timestamp}")
    print(f"   Query string: {query_string}")
    print(f"   Signature: {signature[:20]}...")
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        
        print(f"   Status Code: {response.status_code}")
        print(f"   Response Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ API Key válida!")
            print(f"   Tipo de cuenta: {data.get('accountType', 'N/A')}")
            print(f"   Permisos de trading: {data.get('canTrade', 'N/A')}")
            print(f"   Permisos de retiro: {data.get('canWithdraw', 'N/A')}")
            print(f"   Permisos de depósito: {data.get('canDeposit', 'N/A')}")
            return True
        else:
            print(f"   ❌ Error HTTP: {response.status_code}")
            print(f"   Response: {response.text}")
            
            # Análisis específico del error
            if response.status_code == 401:
                print(f"   🔍 Error 401: No autorizado")
                print(f"      - API Key inválida")
                print(f"      - API Key deshabilitada")
                print(f"      - Permisos insuficientes")
            elif response.status_code == 403:
                print(f"   🔍 Error 403: Prohibido")
                print(f"      - IP no autorizada")
                print(f"      - Restricciones de IP activas")
            elif response.status_code == 429:
                print(f"   🔍 Error 429: Rate limit excedido")
            else:
                print(f"   🔍 Error {response.status_code}: {response.text}")
            
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Error de conexión: {e}")
        return False

def test_binance_client():
    """Prueba usando la librería de Binance"""
    load_dotenv()
    
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")
    
    print(f"\n🔍 Probando con librería de Binance...")
    
    try:
        client = Client(api_key, api_secret)
        
        # Probar diferentes métodos
        methods = [
            ('get_account', 'Información de cuenta'),
            ('get_exchange_info', 'Información del exchange'),
            ('get_server_time', 'Tiempo del servidor'),
            ('get_system_status', 'Estado del sistema')
        ]
        
        for method_name, description in methods:
            try:
                print(f"   🔍 Probando {method_name} ({description})...")
                method = getattr(client, method_name)
                result = method()
                print(f"   ✅ {method_name} exitoso")
                
                if method_name == 'get_account':
                    print(f"      Tipo: {result.get('accountType', 'N/A')}")
                    print(f"      Trading: {result.get('canTrade', 'N/A')}")
                
            except BinanceAPIException as e:
                print(f"   ❌ {method_name} falló: {e.code} - {e.message}")
            except Exception as e:
                print(f"   ❌ {method_name} error: {e}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error inicializando cliente: {e}")
        return False

def main():
    print("🔍 Verificación Detallada del Estado de la API Key")
    print("=" * 60)
    
    # Prueba 1: Directa con requests
    success1 = test_api_key_directly()
    
    # Prueba 2: Con librería de Binance
    success2 = test_binance_client()
    
    print(f"\n📊 Resumen:")
    print(f"   Prueba directa: {'✅' if success1 else '❌'}")
    print(f"   Prueba con librería: {'✅' if success2 else '❌'}")
    
    if success1 and success2:
        print(f"\n🎉 API Key funcionando correctamente!")
        return True
    else:
        print(f"\n🔧 Problemas detectados. Revisa:")
        print(f"   1. Estado de la API Key en Binance")
        print(f"   2. Permisos configurados")
        print(f"   3. Restricciones de IP")
        print(f"   4. Validez de las credenciales")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 