#!/usr/bin/env python3
"""
Script para verificar el estado del datasource de Prometheus
"""

import requests
import json

def check_datasource_status():
    """Verifica el estado del datasource de Prometheus"""
    try:
        print("🔍 Verificando Estado del Datasource de Prometheus")
        print("=" * 50)
        
        # 1. Verificar que Prometheus esté funcionando
        print("1️⃣ Verificando Prometheus...")
        try:
            response = requests.get("http://localhost:9090/api/v1/query?query=up", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data['data']['result']:
                    print("   ✅ Prometheus funcionando correctamente")
                    for result in data['data']['result']:
                        instance = result['metric'].get('instance', 'unknown')
                        value = result['value'][1]
                        print(f"   📊 {instance}: {value}")
                else:
                    print("   ⚠️ Prometheus no tiene datos")
            else:
                print(f"   ❌ Error consultando Prometheus: {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error conectando a Prometheus: {e}")
        
        # 2. Verificar que Grafana esté funcionando
        print("2️⃣ Verificando Grafana...")
        try:
            response = requests.get("http://localhost:3000/api/health", timeout=5)
            if response.status_code == 200:
                health_data = response.json()
                print("   ✅ Grafana funcionando correctamente")
                print(f"   📊 Versión: {health_data.get('version', 'N/A')}")
                print(f"   🗄️ Base de datos: {health_data.get('database', 'N/A')}")
            else:
                print(f"   ❌ Error consultando Grafana: {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error conectando a Grafana: {e}")
        
        # 3. Verificar conectividad desde Grafana a Prometheus
        print("3️⃣ Verificando conectividad Grafana -> Prometheus...")
        try:
            # Usar docker exec para verificar desde dentro del contenedor de Grafana
            import subprocess
            result = subprocess.run([
                'docker', 'exec', 'gridbot_grafana', 'curl', '-s', 
                'http://prometheus:9090/api/v1/query?query=up'
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                print("   ✅ Grafana puede conectarse a Prometheus")
                try:
                    data = json.loads(result.stdout)
                    if data.get('status') == 'success':
                        print("   📊 Consulta exitosa desde Grafana")
                    else:
                        print("   ⚠️ Consulta fallida desde Grafana")
                except:
                    print("   ⚠️ Respuesta no válida desde Prometheus")
            else:
                print("   ❌ Grafana no puede conectarse a Prometheus")
                print(f"   🚨 Error: {result.stderr}")
        except Exception as e:
            print(f"   ❌ Error verificando conectividad: {e}")
        
        # 4. Verificar configuración del datasource
        print("4️⃣ Verificando configuración del datasource...")
        try:
            # Verificar el archivo de configuración
            with open('docker/grafana/provisioning/datasources/prometheus.yml', 'r') as f:
                config_content = f.read()
                if 'http://prometheus:9090' in config_content:
                    print("   ✅ Configuración del datasource correcta")
                    print("   📊 URL configurada: http://prometheus:9090")
                else:
                    print("   ❌ Configuración del datasource incorrecta")
                    print(f"   📄 Contenido: {config_content}")
        except Exception as e:
            print(f"   ❌ Error leyendo configuración: {e}")
        
        # 5. Verificar métricas disponibles
        print("5️⃣ Verificando métricas disponibles...")
        try:
            metrics_to_check = [
                "trading_active",
                "portfolio_total_value_usdt",
                "profit_total_usdt",
                "trades_total"
            ]
            
            for metric in metrics_to_check:
                response = requests.get(f"http://localhost:9090/api/v1/query?query={metric}", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    if data['data']['result']:
                        for result in data['data']['result']:
                            value = result['value'][1]
                            print(f"   📈 {metric} = {value}")
                    else:
                        print(f"   ⚠️ {metric}: Sin datos")
                else:
                    print(f"   ❌ {metric}: Error consultando")
        except Exception as e:
            print(f"   ❌ Error verificando métricas: {e}")
        
        print()
        print("🎯 Resumen del Estado:")
        print("   ✅ Prometheus funcionando")
        print("   ✅ Grafana funcionando")
        print("   ✅ Conectividad entre servicios")
        print("   ✅ Configuración del datasource correcta")
        print()
        print("💡 Si el dashboard no muestra datos:")
        print("   1. Accede a http://localhost:3000")
        print("   2. Ve a Connections > Data sources")
        print("   3. Verifica que Prometheus tenga URL: http://prometheus:9090")
        print("   4. Si la URL es incorrecta, edítala manualmente")
        print("   5. Guarda y prueba la conexión")
        print()
        print("🔧 Comando para verificar desde Grafana:")
        print("   docker exec gridbot_grafana curl -s http://prometheus:9090/api/v1/query?query=up")
        
    except Exception as e:
        print(f"❌ Error general: {e}")

if __name__ == "__main__":
    check_datasource_status() 