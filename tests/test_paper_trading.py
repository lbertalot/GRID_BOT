import pytest
import os
from binance import Client
from unittest.mock import patch
from app.services.grid_strategy import calculate_grid_levels, decide_grid_action
from app.services.strategies.scalping import scalping_strategy
from app.services.strategies.trailing_stop import trailing_stop_strategy


class TestPaperTrading:
    """Tests de paper trading - simulación de órdenes sin ejecutarlas"""

    @pytest.fixture
    def binance_client(self):
        """Fixture para crear cliente de Binance"""
        api_key = os.getenv("BINANCE_API_KEY")
        api_secret = os.getenv("BINANCE_API_SECRET")

        if not api_key or not api_secret:
            pytest.skip("Credenciales de Binance no configuradas")

        return Client(api_key, api_secret)

    def test_grid_strategy_simulation(self, binance_client):
        """Test de simulación de estrategia grid"""
        symbol = "BTCUSDT"

        try:
            # Obtener precio actual
            ticker = binance_client.get_symbol_ticker(symbol=symbol)
            current_price = float(ticker["price"])

            # Configurar parámetros de grid
            min_price = current_price * 0.95  # 5% abajo del precio actual
            max_price = current_price * 1.05  # 5% arriba del precio actual
            grids = 5
            quantity = 0.001

            print("📊 Simulando Grid Strategy:")
            print(f"   Símbolo: {symbol}")
            print(f"   Precio actual: ${current_price}")
            print(f"   Rango: ${min_price:.2f} - ${max_price:.2f}")
            print(f"   Grids: {grids}")
            print(f"   Cantidad: {quantity}")

            # Calcular niveles de grid
            grid_levels = calculate_grid_levels(min_price, max_price, grids)
            print(
                f"   Niveles calculados: {[f'${level:.2f}' for level in grid_levels]}"
            )

            # Simular decisión de trading
            decision = decide_grid_action(current_price, grid_levels, None)
            print(f"   Decisión: {decision}")

            # Validar resultados
            assert len(grid_levels) == grids
            assert min(grid_levels) >= min_price
            assert max(grid_levels) <= max_price
            assert decision is not None

            print("✅ Simulación de Grid Strategy completada")

        except Exception as e:
            pytest.fail(f"Error en simulación de grid strategy: {e}")

    def test_scalping_strategy_simulation(self):
        """Test de simulación de estrategia scalping"""
        # Simular histórico de precios
        price_history = [100, 99, 98, 97, 96, 95, 94, 93, 92, 91]
        balances = {"USDT": 1000, "BTC": 0.01}
        params = {"profit_target": 0.002, "lookback": 3}

        print("📊 Simulando Scalping Strategy:")
        print(f"   Histórico de precios: {price_history}")
        print(f"   Balances: {balances}")
        print(f"   Parámetros: {params}")

        # Ejecutar estrategia
        result = scalping_strategy(
            price_history=price_history, balances=balances, params=params
        )

        print(f"   Resultado: {result}")

        # Validar resultado
        assert "action" in result
        assert result["action"] in ["BUY", "SELL", "HOLD"]
        assert "quantity" in result
        assert "reason" in result

        print("✅ Simulación de Scalping Strategy completada")

    def test_trailing_stop_strategy_simulation(self):
        """Test de simulación de estrategia trailing stop"""
        # Simular histórico de precios con tendencia
        price_history = [100, 102, 105, 108, 110, 112, 115, 118, 120, 122]
        balances = {"BTC": 0.01}
        params = {"trailing_pct": 0.05}

        print("📊 Simulando Trailing Stop Strategy:")
        print(f"   Histórico de precios: {price_history}")
        print(f"   Balances: {balances}")
        print(f"   Parámetros: {params}")

        # Ejecutar estrategia
        result = trailing_stop_strategy(
            price_history=price_history, balances=balances, params=params
        )

        print(f"   Resultado: {result}")

        # Validar resultado
        assert "action" in result
        assert result["action"] in ["BUY", "SELL", "HOLD"]
        assert "quantity" in result
        assert "reason" in result

        print("✅ Simulación de Trailing Stop Strategy completada")

    @patch("binance.Client.order_market_buy")
    @patch("binance.Client.order_market_sell")
    def test_order_simulation(self, mock_sell, mock_buy, binance_client):
        """Test de simulación de órdenes (mocked)"""
        # Configurar mocks
        mock_buy.return_value = {
            "symbol": "BTCUSDT",
            "orderId": 12345,
            "status": "FILLED",
            "fills": [{"price": "50000", "qty": "0.001"}],
        }
        mock_sell.return_value = {
            "symbol": "BTCUSDT",
            "orderId": 12346,
            "status": "FILLED",
            "fills": [{"price": "50100", "qty": "0.001"}],
        }

        print("📊 Simulando órdenes de trading:")

        # Simular orden de compra
        try:
            buy_result = binance_client.order_market_buy(
                symbol="BTCUSDT", quantity=0.001
            )
            print(f"   Orden de compra simulada: {buy_result}")
            assert buy_result["status"] == "FILLED"
        except Exception as e:
            pytest.fail(f"Error simulando orden de compra: {e}")

        # Simular orden de venta
        try:
            sell_result = binance_client.order_market_sell(
                symbol="BTCUSDT", quantity=0.001
            )
            print(f"   Orden de venta simulada: {sell_result}")
            assert sell_result["status"] == "FILLED"
        except Exception as e:
            pytest.fail(f"Error simulando orden de venta: {e}")

        # Verificar que los mocks fueron llamados
        mock_buy.assert_called_once()
        mock_sell.assert_called_once()

        print("✅ Simulación de órdenes completada")

    def test_risk_management_simulation(self):
        """Test de simulación de gestión de riesgo"""
        print("📊 Simulando gestión de riesgo:")

        # Simular diferentes escenarios
        scenarios = [
            {
                "name": "Pérdida máxima tolerable",
                "initial_balance": 1000,
                "max_loss_pct": 0.02,  # 2%
                "max_loss_amount": 20,
            },
            {
                "name": "Take profit objetivo",
                "initial_balance": 1000,
                "take_profit_pct": 0.05,  # 5%
                "take_profit_amount": 50,
            },
            {
                "name": "Stop loss automático",
                "initial_balance": 1000,
                "stop_loss_pct": 0.03,  # 3%
                "stop_loss_amount": 30,
            },
        ]

        for scenario in scenarios:
            print(f"   Escenario: {scenario['name']}")
            print(f"     Balance inicial: ${scenario['initial_balance']}")

            if "max_loss_pct" in scenario:
                max_loss = scenario["initial_balance"] * scenario["max_loss_pct"]
                print(
                    f"     Pérdida máxima: ${max_loss:.2f} ({scenario['max_loss_pct']*100}%)"
                )

            if "take_profit_pct" in scenario:
                take_profit = scenario["initial_balance"] * scenario["take_profit_pct"]
                print(
                    f"     Take profit: ${take_profit:.2f} ({scenario['take_profit_pct']*100}%)"
                )

            if "stop_loss_pct" in scenario:
                stop_loss = scenario["initial_balance"] * scenario["stop_loss_pct"]
                print(
                    f"     Stop loss: ${stop_loss:.2f} ({scenario['stop_loss_pct']*100}%)"
                )

        print("✅ Simulación de gestión de riesgo completada")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
