#!/usr/bin/env python3
"""
Script para probar los endpoints de comisiones
"""

import requests
import json
import time

# Configuración
API_BASE_URL = "http://localhost:8000"
API_KEY = "aPZGos-2ok2Cb9t0OeOMPzUqtMU0GPk0"  # API key del .env

def test_commission_endpoints():
    """Probar todos los endpoints de comisiones"""
    headers = {"Authorization": f"Bearer {API_KEY}"}
    
    print("🚀 Probando endpoints de comisiones...")
    
    # 1. Obtener tasas de comisión
    print("\n📊 1. Probando GET /api/v1/commissions/rates")
    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/commissions/rates", headers=headers)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Tasas: {json.dumps(data, indent=2)}")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # 2. Calcular comisión
    print("\n💰 2. Probando POST /api/v1/commissions/calculate")
    try:
        payload = {
            "symbol": "BTCUSDT",
            "quantity": 0.001,
            "price": 45000,
            "side": "BUY",
            "order_type": "MARKET"
        }
        response = requests.post(f"{API_BASE_URL}/api/v1/commissions/calculate", 
                               headers=headers, json=payload)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Resultado: {json.dumps(data, indent=2)}")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # 3. Validar rentabilidad de grid
    print("\n🔍 3. Probando POST /api/v1/commissions/validate-profitability")
    try:
        payload = {
            "symbol": "BTCUSDT",
            "min_price": 44000,
            "max_price": 46000,
            "quantity": 0.001,
            "num_levels": 5,
            "min_profit_percentage": 0.5
        }
        response = requests.post(f"{API_BASE_URL}/api/v1/commissions/validate-profitability", 
                               headers=headers, json=payload)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Análisis: {json.dumps(data, indent=2)}")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # 4. Calcular ganancia con comisiones
    print("\n📈 4. Probando POST /api/v1/commissions/calculate-profit")
    try:
        params = {
            "symbol": "BTCUSDT",
            "buy_price": 45000,
            "sell_price": 46000,
            "quantity": 0.001,
            "buy_order_type": "MARKET",
            "sell_order_type": "MARKET"
        }
        response = requests.post(f"{API_BASE_URL}/api/v1/commissions/calculate-profit", 
                               headers=headers, params=params)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Análisis de ganancia: {json.dumps(data, indent=2)}")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # 5. Obtener estado del sistema
    print("\n📊 5. Probando GET /api/v1/commissions/status")
    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/commissions/status", headers=headers)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Estado: {json.dumps(data, indent=2)}")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Error: {e}")

def test_health_endpoint():
    """Probar que la API esté funcionando"""
    print("\n🏥 Probando endpoint de salud...")
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ API funcionando correctamente")
        else:
            print(f"   ❌ API no responde: {response.text}")
    except Exception as e:
        print(f"   ❌ Error conectando a la API: {e}")

def main():
    """Función principal"""
    print("🚀 Iniciando pruebas de endpoints de comisiones...")
    
    # Esperar un momento para que la API esté lista
    print("⏳ Esperando que la API esté lista...")
    time.sleep(5)
    
    # Probar salud de la API
    test_health_endpoint()
    
    # Probar endpoints de comisiones
    test_commission_endpoints()
    
    print("\n✅ Pruebas completadas!")

if __name__ == "__main__":
    main()
