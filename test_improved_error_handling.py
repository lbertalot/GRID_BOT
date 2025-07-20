#!/usr/bin/env python3
"""
Script para probar el manejo de errores mejorado en grid trading
"""

import requests
import json
import time

def test_improved_error_handling():
    """Prueba el manejo de errores mejorado"""
    
    base_url = "http://localhost:8000"
    api_key = "aPZGos-2ok2Cb9t0OeOMPzUqtMU0GPk0"
    
    print("🧪 Probando manejo de errores mejorado...")
    
    # Casos de prueba con cantidades problemáticas
    test_cases = [
        {
            "name": "Cantidad con demasiada precisión",
            "params": {
                "symbol": "BNBUSDT",
                "min_price": 700,
                "max_price": 800,
                "grids": 8,
                "quantity": 0.008123456,  # Demasiada precisión
                "last_action": None
            }
        },
        {
            "name": "Cantidad muy pequeña",
            "params": {
                "symbol": "BNBUSDT",
                "min_price": 700,
                "max_price": 800,
                "grids": 8,
                "quantity": 0.0001,  # Muy pequeña
                "last_action": None
            }
        },
        {
            "name": "Cantidad correcta",
            "params": {
                "symbol": "BNBUSDT",
                "min_price": 700,
                "max_price": 800,
                "grids": 8,
                "quantity": 0.008,  # Correcta
                "last_action": None
            }
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📋 Prueba {i}: {test_case['name']}")
        print(f"   📊 Parámetros: {test_case['params']}")
        
        try:
            response = requests.post(
                f"{base_url}/api/trade/run_grid",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json=test_case['params'],
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"   ✅ Éxito")
                if 'validation' in result:
                    validation = result['validation']
                    if validation.get('warnings'):
                        print(f"   ⚠️ Advertencias:")
                        for warning in validation['warnings']:
                            print(f"      • {warning}")
                    if 'quantity_info' in validation:
                        qty_info = validation['quantity_info']
                        print(f"   🔧 Cantidad ajustada: {qty_info['original_quantity']} → {qty_info['adjusted_quantity']}")
            else:
                error = response.json()
                print(f"   ❌ Error: {error.get('detail', 'Error desconocido')}")
                
        except Exception as e:
            print(f"   ❌ Error en la solicitud: {e}")
        
        # Esperar entre pruebas
        time.sleep(2)
    
    print(f"\n🎯 Pruebas completadas")
    print(f"💡 Revisa los mensajes de Telegram para ver los errores detallados")

def test_symbol_info():
    """Prueba la obtención de información de símbolos"""
    
    base_url = "http://localhost:8000"
    api_key = "aPZGos-2ok2Cb9t0OeOMPzUqtMU0GPk0"
    
    print("\n🔍 Probando información de símbolos...")
    
    symbols = ["BNBUSDT", "BTCUSDT", "ETHUSDT", "LTCUSDT", "LINKUSDT", "DOTUSDT"]
    
    for symbol in symbols:
        print(f"\n📊 Símbolo: {symbol}")
        
        try:
            # Probar con una cantidad problemática
            test_params = {
                "symbol": symbol,
                "min_price": 100,
                "max_price": 200,
                "grids": 5,
                "quantity": 0.001234567,  # Cantidad con demasiada precisión
                "last_action": None
            }
            
            response = requests.post(
                f"{base_url}/api/trade/run_grid",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json=test_params,
                timeout=30
            )
            
            if response.status_code == 400:
                error = response.json()
                error_detail = error.get('detail', '')
                if 'Step Size' in error_detail:
                    print(f"   ✅ Error de precisión detectado correctamente")
                    print(f"   📝 Mensaje: {error_detail[:100]}...")
                else:
                    print(f"   ⚠️ Error diferente: {error_detail[:100]}...")
            else:
                print(f"   ✅ Orden ejecutada sin problemas")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        time.sleep(1)

if __name__ == "__main__":
    print("🚀 Iniciando pruebas de manejo de errores mejorado...")
    
    # Probar casos específicos
    test_improved_error_handling()
    
    # Probar información de símbolos
    test_symbol_info()
    
    print("\n✅ Pruebas completadas")
    print("📱 Revisa Telegram para ver los mensajes de error detallados") 