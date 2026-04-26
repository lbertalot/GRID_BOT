"""
Tests para TradeExecutor - Bug #1 Fix
GridBot v2.5

Tests de integración para verificar que TradeExecutor:
1. Ejecuta órdenes correctamente
2. Actualiza balances con BalanceService
3. Guarda trades en DB
4. Maneja errores de concurrencia
"""

import pytest
from decimal import Decimal
from unittest.mock import Mock, patch

from app.services.trade_executor import TradeExecutor, get_trade_executor


@pytest.fixture
def mock_binance_client():
    """Mock del cliente Binance"""
    client = Mock()
    client.create_order = Mock(
        return_value={
            "symbol": "BTCUSDT",
            "orderId": 12345,
            "clientOrderId": "test_order_123",
            "status": "FILLED",
            "executedQty": "0.001",
            "cummulativeQuoteQty": "50.00",
            "fills": [{"price": "50000.00", "qty": "0.001"}],
        }
    )
    return client


@pytest.fixture
def trade_executor(mock_binance_client):
    """TradeExecutor con mocks"""
    executor = TradeExecutor()
    executor.binance_client = mock_binance_client
    return executor


class TestTradeExecutor:
    """Test suite para TradeExecutor"""

    def test_get_trade_executor_singleton(self):
        """Verificar que get_trade_executor retorna la misma instancia"""
        executor1 = get_trade_executor()
        executor2 = get_trade_executor()
        assert executor1 is executor2

    def test_execute_market_buy_success(self, trade_executor, mock_binance_client):
        """Test: Ejecutar market buy exitosamente"""
        symbol = "BTCUSDT"
        quantity = Decimal("0.001")

        with patch("app.services.trade_executor.SessionLocal"):
            with patch(
                "app.services.trade_executor.BalanceService.update_balance"
            ) as mock_update_balance:
                mock_update_balance.return_value = None
                result = trade_executor.execute_market_buy(symbol, quantity)

            # Verificar llamada a Binance
            mock_binance_client.create_order.assert_called_once()

            # Verificar actualización de balances
            assert mock_update_balance.call_count == 2

            # Verificar resultado
            assert result["status"] == "FILLED"
            assert result["symbol"] == "BTCUSDT"

    def test_execute_market_sell_success(self, trade_executor, mock_binance_client):
        """Test: Ejecutar market sell exitosamente"""
        symbol = "ETHUSDT"
        quantity = Decimal("0.01")

        mock_binance_client.create_order.return_value = {
            "symbol": "ETHUSDT",
            "orderId": 67890,
            "clientOrderId": "test_order_456",
            "status": "FILLED",
            "executedQty": "0.01",
            "cummulativeQuoteQty": "30.00",
            "fills": [{"price": "3000.00", "qty": "0.01"}],
        }

        with patch("app.services.trade_executor.SessionLocal"):
            with patch(
                "app.services.trade_executor.BalanceService.update_balance"
            ) as mock_update_balance:
                mock_update_balance.return_value = None
                result = trade_executor.execute_market_sell(symbol, quantity)

            # Verificar actualización de balances (inverso de buy)
            assert mock_update_balance.call_count == 2  # +USDT, -ETH

            # Verificar resultado
            assert result["status"] == "FILLED"

    def test_execute_order_with_balance_update_error_does_not_fail_order(
        self, trade_executor
    ):
        """Si falla update de balances, la orden ejecutada aún se retorna."""
        with patch(
            "app.services.trade_executor.BalanceService.update_balance"
        ) as mock_update_balance:
            mock_update_balance.side_effect = Exception("balance update failed")
            with patch("app.services.trade_executor.SessionLocal"):
                result = trade_executor.execute_market_buy("BTCUSDT", Decimal("0.001"))
        assert "orderId" in result

    def test_execute_order_binance_error(self, trade_executor, mock_binance_client):
        """Test: Manejar error de Binance API"""
        # Simular error de Binance
        mock_binance_client.create_order.side_effect = Exception("Binance API Error")

        with patch("app.services.trade_executor.SessionLocal"):
            with pytest.raises(Exception, match="Binance API Error"):
                trade_executor.execute_market_buy("BTCUSDT", Decimal("0.001"))

    def test_execute_order_passes_extra_kwargs(self, trade_executor):
        """Verificar que kwargs extras se pasan a create_order."""
        with patch("app.services.trade_executor.SessionLocal"):
            trade_executor.execute_order(
                symbol="BTCUSDT",
                side="BUY",
                order_type="MARKET",
                quantity=Decimal("0.001"),
                newClientOrderId="UNIQUE_ORDER_123",
            )
        call_kwargs = trade_executor.binance_client.create_order.call_args[1]
        assert call_kwargs.get("newClientOrderId") == "UNIQUE_ORDER_123"

    def test_balance_updates_are_called_in_expected_order(self, trade_executor):
        """Test: Verificar que updates de balance son atómicos"""
        update_calls = []

        def track_updates(*args):
            asset, amount = args[1], args[2]
            update_calls.append((asset, amount))

        with patch(
            "app.services.trade_executor.BalanceService.update_balance"
        ) as mock_update_balance:
            mock_update_balance.side_effect = track_updates
            with patch("app.services.trade_executor.SessionLocal"):
                trade_executor.execute_market_buy("BTCUSDT", Decimal("0.001"))

            # Verificar que ambos updates se llamaron en orden
            assert len(update_calls) == 2
            # Primero -USDT
            assert update_calls[0][0] == "USDT"
            assert update_calls[0][1] < 0
            # Luego +BTC
            assert update_calls[1][0] == "BTC"
            assert update_calls[1][1] > 0

    def test_default_recv_window_is_set(self, trade_executor):
        """Test: recvWindow por defecto se inyecta en create_order."""
        with patch("app.services.trade_executor.SessionLocal"):
            trade_executor.execute_market_buy("BTCUSDT", Decimal("0.001"))
        call_kwargs = trade_executor.binance_client.create_order.call_args[1]
        assert call_kwargs.get("recvWindow") == 10000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
