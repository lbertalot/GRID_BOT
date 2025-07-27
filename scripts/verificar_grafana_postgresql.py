#!/usr/bin/env python3
"""
Script para verificar la configuración de PostgreSQL en Grafana
"""

import requests
import json
import time
from datetime import datetime

# Configuración
GRAFANA_URL = "http://localhost:3000"
GRAFANA_USER = "admin"
GRAFANA_PASSWORD = "gridbot123"
POSTGRES_DS_NAME = "PostgreSQL"

def check_grafana_health():
    """Verificar que Grafana esté funcionando"""
    try:
        response = requests.get(f"{GRAFANA_URL}/api/health", timeout=5)
        if response.status_code == 200:
            print("✅ Grafana está funcionando correctamente")
            return True
        else:
            print(f"❌ Grafana no está respondiendo: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error conectando a Grafana: {e}")
        return False

def check_postgresql_datasource():
    """Verificar que el data source de PostgreSQL esté configurado"""
    try:
        response = requests.get(
            f"{GRAFANA_URL}/api/datasources",
            auth=(GRAFANA_USER, GRAFANA_PASSWORD),
            timeout=5
        )
        
        if response.status_code == 200:
            datasources = response.json()
            postgres_ds = None
            
            for ds in datasources:
                if ds.get('name') == POSTGRES_DS_NAME and ds.get('type') == 'grafana-postgresql-datasource':
                    postgres_ds = ds
                    break
            
            if postgres_ds:
                print(f"✅ Data source PostgreSQL configurado:")
                print(f"   - Nombre: {postgres_ds.get('name')}")
                print(f"   - URL: {postgres_ds.get('url')}")
                print(f"   - Base de datos: {postgres_ds.get('jsonData', {}).get('database', 'N/A')}")
                return True
            else:
                print("❌ Data source PostgreSQL no encontrado")
                return False
        else:
            print(f"❌ Error obteniendo data sources: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error verificando data source: {e}")
        return False

def check_postgresql_connection():
    """Verificar la conexión al data source de PostgreSQL"""
    try:
        # Primero obtener el ID del data source
        response = requests.get(
            f"{GRAFANA_URL}/api/datasources",
            auth=(GRAFANA_USER, GRAFANA_PASSWORD),
            timeout=5
        )
        
        if response.status_code != 200:
            print(f"❌ Error obteniendo data sources: {response.status_code}")
            return False
        
        datasources = response.json()
        postgres_ds = None
        
        for ds in datasources:
            if ds.get('name') == POSTGRES_DS_NAME and ds.get('type') == 'grafana-postgresql-datasource':
                postgres_ds = ds
                break
        
        if not postgres_ds:
            print("❌ Data source PostgreSQL no encontrado")
            return False
        
        ds_id = postgres_ds.get('id')
        
        # Query simple para probar la conexión
        query = {
            "queries": [
                {
                    "refId": "A",
                    "rawQuery": True,
                    "rawSql": "SELECT 1 as test",
                    "format": "table"
                }
            ],
            "from": "now-1h",
            "to": "now"
        }
        
        response = requests.post(
            f"{GRAFANA_URL}/api/datasources/{ds_id}/resources/query",
            auth=(GRAFANA_USER, GRAFANA_PASSWORD),
            headers={'Content-Type': 'application/json'},
            data=json.dumps(query),
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('results', {}).get('A', {}).get('frames'):
                print("✅ Conexión a PostgreSQL exitosa")
                return True
            else:
                print("❌ Error en la consulta a PostgreSQL")
                return False
        else:
            print(f"❌ Error probando conexión: {response.status_code}")
            print(f"   Respuesta: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error probando conexión: {e}")
        return False

def check_dashboards():
    """Verificar que los dashboards estén cargados"""
    try:
        response = requests.get(
            f"{GRAFANA_URL}/api/search",
            auth=(GRAFANA_USER, GRAFANA_PASSWORD),
            timeout=5
        )
        
        if response.status_code == 200:
            dashboards = response.json()
            postgres_dashboard = None
            
            for dashboard in dashboards:
                if 'postgresql' in dashboard.get('tags', []) and 'gridbot' in dashboard.get('tags', []):
                    postgres_dashboard = dashboard
                    break
            
            if postgres_dashboard:
                print(f"✅ Dashboard PostgreSQL encontrado:")
                print(f"   - Título: {postgres_dashboard.get('title')}")
                print(f"   - Tags: {postgres_dashboard.get('tags')}")
                return True
            else:
                print("❌ Dashboard PostgreSQL no encontrado")
                return False
        else:
            print(f"❌ Error obteniendo dashboards: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error verificando dashboards: {e}")
        return False

def main():
    """Función principal"""
    print("🔍 Verificando configuración de PostgreSQL en Grafana")
    print("=" * 60)
    
    checks = [
        ("Salud de Grafana", check_grafana_health),
        ("Data Source PostgreSQL", check_postgresql_datasource),
        ("Conexión PostgreSQL", check_postgresql_connection),
        ("Dashboards", check_dashboards)
    ]
    
    results = []
    
    for check_name, check_func in checks:
        print(f"\n📋 Verificando: {check_name}")
        print("-" * 40)
        result = check_func()
        results.append((check_name, result))
        time.sleep(1)
    
    print("\n" + "=" * 60)
    print("📊 RESUMEN DE VERIFICACIÓN")
    print("=" * 60)
    
    all_passed = True
    for check_name, result in results:
        status = "✅ PASÓ" if result else "❌ FALLÓ"
        print(f"{status} - {check_name}")
        if not result:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ¡TODAS LAS VERIFICACIONES PASARON!")
        print("✅ PostgreSQL está correctamente configurado en Grafana")
        print(f"🌐 Accede a Grafana en: {GRAFANA_URL}")
        print("👤 Usuario: admin / Contraseña: gridbot123")
    else:
        print("⚠️  ALGUNAS VERIFICACIONES FALLARON")
        print("🔧 Revisa los logs de Grafana para más detalles")
    
    print("=" * 60)

if __name__ == "__main__":
    main() 