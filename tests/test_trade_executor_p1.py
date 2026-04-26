"""
Tests P1 (FASE 3) — TradeExecutor
─────────────────────────────────────────────────────────────────
Cubre la deuda de testing alta de TESTING_RULES.md §7:
  - Idempotencia y manejo de client_order_id end-to-end.
  - Mitigación de error -1021 (timestamp drift) sin bloquear el event loop.
  - Actualización contable post-trade en BUY/SELL con Decimal estricto.
  - Manejo defensivo cuando BalanceService falla (no re-raise).

Política:
  - 100% offline: stubs Binance vía conftest.
  - Sin lógica de negocio modificada (TESTING_RULES §1).
  - Decimal en cálculos monetarios (AGENTS.md §Estilo).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from app.services.trade_executor import TradeExecutor


# ─────────────────────────────────────────────────────────────────
# Helpers / Fixtures
# ─────────────────────────────────────────────────────────────────


def _make_filled_order(
    order_id: int = 12345,
    client_order_id: str = "gridbot_test_001",
    symbol: str = "BTCUSDT",
    executed_qty: str = "0.001",
    fills: list[Dict[str, Any]] | None = None,
    status: str = "FILLED",
) -> Dict[str, Any]:
    """Construye una respuesta canónica de Binance para una orden FILLED."""
    if fills is None:
        fills = [
            {
                "qty": "0.001",
                "price": "50000.00",
                "commission": "0.05",
                "commissionAsset": "USDT",
            }
        ]
    return {
        "orderId": order_id,
        "clientOrderId": client_order_id,
        "symbol": symbol,
        "status": status,
        "executedQty": executed_qty,
        "fills": fills,
    }


@pytest.fixture
def executor_with_mocks() -> tuple[TradeExecutor, MagicMock, MagicMock]:
    """TradeExecutor con `binance_client` y `BalanceService.update_balance` mockeados."""
    executor = TradeExecutor()
    mock_client = MagicMock()
    executor.binance_client = mock_client
    with patch(
        "app.services.trade_executor.BalanceService.update_balance"
    ) as mock_update:
        with patch("app.services.trade_executor.SessionLocal") as mock_session:
            mock_session.return_value = MagicMock()
            yield executor, mock_client, mock_update


# ─────────────────────────────────────────────────────────────────
# Idempotencia client_order_id (deuda alta §7)
# ─────────────────────────────────────────────────────────────────


def test_execute_order_propaga_client_order_id(executor_with_mocks):
    """
    RED-GREEN: el client_order_id provisto por el caller DEBE viajar a
    Binance (kwargs) para garantizar idempotencia at-least-once.
    """
    executor, mock_client, _ = executor_with_mocks
    mock_client.create_order.return_value = _make_filled_order(
        client_order_id="trace_idemp_42"
    )

    result = executor.execute_order(
        symbol="BTCUSDT",
        side="BUY",
        order_type="MARKET",
        quantity="0.001",
        newClientOrderId="trace_idemp_42",
    )

    assert result["clientOrderId"] == "trace_idemp_42"
    mock_client.create_order.assert_called_once()
    call_kwargs = mock_client.create_order.call_args.kwargs
    assert call_kwargs.get("newClientOrderId") == "trace_idemp_42"


def test_execute_order_recv_window_default_10s(executor_with_mocks):
    """recvWindow = 10s por defecto (mitigación skew vs Binance)."""
    executor, mock_client, _ = executor_with_mocks
    mock_client.create_order.return_value = _make_filled_order()

    executor.execute_order("BTCUSDT", "BUY", "MARKET", "0.001")

    call_kwargs = mock_client.create_order.call_args.kwargs
    assert call_kwargs.get("recvWindow") == 10000


def test_execute_order_recv_window_caller_override(executor_with_mocks):
    """Si el caller pasa recvWindow, se respeta (no lo pisa)."""
    executor, mock_client, _ = executor_with_mocks
    mock_client.create_order.return_value = _make_filled_order()

    executor.execute_order("BTCUSDT", "BUY", "MARKET", "0.001", recvWindow=5000)

    assert mock_client.create_order.call_args.kwargs["recvWindow"] == 5000


# ─────────────────────────────────────────────────────────────────
# Mitigación error -1021 (timestamp drift)
# ─────────────────────────────────────────────────────────────────


def test_execute_order_reintenta_en_error_1021(executor_with_mocks):
    """
    Ante error -1021 sincroniza tiempo con Binance y reintenta.
    Verifica que se llame create_order DOS veces y que la 2da incluya timestamp.
    """
    executor, mock_client, _ = executor_with_mocks

    err = Exception("APIError(code=-1021): Timestamp for this request is outside")
    mock_client.create_order.side_effect = [err, _make_filled_order()]

    fake_resp = MagicMock()
    fake_resp.json.return_value = {"serverTime": 1_700_000_000_000}

    with patch("app.services.trade_executor.requests.get", return_value=fake_resp):
        with patch("app.services.trade_executor.time.sleep"):
            result = executor.execute_order("BTCUSDT", "BUY", "MARKET", "0.001")

    assert result["status"] == "FILLED"
    assert mock_client.create_order.call_count == 2
    second_call_kwargs = mock_client.create_order.call_args_list[1].kwargs
    assert "timestamp" in second_call_kwargs


def test_execute_order_otros_errores_no_reintentan(executor_with_mocks):
    """Errores distintos a -1021 deben re-elevarse sin reintento."""
    executor, mock_client, _ = executor_with_mocks
    mock_client.create_order.side_effect = Exception(
        "APIError(code=-2010): insufficient balance"
    )

    with pytest.raises(Exception, match="-2010"):
        executor.execute_order("BTCUSDT", "BUY", "MARKET", "0.001")

    assert mock_client.create_order.call_count == 1


# ─────────────────────────────────────────────────────────────────
# Status no-FILLED → no actualiza balances
# ─────────────────────────────────────────────────────────────────


def test_execute_order_status_new_no_actualiza_balance(executor_with_mocks):
    """Un status que NO sea FILLED/PARTIALLY_FILLED no debe tocar balances."""
    executor, mock_client, mock_update = executor_with_mocks
    mock_client.create_order.return_value = _make_filled_order(status="NEW")

    result = executor.execute_order("BTCUSDT", "BUY", "MARKET", "0.001")

    assert result["status"] == "NEW"
    mock_update.assert_not_called()


def test_execute_order_partially_filled_actualiza_balance(executor_with_mocks):
    """PARTIALLY_FILLED sí debe propagar la actualización contable."""
    executor, mock_client, mock_update = executor_with_mocks
    mock_client.create_order.return_value = _make_filled_order(
        status="PARTIALLY_FILLED"
    )

    executor.execute_order("BTCUSDT", "BUY", "MARKET", "0.001")

    assert mock_update.called


# ─────────────────────────────────────────────────────────────────
# Cálculo contable post-trade — BUY (cobertura crítica financiera)
# ─────────────────────────────────────────────────────────────────


def test_buy_actualiza_balances_con_decimal_y_comision(executor_with_mocks):
    """
    BUY 0.001 BTC @ 50000 con commission 0.05 USDT debe:
      - restar (0.001 * 50000 + 0.05) = 50.05 USDT
      - sumar 0.001 BTC
    Cálculo en Decimal sin float drift (TESTING_RULES §3).
    """
    executor, mock_client, mock_update = executor_with_mocks
    mock_client.create_order.return_value = _make_filled_order(
        executed_qty="0.001",
        fills=[
            {
                "qty": "0.001",
                "price": "50000.00",
                "commission": "0.05",
                "commissionAsset": "USDT",
            }
        ],
    )

    executor.execute_order("BTCUSDT", "BUY", "MARKET", "0.001")

    calls = mock_update.call_args_list
    assert len(calls) == 2
    by_asset = {c.args[1]: c.args[2] for c in calls}
    assert by_asset["USDT"] == Decimal("-50.05")
    assert by_asset["BTC"] == Decimal("0.001")


# ─────────────────────────────────────────────────────────────────
# Cálculo contable post-trade — SELL
# ─────────────────────────────────────────────────────────────────


def test_sell_actualiza_balances_con_decimal_y_comision(executor_with_mocks):
    """
    SELL 0.001 BTC @ 50000 con commission 0.05 USDT debe:
      - restar 0.001 BTC
      - sumar (0.001 * 50000 - 0.05) = 49.95 USDT
    """
    executor, mock_client, mock_update = executor_with_mocks
    mock_client.create_order.return_value = _make_filled_order(
        executed_qty="0.001",
        fills=[
            {
                "qty": "0.001",
                "price": "50000.00",
                "commission": "0.05",
                "commissionAsset": "USDT",
            }
        ],
    )

    executor.execute_order("BTCUSDT", "SELL", "MARKET", "0.001")

    by_asset = {c.args[1]: c.args[2] for c in mock_update.call_args_list}
    assert by_asset["BTC"] == Decimal("-0.001")
    assert by_asset["USDT"] == Decimal("49.95")


def test_buy_multiples_fills_promedia_precio_ponderado(executor_with_mocks):
    """
    Múltiples fills: precio promedio ponderado por cantidad ejecutada.
    qty 0.0006 @ 50000 + qty 0.0004 @ 51000 → vwap = 50400.0
    Coste total esperado = 0.001 * 50400 + 0.05 = 50.45.
    """
    executor, mock_client, mock_update = executor_with_mocks
    mock_client.create_order.return_value = _make_filled_order(
        executed_qty="0.001",
        fills=[
            {
                "qty": "0.0006",
                "price": "50000.00",
                "commission": "0.03",
                "commissionAsset": "USDT",
            },
            {
                "qty": "0.0004",
                "price": "51000.00",
                "commission": "0.02",
                "commissionAsset": "USDT",
            },
        ],
    )

    executor.execute_order("BTCUSDT", "BUY", "MARKET", "0.001")

    by_asset = {c.args[1]: c.args[2] for c in mock_update.call_args_list}
    assert by_asset["USDT"] == Decimal("-50.45")
    assert by_asset["BTC"] == Decimal("0.001")


# ─────────────────────────────────────────────────────────────────
# update_balance=False (bypass contable explícito)
# ─────────────────────────────────────────────────────────────────


def test_execute_order_update_balance_false_no_toca_db(executor_with_mocks):
    """update_balance=False es la flag oficial para reconciliación batch."""
    executor, mock_client, mock_update = executor_with_mocks
    mock_client.create_order.return_value = _make_filled_order()

    executor.execute_order("BTCUSDT", "BUY", "MARKET", "0.001", update_balance=False)

    mock_update.assert_not_called()


# ─────────────────────────────────────────────────────────────────
# Resiliencia: error en BalanceService NO debe propagar
# ─────────────────────────────────────────────────────────────────


def test_balance_service_error_no_propaga(executor_with_mocks):
    """
    Si la actualización contable falla DESPUÉS de la orden ejecutada,
    el error se loggea pero NO se propaga (la orden ya está en Binance).
    Política documentada en trade_executor.py:230.
    """
    executor, mock_client, mock_update = executor_with_mocks
    mock_client.create_order.return_value = _make_filled_order()
    mock_update.side_effect = RuntimeError("DB connection lost")

    result = executor.execute_order("BTCUSDT", "BUY", "MARKET", "0.001")

    assert result["status"] == "FILLED"
    assert result["orderId"] == 12345


# ─────────────────────────────────────────────────────────────────
# Shortcuts
# ─────────────────────────────────────────────────────────────────


def test_execute_market_buy_shortcut(executor_with_mocks):
    executor, mock_client, _ = executor_with_mocks
    mock_client.create_order.return_value = _make_filled_order()

    executor.execute_market_buy("BTCUSDT", "0.001")

    kwargs = mock_client.create_order.call_args.kwargs
    assert kwargs["side"] == "BUY"
    assert kwargs["order_type"] == "MARKET"


def test_execute_market_sell_shortcut(executor_with_mocks):
    executor, mock_client, _ = executor_with_mocks
    mock_client.create_order.return_value = _make_filled_order()

    executor.execute_market_sell("BTCUSDT", "0.001")

    kwargs = mock_client.create_order.call_args.kwargs
    assert kwargs["side"] == "SELL"
    assert kwargs["order_type"] == "MARKET"


def test_execute_limit_buy_incluye_gtc_y_price(executor_with_mocks):
    executor, mock_client, _ = executor_with_mocks
    mock_client.create_order.return_value = _make_filled_order()

    executor.execute_limit_buy("BTCUSDT", "0.001", "49000.00")

    kwargs = mock_client.create_order.call_args.kwargs
    assert kwargs["side"] == "BUY"
    assert kwargs["order_type"] == "LIMIT"
    assert kwargs["timeInForce"] == "GTC"
    assert kwargs["price"] == "49000.00"


def test_execute_limit_sell_incluye_gtc_y_price(executor_with_mocks):
    executor, mock_client, _ = executor_with_mocks
    mock_client.create_order.return_value = _make_filled_order()

    executor.execute_limit_sell("BTCUSDT", "0.001", "51000.00")

    kwargs = mock_client.create_order.call_args.kwargs
    assert kwargs["side"] == "SELL"
    assert kwargs["order_type"] == "LIMIT"
    assert kwargs["timeInForce"] == "GTC"


# ─────────────────────────────────────────────────────────────────
# Singleton: get_trade_executor()
# ─────────────────────────────────────────────────────────────────


def test_get_trade_executor_devuelve_singleton():
    from app.services.trade_executor import get_trade_executor

    a = get_trade_executor()
    b = get_trade_executor()
    assert a is b
    assert isinstance(a, TradeExecutor)
