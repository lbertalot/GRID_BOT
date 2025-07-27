#!/usr/bin/env python3
"""
Script para verificar las métricas de trading en Prometheus
"""

import requests
import json
import time
from datetime import datetime

# Configuración
PROMETHEUS_URL = "http://localhost:9090"
GRAFANA_URL = "http://localhost:3000"
GRAFANA_USER = "admin"
GRAFANA_PASSWORD = "gridbot123"

def check_prometheus_health():
    """Verificar que Prometheus esté funcionando"""
    try:
        response = requests.get(f"{PROMETHEUS_URL}/-/healthy", timeout=5)
        if response.status_code == 200:
            print("✅ Prometheus está funcionando correctamente")
            return True
        else:
            print(f"❌ Prometheus no está respondiendo: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error conectando a Prometheus: {e}")
        return False

def check_gridbot_metrics():
    """Verificar que las métricas del GridBot estén disponibles"""
    metrics_to_check = [
        "gridbot_binance_connection_status",
        "gridbot_api_requests_total",
        "gridbot_api_request_duration_seconds_count",
        "gridbot_binance_api_calls_total",
        "gridbot_binance_api_latency_seconds_count",
        "gridbot_cpu_usage_percent",
        "gridbot_memory_usage_bytes"
    ]
    
    available_metrics = []
    missing_metrics = []
    
    for metric in metrics_to_check:
        try:
            response = requests.get(
                f"{PROMETHEUS_URL}/api/v1/query",
                params={"query": metric},
                timeout=5
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'success' and result.get('data', {}).get('result'):
                    available_metrics.append(metric)
                    print(f"✅ {metric}")
                else:
                    missing_metrics.append(metric)
                    print(f"❌ {metric} - Sin datos")
            else:
                missing_metrics.append(metric)
                print(f"❌ {metric} - Error HTTP {response.status_code}")
        except Exception as e:
            missing_metrics.append(metric)
            print(f"❌ {metric} - Error: {e}")
    
    return available_metrics, missing_metrics

def check_binance_connection():
    """Verificar el estado de conexión con Binance"""
    try:
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": "gridbot_binance_connection_status"},
            timeout=5
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('status') == 'success' and result.get('data', {}).get('result'):
                value = result['data']['result'][0]['value'][1]
                if value == "1":
                    print("✅ Binance Connection: REAL TRADING MODE")
                    return True
                else:
                    print("⚠️  Binance Connection: SIMULATION MODE")
                    return False
            else:
                print("❌ No se pudo obtener el estado de conexión")
                return False
        else:
            print(f"❌ Error obteniendo estado de conexión: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error verificando conexión: {e}")
        return False

def check_api_performance():
    """Verificar métricas de rendimiento de la API"""
    try:
        # Verificar tasa de requests
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": "rate(gridbot_api_requests_total[5m])"},
            timeout=5
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('status') == 'success' and result.get('data', {}).get('result'):
                print("✅ API Performance metrics disponibles")
                for item in result['data']['result']:
                    endpoint = item['metric'].get('endpoint', 'N/A')
                    value = float(item['value'][1])
                    print(f"   - {endpoint}: {value:.2f} req/s")
                return True
            else:
                print("❌ No se pudieron obtener métricas de rendimiento")
                return False
        else:
            print(f"❌ Error obteniendo métricas de rendimiento: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error verificando rendimiento: {e}")
        return False

def check_grafana_dashboard():
    """Verificar que el dashboard de trading esté disponible"""
    try:
        response = requests.get(
            f"{GRAFANA_URL}/api/search",
            auth=(GRAFANA_USER, GRAFANA_PASSWORD),
            timeout=5
        )
        
        if response.status_code == 200:
            dashboards = response.json()
            trading_dashboard = None
            
            for dashboard in dashboards:
                if 'trading' in dashboard.get('title', '').lower():
                    trading_dashboard = dashboard
                    break
            
            if trading_dashboard:
                print(f"✅ Dashboard de Trading encontrado:")
                print(f"   - Título: {trading_dashboard.get('title')}")
                print(f"   - URL: {trading_dashboard.get('url')}")
                print(f"   - Tags: {trading_dashboard.get('tags')}")
                return True
            else:
                print("❌ Dashboard de Trading no encontrado")
                return False
        else:
            print(f"❌ Error obteniendo dashboards: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error verificando dashboard: {e}")
        return False

def main():
    """Función principal"""
    print("🔍 Verificando métricas de trading del GridBot")
    print("=" * 60)
    
    # Verificar salud de Prometheus
    print("\n📋 Verificando: Salud de Prometheus")
    print("-" * 40)
    if not check_prometheus_health():
        print("❌ Prometheus no está disponible")
        return
    
    # Verificar métricas disponibles
    print("\n📋 Verificando: Métricas del GridBot")
    print("-" * 40)
    available, missing = check_gridbot_metrics()
    
    print(f"\n📊 Resumen de métricas:")
    print(f"   ✅ Disponibles: {len(available)}")
    print(f"   ❌ Faltantes: {len(missing)}")
    
    if missing:
        print(f"\n⚠️  Métricas faltantes: {', '.join(missing)}")
    
    # Verificar conexión con Binance
    print("\n📋 Verificando: Conexión con Binance")
    print("-" * 40)
    binance_connected = check_binance_connection()
    
    # Verificar rendimiento de la API
    print("\n📋 Verificando: Rendimiento de la API")
    print("-" * 40)
    api_performance = check_api_performance()
    
    # Verificar dashboard de Grafana
    print("\n📋 Verificando: Dashboard de Trading")
    print("-" * 40)
    dashboard_available = check_grafana_dashboard()
    
    print("\n" + "=" * 60)
    print("📊 RESUMEN DE VERIFICACIÓN")
    print("=" * 60)
    
    checks = [
        ("Prometheus", True),
        ("Métricas GridBot", len(available) > 0),
        ("Conexión Binance", binance_connected),
        ("Rendimiento API", api_performance),
        ("Dashboard Trading", dashboard_available)
    ]
    
    all_passed = True
    for check_name, result in checks:
        status = "✅ PASÓ" if result else "❌ FALLÓ"
        print(f"{status} - {check_name}")
        if not result:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ¡TODAS LAS VERIFICACIONES PASARON!")
        print("✅ El sistema de métricas de trading está funcionando correctamente")
        print(f"🌐 Accede al dashboard en: {GRAFANA_URL}")
        print("👤 Usuario: admin / Contraseña: gridbot123")
    else:
        print("⚠️  ALGUNAS VERIFICACIONES FALLARON")
        print("🔧 Revisa los logs para más detalles")
    
    print("=" * 60)

if __name__ == "__main__":
    main() 