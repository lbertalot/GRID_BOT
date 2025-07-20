#!/usr/bin/env python3
"""
Script para configurar el dashboard funcional de GridBot
"""

import requests
import json
import time
import subprocess
import os
from datetime import datetime

def setup_working_dashboard():
    """Configurar dashboard funcional de GridBot"""
    
    grafana_url = "http://localhost:3000"
    username = "admin"
    password = "gridbot123"
    
    print("🔧 Configurando Dashboard Funcional de GridBot...")
    print("=" * 60)
    
    # 1. Verificar conexión a Grafana
    try:
        response = requests.get(f"{grafana_url}/api/health")
        if response.status_code != 200:
            print("   ❌ Grafana no está disponible")
            return False
        print("   ✅ Grafana está disponible")
    except Exception as e:
        print(f"   ❌ Error conectando a Grafana: {e}")
        return False
    
    # 2. Verificar conexión a Prometheus
    try:
        response = requests.get("http://localhost:9090/api/v1/query?query=up")
        if response.status_code != 200:
            print("   ❌ Prometheus no está disponible")
            return False
        print("   ✅ Prometheus está disponible")
    except Exception as e:
        print(f"   ❌ Error conectando a Prometheus: {e}")
        return False
    
    # 3. Verificar métricas disponibles
    print("\n📊 Verificando métricas disponibles...")
    
    metrics_to_check = [
        "gridbot_binance_connection_status",
        "gridbot_api_requests_total",
        "gridbot_binance_api_calls_total",
        "gridbot_memory_usage_bytes",
        "gridbot_cpu_usage_percent"
    ]
    
    available_metrics = []
    for metric in metrics_to_check:
        try:
            response = requests.get(f"http://localhost:9090/api/v1/query?query={metric}")
            if response.status_code == 200:
                data = response.json()
                if data['data']['result']:
                    available_metrics.append(metric)
                    print(f"   ✅ {metric}")
                else:
                    print(f"   ⚠️  {metric} (sin datos)")
            else:
                print(f"   ❌ {metric} (error)")
        except Exception as e:
            print(f"   ❌ {metric} (error: {e})")
    
    if not available_metrics:
        print("   ❌ No hay métricas disponibles")
        return False
    
    print(f"   📈 {len(available_metrics)} métricas disponibles")
    
    # 4. Importar dashboard funcional
    print("\n📋 Importando dashboard funcional...")
    
    dashboard_file = "working_dashboard.json"
    if not os.path.exists(dashboard_file):
        print(f"   ❌ Archivo {dashboard_file} no encontrado")
        return False
    
    try:
        with open(dashboard_file, 'r') as f:
            dashboard_data = json.load(f)
        
        response = requests.post(
            f"{grafana_url}/api/dashboards/db",
            auth=(username, password),
            headers={"Content-Type": "application/json"},
            json=dashboard_data
        )
        
        if response.status_code == 200:
            result = response.json()
            dashboard_url = f"{grafana_url}{result['url']}"
            print(f"   ✅ Dashboard importado: {dashboard_url}")
        else:
            print(f"   ❌ Error importando dashboard: {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    # 5. Configurar actualización automática de métricas
    print("\n🔄 Configurando actualización automática...")
    
    # Crear script de actualización
    update_script = """#!/bin/bash
# Script para actualizar métricas automáticamente
cd /app
python3 generate_pnl_metrics.py
"""
    
    with open("update_metrics.sh", "w") as f:
        f.write(update_script)
    
    os.chmod("update_metrics.sh", 0o755)
    print("   ✅ Script de actualización creado")
    
    # 6. Mostrar instrucciones
    print("\n🎉 Configuración Completada!")
    print("\n📋 CÓMO USAR EL DASHBOARD FUNCIONAL:")
    print("\n1. 🖥️  DASHBOARD GRAFANA:")
    print(f"   • URL: {dashboard_url}")
    print("   • Usuario: admin")
    print("   • Contraseña: gridbot123")
    print("   • Actualización automática cada 30 segundos")
    
    print("\n2. 📊 MÉTRICAS DISPONIBLES:")
    for metric in available_metrics:
        print(f"   • {metric}")
    
    print("\n3. 🔧 COMANDOS ÚTILES:")
    print("   • Ver métricas: curl http://localhost:8000/api/metrics/metrics/")
    print("   • Ver P&L: docker-compose exec api python3 generate_pnl_metrics.py")
    print("   • Prometheus: http://localhost:9090")
    print("   • Grafana: http://localhost:3000")
    
    print("\n4. 🎯 INTERPRETACIÓN:")
    print("   • 🟢 Binance Connection Status = 1: Conectado a Binance")
    print("   • 📈 API Requests: Número de peticiones por minuto")
    print("   • 📊 Binance API Calls: Llamadas a la API de Binance")
    print("   • 💾 Memory Usage: Uso de memoria en MB")
    print("   • 🔥 CPU Usage: Uso de CPU en porcentaje")
    
    print("\n5. 🔄 ACTUALIZACIÓN AUTOMÁTICA:")
    print("   • Las métricas se actualizan automáticamente")
    print("   • Prometheus recoge datos cada 15 segundos")
    print("   • Grafana actualiza el dashboard cada 30 segundos")
    
    print("\n6. 🚨 SOLUCIÓN DE PROBLEMAS:")
    print("   • Si no ves datos: Verifica que la API esté funcionando")
    print("   • Si hay errores: Revisa los logs con docker-compose logs api")
    print("   • Si Prometheus no recibe datos: Reinicia con docker-compose restart prometheus")
    
    return True

if __name__ == "__main__":
    setup_working_dashboard() 