#!/usr/bin/env python3
"""
Script para verificar la compatibilidad del dashboard con las métricas disponibles
"""

import requests
import json
import re

def verify_dashboard_metrics():
    """Verifica la compatibilidad del dashboard con las métricas disponibles"""
    try:
        print("🔍 Verificando Compatibilidad del Dashboard con Métricas")
        print("=" * 60)
        
        # Métricas requeridas por el dashboard
        dashboard_metrics = [
            "profit_total_usdt",
            "roi_daily_percent", 
            "profit_daily_usdt",
            "portfolio_total_value_usdt",
            "trades_executed_total",
            "bot_last_execution_timestamp",
            "bot_errors_total",
            "trades_success_rate",
            "profit_by_asset_usdt",
            "roi_by_asset_percent"
        ]
        
        # 1. Obtener todas las métricas disponibles
        print("1️⃣ Obteniendo métricas disponibles en Prometheus...")
        try:
            response = requests.get("http://localhost:9090/api/v1/label/__name__/values", timeout=10)
            if response.status_code == 200:
                available_metrics = response.json()['data']
                print(f"   📊 Total de métricas disponibles: {len(available_metrics)}")
            else:
                print(f"   ❌ Error obteniendo métricas: {response.status_code}")
                return
        except Exception as e:
            print(f"   ❌ Error conectando a Prometheus: {e}")
            return
        
        # 2. Verificar métricas del dashboard
        print("2️⃣ Verificando métricas requeridas por el dashboard...")
        dashboard_status = {}
        
        for metric in dashboard_metrics:
            try:
                response = requests.get(f"http://localhost:9090/api/v1/query?query={metric}", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    if data['data']['result']:
                        dashboard_status[metric] = {
                            'available': True,
                            'has_data': True,
                            'value': data['data']['result'][0]['value'][1] if data['data']['result'] else 'N/A'
                        }
                        print(f"   ✅ {metric}: Disponible con datos")
                    else:
                        dashboard_status[metric] = {
                            'available': True,
                            'has_data': False,
                            'value': 'Sin datos'
                        }
                        print(f"   ⚠️ {metric}: Disponible pero sin datos")
                else:
                    dashboard_status[metric] = {
                        'available': False,
                        'has_data': False,
                        'value': 'Error'
                    }
                    print(f"   ❌ {metric}: No disponible")
            except Exception as e:
                dashboard_status[metric] = {
                    'available': False,
                    'has_data': False,
                    'value': f'Error: {e}'
                }
                print(f"   ❌ {metric}: Error - {e}")
        
        # 3. Verificar métricas específicas con valores
        print("3️⃣ Verificando valores de métricas principales...")
        key_metrics = [
            "profit_total_usdt",
            "portfolio_total_value_usdt", 
            "trades_total",
            "trading_active"
        ]
        
        for metric in key_metrics:
            try:
                response = requests.get(f"http://localhost:9090/api/v1/query?query={metric}", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    if data['data']['result']:
                        for result in data['data']['result']:
                            value = result['value'][1]
                            labels = result['metric']
                            print(f"   📈 {metric} = {value}")
                            if 'strategy' in labels:
                                print(f"      🏷️ Strategy: {labels['strategy']}")
                            if 'symbol' in labels:
                                print(f"      🏷️ Symbol: {labels['symbol']}")
                            if 'side' in labels:
                                print(f"      🏷️ Side: {labels['side']}")
                    else:
                        print(f"   ⚠️ {metric}: Sin datos")
                else:
                    print(f"   ❌ {metric}: Error consultando")
            except Exception as e:
                print(f"   ❌ {metric}: Error - {e}")
        
        # 4. Verificar métricas por activo
        print("4️⃣ Verificando métricas por activo...")
        asset_metrics = [
            "profit_by_asset_usdt",
            "roi_by_asset_percent"
        ]
        
        for metric in asset_metrics:
            try:
                response = requests.get(f"http://localhost:9090/api/v1/query?query={metric}", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    if data['data']['result']:
                        print(f"   📊 {metric}:")
                        for result in data['data']['result']:
                            value = result['value'][1]
                            asset = result['metric'].get('asset', 'unknown')
                            print(f"      🪙 {asset}: {value}")
                    else:
                        print(f"   ⚠️ {metric}: Sin datos")
                else:
                    print(f"   ❌ {metric}: Error consultando")
            except Exception as e:
                print(f"   ❌ {metric}: Error - {e}")
        
        # 5. Resumen de compatibilidad
        print("5️⃣ Resumen de compatibilidad del dashboard...")
        available_count = sum(1 for status in dashboard_status.values() if status['available'])
        with_data_count = sum(1 for status in dashboard_status.values() if status['has_data'])
        
        print(f"   📊 Métricas requeridas: {len(dashboard_metrics)}")
        print(f"   ✅ Métricas disponibles: {available_count}")
        print(f"   📈 Métricas con datos: {with_data_count}")
        print(f"   📊 Compatibilidad: {(available_count/len(dashboard_metrics)*100):.1f}%")
        
        # 6. Detalles de métricas faltantes
        missing_metrics = [metric for metric in dashboard_metrics if not dashboard_status[metric]['available']]
        if missing_metrics:
            print("   ❌ Métricas faltantes:")
            for metric in missing_metrics:
                print(f"      • {metric}")
        
        metrics_without_data = [metric for metric in dashboard_metrics if dashboard_status[metric]['available'] and not dashboard_status[metric]['has_data']]
        if metrics_without_data:
            print("   ⚠️ Métricas sin datos:")
            for metric in metrics_without_data:
                print(f"      • {metric}")
        
        # 7. Recomendaciones
        print("6️⃣ Recomendaciones:")
        if available_count == len(dashboard_metrics):
            print("   ✅ Dashboard completamente compatible")
        elif available_count >= len(dashboard_metrics) * 0.8:
            print("   ⚠️ Dashboard mayormente compatible (algunos paneles pueden no mostrar datos)")
        else:
            print("   ❌ Dashboard con problemas de compatibilidad")
        
        print()
        print("💡 Para mejorar la compatibilidad:")
        print("   1. Verificar que todas las métricas estén siendo generadas")
        print("   2. Revisar el sistema de métricas centralizado")
        print("   3. Actualizar el dashboard si es necesario")
        print()
        print("🎯 Estado del Dashboard:")
        if available_count == len(dashboard_metrics):
            print("   ✅ COMPLETAMENTE OPERATIVO")
        elif available_count >= len(dashboard_metrics) * 0.8:
            print("   ⚠️ PARCIALMENTE OPERATIVO")
        else:
            print("   ❌ CON PROBLEMAS")
        
    except Exception as e:
        print(f"❌ Error en verificación: {e}")

if __name__ == "__main__":
    verify_dashboard_metrics() 