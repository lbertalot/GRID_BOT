"""P1: POST /order MARKET y capa BrokerAdapter (``USE_BROKER_ADAPTER``)."""

from __future__ import annotations

from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api import trade as trade_module


def _filled() -> Dict[str, Any]:
    return {
        "orderId": 1,
        "status": "FILLED",
        "fills": [{"price": "50000", "qty": "0.001"}],
    }


@pytest.fixture
def api_headers(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    monkeypatch.setenv("API_KEY", "test-api-key")
    return {"Authorization": "Bearer test-api-key"}


def test_place_order_market_prefers_adapter_when_flag_on(
    api_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BINANCE_API_KEY", "k")
    monkeypatch.setenv("BINANCE_SECRET_KEY", "s")
    monkeypatch.setenv("USE_BROKER_ADAPTER", "true")
    monkeypatch.setenv("BROKER_PRIMARY_VENUE", "binance_spot")

    mock_client = MagicMock()
    mock_client.get_symbol_ticker.return_value = {"price": "50000"}
    mock_db = MagicMock()

    async def _adapter(**kwargs: Any) -> Dict[str, Any]:
        assert kwargs["symbol"] == "BTCUSDT"
        assert kwargs["client_order_id"] == "cid-test"
        return _filled()

    with patch.object(trade_module, "Client", return_value=mock_client):
        with patch.object(trade_module, "OrderValidator") as mock_validator_cls:
            mock_validator_cls.return_value.validate_order_parameters.return_value = {
                "is_valid": True,
                "recommended_quantity": 0.001,
                "errors": [],
            }
            with patch.object(
                trade_module._operation_tracker,
                "generate_client_order_id",
                return_value="cid-test",
            ):
                with patch.object(
                    trade_module._operation_tracker,
                    "track_operation",
                    new_callable=AsyncMock,
                ):
                    with patch.object(
                        trade_module._operation_tracker,
                        "update_operation_status",
                        new_callable=AsyncMock,
                    ):
                        with patch.object(trade_module, "log_trade"):
                            with patch.object(trade_module, "send_telegram_alert"):
                                with patch.object(
                                    trade_module,
                                    "place_spot_market_via_adapter",
                                    new_callable=AsyncMock,
                                    side_effect=_adapter,
                                ) as mock_adapter:
                                    app.dependency_overrides[trade_module.get_db] = (
                                        lambda: mock_db
                                    )
                                    try:
                                        client = TestClient(
                                            app, base_url="http://localhost"
                                        )
                                        response = client.post(
                                            "/api/trade/order",
                                            json={
                                                "symbol": "BTCUSDT",
                                                "side": "BUY",
                                                "quantity": 0.001,
                                                "type": "MARKET",
                                            },
                                            headers=api_headers,
                                        )
                                    finally:
                                        app.dependency_overrides.clear()

    assert response.status_code == 200
    mock_adapter.assert_awaited_once()
    mock_client.order_market_buy.assert_not_called()


def test_place_order_market_fallback_on_timestamp_1021(
    api_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BINANCE_API_KEY", "k")
    monkeypatch.setenv("BINANCE_SECRET_KEY", "s")
    monkeypatch.setenv("USE_BROKER_ADAPTER", "true")
    monkeypatch.setenv("BROKER_PRIMARY_VENUE", "binance_spot")

    mock_client = MagicMock()
    mock_client.get_symbol_ticker.return_value = {"price": "50000"}
    mock_client.order_market_buy.return_value = _filled()
    mock_db = MagicMock()

    with patch.object(trade_module, "Client", return_value=mock_client):
        with patch.object(trade_module, "OrderValidator") as mock_validator_cls:
            mock_validator_cls.return_value.validate_order_parameters.return_value = {
                "is_valid": True,
                "recommended_quantity": 0.001,
                "errors": [],
            }
            with patch.object(
                trade_module._operation_tracker,
                "generate_client_order_id",
                return_value="cid-fallback",
            ):
                with patch.object(
                    trade_module._operation_tracker,
                    "track_operation",
                    new_callable=AsyncMock,
                ):
                    with patch.object(
                        trade_module._operation_tracker,
                        "update_operation_status",
                        new_callable=AsyncMock,
                    ):
                        with patch.object(trade_module, "log_trade"):
                            with patch.object(trade_module, "send_telegram_alert"):
                                with patch.object(
                                    trade_module,
                                    "place_spot_market_via_adapter",
                                    new_callable=AsyncMock,
                                    side_effect=Exception(
                                        "Binance API error -1021 timestamp"
                                    ),
                                ):
                                    app.dependency_overrides[trade_module.get_db] = (
                                        lambda: mock_db
                                    )
                                    try:
                                        client = TestClient(
                                            app, base_url="http://localhost"
                                        )
                                        response = client.post(
                                            "/api/trade/order",
                                            json={
                                                "symbol": "BTCUSDT",
                                                "side": "BUY",
                                                "quantity": 0.001,
                                                "type": "MARKET",
                                            },
                                            headers=api_headers,
                                        )
                                    finally:
                                        app.dependency_overrides.clear()

    assert response.status_code == 200
    mock_client.order_market_buy.assert_called_once()


def test_place_order_market_skips_adapter_when_flag_off(
    api_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BINANCE_API_KEY", "k")
    monkeypatch.setenv("BINANCE_SECRET_KEY", "s")
    monkeypatch.delenv("USE_BROKER_ADAPTER", raising=False)

    mock_client = MagicMock()
    mock_client.get_symbol_ticker.return_value = {"price": "50000"}
    mock_client.order_market_buy.return_value = _filled()
    mock_db = MagicMock()

    with patch.object(trade_module, "Client", return_value=mock_client):
        with patch.object(trade_module, "OrderValidator") as mock_validator_cls:
            mock_validator_cls.return_value.validate_order_parameters.return_value = {
                "is_valid": True,
                "recommended_quantity": 0.001,
                "errors": [],
            }
            with patch.object(
                trade_module._operation_tracker,
                "generate_client_order_id",
                return_value="cid-legacy",
            ):
                with patch.object(
                    trade_module._operation_tracker,
                    "track_operation",
                    new_callable=AsyncMock,
                ):
                    with patch.object(
                        trade_module._operation_tracker,
                        "update_operation_status",
                        new_callable=AsyncMock,
                    ):
                        with patch.object(trade_module, "log_trade"):
                            with patch.object(trade_module, "send_telegram_alert"):
                                with patch.object(
                                    trade_module,
                                    "place_spot_market_via_adapter",
                                    new_callable=AsyncMock,
                                ) as mock_adapter:
                                    app.dependency_overrides[trade_module.get_db] = (
                                        lambda: mock_db
                                    )
                                    try:
                                        client = TestClient(
                                            app, base_url="http://localhost"
                                        )
                                        response = client.post(
                                            "/api/trade/order",
                                            json={
                                                "symbol": "BTCUSDT",
                                                "side": "BUY",
                                                "quantity": 0.001,
                                                "type": "MARKET",
                                            },
                                            headers=api_headers,
                                        )
                                    finally:
                                        app.dependency_overrides.clear()

    assert response.status_code == 200
    mock_adapter.assert_not_called()
    mock_client.order_market_buy.assert_called_once()
