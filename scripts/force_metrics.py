#!/usr/bin/env python3
"""
Script para forzar la actualización de métricas en la API
"""

import requests
import time

def force_metrics_update():
    """Fuerza la actualización de métricas"""
    try:
        print("🔄 Forzando actualización de métricas...")
        
        # Llamar al endpoint de actualización de métricas
        response = requests.post("http://localhost:8000/api/v1/metrics/update")
        
        if response.status_code == 200:
            print("✅ Métricas actualizadas exitosamente")
            print(f"📊 Respuesta: {response.json()}")
        else:
            print(f"❌ Error actualizando métricas: {response.status_code}")
            print(f"📄 Respuesta: {response.text}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def check_metrics():
    """Verifica las métricas disponibles"""
    try:
        print("\n📊 Verificando métricas disponibles...")
        
        # Verificar endpoint de métricas
        response = requests.get("http://localhost:8000/metrics")
        
        if response.status_code == 200:
            metrics_text = response.text
            print(f"✅ Endpoint de métricas funcionando")
            print(f"📏 Tamaño de respuesta: {len(metrics_text)} bytes")
            
            # Buscar métricas específicas
            if "profit_total_usdt" in metrics_text:
                print("✅ Métrica profit_total_usdt encontrada")
            else:
                print("❌ Métrica profit_total_usdt NO encontrada")
                
            if "roi_daily_percent" in metrics_text:
                print("✅ Métrica roi_daily_percent encontrada")
            else:
                print("❌ Métrica roi_daily_percent NO encontrada")
                
            if "portfolio_total_value_usdt" in metrics_text:
                print("✅ Métrica portfolio_total_value_usdt encontrada")
            else:
                print("❌ Métrica portfolio_total_value_usdt NO encontrada")
                
        else:
            print(f"❌ Error accediendo a métricas: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error verificando métricas: {e}")

if __name__ == "__main__":
    force_metrics_update()
    time.sleep(2)
    check_metrics() 