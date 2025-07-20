#!/usr/bin/env python3
"""
Script para configurar el dashboard de Grafana automáticamente
"""

import requests
import json
import time

def setup_grafana_dashboard():
    """Configura el dashboard de Grafana"""
    
    grafana_url = "http://localhost:3000"
    username = "admin"
    password = "admin"  # Contraseña por defecto
    
    print("🔧 Configurando Dashboard de Grafana...")
    
    # 1. Crear fuente de datos de Prometheus
    print("   📊 Configurando fuente de datos Prometheus...")
    
    prometheus_datasource = {
        "name": "Prometheus",
        "type": "prometheus",
        "url": "http://prometheus:9090",
        "access": "proxy",
        "isDefault": True
    }
    
    try:
        # Intentar crear la fuente de datos
        response = requests.post(
            f"{grafana_url}/api/datasources",
            auth=(username, password),
            headers={"Content-Type": "application/json"},
            json=prometheus_datasource
        )
        
        if response.status_code == 200:
            print("   ✅ Fuente de datos Prometheus creada")
        elif response.status_code == 409:
            print("   ℹ️  Fuente de datos Prometheus ya existe")
        else:
            print(f"   ❌ Error creando fuente de datos: {response.text}")
            
    except Exception as e:
        print(f"   ❌ Error conectando a Grafana: {e}")
        return False
    
    # 2. Crear dashboard
    print("   📈 Creando dashboard...")
    
    try:
        with open('grafana_dashboard.json', 'r') as f:
            dashboard_config = json.load(f)
        
        # Agregar configuración adicional
        dashboard_config['dashboard']['uid'] = 'gridbot-dashboard'
        dashboard_config['dashboard']['version'] = 1
        
        response = requests.post(
            f"{grafana_url}/api/dashboards/db",
            auth=(username, password),
            headers={"Content-Type": "application/json"},
            json=dashboard_config
        )
        
        if response.status_code == 200:
            result = response.json()
            dashboard_url = f"{grafana_url}{result['url']}"
            print(f"   ✅ Dashboard creado exitosamente")
            print(f"   🔗 URL: {dashboard_url}")
            return True
        else:
            print(f"   ❌ Error creando dashboard: {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def main():
    """Función principal"""
    
    print("🎯 Configurando Grafana Dashboard para GridBot")
    print("=" * 50)
    
    # Esperar a que Grafana esté listo
    print("⏳ Esperando a que Grafana esté listo...")
    time.sleep(10)
    
    success = setup_grafana_dashboard()
    
    if success:
        print(f"\n🎉 Dashboard configurado exitosamente!")
        print(f"📊 Accede a Grafana en: http://localhost:3000")
        print(f"👤 Usuario: admin")
        print(f"🔑 Contraseña: admin")
        print(f"\n📈 El dashboard incluye:")
        print(f"   • Estado del sistema")
        print(f"   • Uso de CPU")
        print(f"   • Uso de memoria")
        print(f"   • Métricas de garbage collection")
    else:
        print(f"\n❌ Error configurando dashboard")

if __name__ == "__main__":
    main() 