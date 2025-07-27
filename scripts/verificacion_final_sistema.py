#!/usr/bin/env python3
"""
Script de Verificación Final del Sistema - Grid Trading Bot
Verifica que todos los componentes estén funcionando de manera óptima
"""

import asyncio
import sys
import os
import time
from datetime import datetime
import json

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.performance_analyzer import performance_analyzer
from app.services.risk_manager import risk_manager
from app.services.config_manager import config_manager
from app.services.auto_rebalancer import auto_rebalancer

class SistemaVerificador:
    def __init__(self):
        self.resultados = {}
        self.tiempo_inicio = time.time()
        
    async def verificar_performance_analyzer(self):
        """Verifica el PerformanceAnalyzer"""
        print("📊 Verificando PerformanceAnalyzer...")
        try:
            # Verificar métricas básicas
            metrics = await performance_analyzer.calculate_comprehensive_metrics(30)
            
            self.resultados['performance_analyzer'] = {
                'status': 'success',
                'total_return': metrics.total_return,
                'sharpe_ratio': metrics.sharpe_ratio,
                'max_drawdown': metrics.max_drawdown,
                'win_rate': metrics.win_rate
            }
            print("   ✅ PerformanceAnalyzer funcionando correctamente")
            return True
        except Exception as e:
            self.resultados['performance_analyzer'] = {
                'status': 'error',
                'error': str(e)
            }
            print(f"   ❌ Error en PerformanceAnalyzer: {e}")
            return False
    
    async def verificar_risk_manager(self):
        """Verifica el RiskManager"""
        print("🛡️ Verificando RiskManager...")
        try:
            # Verificar estado de riesgo
            risk_status = await risk_manager.get_risk_status()
            
            self.resultados['risk_manager'] = {
                'status': 'success',
                'risk_level': risk_status.get('risk_level', 'unknown'),
                'trading_enabled': risk_status.get('trading_enabled', False),
                'emergency_stop': risk_status.get('emergency_stop', False)
            }
            print("   ✅ RiskManager funcionando correctamente")
            return True
        except Exception as e:
            self.resultados['risk_manager'] = {
                'status': 'error',
                'error': str(e)
            }
            print(f"   ❌ Error en RiskManager: {e}")
            return False
    
    async def verificar_config_manager(self):
        """Verifica el ConfigManager"""
        print("⚙️ Verificando ConfigManager...")
        try:
            # Verificar optimización básica
            from app.services.config_manager import OptimizationRequest, OptimizationStrategy
            
            request = OptimizationRequest(
                symbol="BTC",
                strategy=OptimizationStrategy.GRID_OPTIMIZATION,
                investment_amount=1000.0,
                risk_tolerance=0.5
            )
            
            config = await config_manager.optimize_parameters(request)
            
            self.resultados['config_manager'] = {
                'status': 'success',
                'optimization_score': config.confidence_score,
                'grid_levels': config.grids,
                'quantity': config.quantity
            }
            print("   ✅ ConfigManager funcionando correctamente")
            return True
        except Exception as e:
            self.resultados['config_manager'] = {
                'status': 'error',
                'error': str(e)
            }
            print(f"   ❌ Error en ConfigManager: {e}")
            return False
    
    async def verificar_auto_rebalancer(self):
        """Verifica el AutoRebalancer"""
        print("🔄 Verificando AutoRebalancer...")
        try:
            # Verificar estado del rebalanceo
            status = await auto_rebalancer.get_rebalance_status()
            
            self.resultados['auto_rebalancer'] = {
                'status': 'success',
                'last_rebalance': status.get('last_rebalance', 'unknown'),
                'rebalance_count': status.get('rebalance_count', 0),
                'is_active': status.get('is_active', False)
            }
            print("   ✅ AutoRebalancer funcionando correctamente")
            return True
        except Exception as e:
            self.resultados['auto_rebalancer'] = {
                'status': 'error',
                'error': str(e)
            }
            print(f"   ❌ Error en AutoRebalancer: {e}")
            return False
    
    async def verificar_metricas_rendimiento(self):
        """Verifica métricas de rendimiento del sistema"""
        print("📈 Verificando métricas de rendimiento...")
        try:
            # Obtener métricas del portfolio
            portfolio_value = await performance_analyzer.get_current_portfolio_value()
            allocation = await performance_analyzer.get_portfolio_allocation()
            
            self.resultados['metricas_rendimiento'] = {
                'status': 'success',
                'portfolio_value': portfolio_value,
                'total_assets': len(allocation),
                'top_assets': list(allocation.items())[:5] if allocation else []
            }
            print("   ✅ Métricas de rendimiento obtenidas correctamente")
            return True
        except Exception as e:
            self.resultados['metricas_rendimiento'] = {
                'status': 'error',
                'error': str(e)
            }
            print(f"   ❌ Error obteniendo métricas: {e}")
            return False
    
    async def verificar_optimizacion_configuracion(self):
        """Verifica el sistema de optimización de configuración"""
        print("🎯 Verificando optimización de configuración...")
        try:
            # Probar optimización con diferentes estrategias
            from app.services.config_manager import OptimizationRequest, OptimizationStrategy
            
            estrategias = [
                OptimizationStrategy.GRID_OPTIMIZATION,
                OptimizationStrategy.VOLATILITY_BASED,
                OptimizationStrategy.VOLUME_BASED
            ]
            mejores_configs = []
            
            for estrategia in estrategias:
                request = OptimizationRequest(
                    symbol="BTC",
                    strategy=estrategia,
                    investment_amount=1000.0,
                    risk_tolerance=0.5
                )
                
                config = await config_manager.optimize_parameters(request)
                mejores_configs.append({
                    'estrategia': estrategia.value,
                    'score': config.confidence_score,
                    'roi': config.backtest_results.get('roi', 0) if config.backtest_results else 0
                })
            
            # Encontrar la mejor estrategia
            mejor_config = max(mejores_configs, key=lambda x: x['score'])
            
            self.resultados['optimizacion_configuracion'] = {
                'status': 'success',
                'mejor_estrategia': mejor_config['estrategia'],
                'mejor_score': mejor_config['score'],
                'estrategias_probadas': len(estrategias)
            }
            print(f"   ✅ Optimización funcionando - Mejor estrategia: {mejor_config['estrategia']}")
            return True
        except Exception as e:
            self.resultados['optimizacion_configuracion'] = {
                'status': 'error',
                'error': str(e)
            }
            print(f"   ❌ Error en optimización: {e}")
            return False
    
    async def generar_reporte_final(self):
        """Genera reporte final de verificación"""
        tiempo_total = time.time() - self.tiempo_inicio
        
        # Calcular estadísticas
        total_checks = len(self.resultados)
        checks_exitosos = sum(1 for r in self.resultados.values() if r['status'] == 'success')
        tasa_exito = (checks_exitosos / total_checks * 100) if total_checks > 0 else 0
        
        reporte = {
            'fecha_verificacion': datetime.now().isoformat(),
            'tiempo_total_segundos': round(tiempo_total, 2),
            'total_checks': total_checks,
            'checks_exitosos': checks_exitosos,
            'tasa_exito_porcentaje': round(tasa_exito, 2),
            'estado_general': 'EXCELENTE' if tasa_exito >= 90 else 'BUENO' if tasa_exito >= 70 else 'REQUIERE_ATENCION',
            'resultados_detallados': self.resultados,
            'recomendaciones': self.generar_recomendaciones()
        }
        
        # Guardar reporte
        nombre_archivo = f"verificacion_final_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(nombre_archivo, 'w') as f:
            json.dump(reporte, f, indent=2, ensure_ascii=False)
        
        return reporte
    
    def generar_recomendaciones(self):
        """Genera recomendaciones basadas en los resultados"""
        recomendaciones = []
        
        if self.resultados.get('performance_analyzer', {}).get('status') == 'success':
            metrics = self.resultados['performance_analyzer']
            if metrics.get('total_return', 0) < 0:
                recomendaciones.append("📉 Considerar optimizar parámetros de trading para mejorar ROI")
            if metrics.get('max_drawdown', 0) > 10:
                recomendaciones.append("⚠️ Revisar límites de riesgo para reducir drawdown")
        
        if self.resultados.get('risk_manager', {}).get('status') == 'success':
            risk = self.resultados['risk_manager']
            if not risk.get('trading_enabled', False):
                recomendaciones.append("🛑 Verificar por qué el trading está deshabilitado")
        
        if len(recomendaciones) == 0:
            recomendaciones.append("🎉 Sistema funcionando de manera óptima - continuar monitoreo")
        
        return recomendaciones

async def main():
    """Función principal de verificación"""
    print("🚀 INICIANDO VERIFICACIÓN FINAL DEL SISTEMA")
    print("=" * 60)
    
    verificador = SistemaVerificador()
    
    # Ejecutar verificaciones
    await verificador.verificar_performance_analyzer()
    await verificador.verificar_risk_manager()
    await verificador.verificar_config_manager()
    await verificador.verificar_auto_rebalancer()
    await verificador.verificar_metricas_rendimiento()
    await verificador.verificar_optimizacion_configuracion()
    
    # Generar reporte final
    print("\n📋 Generando reporte final...")
    reporte = await verificador.generar_reporte_final()
    
    # Mostrar resumen
    print("\n" + "=" * 60)
    print("📊 RESUMEN DE VERIFICACIÓN FINAL")
    print("=" * 60)
    print(f"✅ Checks exitosos: {reporte['checks_exitosos']}/{reporte['total_checks']}")
    print(f"📈 Tasa de éxito: {reporte['tasa_exito_porcentaje']}%")
    print(f"⏱️ Tiempo total: {reporte['tiempo_total_segundos']} segundos")
    print(f"🏆 Estado general: {reporte['estado_general']}")
    
    print("\n💡 Recomendaciones:")
    for rec in reporte['recomendaciones']:
        print(f"   {rec}")
    
    print(f"\n📄 Reporte completo guardado en: {reporte.get('archivo', 'N/A')}")
    
    if reporte['tasa_exito_porcentaje'] >= 90:
        print("\n🎉 ¡SISTEMA FUNCIONANDO DE MANERA ÓPTIMA!")
    else:
        print("\n⚠️ Sistema requiere atención en algunos componentes")

if __name__ == "__main__":
    asyncio.run(main()) 