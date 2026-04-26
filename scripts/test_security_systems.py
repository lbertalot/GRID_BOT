#!/usr/bin/env python3
"""
Script de Prueba de Sistemas de Seguridad para GridBot V2.5
Prueba circuit breakers, validación de precisión y monitoreo
"""

import sys
import os
import logging
from datetime import datetime

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configurar logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_circuit_breaker():
    """Prueba el sistema de circuit breakers"""
    print("\n🔌 PROBANDO CIRCUIT BREAKER")
    print("=" * 40)

    try:
        from app.core.circuit_breaker import (
            check_trading_allowed,
            record_trade_result,
            circuit_breaker,
        )

        # Prueba 1: Verificar estado inicial
        allowed, msg = check_trading_allowed()
        print(f"✅ Estado inicial: {'Permitido' if allowed else 'Bloqueado'} - {msg}")

        # Prueba 2: Registrar pérdida pequeña
        print("\n📉 Registrando pérdida pequeña...")
        record_trade_result(-5.0, 0.015)  # $5 pérdida, ~1.5% del balance

        allowed, msg = check_trading_allowed()
        print(
            f"   Estado después de pérdida: {'Permitido' if allowed else 'Bloqueado'} - {msg}"
        )

        # Prueba 3: Registrar pérdida que excede límite
        print("\n📉 Registrando pérdida que excede límite...")
        record_trade_result(-10.0, 0.03)  # $10 pérdida, ~3% del balance

        allowed, msg = check_trading_allowed()
        print(
            f"   Estado después de pérdida grande: {'Permitido' if allowed else 'Bloqueado'} - {msg}"
        )

        # Prueba 4: Obtener estado
        status = circuit_breaker.get_status()
        print("\n📊 Estado del circuit breaker:")
        print(f"   Abierto: {status['is_open']}")
        print(f"   Razón: {status['reason']}")
        print(f"   Pérdida diaria: {status['current_state']['daily_loss']:.2%}")
        print(f"   Pérdida total: {status['current_state']['total_loss']:.2%}")

        return True

    except Exception as e:
        print(f"❌ Error probando circuit breaker: {e}")
        return False


def test_precision_validator():
    """Prueba el sistema de validación de precisión"""
    print("\n🎯 PROBANDO VALIDACIÓN DE PRECISIÓN")
    print("=" * 40)

    try:
        from app.core.precision_validator import (
            validate_trading_order,
            get_symbol_precision_info,
        )

        # Prueba 1: Validar orden válida
        print("\n✅ Probando orden válida...")
        valid, data, msg = validate_trading_order("BTCUSDT", 0.001, 108000)
        print(f"   Resultado: {'Válido' if valid else 'Inválido'} - {msg}")
        if valid:
            print(f"   Cantidad ajustada: {data['quantity']}")
            print(f"   Precio ajustado: {data['price']}")
            print(f"   Valor notional: ${data['notional_value']:.2f}")

        # Prueba 2: Validar orden con cantidad inválida
        print("\n❌ Probando cantidad inválida...")
        valid, data, msg = validate_trading_order("BTCUSDT", 0.0000001, 108000)
        print(f"   Resultado: {'Válido' if valid else 'Inválido'} - {msg}")

        # Prueba 3: Validar orden con valor notional bajo
        print("\n❌ Probando valor notional bajo...")
        valid, data, msg = validate_trading_order("BTCUSDT", 0.00001, 1000)
        print(f"   Resultado: {'Válido' if valid else 'Inválido'} - {msg}")

        # Prueba 4: Obtener información de precisión
        print("\n📊 Información de precisión BTCUSDT:")
        precision_info = get_symbol_precision_info("BTCUSDT")
        print(f"   Precisión cantidad: {precision_info['quantity_precision']}")
        print(f"   Precisión precio: {precision_info['price_precision']}")
        print(f"   Step size: {precision_info['min_quantity']}")
        print(f"   Valor notional mínimo: ${precision_info['min_notional']}")

        return True

    except Exception as e:
        print(f"❌ Error probando validación de precisión: {e}")
        return False


def test_monitoring_system():
    """Prueba el sistema de monitoreo"""
    print("\n📊 PROBANDO SISTEMA DE MONITOREO")
    print("=" * 40)

    try:
        from app.core.monitoring import (
            record_trade_event,
            update_balance_monitoring,
            get_monitoring_status,
        )

        # Prueba 1: Registrar trade exitoso
        print("\n✅ Registrando trade exitoso...")
        record_trade_event("BTCUSDT", "BUY", 0.001, 108000, True, 5.0)
        print("   Trade exitoso registrado")

        # Prueba 2: Registrar trade fallido
        print("\n❌ Registrando trade fallido...")
        record_trade_event("ETHUSDT", "SELL", 0.01, 4400, False, -2.0)
        print("   Trade fallido registrado")

        # Prueba 3: Actualizar balance
        print("\n💰 Actualizando balance...")
        update_balance_monitoring(310.0)  # Simular pérdida
        print("   Balance actualizado")

        # Prueba 4: Obtener estado del monitoreo
        print("\n📊 Estado del monitoreo:")
        status = get_monitoring_status()
        print(f"   Estado del sistema: {status['system_status']}")
        print(f"   Total trades: {status['metrics']['total_trades']}")
        print(f"   Trades exitosos: {status['metrics']['successful_trades']}")
        print(f"   Trades fallidos: {status['metrics']['failed_trades']}")
        print(f"   Balance actual: ${status['metrics']['current_balance']:.2f}")
        print(f"   PnL diario: {status['metrics']['daily_pnl']:.2%}")

        return True

    except Exception as e:
        print(f"❌ Error probando sistema de monitoreo: {e}")
        return False


def test_safety_validator():
    """Prueba el validador de seguridad integrado"""
    print("\n🛡️ PROBANDO VALIDADOR DE SEGURIDAD")
    print("=" * 40)

    try:
        from app.core.safety_validator import (
            validate_and_execute_trade,
            get_system_safety_status,
        )

        # Prueba 1: Validar trade válido
        print("\n✅ Probando trade válido...")
        success, data, msg = validate_and_execute_trade("BTCUSDT", "BUY", 0.001, 108000)
        print(f"   Resultado: {'Éxito' if success else 'Fallo'} - {msg}")
        if success:
            print(f"   Datos validados: {data}")

        # Prueba 2: Validar trade con valor muy alto
        print("\n❌ Probando trade con valor muy alto...")
        success, data, msg = validate_and_execute_trade("BTCUSDT", "BUY", 1.0, 108000)
        print(f"   Resultado: {'Éxito' if success else 'Fallo'} - {msg}")

        # Prueba 3: Obtener estado de seguridad
        print("\n🛡️ Estado de seguridad del sistema:")
        safety_status = get_system_safety_status()
        print(
            f"   Circuit breaker: {'Abierto' if safety_status['circuit_breaker']['is_open'] else 'Cerrado'}"
        )
        print(f"   Sistema seguro: {'Sí' if safety_status['system_safe'] else 'No'}")
        print(f"   Estado monitoreo: {safety_status['monitoring']['system_status']}")

        return True

    except Exception as e:
        print(f"❌ Error probando validador de seguridad: {e}")
        return False


def test_emergency_functions():
    """Prueba funciones de emergencia"""
    print("\n🚨 PROBANDO FUNCIONES DE EMERGENCIA")
    print("=" * 40)

    try:
        from app.core.safety_validator import trigger_emergency_stop
        from app.core.circuit_breaker import circuit_breaker

        # Prueba 1: Activar parada de emergencia
        print("\n🚨 Activando parada de emergencia...")
        trigger_emergency_stop("Prueba de emergencia")

        # Verificar que el circuit breaker está abierto
        allowed, msg = circuit_breaker.check_limits()
        print(f"   Circuit breaker: {'Abierto' if not allowed else 'Cerrado'} - {msg}")

        # Prueba 2: Cerrar circuit breaker
        print("\n✅ Cerrando circuit breaker...")
        circuit_breaker.close_circuit("Fin de prueba")

        allowed, msg = circuit_breaker.check_limits()
        print(f"   Circuit breaker: {'Abierto' if not allowed else 'Cerrado'} - {msg}")

        return True

    except Exception as e:
        print(f"❌ Error probando funciones de emergencia: {e}")
        return False


def main():
    """Función principal de pruebas"""
    print("🧪 INICIANDO PRUEBAS DE SISTEMAS DE SEGURIDAD")
    print("=" * 50)
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Ejecutar todas las pruebas
    tests = [
        ("Circuit Breaker", test_circuit_breaker),
        ("Validación de Precisión", test_precision_validator),
        ("Sistema de Monitoreo", test_monitoring_system),
        ("Validador de Seguridad", test_safety_validator),
        ("Funciones de Emergencia", test_emergency_functions),
    ]

    results = []

    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ Error en prueba {test_name}: {e}")
            results.append((test_name, False))

    # Resumen de resultados
    print("\n" + "=" * 50)
    print("📊 RESUMEN DE PRUEBAS")
    print("=" * 50)

    passed = 0
    total = len(results)

    for test_name, success in results:
        status = "✅ PASÓ" if success else "❌ FALLÓ"
        print(f"   {test_name}: {status}")
        if success:
            passed += 1

    print(f"\n🎯 Resultado: {passed}/{total} pruebas pasaron")

    if passed == total:
        print(
            "🎉 ¡TODAS LAS PRUEBAS PASARON! Los sistemas de seguridad están funcionando correctamente."
        )
    else:
        print("⚠️ Algunas pruebas fallaron. Revisar los errores antes de continuar.")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
