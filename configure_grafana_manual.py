#!/usr/bin/env python3
"""
Script para configurar Grafana manualmente desde el host
"""

import requests
import json
import time

def configure_grafana():
    """Configura Grafana manualmente"""
    
    grafana_url = "http://localhost:3000"
    username = "admin"
    password = "admin"
    
    print("🔧 Configurando Grafana Manualmente...")
    
    # 1. Verificar conexión
    try:
        response = requests.get(f"{grafana_url}/api/health")
        print(f"   ✅ Grafana está disponible: {response.json()}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    # 2. Crear fuente de datos Prometheus
    print("   📊 Configurando fuente de datos Prometheus...")
    
    datasource = {
        "name": "Prometheus",
        "type": "prometheus",
        "url": "http://prometheus:9090",
        "access": "proxy",
        "isDefault": True
    }
    
    try:
        response = requests.post(
            f"{grafana_url}/api/datasources",
            auth=(username, password),
            headers={"Content-Type": "application/json"},
            json=datasource
        )
        
        if response.status_code == 200:
            print("   ✅ Fuente de datos creada")
        elif response.status_code == 409:
            print("   ℹ️  Fuente de datos ya existe")
        else:
            print(f"   ❌ Error: {response.text}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # 3. Crear dashboard
    print("   📈 Creando dashboard de trading...")
    
    try:
        with open('trading_dashboard.json', 'r') as f:
            dashboard = json.load(f)
        
        response = requests.post(
            f"{grafana_url}/api/dashboards/db",
            auth=(username, password),
            headers={"Content-Type": "application/json"},
            json=dashboard
        )
        
        if response.status_code == 200:
            result = response.json()
            dashboard_url = f"{grafana_url}{result['url']}"
            print(f"   ✅ Dashboard creado")
            print(f"   🔗 URL: {dashboard_url}")
            return True
        else:
            print(f"   ❌ Error: {response.text}")
            return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def main():
    """Función principal"""
    
    print("🎯 Configuración Manual de Grafana")
    print("=" * 40)
    
    success = configure_grafana()
    
    if success:
        print(f"\n🎉 Configuración completada!")
        print(f"📊 Grafana: http://localhost:3000")
        print(f"👤 Usuario: admin")
        print(f"🔑 Contraseña: admin")
        print(f"\n📈 Dashboard incluye:")
        print(f"   • Estado del sistema")
        print(f"   • Balance USDT/BNB")
        print(f"   • Estrategias activas")
        print(f"   • Ganancias/pérdidas")
        print(f"   • Volumen de trading")
        print(f"   • Métricas de API")
    else:
        print(f"\n❌ Error en la configuración")

if __name__ == "__main__":
    main() 