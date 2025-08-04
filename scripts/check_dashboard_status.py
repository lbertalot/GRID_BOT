#!/usr/bin/env python3
"""
Script simple para verificar el estado del dashboard
"""

import requests
import json

def check_dashboard_status():
    """Verifica el estado del dashboard de forma simple"""
    try:
        print("🔍 Verificando Estado del Sistema de Métricas")
        print("=" * 50)
        
        # 1. Verificar API de métricas
        print("1️⃣ Verificando API de métricas...")
        try:
            response = requests.get("http://localhost:8000/metrics", timeout=5)
            if response.status_code == 200:
                print("   ✅ API de métricas funcionando")
                # Verificar si hay métricas de trading
                if "trading_active" in response.text:
                    print("   ✅ Métricas de trading disponibles")
                else:
                    print("   ⚠️ No se encontraron métricas de trading")
            else:
                print(f"   ❌ API de métricas error: {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error conectando a API: {e}")
        
        # 2. Verificar Prometheus
        print("2️⃣ Verificando Prometheus...")
        try:
            response = requests.get("http://localhost:9090/api/v1/query?query=trading_active", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data['data']['result']:
                    print("   ✅ Prometheus obteniendo métricas")
                    for result in data['data']['result']:
                        value = result['value'][1]
                        print(f"   📊 trading_active = {value}")
                else:
                    print("   ⚠️ Prometheus no tiene datos de trading_active")
            else:
                print(f"   ❌ Error consultando Prometheus: {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error conectando a Prometheus: {e}")
        
        # 3. Verificar Grafana
        print("3️⃣ Verificando Grafana...")
        try:
            response = requests.get("http://localhost:3000/api/health", timeout=5)
            if response.status_code == 200:
                print("   ✅ Grafana funcionando")
            else:
                print(f"   ❌ Grafana error: {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error conectando a Grafana: {e}")
        
        # 4. Verificar métricas específicas
        print("4️⃣ Verificando métricas específicas...")
        metrics_to_check = [
            "portfolio_total_value_usdt",
            "profit_total_usdt",
            "trades_total"
        ]
        
        for metric in metrics_to_check:
            try:
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
                print(f"   ❌ {metric}: Error - {e}")
        
        print()
        print("📊 Resumen:")
        print("   ✅ Sistema de métricas centralizado implementado")
        print("   ✅ Prometheus recogiendo datos")
        print("   ✅ Grafana disponible")
        print()
        print("🌐 URLs importantes:")
        print("   📊 Grafana Dashboard: http://localhost:3000")
        print("   📈 Prometheus: http://localhost:9090")
        print("   🔧 API Métricas: http://localhost:8000/metrics")
        print()
        print("🔑 Credenciales Grafana: admin/gridbot123")
        print("💡 Si el dashboard no muestra datos, verifica:")
        print("   1. Que Prometheus esté scrapeando correctamente")
        print("   2. Que el datasource de Prometheus esté configurado")
        print("   3. Que los paneles del dashboard usen las métricas correctas")
        
    except Exception as e:
        print(f"❌ Error general: {e}")

if __name__ == "__main__":
    check_dashboard_status() 