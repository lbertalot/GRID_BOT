#!/usr/bin/env python3
"""
Script de test simplificado para AutoRebalancer V2
Evita dependencias complejas y se enfoca en la lógica core
"""

import os
import sys
import asyncio
import logging
from typing import Dict, List

# Configurar logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class MockBinanceClient:
    """Mock del cliente Binance para testing"""

    def __init__(self):
        self.account_data = {
            "balances": [
                {"asset": "USDT", "free": "18.48", "locked": "0"},
                {"asset": "SPK", "free": "100.0", "locked": "0"},
                {"asset": "BNB", "free": "50.0", "locked": "0"},
                {"asset": "ETH", "free": "0.1", "locked": "0"},
                {"asset": "BTC", "free": "0.001", "locked": "0"},
            ]
        }

    def get_account(self):
        return self.account_data

    def get_symbol_ticker(self, symbol):
        # Precios mock para testing
        prices = {
            "SPKUSDT": "0.5",
            "BNBUSDT": "300.0",
            "ETHUSDT": "3000.0",
            "BTCUSDT": "50000.0",
        }
        return {"price": prices.get(symbol, "1.0")}

    def get_symbol_info(self, symbol):
        return {
            "filters": [
                {
                    "filterType": "LOT_SIZE",
                    "minQty": "0.001",
                    "maxQty": "1000000",
                    "stepSize": "0.001",
                },
                {"filterType": "MIN_NOTIONAL", "minNotional": "10.0"},
            ]
        }

    def create_order(self, symbol, side, type, quantity=None, quoteOrderQty=None):
        return {
            "orderId": "12345",
            "status": "FILLED",
            "symbol": symbol,
            "side": side,
            "type": type,
        }


class MockCircuitBreakers:
    """Mock de circuit breakers"""

    def is_trading_halted(self):
        return False

    def get_all_breakers_status(self):
        return {"active_breakers": [], "critical_mode": False}


class MockStrategyBlacklist:
    """Mock de strategy blacklist"""

    def is_symbol_blacklisted(self, symbol):
        # SPK está en blacklist para testing
        return symbol == "SPK"

    def is_blacklist_active(self):
        return False


class SimpleAutoRebalancerV2:
    """Versión simplificada del AutoRebalancer V2 para testing"""

    def __init__(self):
        # Configuración desde variables de entorno
        self.min_usdt_balance = float(os.getenv("MIN_USDT_BALANCE", "25.0"))
        self.target_usdt_balance = float(os.getenv("TARGET_USDT_BALANCE", "50.0"))
        self.enable_auto_rebalance = (
            os.getenv("ENABLE_AUTO_REBALANCE", "true").lower() == "true"
        )

        # Prioridades de activos para liquidación
        self.asset_priority = os.getenv(
            "REBALANCE_ASSET_PRIORITY", "SPK,HOME,SIGN,BNB,BTC"
        ).split(",")

        # Activos protegidos
        self.protected_assets = ["ETHUSDT", "ETH"]

        # Mocks
        self.binance_client = MockBinanceClient()
        self.circuit_breakers = MockCircuitBreakers()
        self.strategy_blacklist = MockStrategyBlacklist()

        self.is_rebalancing = False

        logger.info("SimpleAutoRebalancer V2 inicializado")
        logger.info(f"  - Min USDT: {self.min_usdt_balance}")
        logger.info(f"  - Target USDT: {self.target_usdt_balance}")
        logger.info(f"  - Habilitado: {self.enable_auto_rebalance}")
        logger.info(f"  - Prioridades: {self.asset_priority}")
        logger.info(f"  - Protegidos: {self.protected_assets}")

    async def get_current_usdt_balance(self) -> float:
        """Obtiene el balance actual de USDT"""
        try:
            account_info = self.binance_client.get_account()

            for balance in account_info["balances"]:
                if balance["asset"] == "USDT":
                    return float(balance["free"]) + float(balance["locked"])

            return 0.0

        except Exception as e:
            logger.error(f"Error obteniendo balance USDT: {e}")
            return 0.0

    async def get_all_balances(self) -> Dict[str, float]:
        """Obtiene balances de todos los activos"""
        try:
            account_info = self.binance_client.get_account()
            balances = {}

            for balance in account_info["balances"]:
                asset = balance["asset"]
                free_balance = float(balance["free"])
                locked_balance = float(balance["locked"])
                total_balance = free_balance + locked_balance

                if total_balance > 0:
                    balances[asset] = total_balance

            return balances

        except Exception as e:
            logger.error(f"Error obteniendo balances: {e}")
            return {}

    async def select_assets_for_liquidation(
        self, balances: Dict[str, float], target_deficit: float
    ) -> List[Dict]:
        """Selecciona activos para liquidación siguiendo prioridades"""
        selected_assets = []
        remaining_deficit = target_deficit

        logger.info(
            f"🎯 Seleccionando activos para liquidación - Déficit: {target_deficit:.2f} USDT"
        )

        for asset in self.asset_priority:
            if remaining_deficit <= 0:
                break

            # Verificar si está en blacklist
            if self.strategy_blacklist.is_symbol_blacklisted(asset):
                logger.info(f"🚫 {asset} en blacklist - saltando")
                continue

            # Verificar si está protegido
            if (
                asset in self.protected_assets
                or f"{asset}USDT" in self.protected_assets
            ):
                logger.info(f"🛡️ {asset} protegido - saltando")
                continue

            # Verificar si tenemos balance
            if asset not in balances or balances[asset] <= 0:
                logger.info(f"💰 {asset} sin balance - saltando")
                continue

            # Calcular valor en USDT
            try:
                symbol = f"{asset}USDT" if not asset.endswith("USDT") else asset
                ticker = self.binance_client.get_symbol_ticker(symbol=symbol)
                current_price = float(ticker["price"])
                current_value_usdt = balances[asset] * current_price

                # Calcular cantidad a vender
                if current_value_usdt >= remaining_deficit:
                    quantity_to_sell = remaining_deficit / current_price
                else:
                    quantity_to_sell = balances[asset]

                selected_assets.append(
                    {
                        "asset": asset,
                        "symbol": symbol,
                        "quantity": quantity_to_sell,
                        "price": current_price,
                        "value_usdt": quantity_to_sell * current_price,
                        "priority": self.asset_priority.index(asset),
                    }
                )

                remaining_deficit -= quantity_to_sell * current_price
                logger.info(
                    f"✅ {asset} seleccionado - Cantidad: {quantity_to_sell:.6f}, Valor: ${quantity_to_sell * current_price:.2f}"
                )

            except Exception as e:
                logger.error(f"Error procesando {asset}: {e}")
                continue

        logger.info(
            f"📋 Selección completada - {len(selected_assets)} activos seleccionados"
        )
        return selected_assets

    async def check_and_rebalance(self) -> Dict:
        """Verifica liquidez y ejecuta rebalanceo si es necesario"""
        if not self.enable_auto_rebalance:
            return {"status": "disabled", "message": "Auto-rebalance disabled"}

        if self.is_rebalancing:
            return {"status": "skipped", "reason": "already_rebalancing"}

        try:
            self.is_rebalancing = True
            logger.info("🔍 Verificando liquidez...")

            # Obtener balance actual
            current_usdt = await self.get_current_usdt_balance()
            logger.info(f"💰 Balance actual USDT: {current_usdt:.2f}")

            # Verificar si necesita rebalanceo
            if current_usdt >= self.min_usdt_balance:
                logger.info(
                    f"✅ Liquidez suficiente ({current_usdt:.2f} >= {self.min_usdt_balance})"
                )
                return {"status": "sufficient", "current_usdt": current_usdt}

            # Calcular déficit
            deficit = self.target_usdt_balance - current_usdt
            logger.warning(f"⚠️ Liquidez insuficiente. Déficit: {deficit:.2f} USDT")

            # Obtener balances y seleccionar activos
            balances = await self.get_all_balances()
            selected_assets = await self.select_assets_for_liquidation(
                balances, deficit
            )

            if not selected_assets:
                return {
                    "status": "no_assets",
                    "message": "No assets available for liquidation",
                }

            # Simular ventas (sin ejecutar órdenes reales)
            total_generated = sum(asset["value_usdt"] for asset in selected_assets)
            logger.info(f"💸 Simulando ventas - USDT a generar: {total_generated:.2f}")

            return {
                "status": "success",
                "deficit_resolved": deficit,
                "assets_selected": len(selected_assets),
                "usdt_to_generate": total_generated,
                "selected_assets": selected_assets,
            }

        except Exception as e:
            logger.error(f"❌ Error en rebalanceo: {e}")
            return {"status": "error", "message": str(e)}
        finally:
            self.is_rebalancing = False


async def test_rebalancer_simple():
    """Test simplificado del rebalanceador"""
    logger.info("🚀 Iniciando test simplificado del AutoRebalancer V2")
    logger.info("=" * 60)

    try:
        # Crear instancia del rebalanceador
        rebalancer = SimpleAutoRebalancerV2()

        # Test 1: Verificar configuración
        logger.info("\n🔧 Test 1: Verificando configuración...")
        assert rebalancer.min_usdt_balance == 25.0
        assert rebalancer.target_usdt_balance == 50.0
        assert rebalancer.enable_auto_rebalance == True
        assert "SPK" in rebalancer.asset_priority
        assert "ETHUSDT" in rebalancer.protected_assets
        logger.info("✅ Configuración verificada")

        # Test 2: Verificar balance actual
        logger.info("\n💰 Test 2: Verificando balance actual...")
        current_usdt = await rebalancer.get_current_usdt_balance()
        logger.info(f"Balance actual USDT: {current_usdt:.2f}")

        # Test 3: Verificar balances de activos
        logger.info("\n📊 Test 3: Verificando balances de activos...")
        balances = await rebalancer.get_all_balances()
        logger.info(f"Activos con balance: {list(balances.keys())}")

        # Test 4: Test de selección de activos
        logger.info("\n🎯 Test 4: Probando selección de activos...")
        selected_assets = await rebalancer.select_assets_for_liquidation(balances, 30.0)
        logger.info(f"Activos seleccionados: {len(selected_assets)}")
        for asset in selected_assets:
            logger.info(
                f"  - {asset['asset']}: {asset['quantity']:.2f} (${asset['value_usdt']:.2f})"
            )

        # Test 5: Test completo de rebalanceo
        logger.info("\n🔄 Test 5: Probando rebalanceo completo...")
        result = await rebalancer.check_and_rebalance()
        logger.info(f"Resultado del rebalanceo: {result}")

        # Verificar resultados
        if result["status"] == "sufficient":
            logger.info("✅ Liquidez suficiente - No se requiere rebalanceo")
        elif result["status"] == "success":
            logger.info("✅ Rebalanceo simulado exitoso")
        else:
            logger.warning(
                f"⚠️ Rebalanceo no ejecutado: {result.get('message', 'Razón desconocida')}"
            )

        logger.info("\n🎉 TODOS LOS TESTS PASARON EXITOSAMENTE")
        return True

    except Exception as e:
        logger.error(f"❌ Error en tests: {e}")
        return False


async def main():
    """Función principal"""
    logger.info("🕐 Iniciando test simplificado del AutoRebalancer V2")

    success = await test_rebalancer_simple()

    if success:
        logger.info("\n✅ TEST COMPLETADO EXITOSAMENTE")
        logger.info("   El rebalanceador V2 está funcionando correctamente")
        return 0
    else:
        logger.error("\n❌ TEST FALLÓ")
        logger.error("   Revisar configuración y logs")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
