"""
Test para validar las optimizaciones del rebalanceador automático
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock

from app.services.auto_rebalancer_v2 import AutoRebalancerV2


class TestRebalancerOptimization:
    """Tests para validar las correcciones del rebalanceador"""

    @pytest.fixture
    def mock_binance_client(self):
        """Mock del cliente de Binance"""
        client = Mock()

        # Mock para get_symbol_ticker
        client.get_symbol_ticker.side_effect = lambda symbol: {
            "price": "0.04"
            if "SPK" in symbol
            else "1046.34"
            if "BNB" in symbol
            else "100.0"
        }

        # Mock para get_symbol_info
        client.get_symbol_info.side_effect = lambda symbol: {
            "filters": [
                {
                    "filterType": "LOT_SIZE",
                    "minQty": "1.0",
                    "maxQty": "913205152.0",
                    "stepSize": "1.0",
                },
                {"filterType": "MIN_NOTIONAL", "minNotional": "10.0"},
            ]
        }

        return client

    @pytest.fixture
    def rebalancer(self, mock_binance_client):
        """Instancia del rebalanceador con mocks"""
        with patch(
            "app.services.auto_rebalancer_v2.get_binance_client_singleton"
        ) as mock_singleton:
            mock_singleton.return_value.client = mock_binance_client

            # Mock para strategy blacklist
            with patch(
                "app.services.auto_rebalancer_v2.StrategyBlacklist"
            ) as mock_blacklist:
                mock_blacklist.return_value.is_symbol_blacklisted.return_value = False

                rebalancer = AutoRebalancerV2()
                return rebalancer

    @pytest.mark.asyncio
    async def test_asset_priority_selection(self, rebalancer):
        """Si un activo no cumple filtros, se selecciona el siguiente válido por prioridad."""
        # Simular balances con SPK y BNB
        balances = {"SPK": 0.14068269, "BNB": 0.00343048, "USDT": 17.29}

        target_deficit = 20.0

        # Ejecutar selección de activos
        selected_assets = await rebalancer._select_assets_for_liquidation(
            balances, target_deficit
        )

        assert len(selected_assets) > 0, "Debe seleccionar al menos un activo"
        assert selected_assets[0]["asset"] == "BNB"

    @pytest.mark.asyncio
    async def test_quantity_validation_fix(self, rebalancer):
        """Si no cumple MIN_NOTIONAL debe invalidarse aunque se ajuste cantidad mínima."""
        # Test con cantidad muy pequeña que antes se redondeaba a 0
        symbol = "SPKUSDT"
        quantity = 0.5  # Menor que step_size de 1.0

        is_valid = await rebalancer._validate_sale_parameters(symbol, quantity)
        assert not is_valid

    @pytest.mark.asyncio
    async def test_rebalance_with_improved_logging(self, rebalancer):
        """Test que el rebalanceo incluye logging mejorado"""
        # Mock para get_current_usdt_balance
        rebalancer._get_current_usdt_balance = AsyncMock(return_value=17.29)

        # Mock para _get_all_balances
        rebalancer._get_all_balances = AsyncMock(
            return_value={"SPK": 0.14068269, "BNB": 0.00343048, "USDT": 17.29}
        )

        # Mock para _execute_sales
        rebalancer._execute_sales = AsyncMock(
            return_value=[
                {
                    "status": "success",
                    "symbol": "SPKUSDT",
                    "pnl": 0.05,
                    "quantity": 0.14068269,
                    "value_usdt": 5.63,
                }
            ]
        )

        # Ejecutar rebalanceo
        result = await rebalancer._execute_liquidity_rebalance(20.0)

        # Verificar que incluye información de logging mejorado
        assert "initial_usdt_balance" in result
        assert "final_usdt_balance" in result
        assert "total_pnl" in result
        assert result["status"] == "success"

    def test_calibration_mode_parameters(self):
        """Test que los nuevos parámetros de calibración están configurados"""
        # Verificar que las constantes están actualizadas
        from app.services.trading_tasks import (
            MIN_DECISION_CONFIDENCE,
            SAFE_MIN_USDT,
            CALIBRATION_MODE,
        )

        assert MIN_DECISION_CONFIDENCE == 0.50, "Confianza mínima debe ser 0.50"
        assert SAFE_MIN_USDT == 15.0, "USDT mínimo debe ser 15.0"
        assert isinstance(CALIBRATION_MODE, bool), "CALIBRATION_MODE debe ser booleano"

    @pytest.mark.asyncio
    async def test_rebalance_priority_order(self, rebalancer):
        """Test que el orden de prioridades se respeta correctamente"""
        # Configurar prioridades
        expected_priority = ["SPK", "HOME", "SIGN", "BNB", "BTC"]
        assert (
            rebalancer.asset_priority == expected_priority
        ), "Prioridades deben coincidir"

        # Test con múltiples activos disponibles
        balances = {
            "SPK": 0.14068269,
            "HOME": 12.03942478,
            "BNB": 0.00343048,
            "USDT": 17.29,
        }

        selected_assets = await rebalancer._select_assets_for_liquidation(
            balances, 50.0
        )

        # SPK no cumple MIN_NOTIONAL, HOME sí cumple y debe quedar primero seleccionado
        if selected_assets:
            first_asset = selected_assets[0]["asset"]
            assert (
                first_asset == "HOME"
            ), f"Primer activo válido debe ser HOME, no {first_asset}"


if __name__ == "__main__":
    # Ejecutar tests específicos
    pytest.main([__file__, "-v"])
