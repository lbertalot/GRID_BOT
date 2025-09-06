#!/usr/bin/env python3
"""
Test del Sistema de Integridad Completo - GridBot v2.5
Script para validar que todo el sistema de integridad funcione correctamente
"""

import asyncio
import json
import logging
import sys
import os
from datetime import datetime

# Agregar el directorio raíz al path para importar módulos
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.balance_validator import BalanceValidator
from app.core.operation_tracker import OperationTracker, OperationStatus
from app.core.integrity_monitor import IntegrityMonitor
from app.core.circuit_breakers import CircuitBreakers
from app.core.grafana_metrics import GrafanaMetrics
from app.core.telegram_bot import TelegramBot
from app.core.database import Database

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class IntegritySystemTester:
    def __init__(self):
        self.test_results = {
            'timestamp': datetime.now().isoformat(),
            'tests': {},
            'overall_status': 'PENDING'
        }
        
    async def run_system_test(self):
        """Ejecutar prueba completa del sistema de integridad"""
        logger.info("🚀 Iniciando prueba completa del sistema de integridad")
        
        try:
            # Test 1: Inicialización de componentes
            await self.test_component_initialization()
            
            # Test 2: Integración entre componentes
            await self.test_component_integration()
            
            # Test 3: Funcionalidad de circuit breakers
            await self.test_circuit_breakers()
            
            # Test 4: Sistema de métricas
            await self.test_metrics_system()
            
            # Test 5: Sistema de alertas
            await self.test_alert_system()
            
            # Test 6: Simulación de operaciones
            await self.test_operation_simulation()
            
            # Test 7: Simulación de validación de balances
            await self.test_balance_validation_simulation()
            
            # Evaluar resultados generales
            await self.evaluate_overall_results()
            
            # Generar reporte
            await self.generate_system_test_report()
            
        except Exception as e:
            logger.error(f"❌ Error ejecutando prueba del sistema: {e}")
            self.test_results['overall_status'] = 'ERROR'
            self.test_results['error'] = str(e)
    
    async def test_component_initialization(self):
        """Probar inicialización de todos los componentes"""
        logger.info("🔍 Probando inicialización de componentes...")
        
        try:
            # Inicializar todos los componentes
            db = Database()
            telegram_bot = TelegramBot()
            grafana_metrics = GrafanaMetrics()
            circuit_breakers = CircuitBreakers()
            balance_validator = BalanceValidator()
            operation_tracker = OperationTracker()
            integrity_monitor = IntegrityMonitor()
            
            # Verificar que todos se inicializaron correctamente
            assert db is not None, "Database no se inicializó"
            assert telegram_bot is not None, "TelegramBot no se inicializó"
            assert grafana_metrics is not None, "GrafanaMetrics no se inicializó"
            assert circuit_breakers is not None, "CircuitBreakers no se inicializó"
            assert balance_validator is not None, "BalanceValidator no se inicializó"
            assert operation_tracker is not None, "OperationTracker no se inicializó"
            assert integrity_monitor is not None, "IntegrityMonitor no se inicializó"
            
            self.test_results['tests']['component_initialization'] = {
                'status': 'PASSED',
                'details': 'Todos los componentes se inicializaron correctamente',
                'components': ['Database', 'TelegramBot', 'GrafanaMetrics', 'CircuitBreakers', 'BalanceValidator', 'OperationTracker', 'IntegrityMonitor']
            }
            
            logger.info("✅ Inicialización de componentes: PASSED")
            
        except Exception as e:
            logger.error(f"❌ Inicialización de componentes: FAILED - {e}")
            self.test_results['tests']['component_initialization'] = {
                'status': 'FAILED',
                'error': str(e)
            }
    
    async def test_component_integration(self):
        """Probar integración entre componentes"""
        logger.info("🔍 Probando integración entre componentes...")
        
        try:
            # Crear instancias
            balance_validator = BalanceValidator()
            operation_tracker = OperationTracker()
            integrity_monitor = IntegrityMonitor()
            
            # Conectar componentes
            integrity_monitor.set_components(balance_validator, operation_tracker)
            
            # Verificar conexiones
            assert integrity_monitor.balance_validator is balance_validator, "BalanceValidator no se conectó correctamente"
            assert integrity_monitor.operation_tracker is operation_tracker, "OperationTracker no se conectó correctamente"
            
            self.test_results['tests']['component_integration'] = {
                'status': 'PASSED',
                'details': 'Componentes integrados correctamente',
                'connections': ['BalanceValidator -> IntegrityMonitor', 'OperationTracker -> IntegrityMonitor']
            }
            
            logger.info("✅ Integración entre componentes: PASSED")
            
        except Exception as e:
            logger.error(f"❌ Integración entre componentes: FAILED - {e}")
            self.test_results['tests']['component_integration'] = {
                'status': 'FAILED',
                'error': str(e)
            }
    
    async def test_circuit_breakers(self):
        """Probar funcionalidad de circuit breakers"""
        logger.info("🔍 Probando circuit breakers...")
        
        try:
            circuit_breakers = CircuitBreakers()
            
            # Verificar estado inicial
            assert not circuit_breakers.is_critical_mode_active(), "Modo crítico no debería estar activo inicialmente"
            
            # Activar circuit breaker específico
            await circuit_breakers.activate_breaker('balance_discrepancy', 'Test de activación')
            assert circuit_breakers.is_breaker_active('balance_discrepancy'), "Circuit breaker no se activó"
            
            # Activar modo crítico
            await circuit_breakers.activate_critical_mode()
            assert circuit_breakers.is_critical_mode_active(), "Modo crítico no se activó"
            
            # Desactivar modo crítico
            await circuit_breakers.deactivate_critical_mode()
            assert not circuit_breakers.is_critical_mode_active(), "Modo crítico no se desactivó"
            
            # Obtener resumen
            summary = circuit_breakers.get_breaker_summary()
            assert 'CIRCUIT BREAKERS' in summary, "Resumen de circuit breakers no se generó correctamente"
            
            self.test_results['tests']['circuit_breakers'] = {
                'status': 'PASSED',
                'details': 'Circuit breakers funcionando correctamente',
                'features_tested': ['Activación individual', 'Modo crítico', 'Desactivación', 'Resumen']
            }
            
            logger.info("✅ Circuit breakers: PASSED")
            
        except Exception as e:
            logger.error(f"❌ Circuit breakers: FAILED - {e}")
            self.test_results['tests']['circuit_breakers'] = {
                'status': 'FAILED',
                'error': str(e)
            }
    
    async def test_metrics_system(self):
        """Probar sistema de métricas"""
        logger.info("🔍 Probando sistema de métricas...")
        
        try:
            grafana_metrics = GrafanaMetrics()
            
            # Registrar algunas métricas
            await grafana_metrics.record_metric('test_metric_1', 100)
            await grafana_metrics.record_metric('test_metric_2', 200.5)
            await grafana_metrics.record_metric('test_metric_3', 'test_value')
            
            # Obtener resumen
            summary = grafana_metrics.get_metrics_summary()
            assert summary['total_metrics'] == 3, "Número incorrecto de métricas registradas"
            assert summary['unique_metrics'] == 3, "Número incorrecto de métricas únicas"
            
            # Verificar métricas específicas
            metric_1_data = summary['metrics_by_name']['test_metric_1']
            assert metric_1_data['latest_value'] == 100, "Valor de métrica incorrecto"
            assert metric_1_data['count'] == 1, "Conteo de métrica incorrecto"
            
            self.test_results['tests']['metrics_system'] = {
                'status': 'PASSED',
                'details': 'Sistema de métricas funcionando correctamente',
                'metrics_registered': 3,
                'features_tested': ['Registro de métricas', 'Resumen', 'Estadísticas']
            }
            
            logger.info("✅ Sistema de métricas: PASSED")
            
        except Exception as e:
            logger.error(f"❌ Sistema de métricas: FAILED - {e}")
            self.test_results['tests']['metrics_system'] = {
                'status': 'FAILED',
                'error': str(e)
            }
    
    async def test_alert_system(self):
        """Probar sistema de alertas"""
        logger.info("🔍 Probando sistema de alertas...")
        
        try:
            telegram_bot = TelegramBot()
            
            # Enviar alerta de prueba
            result = await telegram_bot.send_alert("🧪 Test de alerta del sistema de integridad")
            assert result == True, "Alerta no se envió correctamente"
            
            # Enviar alerta síncrona
            result_sync = telegram_bot.send_alert_sync("🧪 Test de alerta síncrona")
            assert result_sync == True, "Alerta síncrona no se envió correctamente"
            
            self.test_results['tests']['alert_system'] = {
                'status': 'PASSED',
                'details': 'Sistema de alertas funcionando correctamente',
                'features_tested': ['Alertas asíncronas', 'Alertas síncronas', 'Modo simulado']
            }
            
            logger.info("✅ Sistema de alertas: PASSED")
            
        except Exception as e:
            logger.error(f"❌ Sistema de alertas: FAILED - {e}")
            self.test_results['tests']['alert_system'] = {
                'status': 'FAILED',
                'error': str(e)
            }
    
    async def test_operation_simulation(self):
        """Probar simulación de operaciones"""
        logger.info("🔍 Probando simulación de operaciones...")
        
        try:
            operation_tracker = OperationTracker()
            
            # Simular operación de compra
            buy_operation = {
                'asset': 'BTCUSDT',
                'type': 'GRID_BUY',
                'side': 'BUY',
                'quantity': 0.001,
                'price': 50000,
                'user_id': 'test_user',
                'strategy_id': 'test_strategy',
                'grid_level': 1
            }
            
            operation_id = await operation_tracker.track_operation(buy_operation)
            assert operation_id is not None, "ID de operación no se generó"
            
            # Simular operación de venta
            sell_operation = {
                'asset': 'ETHUSDT',
                'type': 'GRID_SELL',
                'side': 'SELL',
                'quantity': 0.01,
                'price': 3000,
                'user_id': 'test_user',
                'strategy_id': 'test_strategy',
                'grid_level': 2
            }
            
            sell_operation_id = await operation_tracker.track_operation(sell_operation)
            assert sell_operation_id is not None, "ID de operación de venta no se generó"
            
            # Verificar estado inicial
            summary = await operation_tracker.get_operation_summary()
            assert summary['total_operations'] == 2, "Número incorrecto de operaciones"
            assert summary['active_operations'] == 2, "Número incorrecto de operaciones activas"
            
            # Simular operación completada
            result_data = {
                'executed_price': 50001,
                'executed_quantity': 0.001,
                'fees': 0.0001
            }
            
            await operation_tracker.update_operation_status(operation_id, OperationStatus.COMPLETED, result_data)
            
            # Verificar estado final
            final_summary = await operation_tracker.get_operation_summary()
            assert final_summary['successful_operations'] == 1, "Operación exitosa no se registró"
            assert final_summary['active_operations'] == 1, "Operación completada no se movió del estado activo"
            
            self.test_results['tests']['operation_simulation'] = {
                'status': 'PASSED',
                'details': 'Simulación de operaciones funcionando correctamente',
                'operations_tested': 2,
                'features_tested': ['Tracking de operaciones', 'Actualización de estado', 'Métricas']
            }
            
            logger.info("✅ Simulación de operaciones: PASSED")
            
        except Exception as e:
            logger.error(f"❌ Simulación de operaciones: FAILED - {e}")
            self.test_results['tests']['operation_simulation'] = {
                'status': 'FAILED',
                'error': str(e)
            }
    
    async def test_balance_validation_simulation(self):
        """Probar simulación de validación de balances"""
        logger.info("🔍 Probando simulación de validación de balances...")
        
        try:
            balance_validator = BalanceValidator()
            
            # Obtener resumen inicial
            initial_summary = await balance_validator.get_validation_summary()
            assert 'integrity_score' in initial_summary, "Resumen inicial no contiene integrity_score"
            assert 'total_validations' in initial_summary, "Resumen inicial no contiene total_validations"
            
            # Forzar validación
            await balance_validator.force_validation()
            
            # Obtener resumen después de validación
            final_summary = await balance_validator.get_validation_summary()
            assert final_summary['total_validations'] > initial_summary['total_validations'], "Validación no se ejecutó"
            
            # Verificar métricas de integridad
            assert balance_validator.integrity_score >= 0, "Score de integridad inválido"
            assert balance_validator.integrity_score <= 100, "Score de integridad excede 100"
            
            self.test_results['tests']['balance_validation_simulation'] = {
                'status': 'PASSED',
                'details': 'Simulación de validación de balances funcionando correctamente',
                'initial_validations': initial_summary['total_validations'],
                'final_validations': final_summary['total_validations'],
                'integrity_score': balance_validator.integrity_score
            }
            
            logger.info("✅ Simulación de validación de balances: PASSED")
            
        except Exception as e:
            logger.error(f"❌ Simulación de validación de balances: FAILED - {e}")
            self.test_results['tests']['balance_validation_simulation'] = {
                'status': 'FAILED',
                'error': str(e)
            }
    
    async def evaluate_overall_results(self):
        """Evaluar resultados generales de las pruebas"""
        logger.info("📊 Evaluando resultados generales del sistema...")
        
        passed_tests = 0
        failed_tests = 0
        
        for test_name, test_result in self.test_results['tests'].items():
            if test_result['status'] == 'PASSED':
                passed_tests += 1
            else:
                failed_tests += 1
        
        total_tests = len(self.test_results['tests'])
        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        
        if failed_tests == 0:
            self.test_results['overall_status'] = 'PASSED'
            self.test_results['summary'] = f"Todas las pruebas del sistema pasaron exitosamente ({passed_tests}/{total_tests})"
        elif success_rate >= 80:
            self.test_results['overall_status'] = 'PARTIALLY_PASSED'
            self.test_results['summary'] = f"La mayoría de las pruebas del sistema pasaron ({passed_tests}/{total_tests}, {success_rate:.1f}%)"
        else:
            self.test_results['overall_status'] = 'FAILED'
            self.test_results['summary'] = f"Muchas pruebas del sistema fallaron ({passed_tests}/{total_tests}, {success_rate:.1f}%)"
        
        self.test_results['passed_tests'] = passed_tests
        self.test_results['failed_tests'] = failed_tests
        self.test_results['total_tests'] = total_tests
        self.test_results['success_rate'] = success_rate
        
        logger.info(f"📊 Resultados del sistema: {passed_tests}/{total_tests} pruebas pasaron ({success_rate:.1f}%)")
    
    async def generate_system_test_report(self):
        """Generar reporte de pruebas del sistema"""
        logger.info("📋 Generando reporte de pruebas del sistema...")
        
        # Crear nombre de archivo con timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        reports_dir = os.getenv('REPORTS_DIR', 'reports')
        integrity_dir = os.path.join(reports_dir, 'integrity')
        try:
            os.makedirs(integrity_dir, exist_ok=True)
        except Exception:
            pass
        filename = os.path.join(integrity_dir, f"integrity_system_test_report_{timestamp}.json")
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.test_results, f, indent=2, ensure_ascii=False)
            
            logger.info(f"📋 Reporte del sistema guardado en: {filename}")
            
            # Mostrar resumen en consola
            print("\n" + "="*70)
            print("📊 REPORTE DE PRUEBAS DEL SISTEMA DE INTEGRIDAD COMPLETO")
            print("="*70)
            print(f"🕐 Timestamp: {self.test_results['timestamp']}")
            print(f"📈 Estado General: {self.test_results['overall_status']}")
            print(f"📋 Resumen: {self.test_results['summary']}")
            print(f"✅ Pruebas Exitosas: {self.test_results['passed_tests']}")
            print(f"❌ Pruebas Fallidas: {self.test_results['failed_tests']}")
            print(f"📊 Tasa de Éxito: {self.test_results['success_rate']:.1f}%")
            print("\n📋 Detalles por Componente:")
            
            for test_name, test_result in self.test_results['tests'].items():
                status_emoji = "✅" if test_result['status'] == 'PASSED' else "❌"
                print(f"  {status_emoji} {test_name}: {test_result['status']}")
                if test_result['status'] == 'FAILED':
                    print(f"     Error: {test_result['error']}")
                elif 'details' in test_result:
                    print(f"     {test_result['details']}")
            
            print("="*70)
            
        except Exception as e:
            logger.error(f"❌ Error generando reporte del sistema: {e}")

async def main():
    """Función principal"""
    logger.info("🚀 Iniciando prueba completa del sistema de integridad")
    
    tester = IntegritySystemTester()
    await tester.run_system_test()
    
    logger.info("🏁 Prueba del sistema completada")

if __name__ == "__main__":
    asyncio.run(main())
