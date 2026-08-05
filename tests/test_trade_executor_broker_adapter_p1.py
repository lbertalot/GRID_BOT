"""P1: TradeExecutor opcional vía BrokerAdapter (USE_BROKER_ADAPTER)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.broker_adapter.types import BrokerMarketOrderRequest, BrokerOrderAck
from app.services.trade_executor import TradeExecutor


def _filled() -> Dict[str, Any]:
    return {
        "orderId": 99,
        "clientOrderId": "x",
        "symbol": "BTCUSDT",
        "status": "FILLED",
        "executedQty": "0.001",
        "fills": [
            {
                "qty": "0.001",
                "price": "50000.00",
                "commission": "0.05",
                "commissionAsset": "USDT",
            }
        ],
    }


@pytest.fixture
def executor_legacy_client() -> tuple[TradeExecutor, MagicMock]:
    executor = TradeExecutor()
    mock_client = MagicMock()
    executor.binance_client = mock_client
    return executor, mock_client


def test_market_order_legacy_when_adapter_flag_off(
    executor_legacy_client: tuple[TradeExecutor, MagicMock],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("USE_BROKER_ADAPTER", raising=False)
    executor, mock_client = executor_legacy_client
    mock_client.create_order.return_value = _filled()

    with patch("app.services.trade_executor.BalanceService.update_balance"):
        with patch("app.services.trade_executor.SessionLocal") as mock_session:
            mock_session.return_value = MagicMock()
            executor.execute_order("BTCUSDT", "BUY", "MARKET", "0.001")

    mock_client.create_order.assert_called_once()
    call_kw = mock_client.create_order.call_args.kwargs
    assert call_kw["order_type"] == "MARKET"


def test_market_order_adapter_path_invokes_place_market(
    executor_legacy_client: tuple[TradeExecutor, MagicMock],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("USE_BROKER_ADAPTER", "true")
    monkeypatch.setenv("BROKER_PRIMARY_VENUE", "binance_spot")
    executor, mock_client = executor_legacy_client

    async def _place(req: BrokerMarketOrderRequest) -> BrokerOrderAck:
        assert req.symbol_code == "BTCUSDT"
        assert req.side == "BUY"
        assert req.quantity_base == Decimal("0.001")
        assert req.client_order_id == "idem-1"
        assert req.recv_window_ms == 10000
        return BrokerOrderAck(
            venue_order_id="99",
            status="FILLED",
            symbol_code="BTCUSDT",
            side="BUY",
            raw=_filled(),
        )

    mock_ad = MagicMock()
    mock_ad.place_market_order = AsyncMock(side_effect=_place)

    with patch(
        "app.services.trade_executor.create_broker_adapter_from_env",
        return_value=mock_ad,
    ):
        with patch("app.services.trade_executor.BalanceService.update_balance"):
            with patch("app.services.trade_executor.SessionLocal") as mock_session:
                mock_session.return_value = MagicMock()
                executor.execute_order(
                    "BTCUSDT",
                    "BUY",
                    "MARKET",
                    "0.001",
                    newClientOrderId="idem-1",
                )

    mock_ad.place_market_order.assert_awaited_once()
    mock_client.create_order.assert_not_called()


def test_market_extra_kwarg_forces_legacy(
    executor_legacy_client: tuple[TradeExecutor, MagicMock],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("USE_BROKER_ADAPTER", "true")
    executor, mock_client = executor_legacy_client
    mock_client.create_order.return_value = _filled()

    with patch(
        "app.services.trade_executor.create_broker_adapter_from_env",
    ) as mock_factory:
        with patch("app.services.trade_executor.BalanceService.update_balance"):
            with patch("app.services.trade_executor.SessionLocal") as mock_session:
                mock_session.return_value = MagicMock()
                executor.execute_order(
                    "BTCUSDT",
                    "BUY",
                    "MARKET",
                    "0.001",
                    timeInForce="GTC",
                )

    mock_factory.assert_not_called()
    mock_client.create_order.assert_called_once()


def test_adapter_1021_falls_back_to_legacy(
    executor_legacy_client: tuple[TradeExecutor, MagicMock],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("USE_BROKER_ADAPTER", "true")
    executor, mock_client = executor_legacy_client
    mock_client.create_order.return_value = _filled()

    mock_ad = MagicMock()
    mock_ad.place_market_order = AsyncMock(
        side_effect=Exception("APIError(code=-1021): Timestamp outside")
    )

    with patch(
        "app.services.trade_executor.create_broker_adapter_from_env",
        return_value=mock_ad,
    ):
        with patch("app.services.trade_executor.BalanceService.update_balance"):
            with patch("app.services.trade_executor.SessionLocal") as mock_session:
                mock_session.return_value = MagicMock()
                executor.execute_order("BTCUSDT", "BUY", "MARKET", "0.001")

    mock_client.create_order.assert_called_once()
