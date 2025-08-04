#!/usr/bin/env python3
"""
Script para arreglar las métricas del dashboard de Grafana
"""

import subprocess
import time
import requests

def fix_dashboard_metrics():
    """Arregla las métricas del dashboard"""
    try:
        print("🔧 Arreglando métricas del dashboard")
        print("=" * 40)
        
        # Paso 1: Detener la API
        print("🛑 Deteniendo API...")
        subprocess.run(['docker-compose', 'stop', 'api'], check=True)
        time.sleep(2)
        
        # Paso 2: Iniciar la API
        print("🚀 Iniciando API...")
        subprocess.run(['docker-compose', 'start', 'api'], check=True)
        time.sleep(10)
        
        # Paso 3: Ejecutar métricas en el contenedor
        print("📊 Ejecutando métricas en el contenedor...")
        result = subprocess.run([
            'docker', 'exec', 'gridbot_api', 'python', '/app/scripts/generate_real_metrics.py'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Métricas ejecutadas exitosamente")
            print(result.stdout)
        else:
            print(f"❌ Error ejecutando métricas: {result.stderr}")
        
        # Paso 4: Verificar que las métricas están disponibles
        print("\n🔍 Verificando métricas...")
        time.sleep(5)
        
        try:
            response = requests.get("http://localhost:8000/metrics", timeout=10)
            if response.status_code == 200:
                metrics_text = response.text
                if "profit_total_usdt" in metrics_text:
                    print("✅ Métricas disponibles en endpoint")
                    
                    # Buscar valores específicos
                    import re
                    profit_match = re.search(r'profit_total_usdt\{strategy="grid"\} ([\d.]+)', metrics_text)
                    if profit_match:
                        profit_value = float(profit_match.group(1))
                        print(f"💰 Ganancia total: ${profit_value}")
                    
                    portfolio_match = re.search(r'portfolio_total_value_usdt\{strategy="grid"\} ([\d.]+)', metrics_text)
                    if portfolio_match:
                        portfolio_value = float(portfolio_match.group(1))
                        print(f"🏦 Valor del portafolio: ${portfolio_value}")
                else:
                    print("❌ Métricas no encontradas en endpoint")
            else:
                print(f"❌ Error accediendo a endpoint: {response.status_code}")
        except Exception as e:
            print(f"❌ Error verificando métricas: {e}")
        
        # Paso 5: Esperar a que Prometheus las recolecte
        print("\n⏳ Esperando a que Prometheus recolecte métricas...")
        time.sleep(30)
        
        try:
            response = requests.get("http://localhost:9090/api/v1/query?query=profit_total_usdt", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('data', {}).get('result'):
                    for result in data['data']['result']:
                        value = float(result['value'][1])
                        print(f"📊 Prometheus - Ganancia total: ${value}")
                else:
                    print("❌ No hay datos en Prometheus")
            else:
                print(f"❌ Error consultando Prometheus: {response.status_code}")
        except Exception as e:
            print(f"❌ Error consultando Prometheus: {e}")
        
        print("\n🎉 Proceso completado")
        print("🌐 Verifica el dashboard en: http://localhost:3000")
        print("   Usuario: admin")
        print("   Contraseña: gridbot123")
        
    except Exception as e:
        print(f"❌ Error arreglando métricas: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    fix_dashboard_metrics() 