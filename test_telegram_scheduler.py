#!/usr/bin/env python3
"""
Script para probar el envío de alertas de Telegram desde el scheduler
"""

import requests
import json
import time

def test_telegram_from_scheduler():
    """Prueba el envío de alertas de Telegram desde el scheduler"""
    
    base_url = "http://localhost:8000"
    api_key = "aPZGos-2ok2Cb9t0OeOMPzUqtMU0GPk0"
    
    print("🧪 Probando envío de alertas de Telegram desde el scheduler...")
    
    # Ejecutar una orden manual para generar una alerta
    print("📤 Ejecutando orden manual para generar alerta...")
    
    try:
        response = requests.post(
            f"{base_url}/api/trade/order",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "symbol": "BNBUSDT",
                "side": "BUY",
                "type": "MARKET",
                "quantity": 0.007
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Orden ejecutada exitosamente")
            print(f"📋 Orden ID: {result['order'].get('orderId', 'N/A')}")
            print("📱 Deberías recibir una alerta de Telegram")
        else:
            error = response.json()
            print(f"❌ Error ejecutando orden: {error.get('message', 'Error desconocido')}")
            
    except Exception as e:
        print(f"❌ Error en la solicitud: {e}")
    
    # Esperar un momento para que se procese
    print("\n⏳ Esperando 10 segundos para que se procese la alerta...")
    time.sleep(10)
    
    # Verificar logs del contenedor
    print("\n📋 Verificando logs del contenedor...")
    import subprocess
    try:
        logs = subprocess.check_output(
            ["docker", "logs", "gridbot_api", "--tail", "20"],
            text=True
        )
        print("📄 Últimos 20 logs del contenedor:")
        print(logs)
    except Exception as e:
        print(f"❌ Error obteniendo logs: {e}")

def test_telegram_direct():
    """Prueba el envío directo de alertas de Telegram"""
    
    print("\n🔍 Probando envío directo de alertas de Telegram...")
    
    try:
        response = requests.post(
            "http://localhost:8000/api/trade/run_grid",
            headers={
                "Authorization": "Bearer aPZGos-2ok2Cb9t0OeOMPzUqtMU0GPk0",
                "Content-Type": "application/json"
            },
            json={
                "symbol": "BNBUSDT",
                "min_price": 700,
                "max_price": 800,
                "grids": 8,
                "quantity": 0.007,
                "last_action": None
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Grid ejecutado exitosamente")
            if 'order_result' in result:
                print("📱 Deberías recibir una alerta de Telegram detallada")
            else:
                print("⏸️ No se ejecutó orden (sin acción requerida)")
        else:
            error = response.json()
            print(f"❌ Error ejecutando grid: {error.get('message', 'Error desconocido')}")
            
    except Exception as e:
        print(f"❌ Error en la solicitud: {e}")

if __name__ == "__main__":
    print("🚀 Iniciando pruebas de Telegram desde scheduler...")
    
    # Probar envío directo
    test_telegram_direct()
    
    # Probar desde scheduler
    test_telegram_from_scheduler()
    
    print("\n✅ Pruebas completadas")
    print("📱 Revisa Telegram para ver si recibiste las alertas") 