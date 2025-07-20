#!/usr/bin/env python3
"""
Script completo para configurar Grafana desde el host
"""

import requests
import json
import time

def setup_grafana_complete():
    """Configura Grafana completamente"""
    
    grafana_url = "http://localhost:3000"
    username = "admin"
    password = "admin"
    
    print("🔧 Configurando Grafana Completamente...")
    
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
        
        # Asegurar que el UID sea único
        dashboard['dashboard']['uid'] = 'gridbot-trading-' + str(int(time.time()))
        dashboard['dashboard']['title'] = 'GridBot Trading Dashboard'
        
        response = requests.post(
            f"{grafana_url}/api/dashboards/db",
            auth=(username, password),
            headers={"Content-Type": "application/json"},
            json=dashboard
        )
        
        if response.status_code == 200:
            result = response.json()
            dashboard_url = f"{grafana_url}{result['url']}"
            dashboard_uid = result['uid']
            print(f"   ✅ Dashboard creado exitosamente")
            print(f"   🔗 URL: {dashboard_url}")
            print(f"   🆔 UID: {dashboard_uid}")
            return True
        else:
            print(f"   ❌ Error: {response.text}")
            return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def list_dashboards():
    """Lista todos los dashboards disponibles"""
    
    grafana_url = "http://localhost:3000"
    username = "admin"
    password = "admin"
    
    print("   📋 Listando dashboards disponibles...")
    
    try:
        response = requests.get(
            f"{grafana_url}/api/search",
            auth=(username, password)
        )
        
        if response.status_code == 200:
            dashboards = response.json()
            if dashboards:
                print("   📊 Dashboards encontrados:")
                for dashboard in dashboards:
                    print(f"      • {dashboard.get('title', 'Sin título')} (UID: {dashboard.get('uid', 'Sin UID')})")
            else:
                print("   ℹ️  No hay dashboards disponibles")
        else:
            print(f"   ❌ Error listando dashboards: {response.text}")
    except Exception as e:
        print(f"   ❌ Error: {e}")

def main():
    """Función principal"""
    
    print("🎯 Configuración Completa de Grafana")
    print("=" * 40)
    
    # Configurar Grafana
    success = setup_grafana_complete()
    
    if success:
        print(f"\n🎉 Configuración completada!")
        print(f"📊 Grafana: http://localhost:3000")
        print(f"👤 Usuario: admin")
        print(f"🔑 Contraseña: admin")
        
        # Listar dashboards
        list_dashboards()
        
        print(f"\n📈 Para acceder al dashboard:")
        print(f"   1. Ve a http://localhost:3000")
        print(f"   2. Inicia sesión con admin/admin")
        print(f"   3. Ve a Dashboards → GridBot Trading Dashboard")
        print(f"   4. O busca 'GridBot' en la barra de búsqueda")
        
        # Enviar alerta de Telegram
        try:
            telegram_url = "https://api.telegram.org/bot8064465462:AAEmpOz78phwtPGWvC3jDmGXUyTYTinhqi8/sendMessage"
            alert_message = "🎯 Dashboard de Grafana Configurado\n\n"
            alert_message += "📊 URL: http://localhost:3000\n"
            alert_message += "👤 Usuario: admin\n"
            alert_message += "🔑 Contraseña: admin\n\n"
            alert_message += "📈 Dashboard: GridBot Trading Dashboard\n"
            alert_message += "🔍 Busca 'GridBot' en la barra de búsqueda"
            
            telegram_data = {
                "chat_id": "1248403886",
                "text": alert_message
            }
            requests.post(telegram_url, data=telegram_data)
            print(f"\n📱 Alerta enviada a Telegram")
        except Exception as e:
            print(f"\n❌ Error enviando alerta: {e}")
    else:
        print(f"\n❌ Error en la configuración")

if __name__ == "__main__":
    main() 