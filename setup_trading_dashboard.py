#!/usr/bin/env python3
"""
Script para configurar el dashboard de trading en Grafana
"""

import requests
import json
import time
import os

def setup_trading_dashboard():
    """Configura el dashboard de trading en Grafana"""
    
    grafana_url = "http://localhost:3000"
    username = "admin"
    password = "admin"  # Contraseña por defecto
    
    print("🔧 Configurando Dashboard de Trading en Grafana...")
    
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
    
    # 2. Crear fuente de datos de Prometheus si no existe
    print("   📊 Configurando fuente de datos Prometheus...")
    
    prometheus_datasource = {
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
            json=prometheus_datasource
        )
        
        if response.status_code == 200:
            print("   ✅ Fuente de datos Prometheus creada")
        elif response.status_code == 409:
            print("   ℹ️  Fuente de datos Prometheus ya existe")
        else:
            print(f"   ❌ Error creando fuente de datos: {response.text}")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # 3. Crear dashboard de trading
    print("   📈 Creando dashboard de trading...")
    
    try:
        with open('trading_dashboard.json', 'r') as f:
            dashboard_config = json.load(f)
        
        # Agregar configuración adicional
        dashboard_config['dashboard']['uid'] = 'gridbot-trading'
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
            print(f"   ✅ Dashboard de trading creado exitosamente")
            print(f"   🔗 URL: {dashboard_url}")
            return True
        else:
            print(f"   ❌ Error creando dashboard: {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def initialize_metrics():
    """Inicializa métricas con valores por defecto"""
    
    print("   📊 Inicializando métricas...")
    
    # Obtener balance actual
    try:
        response = requests.get("http://localhost:8000/api/trade/balances")
        if response.status_code == 200:
            balances = response.json()
            
            # Actualizar métricas de balance
            for asset, amount in balances.items():
                if asset in ['USDT', 'BNB', 'BTC', 'LTC', 'LINK', 'DOT']:
                    print(f"      • {asset}: {amount}")
            
            return True
    except Exception as e:
        print(f"      ❌ Error obteniendo balance: {e}")
    
    return False

def main():
    """Función principal"""
    
    print("🎯 Configurando Dashboard de Trading para GridBot")
    print("=" * 55)
    
    # Esperar a que los servicios estén listos
    print("⏳ Esperando a que los servicios estén listos...")
    time.sleep(5)
    
    # Inicializar métricas
    initialize_metrics()
    
    # Configurar dashboard
    success = setup_trading_dashboard()
    
    if success:
        print(f"\n🎉 Dashboard de Trading configurado exitosamente!")
        print(f"📊 Accede a Grafana en: http://localhost:3000")
        print(f"👤 Usuario: admin")
        print(f"🔑 Contraseña: admin")
        print(f"\n📈 El dashboard incluye:")
        print(f"   • Estado general del sistema")
        print(f"   • Balance USDT y BNB")
        print(f"   • Estrategias activas")
        print(f"   • Órdenes ejecutadas (24h)")
        print(f"   • Volumen de trading (24h)")
        print(f"   • Ganancias/pérdidas por estrategia")
        print(f"   • Niveles de grid activos")
        print(f"   • Llamadas API Binance")
        print(f"   • Latencia API Binance")
        print(f"   • Estado de conexión Binance")
        print(f"   • Uso de CPU y memoria")
        
        # Enviar alerta de Telegram
        try:
            telegram_url = "https://api.telegram.org/bot8064465462:AAEmpOz78phwtPGWvC3jDmGXUyTYTinhqi8/sendMessage"
            alert_message = "🎯 Dashboard de Trading Configurado\n\n"
            alert_message += "📊 Grafana: http://localhost:3000\n"
            alert_message += "👤 Usuario: admin\n"
            alert_message += "🔑 Contraseña: admin\n\n"
            alert_message += "📈 Métricas disponibles:\n"
            alert_message += "• Estado del sistema\n"
            alert_message += "• Balance USDT/BNB\n"
            alert_message += "• Estrategias activas\n"
            alert_message += "• Ganancias/pérdidas\n"
            alert_message += "• Volumen de trading"
            
            telegram_data = {
                "chat_id": "1248403886",
                "text": alert_message
            }
            requests.post(telegram_url, data=telegram_data)
            print(f"\n📱 Alerta enviada a Telegram")
        except Exception as e:
            print(f"\n❌ Error enviando alerta: {e}")
    else:
        print(f"\n❌ Error configurando dashboard")

if __name__ == "__main__":
    main() 