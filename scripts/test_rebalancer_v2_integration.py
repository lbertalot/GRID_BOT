#!/usr/bin/env python3
"""
Script de validación end-to-end para AutoRebalancer V2
Prueba la integración completa del sistema de liquidez autónoma
"""

import asyncio
import logging
import os
import sys

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.auto_rebalancer_v2 import auto_rebalancer_v2
from app.services.binance_client_singleton import get_binance_client_singleton

# Configurar logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def test_rebalancer_configuration():
    """Test 1: Verificar configuración del rebalanceador"""
    logger.info("🔧 Test 1: Verificando configuración del rebalanceador...")

    try:
        # Verificar variables de entorno
        min_usdt = os.getenv("MIN_USDT_BALANCE", "25.0")
        target_usdt = os.getenv("TARGET_USDT_BALANCE", "50.0")
        enable_rebalance = os.getenv("ENABLE_AUTO_REBALANCE", "true")
        asset_priority = os.getenv("REBALANCE_ASSET_PRIORITY", "SPK,HOME,SIGN,BNB,BTC")

        logger.info(f"✅ MIN_USDT_BALANCE: {min_usdt}")
        logger.info(f"✅ TARGET_USDT_BALANCE: {target_usdt}")
        logger.info(f"✅ ENABLE_AUTO_REBALANCE: {enable_rebalance}")
        logger.info(f"✅ REBALANCE_ASSET_PRIORITY: {asset_priority}")

        # Verificar configuración del rebalanceador
        assert auto_rebalancer_v2.min_usdt_balance == float(min_usdt)
        assert auto_rebalancer_v2.target_usdt_balance == float(target_usdt)
        assert auto_rebalancer_v2.enable_auto_rebalance == (
            enable_rebalance.lower() == "true"
        )
        assert "SPK" in auto_rebalancer_v2.asset_priority
        assert "ETHUSDT" in auto_rebalancer_v2.protected_assets

        logger.info("✅ Configuración del rebalanceador verificada correctamente")
        return True

    except Exception as e:
        logger.error(f"❌ Error en configuración: {e}")
        return False


async def test_binance_connectivity():
    """Test 2: Verificar conectividad con Binance"""
    logger.info("🔗 Test 2: Verificando conectividad con Binance...")

    try:
        client = get_binance_client_singleton()

        # Verificar conectividad de red
        net_check = client.validate_credentials_and_connectivity()
        if not net_check.get("net_ok", False):
            logger.error("❌ Conectividad de red con Binance fallida")
            return False

        # Verificar autenticación
        if not net_check.get("auth_ok", False):
            logger.error("❌ Autenticación con Binance fallida")
            return False

        # Obtener balance de USDT
        account_info = client.client.get_account()
        usdt_balance = 0.0

        for balance in account_info["balances"]:
            if balance["asset"] == "USDT":
                usdt_balance = float(balance["free"]) + float(balance["locked"])
                break

        logger.info(
            f"✅ Conectividad con Binance verificada - Balance USDT: {usdt_balance:.2f}"
        )
        return True

    except Exception as e:
        logger.error(f"❌ Error de conectividad: {e}")
        return False


async def test_rebalance_status():
    """Test 3: Verificar estado del rebalanceador"""
    logger.info("📊 Test 3: Verificando estado del rebalanceador...")

    try:
        status = await auto_rebalancer_v2.get_rebalance_status()

        logger.info("✅ Estado del rebalanceador:")
        logger.info(
            f"   - Balance actual USDT: {status.get('current_usdt_balance', 0):.2f}"
        )
        logger.info(f"   - Mínimo requerido: {status.get('min_usdt_balance', 0):.2f}")
        logger.info(f"   - Objetivo: {status.get('target_usdt_balance', 0):.2f}")
        logger.info(f"   - Necesita rebalanceo: {status.get('needs_rebalance', False)}")
        logger.info(f"   - Activos disponibles: {status.get('available_assets', [])}")
        logger.info(f"   - Activos protegidos: {status.get('protected_assets', [])}")
        logger.info(f"   - Habilitado: {status.get('enabled', False)}")

        return True

    except Exception as e:
        logger.error(f"❌ Error obteniendo estado: {e}")
        return False


async def test_asset_selection_logic():
    """Test 4: Verificar lógica de selección de activos"""
    logger.info("🎯 Test 4: Verificando lógica de selección de activos...")

    try:
        # Simular balances para testing
        test_balances = {
            "SPK": 100.0,  # Prioridad 1 - debería ser seleccionado
            "HOME": 50.0,  # Prioridad 2 - debería ser seleccionado
            "BNB": 25.0,  # Prioridad 4 - debería ser seleccionado
            "ETH": 10.0,  # Protegido - NO debería ser seleccionado
            "BTC": 5.0,  # Prioridad 5 - debería ser seleccionado
        }

        # Mock del cliente Binance para testing
        with patch.object(
            auto_rebalancer_v2.binance_client, "get_symbol_ticker"
        ) as mock_ticker:
            mock_ticker.return_value = {"price": "1.0"}  # Precio fijo para testing

            # Mock de validación de parámetros
            with patch.object(
                auto_rebalancer_v2, "_validate_sale_parameters", return_value=True
            ):
                selected_assets = (
                    await auto_rebalancer_v2._select_assets_for_liquidation(
                        test_balances, 50.0
                    )
                )

                logger.info("✅ Activos seleccionados para liquidación:")
                for asset in selected_assets:
                    logger.info(
                        f"   - {asset['asset']}: {asset['quantity']:.2f} (Prioridad: {asset['priority']})"
                    )

                # Verificar que se seleccionaron activos
                assert (
                    len(selected_assets) > 0
                ), "No se seleccionaron activos para liquidación"

                # Verificar que ETH no fue seleccionado (está protegido)
                eth_selected = any(a["asset"] == "ETH" for a in selected_assets)
                assert (
                    not eth_selected
                ), "ETH fue seleccionado para liquidación (está protegido)"

                # Verificar prioridades
                priorities = [a["priority"] for a in selected_assets]
                assert priorities == sorted(
                    priorities
                ), "Las prioridades no están ordenadas correctamente"

        logger.info("✅ Lógica de selección de activos verificada correctamente")
        return True

    except Exception as e:
        logger.error(f"❌ Error en lógica de selección: {e}")
        return False


async def test_circuit_breakers_integration():
    """Test 5: Verificar integración con circuit breakers"""
    logger.info("🛡️ Test 5: Verificando integración con circuit breakers...")

    try:
        # Verificar que los circuit breakers están disponibles
        assert hasattr(auto_rebalancer_v2, "circuit_breakers")
        assert hasattr(auto_rebalancer_v2, "strategy_blacklist")

        # Verificar método de verificación
        can_proceed = await auto_rebalancer_v2._check_circuit_breakers()
        logger.info(f"✅ Circuit breakers verificados - Puede proceder: {can_proceed}")

        return True

    except Exception as e:
        logger.error(f"❌ Error en circuit breakers: {e}")
        return False


async def test_full_rebalance_simulation():
    """Test 6: Simulación completa de rebalanceo (sin ejecutar órdenes reales)"""
    logger.info("🔄 Test 6: Simulando rebalanceo completo...")

    try:
        # Verificar estado inicial
        initial_status = await auto_rebalancer_v2.get_rebalance_status()
        logger.info(
            f"📊 Estado inicial: {initial_status.get('current_usdt_balance', 0):.2f} USDT"
        )

        # Simular escenario de liquidez insuficiente
        with patch.object(
            auto_rebalancer_v2, "_get_current_usdt_balance", return_value=15.0
        ):
            with patch.object(
                auto_rebalancer_v2, "_check_circuit_breakers", return_value=True
            ):
                with patch.object(
                    auto_rebalancer_v2,
                    "_execute_liquidity_rebalance",
                    return_value={
                        "status": "success",
                        "assets_sold": 2,
                        "usdt_generated": 35.0,
                        "final_balance": 50.0,
                    },
                ):
                    result = await auto_rebalancer_v2.check_and_rebalance()

                    logger.info(f"✅ Resultado del rebalanceo simulado: {result}")
                    assert result["status"] == "success"
                    assert "deficit_resolved" in result

        logger.info("✅ Simulación de rebalanceo completada exitosamente")
        return True

    except Exception as e:
        logger.error(f"❌ Error en simulación: {e}")
        return False


async def main():
    """Función principal de testing"""
    logger.info("🚀 Iniciando validación end-to-end de AutoRebalancer V2")
    logger.info("=" * 60)

    tests = [
        ("Configuración del rebalanceador", test_rebalancer_configuration),
        ("Conectividad con Binance", test_binance_connectivity),
        ("Estado del rebalanceador", test_rebalance_status),
        ("Lógica de selección de activos", test_asset_selection_logic),
        ("Integración con circuit breakers", test_circuit_breakers_integration),
        ("Simulación de rebalanceo completo", test_full_rebalance_simulation),
    ]

    results = []

    for test_name, test_func in tests:
        logger.info(f"\n🧪 Ejecutando: {test_name}")
        try:
            result = await test_func()
            results.append((test_name, result))
            if result:
                logger.info(f"✅ {test_name}: PASÓ")
            else:
                logger.error(f"❌ {test_name}: FALLÓ")
        except Exception as e:
            logger.error(f"❌ {test_name}: ERROR - {e}")
            results.append((test_name, False))

    # Resumen final
    logger.info("\n" + "=" * 60)
    logger.info("📋 RESUMEN DE RESULTADOS:")

    passed = 0
    total = len(results)

    for test_name, result in results:
        status = "✅ PASÓ" if result else "❌ FALLÓ"
        logger.info(f"   {test_name}: {status}")
        if result:
            passed += 1

    logger.info(f"\n🎯 RESULTADO FINAL: {passed}/{total} tests pasaron")

    if passed == total:
        logger.info(
            "🎉 ¡TODOS LOS TESTS PASARON! El rebalanceador V2 está listo para producción."
        )
        return True
    else:
        logger.error(
            f"⚠️ {total - passed} tests fallaron. Revisar configuración antes de producción."
        )
        return False


if __name__ == "__main__":
    # Importar patch para testing
    from unittest.mock import patch

    # Ejecutar tests
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
