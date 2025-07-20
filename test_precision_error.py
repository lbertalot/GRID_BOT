#!/usr/bin/env python3
"""
Script para reproducir y probar el error de precisión de cantidad
"""

import requests
import json
import time

def reproduce_precision_error():
    """Reproduce el error de precisión de cantidad"""
    
    base_url = "http://localhost:8000"
    api_key = "aPZGos-2ok2Cb9t0OeOMPzUqtMU0GPk0"
    
    print("🔍 Reproduciendo error de precisión de cantidad...")
    
    # Cantidades problemáticas que pueden causar el error -1111
    problematic_quantities = [
        0.008123456,  # Demasiada precisión
        0.008999999,  # Casi en el límite
        0.007999999,  # Casi en el límite
        0.000123456,  # Muy pequeña con mucha precisión
        0.001234567,  # Pequeña con mucha precisión
        0.008000001,  # Ligeramente mayor que el step size
    ]
    
    for i, quantity in enumerate(problematic_quantities, 1):
        print(f"\n📋 Prueba {i}: Cantidad = {quantity}")
        
        grid_params = {
            "symbol": "BNBUSDT",
            "min_price": 700,
            "max_price": 800,
            "grids": 8,
            "quantity": quantity,
            "last_action": None
        }
        
        try:
            response = requests.post(
                f"{base_url}/api/trade/run_grid",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json=grid_params,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"   ✅ Orden ejecutada exitosamente")
                if 'validation' in result:
                    validation = result['validation']
                    if validation.get('warnings'):
                        print(f"   ⚠️ Advertencias:")
                        for warning in validation['warnings']:
                            print(f"      • {warning}")
                    if 'quantity_info' in validation:
                        qty_info = validation['quantity_info']
                        print(f"   🔧 Cantidad ajustada: {qty_info['original_quantity']} → {qty_info['adjusted_quantity']}")
                        print(f"   📏 Step Size: {qty_info['step_size']}")
                        print(f"   📏 Cantidad mínima: {qty_info['min_qty']}")
            else:
                error = response.json()
                error_detail = error.get('detail', '')
                print(f"   ❌ Error detectado:")
                print(f"      📝 {error_detail}")
                
                # Verificar si es el error de precisión
                if 'Error de Precisión' in error_detail or 'Step Size' in error_detail:
                    print(f"   ✅ Error de precisión detectado correctamente")
                elif 'Balance insuficiente' in error_detail:
                    print(f"   ⚠️ Error de balance (esperado)")
                else:
                    print(f"   ❓ Otro tipo de error")
                    
        except Exception as e:
            print(f"   ❌ Error en la solicitud: {e}")
        
        # Esperar entre pruebas
        time.sleep(3)
    
    print(f"\n🎯 Pruebas de precisión completadas")

def test_correct_quantities():
    """Prueba cantidades correctas para comparar"""
    
    base_url = "http://localhost:8000"
    api_key = "aPZGos-2ok2Cb9t0OeOMPzUqtMU0GPk0"
    
    print("\n✅ Probando cantidades correctas...")
    
    # Cantidades correctas que deberían funcionar
    correct_quantities = [
        0.008,    # Exactamente el step size * 8
        0.009,    # Step size * 9
        0.010,    # Step size * 10
        0.001,    # Mínimo step size
        0.002,    # Step size * 2
    ]
    
    for i, quantity in enumerate(correct_quantities, 1):
        print(f"\n📋 Prueba correcta {i}: Cantidad = {quantity}")
        
        grid_params = {
            "symbol": "BNBUSDT",
            "min_price": 700,
            "max_price": 800,
            "grids": 8,
            "quantity": quantity,
            "last_action": None
        }
        
        try:
            response = requests.post(
                f"{base_url}/api/trade/run_grid",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json=grid_params,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"   ✅ Orden ejecutada exitosamente")
                if 'validation' in result:
                    validation = result['validation']
                    if 'quantity_info' in validation:
                        qty_info = validation['quantity_info']
                        if qty_info['original_quantity'] == qty_info['adjusted_quantity']:
                            print(f"   ✅ Cantidad no necesitó ajuste")
                        else:
                            print(f"   ⚠️ Cantidad ajustada: {qty_info['original_quantity']} → {qty_info['adjusted_quantity']}")
            else:
                error = response.json()
                error_detail = error.get('detail', '')
                print(f"   ❌ Error inesperado: {error_detail}")
                
        except Exception as e:
            print(f"   ❌ Error en la solicitud: {e}")
        
        time.sleep(2)
    
    print(f"\n🎯 Pruebas de cantidades correctas completadas")

def get_symbol_info():
    """Obtiene información del símbolo BNBUSDT"""
    
    base_url = "http://localhost:8000"
    api_key = "aPZGos-2ok2Cb9t0OeOMPzUqtMU0GPk0"
    
    print("\n📊 Obteniendo información del símbolo BNBUSDT...")
    
    try:
        # Usar una cantidad problemática para obtener información
        grid_params = {
            "symbol": "BNBUSDT",
            "min_price": 700,
            "max_price": 800,
            "grids": 8,
            "quantity": 0.008123456,  # Cantidad problemática
            "last_action": None
        }
        
        response = requests.post(
            f"{base_url}/api/trade/run_grid",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json=grid_params,
            timeout=30
        )
        
        if response.status_code == 400:
            error = response.json()
            error_detail = error.get('detail', '')
            print(f"📝 Información del error:")
            print(f"   {error_detail}")
        else:
            print(f"⚠️ No se pudo obtener información del error")
            
    except Exception as e:
        print(f"❌ Error obteniendo información: {e}")

if __name__ == "__main__":
    print("🚀 Iniciando pruebas de error de precisión...")
    
    # Obtener información del símbolo
    get_symbol_info()
    
    # Probar cantidades problemáticas
    reproduce_precision_error()
    
    # Probar cantidades correctas
    test_correct_quantities()
    
    print("\n✅ Todas las pruebas completadas")
    print("📱 Revisa Telegram para ver los mensajes de error detallados")
    print("💡 Los errores de precisión ahora deberían ser más descriptivos") 