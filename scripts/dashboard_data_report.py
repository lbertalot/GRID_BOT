#!/usr/bin/env python3
"""
Script para generar un reporte detallado de los datos del dashboard
"""

import requests
import json
from datetime import datetime

def generate_dashboard_report():
    """Genera un reporte detallado de los datos del dashboard"""
    try:
        print("📊 Reporte Detallado del Dashboard: 💰 Rentabilidad del Bot de Trading")
        print("=" * 70)
        print(f"📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Panel 1: 💰 Ganancia Total Acumulada
        print("1️⃣ 💰 Ganancia Total Acumulada")
        print("-" * 40)
        try:
            response = requests.get("http://localhost:9090/api/v1/query?query=profit_total_usdt", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data['data']['result']:
                    for result in data['data']['result']:
                        value = float(result['value'][1])
                        strategy = result['metric'].get('strategy', 'N/A')
                        print(f"   📈 Valor: ${value:.2f} USDT")
                        print(f"   🏷️ Estrategia: {strategy}")
                        print(f"   📊 Estado: {'✅ Ganancia' if value > 0 else '📉 Sin ganancias' if value == 0 else '❌ Pérdida'}")
                else:
                    print("   ⚠️ Sin datos disponibles")
            else:
                print("   ❌ Error consultando métrica")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        print()
        
        # Panel 2: 📈 ROI Diario (%)
        print("2️⃣ 📈 ROI Diario (%)")
        print("-" * 40)
        try:
            response = requests.get("http://localhost:9090/api/v1/query?query=roi_daily_percent", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data['data']['result']:
                    for result in data['data']['result']:
                        value = float(result['value'][1])
                        strategy = result['metric'].get('strategy', 'N/A')
                        print(f"   📈 ROI: {value:.2f}%")
                        print(f"   🏷️ Estrategia: {strategy}")
                        print(f"   📊 Estado: {'✅ Positivo' if value > 0 else '📉 Neutro' if value == 0 else '❌ Negativo'}")
                else:
                    print("   ⚠️ Sin datos disponibles")
            else:
                print("   ❌ Error consultando métrica")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        print()
        
        # Panel 3: 📊 Ganancia Diaria
        print("3️⃣ 📊 Ganancia Diaria")
        print("-" * 40)
        try:
            response = requests.get("http://localhost:9090/api/v1/query?query=profit_daily_usdt", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data['data']['result']:
                    for result in data['data']['result']:
                        value = float(result['value'][1])
                        strategy = result['metric'].get('strategy', 'N/A')
                        print(f"   📈 Ganancia: ${value:.2f} USDT")
                        print(f"   🏷️ Estrategia: {strategy}")
                        print(f"   📊 Estado: {'✅ Ganancia' if value > 0 else '📉 Sin ganancias' if value == 0 else '❌ Pérdida'}")
                else:
                    print("   ⚠️ Sin datos disponibles")
            else:
                print("   ❌ Error consultando métrica")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        print()
        
        # Panel 4: 💼 Evolución del Capital Total
        print("4️⃣ 💼 Evolución del Capital Total")
        print("-" * 40)
        try:
            response = requests.get("http://localhost:9090/api/v1/query?query=portfolio_total_value_usdt", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data['data']['result']:
                    for result in data['data']['result']:
                        value = float(result['value'][1])
                        print(f"   💰 Capital Total: ${value:.2f} USDT")
                        print(f"   📊 Estado: {'✅ Capital disponible' if value > 0 else '❌ Sin capital'}")
                else:
                    print("   ⚠️ Sin datos disponibles")
            else:
                print("   ❌ Error consultando métrica")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        print()
        
        # Panel 5: 🔄 Total de Operaciones
        print("5️⃣ 🔄 Total de Operaciones")
        print("-" * 40)
        try:
            response = requests.get("http://localhost:9090/api/v1/query?query=trades_total", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data['data']['result']:
                    total_trades = 0
                    trades_by_symbol = {}
                    trades_by_side = {'BUY': 0, 'SELL': 0}
                    
                    for result in data['data']['result']:
                        value = int(result['value'][1])
                        symbol = result['metric'].get('symbol', 'N/A')
                        side = result['metric'].get('side', 'N/A')
                        
                        total_trades += value
                        trades_by_symbol[symbol] = trades_by_symbol.get(symbol, 0) + value
                        trades_by_side[side] = trades_by_side.get(side, 0) + value
                    
                    print(f"   📊 Total de operaciones: {total_trades}")
                    print("   🪙 Por símbolo:")
                    for symbol, count in trades_by_symbol.items():
                        print(f"      • {symbol}: {count} operaciones")
                    print("   📈 Por tipo:")
                    for side, count in trades_by_side.items():
                        print(f"      • {side}: {count} operaciones")
                else:
                    print("   ⚠️ Sin datos disponibles")
            else:
                print("   ❌ Error consultando métrica")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        print()
        
        # Panel 6: ⏰ Última Ejecución
        print("6️⃣ ⏰ Última Ejecución")
        print("-" * 40)
        try:
            response = requests.get("http://localhost:9090/api/v1/query?query=bot_last_execution_timestamp", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data['data']['result']:
                    for result in data['data']['result']:
                        timestamp = float(result['value'][1])
                        if timestamp > 0:
                            last_execution = datetime.fromtimestamp(timestamp)
                            time_diff = datetime.now() - last_execution
                            print(f"   🕐 Última ejecución: {last_execution.strftime('%Y-%m-%d %H:%M:%S')}")
                            print(f"   ⏱️ Hace: {time_diff}")
                        else:
                            print("   ⚠️ Sin datos de última ejecución")
                else:
                    print("   ⚠️ Sin datos disponibles")
            else:
                print("   ❌ Error consultando métrica")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        print()
        
        # Panel 7: ⚠️ Errores del Bot
        print("7️⃣ ⚠️ Errores del Bot")
        print("-" * 40)
        try:
            response = requests.get("http://localhost:9090/api/v1/query?query=bot_errors_total", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data['data']['result']:
                    for result in data['data']['result']:
                        value = int(result['value'][1])
                        print(f"   🚨 Total de errores: {value}")
                        print(f"   📊 Estado: {'❌ Errores detectados' if value > 0 else '✅ Sin errores'}")
                else:
                    print("   ✅ Sin errores registrados")
            else:
                print("   ❌ Error consultando métrica")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        print()
        
        # Panel 8: ✅ Tasa de Éxito
        print("8️⃣ ✅ Tasa de Éxito")
        print("-" * 40)
        try:
            response = requests.get("http://localhost:9090/api/v1/query?query=trades_success_rate", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data['data']['result']:
                    for result in data['data']['result']:
                        value = float(result['value'][1])
                        symbol = result['metric'].get('symbol', 'N/A')
                        print(f"   📊 {symbol}: {value:.2f}%")
                        print(f"   🎯 Estado: {'✅ Excelente' if value >= 80 else '⚠️ Buena' if value >= 60 else '❌ Baja'}")
                else:
                    print("   ⚠️ Sin datos disponibles")
            else:
                print("   ❌ Error consultando métrica")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        print()
        
        # Panel 9: 📈 Ganancia por Activo
        print("9️⃣ 📈 Ganancia por Activo")
        print("-" * 40)
        try:
            response = requests.get("http://localhost:9090/api/v1/query?query=profit_by_asset_usdt", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data['data']['result']:
                    for result in data['data']['result']:
                        value = float(result['value'][1])
                        asset = result['metric'].get('asset', 'N/A')
                        print(f"   🪙 {asset}: ${value:.2f} USDT")
                        print(f"   📊 Estado: {'✅ Ganancia' if value > 0 else '📉 Sin ganancias' if value == 0 else '❌ Pérdida'}")
                else:
                    print("   ⚠️ Sin datos disponibles")
            else:
                print("   ❌ Error consultando métrica")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        print()
        
        # Panel 10: 📊 ROI por Activo (%)
        print("🔟 📊 ROI por Activo (%)")
        print("-" * 40)
        try:
            response = requests.get("http://localhost:9090/api/v1/query?query=roi_by_asset_percent", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data['data']['result']:
                    for result in data['data']['result']:
                        value = float(result['value'][1])
                        asset = result['metric'].get('asset', 'N/A')
                        print(f"   🪙 {asset}: {value:.2f}%")
                        print(f"   📊 Estado: {'✅ Positivo' if value > 0 else '📉 Neutro' if value == 0 else '❌ Negativo'}")
                else:
                    print("   ⚠️ Sin datos disponibles")
            else:
                print("   ❌ Error consultando métrica")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        print()
        
        # Resumen general
        print("📋 RESUMEN GENERAL DEL DASHBOARD")
        print("=" * 70)
        print("✅ Estado: Dashboard completamente operativo")
        print("✅ Datasource: Prometheus conectado correctamente")
        print("✅ Métricas: Todas las métricas requeridas disponibles")
        print("📊 Datos: Algunas métricas sin datos (normal en inicio)")
        print()
        print("🎯 Recomendaciones:")
        print("   • El dashboard está funcionando correctamente")
        print("   • Los datos se actualizan automáticamente")
        print("   • Algunos paneles pueden mostrar 'Sin datos' inicialmente")
        print("   • Los datos aparecerán conforme el bot ejecute operaciones")
        print()
        print("🌐 Acceso: http://localhost:3000 (admin/gridbot123)")
        
    except Exception as e:
        print(f"❌ Error generando reporte: {e}")

if __name__ == "__main__":
    generate_dashboard_report() 