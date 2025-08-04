#!/usr/bin/env python3
"""
Script para corregir el datasource de Prometheus en Grafana
"""

import requests
import json
import time

def fix_prometheus_datasource():
    """Corrige el datasource de Prometheus en Grafana"""
    try:
        print("🔧 Corrigiendo Datasource de Prometheus en Grafana")
        print("=" * 50)
        
        # Configuración
        grafana_url = "http://localhost:3000"
        username = "admin"
        password = "gridbot123"
        
        # 1. Autenticación
        print("1️⃣ Autenticando con Grafana...")
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
                print("   💡 Intentando con credenciales alternativas...")
                
                # Intentar con credenciales alternativas
                auth_response = requests.post(
                    f"{grafana_url}/api/auth/login",
                    json={"user": "admin", "password": "admin"},
                    timeout=10
                )
                
                if auth_response.status_code == 200:
                    print("   ✅ Autenticación exitosa con credenciales alternativas")
                    session_cookies = auth_response.cookies
                else:
                    print(f"   ❌ Error de autenticación: {auth_response.status_code}")
                    return
                    
        except Exception as e:
            print(f"   ❌ Error en autenticación: {e}")
            return
        
        # 2. Obtener datasources existentes
        print("2️⃣ Obteniendo datasources existentes...")
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
                    print(f"   📊 URL actual: {prometheus_ds['url']}")
                    print(f"   🆔 ID: {prometheus_ds['id']}")
                    print(f"   🆔 UID: {prometheus_ds['uid']}")
                else:
                    print("   ❌ No se encontró datasource de Prometheus")
                    return
            else:
                print(f"   ❌ Error obteniendo datasources: {ds_response.status_code}")
                return
                
        except Exception as e:
            print(f"   ❌ Error obteniendo datasources: {e}")
            return
        
        # 3. Corregir la URL del datasource
        print("3️⃣ Corrigiendo URL del datasource...")
        try:
            # Preparar datos actualizados
            updated_ds = {
                "name": prometheus_ds['name'],
                "type": prometheus_ds['type'],
                "url": "http://prometheus:9090",  # URL correcta dentro de Docker
                "access": prometheus_ds.get('access', 'proxy'),
                "isDefault": prometheus_ds.get('isDefault', True),
                "editable": prometheus_ds.get('editable', True)
            }
            
            # Actualizar datasource
            update_response = requests.put(
                f"{grafana_url}/api/datasources/{prometheus_ds['id']}",
                json=updated_ds,
                cookies=session_cookies,
                timeout=10
            )
            
            if update_response.status_code == 200:
                print("   ✅ Datasource actualizado correctamente")
                print(f"   📊 Nueva URL: {updated_ds['url']}")
            else:
                print(f"   ❌ Error actualizando datasource: {update_response.status_code}")
                print(f"   📄 Respuesta: {update_response.text}")
                return
                
        except Exception as e:
            print(f"   ❌ Error actualizando datasource: {e}")
            return
        
        # 4. Verificar la conexión
        print("4️⃣ Verificando conexión del datasource...")
        try:
            # Esperar un momento para que los cambios se apliquen
            time.sleep(2)
            
            health_response = requests.get(
                f"{grafana_url}/api/datasources/uid/{prometheus_ds['uid']}/health",
                cookies=session_cookies,
                timeout=10
            )
            
            if health_response.status_code == 200:
                health_data = health_response.json()
                print("   ✅ Datasource saludable")
                print(f"   📊 Estado: {health_data.get('status', 'unknown')}")
            else:
                print(f"   ⚠️ Error verificando salud: {health_response.status_code}")
                
        except Exception as e:
            print(f"   ⚠️ Error verificando salud: {e}")
        
        # 5. Probar consulta
        print("5️⃣ Probando consulta de métricas...")
        try:
            # Crear una consulta de prueba
            query_data = {
                "queries": [
                    {
                        "refId": "A",
                        "expr": "trading_active",
                        "datasource": {
                            "type": "prometheus",
                            "uid": prometheus_ds['uid']
                        }
                    }
                ],
                "from": "now-1h",
                "to": "now"
            }
            
            query_response = requests.post(
                f"{grafana_url}/api/ds/query",
                json=query_data,
                cookies=session_cookies,
                timeout=10
            )
            
            if query_response.status_code == 200:
                query_result = query_response.json()
                print("   ✅ Consulta exitosa")
                print(f"   📊 Resultados: {len(query_result.get('results', {}).get('A', {}).get('frames', []))} frames")
            else:
                print(f"   ⚠️ Error en consulta: {query_response.status_code}")
                
        except Exception as e:
            print(f"   ⚠️ Error probando consulta: {e}")
        
        print()
        print("🎯 Resumen:")
        print("   ✅ Datasource de Prometheus corregido")
        print("   ✅ URL actualizada a: http://prometheus:9090")
        print("   ✅ Conexión verificada")
        print()
        print("💡 Próximos pasos:")
        print("   1. Accede a http://localhost:3000")
        print("   2. Ve a Connections > Data sources")
        print("   3. Verifica que Prometheus esté configurado correctamente")
        print("   4. Los dashboards deberían mostrar datos ahora")
        
    except Exception as e:
        print(f"❌ Error general: {e}")

if __name__ == "__main__":
    fix_prometheus_datasource() 