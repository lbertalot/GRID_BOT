#!/usr/bin/env python3
"""
Script de Testing para Fase 2: Múltiples Estrategias de Trading
"""

import asyncio
import sys
import os
from datetime import datetime
import json

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.strategies.base import StrategyType
from app.services.strategy_factory import strategy_factory
from app.strategies.dca_strategy import DCAConfig, DCAStrategy
from app.strategies.scalping_strategy import ScalpingConfig, ScalpingStrategy

class EstrategiasTester:
    def __init__(self):
        self.test_results = {}
        self.start_time = datetime.now()
    
    async def test_framework_base(self):
        """Prueba el framework base de estrategias"""
        print("🔧 1. Probando Framework Base de Estrategias...")
        
        try:
            # Verificar que el factory está inicializado
            if not strategy_factory:
                print("   ❌ Strategy Factory no está inicializado")
                return False
            
            # Verificar estrategias disponibles
            available_strategies = strategy_factory.get_available_strategies()
            print(f"   ✅ Estrategias disponibles: {len(available_strategies)}")
            
            for strategy in available_strategies:
                print(f"      - {strategy['name']}: {strategy['description']}")
            
            self.test_results['framework_base'] = {
                'status': 'success',
                'available_strategies': len(available_strategies),
                'strategies': [s['name'] for s in available_strategies]
            }
            return True
            
        except Exception as e:
            print(f"   ❌ Error en framework base: {e}")
            self.test_results['framework_base'] = {
                'status': 'error',
                'error': str(e)
            }
            return False
    
    async def test_dca_strategy(self):
        """Prueba la estrategia DCA"""
        print("💰 2. Probando Estrategia DCA...")
        
        try:
            # Crear configuración DCA
            config = DCAConfig(
                symbol="BTCUSDT",
                strategy_type=StrategyType.DCA,
                investment_amount=50.0,
                risk_tolerance=0.5,
                frequency_hours=24,
                max_investments=5,
                price_threshold=50000.0
            )
            
            # Crear estrategia
            strategy = DCAStrategy(config)
            
            # Validar configuración
            is_valid = await strategy.validate_config()
            print(f"   ✅ Configuración válida: {is_valid}")
            
            # Obtener estado
            status = await strategy.get_status()
            print(f"   ✅ Estado obtenido: {status.get('strategy_type', 'unknown')}")
            
            # Probar obtención de posición
            position = await strategy.get_current_position()
            print(f"   ✅ Posición actual: {position.get('total', 0)}")
            
            self.test_results['dca_strategy'] = {
                'status': 'success',
                'config_valid': is_valid,
                'strategy_type': status['strategy_type'],
                'position': position
            }
            return True
            
        except Exception as e:
            print(f"   ❌ Error en DCA Strategy: {e}")
            self.test_results['dca_strategy'] = {
                'status': 'error',
                'error': str(e)
            }
            return False
    
    async def test_scalping_strategy(self):
        """Prueba la estrategia de Scalping"""
        print("📈 3. Probando Estrategia de Scalping...")
        
        try:
            # Crear configuración Scalping
            config = ScalpingConfig(
                symbol="ETHUSDT",
                strategy_type=StrategyType.SCALPING,
                investment_amount=100.0,
                risk_tolerance=0.7,
                entry_threshold=0.002,
                profit_target=0.005,
                stop_loss=0.003,
                max_position_size=100.0,
                max_hold_time_minutes=30
            )
            
            # Crear estrategia
            strategy = ScalpingStrategy(config)
            
            # Validar configuración
            is_valid = await strategy.validate_config()
            print(f"   ✅ Configuración válida: {is_valid}")
            
            # Obtener estado
            status = await strategy.get_status()
            print(f"   ✅ Estado obtenido: {status.get('strategy_type', 'unknown')}")
            
            # Probar obtención de posición
            position = await strategy.get_current_position()
            print(f"   ✅ Posición actual: {position.get('total', 0)}")
            
            self.test_results['scalping_strategy'] = {
                'status': 'success',
                'config_valid': is_valid,
                'strategy_type': status['strategy_type'],
                'position': position
            }
            return True
            
        except Exception as e:
            print(f"   ❌ Error en Scalping Strategy: {e}")
            self.test_results['scalping_strategy'] = {
                'status': 'error',
                'error': str(e)
            }
            return False
    
    async def test_strategy_factory(self):
        """Prueba el Strategy Factory"""
        print("🏭 4. Probando Strategy Factory...")
        
        try:
            # Crear estrategia DCA a través del factory
            dca_config = strategy_factory.create_config(
                StrategyType.DCA,
                symbol="BNBUSDT",
                investment_amount=25.0,
                risk_tolerance=0.6,
                frequency_hours=12
            )
            
            if dca_config:
                print("   ✅ Configuración DCA creada")
                
                # Crear estrategia
                dca_strategy = strategy_factory.create_strategy(StrategyType.DCA, dca_config)
                if dca_strategy:
                    print("   ✅ Estrategia DCA creada")
                    
                    # Iniciar estrategia
                    strategy_id = "test_dca_001"
                    success = await strategy_factory.start_strategy(strategy_id, dca_strategy)
                    print(f"   ✅ Estrategia iniciada: {success}")
                    
                    if success:
                        # Obtener estado
                        status = await strategy_factory.get_strategy_status(strategy_id)
                        print(f"   ✅ Estado obtenido: {status['strategy_type']}")
                        
                        # Detener estrategia
                        stop_success = await strategy_factory.stop_strategy(strategy_id)
                        print(f"   ✅ Estrategia detenida: {stop_success}")
                        
                        self.test_results['strategy_factory'] = {
                            'status': 'success',
                            'config_created': True,
                            'strategy_created': True,
                            'strategy_started': success,
                            'strategy_stopped': stop_success
                        }
                        return True
                    else:
                        print("   ❌ No se pudo iniciar la estrategia")
                else:
                    print("   ❌ No se pudo crear la estrategia")
            else:
                print("   ❌ No se pudo crear la configuración")
            
            self.test_results['strategy_factory'] = {
                'status': 'error',
                'error': 'Failed to create or start strategy'
            }
            return False
            
        except Exception as e:
            print(f"   ❌ Error en Strategy Factory: {e}")
            self.test_results['strategy_factory'] = {
                'status': 'error',
                'error': str(e)
            }
            return False
    
    async def test_multiple_strategies(self):
        """Prueba múltiples estrategias simultáneamente"""
        print("🔄 5. Probando Múltiples Estrategias...")
        
        try:
            strategies_created = []
            
            # Crear estrategia DCA
            dca_config = strategy_factory.create_config(
                StrategyType.DCA,
                symbol="ADAUSDT",
                investment_amount=30.0,
                risk_tolerance=0.5
            )
            
            if dca_config:
                dca_strategy = strategy_factory.create_strategy(StrategyType.DCA, dca_config)
                if dca_strategy:
                    strategies_created.append(("dca_001", dca_strategy))
            
            # Crear estrategia Scalping
            scalping_config = strategy_factory.create_config(
                StrategyType.SCALPING,
                symbol="DOTUSDT",
                investment_amount=50.0,
                risk_tolerance=0.8
            )
            
            if scalping_config:
                scalping_strategy = strategy_factory.create_strategy(StrategyType.SCALPING, scalping_config)
                if scalping_strategy:
                    strategies_created.append(("scalping_001", scalping_strategy))
            
            print(f"   ✅ Estrategias creadas: {len(strategies_created)}")
            
            # Iniciar todas las estrategias
            started_count = 0
            for strategy_id, strategy in strategies_created:
                success = await strategy_factory.start_strategy(strategy_id, strategy)
                if success:
                    started_count += 1
            
            print(f"   ✅ Estrategias iniciadas: {started_count}")
            
            # Obtener resumen
            summary = strategy_factory.get_strategy_summary()
            print(f"   ✅ Estrategias activas: {summary['active_strategies']}")
            
            # Detener todas las estrategias
            stopped_count = 0
            for strategy_id, _ in strategies_created:
                success = await strategy_factory.stop_strategy(strategy_id)
                if success:
                    stopped_count += 1
            
            print(f"   ✅ Estrategias detenidas: {stopped_count}")
            
            self.test_results['multiple_strategies'] = {
                'status': 'success',
                'strategies_created': len(strategies_created),
                'strategies_started': started_count,
                'strategies_stopped': stopped_count,
                'summary': summary
            }
            return True
            
        except Exception as e:
            print(f"   ❌ Error en múltiples estrategias: {e}")
            self.test_results['multiple_strategies'] = {
                'status': 'error',
                'error': str(e)
            }
            return False
    
    async def test_strategy_metrics(self):
        """Prueba las métricas de las estrategias"""
        print("📊 6. Probando Métricas de Estrategias...")
        
        try:
            # Crear y ejecutar una estrategia para generar métricas
            config = strategy_factory.create_config(
                StrategyType.DCA,
                symbol="LINKUSDT",
                strategy_type=StrategyType.DCA,
                investment_amount=20.0,
                risk_tolerance=0.5
            )
            
            if config:
                strategy = strategy_factory.create_strategy(StrategyType.DCA, config)
                if strategy:
                    # Iniciar estrategia
                    strategy_id = "metrics_test_001"
                    await strategy_factory.start_strategy(strategy_id, strategy)
                    
                    # Obtener métricas iniciales
                    initial_metrics = strategy.get_metrics()
                    print(f"   ✅ Métricas iniciales: {initial_metrics.total_trades} trades")
                    
                    # Simular ejecución (sin órdenes reales)
                    from app.strategies.base import TradingResult, Order, OrderSide, OrderStatus
                    
                    # Crear resultado simulado
                    simulated_result = TradingResult(
                        orders=[],
                        strategy_type=StrategyType.DCA,
                        total_profit=0.0,
                        total_volume=20.0,
                        success=True
                    )
                    
                    # Actualizar métricas
                    await strategy.update_metrics(simulated_result)
                    
                    # Obtener métricas actualizadas
                    updated_metrics = strategy.get_metrics()
                    print(f"   ✅ Métricas actualizadas: {updated_metrics.total_trades} trades")
                    
                    # Detener estrategia
                    await strategy_factory.stop_strategy(strategy_id)
                    
                    self.test_results['strategy_metrics'] = {
                        'status': 'success',
                        'initial_trades': initial_metrics.total_trades,
                        'updated_trades': updated_metrics.total_trades,
                        'total_profit': updated_metrics.total_profit
                    }
                    return True
            
            self.test_results['strategy_metrics'] = {
                'status': 'error',
                'error': 'Failed to test metrics'
            }
            return False
            
        except Exception as e:
            print(f"   ❌ Error en métricas: {e}")
            self.test_results['strategy_metrics'] = {
                'status': 'error',
                'error': str(e)
            }
            return False
    
    async def generate_report(self):
        """Genera reporte final de testing"""
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        # Calcular estadísticas
        total_tests = len(self.test_results)
        successful_tests = sum(1 for r in self.test_results.values() if r['status'] == 'success')
        success_rate = (successful_tests / total_tests * 100) if total_tests > 0 else 0
        
        report = {
            'test_date': self.start_time.isoformat(),
            'duration_seconds': round(duration, 2),
            'total_tests': total_tests,
            'successful_tests': successful_tests,
            'success_rate_percent': round(success_rate, 2),
            'test_results': self.test_results,
            'summary': {
                'framework_working': self.test_results.get('framework_base', {}).get('status') == 'success',
                'dca_working': self.test_results.get('dca_strategy', {}).get('status') == 'success',
                'scalping_working': self.test_results.get('scalping_strategy', {}).get('status') == 'success',
                'factory_working': self.test_results.get('strategy_factory', {}).get('status') == 'success',
                'multiple_strategies_working': self.test_results.get('multiple_strategies', {}).get('status') == 'success',
                'metrics_working': self.test_results.get('strategy_metrics', {}).get('status') == 'success'
            }
        }
        
        # Guardar reporte
        filename = f"test_estrategias_fase2_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        return report

async def main():
    """Función principal de testing"""
    print("🚀 INICIANDO TESTING DE FASE 2: MÚLTIPLES ESTRATEGIAS")
    print("=" * 70)
    
    tester = EstrategiasTester()
    
    # Ejecutar tests
    await tester.test_framework_base()
    await tester.test_dca_strategy()
    await tester.test_scalping_strategy()
    await tester.test_strategy_factory()
    await tester.test_multiple_strategies()
    await tester.test_strategy_metrics()
    
    # Generar reporte
    print("\n📋 Generando reporte final...")
    report = await tester.generate_report()
    
    # Mostrar resumen
    print("\n" + "=" * 70)
    print("📊 RESUMEN DE TESTING FASE 2")
    print("=" * 70)
    print(f"✅ Tests exitosos: {report['successful_tests']}/{report['total_tests']}")
    print(f"📈 Tasa de éxito: {report['success_rate_percent']}%")
    print(f"⏱️ Tiempo total: {report['duration_seconds']} segundos")
    
    print("\n🔍 Estado de Componentes:")
    summary = report['summary']
    print(f"   Framework Base: {'✅' if summary['framework_working'] else '❌'}")
    print(f"   DCA Strategy: {'✅' if summary['dca_working'] else '❌'}")
    print(f"   Scalping Strategy: {'✅' if summary['scalping_working'] else '❌'}")
    print(f"   Strategy Factory: {'✅' if summary['factory_working'] else '❌'}")
    print(f"   Múltiples Estrategias: {'✅' if summary['multiple_strategies_working'] else '❌'}")
    print(f"   Métricas: {'✅' if summary['metrics_working'] else '❌'}")
    
    print(f"\n📄 Reporte guardado en: {filename}")
    
    if report['success_rate_percent'] >= 80:
        print("\n🎉 ¡FASE 2 IMPLEMENTADA EXITOSAMENTE!")
    else:
        print("\n⚠️ Fase 2 requiere atención en algunos componentes")

if __name__ == "__main__":
    asyncio.run(main()) 