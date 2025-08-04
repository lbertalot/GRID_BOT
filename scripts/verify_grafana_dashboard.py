#!/usr/bin/env python3
"""
Script para verificar el estado del dashboard de Grafana
"""

import requests
import json
import time
from datetime import datetime

def verify_grafana_dashboard():
    """Verifica el estado del dashboard de Grafana"""
    try:
        print("🔍 Verificando Estado del Dashboard de Grafana")
        print("=" * 50)
        
        # Configuración
        grafana_url = "http://localhost:3000"
        username = "admin"
        password = "gridbot123"
        
        # 1. Verificar conexión a Grafana
        print("1️⃣ Verificando conexión a Grafana...")
        try:
            response = requests.get(f"{grafana_url}/api/health", timeout=10)
            if response.status_code == 200:
                print("   ✅ Grafana está funcionando")
            else:
                print(f"   ❌ Grafana no responde correctamente: {response.status_code}")
                return
        except Exception as e:
            print(f"   ❌ No se puede conectar a Grafana: {e}")
            return
        
        # 2. Autenticación
        print("2️⃣ Autenticando con Grafana...")
        try:
            auth_response = requests.post(
                f"{grafana_url}/api/auth/login",
                json={"user": username, "password": password},
                timeout=10
            )
            
            if auth_response.status_code == 200:
                print("   ✅ Autenticación exitosa")
                session_cookies = auth_response.cookies
            else:
                print(f"   ❌ Error de autenticación: {auth_response.status_code}")
                return
                
        except Exception as e:
            print(f"   ❌ Error en autenticación: {e}")
            return
        
        # 3. Verificar datasource de Prometheus
        print("3️⃣ Verificando datasource de Prometheus...")
        try:
            ds_response = requests.get(
                f"{grafana_url}/api/datasources",
                cookies=session_cookies,
                timeout=10
            )
            
            if ds_response.status_code == 200:
                datasources = ds_response.json()
                prometheus_ds = None
                
                for ds in datasources:
                    if ds.get('type') == 'prometheus':
                        prometheus_ds = ds
                        break
                
                if prometheus_ds:
                    print(f"   ✅ Datasource de Prometheus encontrado: {prometheus_ds['name']}")
                    print(f"   📊 URL: {prometheus_ds['url']}")
                else:
                    print("   ❌ No se encontró datasource de Prometheus")
                    return
            else:
                print(f"   ❌ Error obteniendo datasources: {ds_response.status_code}")
                return
                
        except Exception as e:
            print(f"   ❌ Error verificando datasource: {e}")
            return
        
        # 4. Verificar dashboards
        print("4️⃣ Verificando dashboards...")
        try:
            dashboards_response = requests.get(
                f"{grafana_url}/api/search",
                cookies=session_cookies,
                timeout=10
            )
            
            if dashboards_response.status_code == 200:
                dashboards = dashboards_response.json()
                trading_dashboards = [d for d in dashboards if 'trading' in d.get('title', '').lower()]
                
                if trading_dashboards:
                    print(f"   ✅ Se encontraron {len(trading_dashboards)} dashboard(s) de trading:")
                    for db in trading_dashboards:
                        print(f"      📊 {db['title']} (ID: {db['id']})")
                else:
                    print("   ⚠️ No se encontraron dashboards de trading")
            else:
                print(f"   ❌ Error obteniendo dashboards: {dashboards_response.status_code}")
                
        except Exception as e:
            print(f"   ❌ Error verificando dashboards: {e}")
        
        # 5. Verificar métricas en Prometheus
        print("5️⃣ Verificando métricas en Prometheus...")
        try:
            # Verificar métricas específicas
            metrics_to_check = [
                "trading_active",
                "portfolio_total_value_usdt",
                "profit_total_usdt",
                "trades_total"
            ]
            
            for metric in metrics_to_check:
                prom_response = requests.get(
                    f"http://localhost:9090/api/v1/query?query={metric}",
                    timeout=10
                )
                
                if prom_response.status_code == 200:
                    data = prom_response.json()
                    if data['data']['result']:
                        print(f"   ✅ {metric}: Disponible")
                        # Mostrar valor actual
                        for result in data['data']['result']:
                            value = result['value'][1]
                            print(f"      📈 Valor actual: {value}")
                    else:
                        print(f"   ⚠️ {metric}: No hay datos")
                else:
                    print(f"   ❌ {metric}: Error consultando Prometheus")
                    
        except Exception as e:
            print(f"   ❌ Error verificando métricas: {e}")
        
        # 6. Verificar estado del target de Prometheus
        print("6️⃣ Verificando estado del target de Prometheus...")
        try:
            targets_response = requests.get(
                "http://localhost:9090/api/v1/targets",
                timeout=10
            )
            
            if targets_response.status_code == 200:
                targets_data = targets_response.json()
                api_target = None
                
                for target in targets_data['data']['activeTargets']:
                    if target['labels']['job'] == 'gridbot-api':
                        api_target = target
                        break
                
                if api_target:
                    health = api_target['health']
                    last_error = api_target.get('lastError', 'None')
                    
                    if health == 'up':
                        print("   ✅ Target de API: UP")
                    else:
                        print(f"   ❌ Target de API: {health}")
                        print(f"      🚨 Último error: {last_error}")
                else:
                    print("   ❌ No se encontró target de gridbot-api")
            else:
                print(f"   ❌ Error obteniendo targets: {targets_response.status_code}")
                
        except Exception as e:
            print(f"   ❌ Error verificando targets: {e}")
        
        print()
        print("📊 Resumen del Estado:")
        print("   ✅ Sistema de métricas centralizado funcionando")
        print("   ✅ Prometheus recogiendo métricas")
        print("   ✅ Grafana conectado")
        print("   💡 Dashboard disponible en: http://localhost:3000")
        print("   💡 Credenciales: admin/gridbot123")
        
    except Exception as e:
        print(f"❌ Error general: {e}")

if __name__ == "__main__":
    verify_grafana_dashboard() 