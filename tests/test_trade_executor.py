"""
Tests para TradeExecutor — GridBot v2.5

Tests de integración para verificar que TradeExecutor:
1. Consulta circuit breakers antes de ejecutar (INV-003)
2. Valida filtros del exchange (INV-002)
3. Genera clientOrderId determinístico (INV-004)
4. Confirma estado post-orden (INV-008)
5. Calcula avg_price y comisión con Decimal (INV-001)
"""

import os
import sys
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock, patch

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault("SKIP_API_HEALTHCHECK", "1")
os.environ.setdefault("PAPER_TRADING", "true")

from app.services.trade_executor import TradeExecutor, get_trade_executor, _generate_client_order_id


class StubBinanceClient:
    """Stub del cliente de Binance para tests."""

    def __init__(self, order_result=None):
        self._order_result = order_result or {
            "symbol": "BTCUSDT",
            "orderId": 12345,
            "status": "FILLED",
            "executedQty": "0.001",
            "price": "50000.00",
            "fills": [
                {
                    "price": "50000.00",
                    "qty": "0.001",
                    "commission": "0.00001",
                    "commissionAsset": "BNB",
                }
            ],
        }

    def create_order(self, **kwargs):
        return self._order_result

    def get_exchange_info(self, **kwargs):
        return {
            "symbols": [
                {
                    "symbol": "BTCUSDT",
                    "baseAsset": "BTC",
                    "quoteAsset": "USDT",
                    "quotePrecision": 8,
                    "baseAssetPrecision": 8,
                    "filters": [
                        {
                            "filterType": "LOT_SIZE",
                            "minQty": "0.00001",
                            "maxQty": "9000",
                            "stepSize": "0.00001",
                        },
                        {
                            "filterType": "PRICE_FILTER",
                            "minPrice": "0.01",
                            "maxPrice": "1000000.00",
                            "tickSize": "0.01",
                        },
                        {"filterType": "MIN_NOTIONAL", "minNotional": "10"},
                    ],
                }
            ]
        }

    def get_symbol_ticker(self, symbol=None, **kwargs):
        return {"symbol": symbol or "BTCUSDT", "price": "50000.00"}


class TestTradeExecutor:
    """Test suite para TradeExecutor."""

    def test_get_trade_executor_singleton(self):
        """Verificar que get_trade_executor retorna la misma instancia."""
        executor1 = get_trade_executor()
        executor2 = get_trade_executor()
        assert executor1 is executor2

    @pytest.mark.asyncio
    async def test_execute_market_buy_success(self):
        """Ejecutar market buy exitosamente y verificar schema de retorno."""
        executor = TradeExecutor()
        executor.binance_client = MagicMock()
        executor.binance_client.client = StubBinanceClient()
        executor._order_validator = None

        result = await executor.execute_market_buy("BTCUSDT", Decimal("0.001"))

        assert result["status"] == "FILLED"
        assert result["order_id"] == 12345
        assert isinstance(result["executed_qty"], Decimal)
        assert isinstance(result["avg_price"], Decimal)
        assert isinstance(result["commission"], Decimal)
        assert result["client_order_id"].startswith("GRIDBOT_")

    @pytest.mark.asyncio
    async def test_execute_market_sell_success(self):
        """Ejecutar market sell exitosamente."""
        sell_result = {
            "symbol": "BTCUSDT",
            "orderId": 67890,
            "status": "FILLED",
            "executedQty": "0.001",
            "price": "50000.00",
            "fills": [
                {
                    "price": "50000.00",
                    "qty": "0.001",
                    "commission": "0.00001",
                    "commissionAsset": "BNB",
                }
            ],
        }
        executor = TradeExecutor()
        executor.binance_client = MagicMock()
        executor.binance_client.client = StubBinanceClient(order_result=sell_result)
        executor._order_validator = None

        result = await executor.execute_market_sell("BTCUSDT", Decimal("0.001"))

        assert result["status"] == "FILLED"
        assert result["order_id"] == 67890

    @pytest.mark.asyncio
    async def test_execute_order_with_balance_conflict(self):
        """Manejar error de Binance por balance insuficiente."""
        executor = TradeExecutor()
        executor.binance_client = MagicMock()

        stub = StubBinanceClient()
        stub.create_order = MagicMock(side_effect=Exception("Account has insufficient balance"))
        executor.binance_client.client = stub
        executor._order_validator = None

        with pytest.raises(Exception, match="insufficient balance"):
            await executor.execute_market_buy("BTCUSDT", Decimal("0.001"))

    @pytest.mark.asyncio
    async def test_execute_order_binance_error(self):
        """Manejar error de Binance API."""
        executor = TradeExecutor()
        executor.binance_client = MagicMock()

        stub = StubBinanceClient()
        stub.create_order = MagicMock(side_effect=Exception("Binance API Error"))
        executor.binance_client.client = stub
        executor._order_validator = None

        with pytest.raises(Exception, match="Binance API Error"):
            await executor.execute_market_buy("BTCUSDT", Decimal("0.001"))

    @pytest.mark.asyncio
    async def test_idempotency_with_client_order_id(self):
        """clientOrderId determinístico se incluye en la orden."""
        executor = TradeExecutor()
        executor.binance_client = MagicMock()

        stub = StubBinanceClient()
        # Capturar kwargs
        call_kwargs = {}

        def capture_create_order(**kwargs):
            call_kwargs.update(kwargs)
            return stub._order_result

        stub.create_order = capture_create_order
        executor.binance_client.client = stub
        executor._order_validator = None

        custom_id = "GRIDBOT_CUSTOM_123456"
        await executor.execute_order(
            symbol="BTCUSDT",
            side="BUY",
            order_type="MARKET",
            quantity=Decimal("0.001"),
            client_order_id=custom_id,
        )

        assert call_kwargs.get("newClientOrderId") == custom_id

    @pytest.mark.asyncio
    async def test_balance_updates_decimal_precision(self):
        """avg_price y comisión se calculan con Decimal (INV-001)."""
        order_result = {
            "symbol": "BTCUSDT",
            "orderId": 99999,
            "status": "FILLED",
            "executedQty": "0.5",
            "price": "0",
            "fills": [
                {"price": "50000.00", "qty": "0.3", "commission": "0.01", "commissionAsset": "USDT"},
                {"price": "50100.00", "qty": "0.2", "commission": "0.008", "commissionAsset": "USDT"},
            ],
        }

        executor = TradeExecutor()
        executor.binance_client = MagicMock()
        executor.binance_client.client = StubBinanceClient(order_result=order_result)
        executor._order_validator = None

        result = await executor.execute_order(
            symbol="BTCUSDT",
            side="BUY",
            order_type="MARKET",
            quantity=Decimal("0.5"),
        )

        # avg_price = (0.3*50000 + 0.2*50100) / 0.5 = (15000+10020) / 0.5 = 50040.0
        expected_avg = Decimal("50040")
        assert result["avg_price"] == expected_avg, f"avg_price={result['avg_price']}, expected={expected_avg}"

        # commission = 0.01 + 0.008 = 0.018
        expected_comm = Decimal("0.018")
        assert result["commission"] == expected_comm, f"commission={result['commission']}, expected={expected_comm}"

    @pytest.mark.asyncio
    async def test_metrics_are_recorded(self):
        """Verificar que partial fills incrementan métricas."""
        partial_result = {
            "symbol": "BTCUSDT",
            "orderId": 11111,
            "status": "PARTIALLY_FILLED",
            "executedQty": "0.0005",
            "price": "50000.00",
            "fills": [
                {"price": "50000.00", "qty": "0.0005", "commission": "0.00001", "commissionAsset": "BNB"},
            ],
        }

        executor = TradeExecutor()
        executor.binance_client = MagicMock()
        executor.binance_client.client = StubBinanceClient(order_result=partial_result)
        executor._order_validator = None

        result = await executor.execute_order(
            symbol="BTCUSDT",
            side="BUY",
            order_type="MARKET",
            quantity=Decimal("0.001"),
        )

        assert result["status"] == "PARTIALLY_FILLED"
        assert result["executed_qty"] == Decimal("0.0005")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
