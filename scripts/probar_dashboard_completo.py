#!/usr/bin/env python3
"""
Script para probar el dashboard completo con métricas avanzadas
Verifica que todos los componentes del Sprint 1.2 funcionen correctamente
"""

import asyncio
import json
import logging
import sys
import os
import requests
from datetime import datetime

# Agregar el directorio raíz al path para importar módulos
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.performance_analyzer import performance_analyzer

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuración
BASE_URL = "http://localhost:8001"
API_BASE = f"{BASE_URL}/api/v1/metrics"


async def test_performance_analyzer():
    """Prueba del PerformanceAnalyzer"""
    
    print("📊 Probando PerformanceAnalyzer...")
    
    try:
        # Calcular métricas comprehensivas
        metrics = await performance_analyzer.calculate_comprehensive_metrics(days=30)
        
        # Verificar que las métricas son válidas
        assert isinstance(metrics.total_return, (int, float)), "total_return debe ser numérico"
        assert isinstance(metrics.sharpe_ratio, (int, float)), "sharpe_ratio debe ser numérico"
        assert isinstance(metrics.max_drawdown, (int, float)), "max_drawdown debe ser numérico"
        assert isinstance(metrics.volatility, (int, float)), "volatility debe ser numérico"
        assert isinstance(metrics.win_rate, (int, float)), "win_rate debe ser numérico"
        assert isinstance(metrics.profit_factor, (int, float)), "profit_factor debe ser numérico"
        assert isinstance(metrics.total_trades, int), "total_trades debe ser entero"
        assert isinstance(metrics.winning_trades, int), "winning_trades debe ser entero"
        assert isinstance(metrics.losing_trades, int), "losing_trades debe ser entero"
        
        print("   ✅ PerformanceAnalyzer funcionando correctamente")
        return True
        
    except Exception as e:
        print(f"   ❌ Error en PerformanceAnalyzer: {e}")
        return False


def test_api_endpoints():
    """Prueba de endpoints de API"""
    
    print("\n🌐 Probando endpoints de API...")
    
    endpoints_to_test = [
        ("/performance?days=30", "GET"),
        ("/allocation", "GET"),
        ("/portfolio/value", "GET"),
        ("/risk?days=30", "GET"),
        ("/trading/stats?days=30", "GET"),
        ("/health", "GET")
    ]
    
    success_count = 0
    
    for endpoint, method in endpoints_to_test:
        try:
            url = f"{API_BASE}{endpoint}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                print(f"   ✅ {method} {endpoint} - OK")
                success_count += 1
            else:
                print(f"   ❌ {method} {endpoint} - Status: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            print(f"   ❌ {method} {endpoint} - Error: {e}")
    
    print(f"   📊 Endpoints exitosos: {success_count}/{len(endpoints_to_test)}")
    return success_count == len(endpoints_to_test)


def test_dashboard_page():
    """Prueba de la página del dashboard"""
    
    print("\n📱 Probando página del dashboard...")
    
    try:
        # Probar página principal
        response = requests.get(f"{BASE_URL}/", timeout=10)
        if response.status_code == 200:
            print("   ✅ Página principal - OK")
        else:
            print(f"   ❌ Página principal - Status: {response.status_code}")
            return False
        
        # Probar página del dashboard
        response = requests.get(f"{BASE_URL}/dashboard", timeout=10)
        if response.status_code == 200:
            print("   ✅ Página del dashboard - OK")
            return True
        else:
            print(f"   ❌ Página del dashboard - Status: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Error accediendo al dashboard: {e}")
        return False


async def test_portfolio_analysis():
    """Prueba de análisis del portafolio"""
    
    print("\n💼 Probando análisis del portafolio...")
    
    try:
        # Obtener valor actual del portafolio
        current_value = await performance_analyzer.get_current_portfolio_value()
        assert current_value > 0, "El valor del portafolio debe ser positivo"
        
        # Obtener distribución del portafolio
        allocation = await performance_analyzer.get_portfolio_allocation()
        assert "error" not in allocation, f"Error en distribución: {allocation.get('error')}"
        assert allocation['total_value'] > 0, "El valor total debe ser positivo"
        assert allocation['assets_count'] > 0, "Debe haber al menos un activo"
        
        print(f"   ✅ Valor del portafolio: ${current_value:.2f}")
        print(f"   ✅ Total de activos: {allocation['assets_count']}")
        print(f"   ✅ Valor total: ${allocation['total_value']:.2f}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error en análisis del portafolio: {e}")
        return False


async def test_asset_performance():
    """Prueba de rendimiento de activos individuales"""
    
    print("\n📈 Probando rendimiento de activos...")
    
    assets_to_test = ['BNBUSDT', 'ANIMEUSDT', 'GPSUSDT']
    success_count = 0
    
    for asset in assets_to_test:
        try:
            performance = await performance_analyzer.get_asset_performance(asset, days=30)
            
            if "error" not in performance:
                print(f"   ✅ {asset}: {performance['price_change_percent']:.2f}%")
                success_count += 1
            else:
                print(f"   ⚠️  {asset}: {performance['error']}")
                
        except Exception as e:
            print(f"   ❌ Error analizando {asset}: {e}")
    
    print(f"   📊 Activos analizados exitosamente: {success_count}/{len(assets_to_test)}")
    return success_count > 0


def generate_sprint_report():
    """Genera reporte del Sprint 1.2"""
    
    print("\n📄 Generando reporte del Sprint 1.2...")
    
    report = {
        "sprint": "1.2 - Dashboard de Rendimiento Avanzado",
        "timestamp": datetime.now().isoformat(),
        "status": "COMPLETADO",
        "funcionalidades_implementadas": [
            "PerformanceAnalyzer con métricas avanzadas",
            "Cálculo de Sharpe Ratio, drawdown, volatilidad",
            "Análisis de distribución del portafolio",
            "Rendimiento por activo individual",
            "API endpoints para métricas avanzadas",
            "Dashboard web moderno con gráficos",
            "Endpoints de riesgo y estadísticas de trading",
            "Visualización en tiempo real"
        ],
        "endpoints_disponibles": [
            "/api/v1/metrics/performance",
            "/api/v1/metrics/allocation",
            "/api/v1/metrics/portfolio/value",
            "/api/v1/metrics/risk",
            "/api/v1/metrics/trading/stats",
            "/api/v1/metrics/health",
            "/dashboard"
        ],
        "tecnologias_utilizadas": [
            "FastAPI para API REST",
            "Chart.js para visualizaciones",
            "Axios para llamadas HTTP",
            "Pandas y NumPy para análisis",
            "HTML5/CSS3 para interfaz moderna"
        ],
        "metricas_calculadas": [
            "Retorno total",
            "Sharpe Ratio",
            "Máximo drawdown",
            "Volatilidad anualizada",
            "Win rate",
            "Profit factor",
            "Estadísticas de trading",
            "Distribución del portafolio"
        ]
    }
    
    report_filename = f"sprint_1_2_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_filename, 'w') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"   📄 Reporte guardado en: {report_filename}")
    return report


async def main():
    """Función principal"""
    
    print("🚀 Iniciando pruebas del Sprint 1.2: Dashboard de Rendimiento Avanzado")
    print("=" * 70)
    
    # Ejecutar todas las pruebas
    tests = [
        ("PerformanceAnalyzer", test_performance_analyzer()),
        ("API Endpoints", test_api_endpoints()),
        ("Dashboard Page", test_dashboard_page()),
        ("Portfolio Analysis", test_portfolio_analysis()),
        ("Asset Performance", test_asset_performance())
    ]
    
    results = []
    
    for test_name, test_coro in tests:
        if asyncio.iscoroutine(test_coro):
            result = await test_coro
        else:
            result = test_coro
        results.append((test_name, result))
    
    # Generar reporte
    report = generate_sprint_report()
    
    # Resumen final
    print("\n" + "=" * 70)
    print("📋 RESUMEN DEL SPRINT 1.2")
    print("=" * 70)
    
    passed_tests = sum(1 for _, result in results if result)
    total_tests = len(results)
    
    for test_name, result in results:
        status = "✅ PASÓ" if result else "❌ FALLÓ"
        print(f"   {status} {test_name}")
    
    print(f"\n📊 Resultado: {passed_tests}/{total_tests} pruebas exitosas")
    
    if passed_tests == total_tests:
        print("\n🎉 ¡SPRINT 1.2 COMPLETADO EXITOSAMENTE!")
        print("\n📋 Funcionalidades implementadas:")
        for func in report["funcionalidades_implementadas"]:
            print(f"   ✅ {func}")
        
        print(f"\n🌐 Dashboard disponible en: {BASE_URL}/dashboard")
        print(f"📊 API disponible en: {API_BASE}")
        
    else:
        print(f"\n⚠️  Sprint completado con {total_tests - passed_tests} fallos")
    
    return passed_tests == total_tests


if __name__ == "__main__":
    # Ejecutar el script
    result = asyncio.run(main())
    sys.exit(0 if result else 1) 