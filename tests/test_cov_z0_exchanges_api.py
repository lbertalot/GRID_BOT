"""S-COV-85 Z0 — exchanges exceptions/init + test_routes (paper-safe paths)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.usefixtures("paper_env")


# ── exchanges.exceptions ────────────────────────────────────────────────────


def test_exchange_exceptions():
    from app.exchanges.exceptions import (
        ConnectionError,
        ExchangeError,
        RateLimitError,
        SymbolFilterError,
        WebSocketError,
    )

    base = ExchangeError("boom", exchange="binance", details={"a": 1})
    assert base.message == "boom"
    assert base.details["a"] == 1

    sfe = SymbolFilterError(
        symbol="BTCUSDT",
        reason="step",
        filter_type="LOT_SIZE",
        provided_value=0.001,
        required_value=0.01,
    )
    assert "BTCUSDT" in str(sfe)
    assert sfe.details["filter_type"] == "LOT_SIZE"

    rle = RateLimitError("/order", retry_after=30)
    assert "retry after 30" in rle.message
    rle2 = RateLimitError("/ticker")
    assert "retry after" not in rle2.message

    wse = WebSocketError("ws down", symbol="ETHUSDT", ws_type="trade")
    assert wse.details["ws_type"] == "trade"

    ce = ConnectionError("timeout", endpoint="/api")
    assert ce.endpoint == "/api"


def test_exchanges_init_exports():
    import app.exchanges as ex

    assert "BinanceClient" in ex.__all__
    assert "SymbolFilterError" in ex.__all__
    assert ex.BinanceClient is not None


# ── test_routes (never live) ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_binance_route_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ALLOW_BINANCE_TEST", raising=False)
    from app.api import test_routes as tr

    out = await tr.test_binance_connection()
    assert out["status"] == "disabled"


@pytest.mark.asyncio
async def test_binance_route_missing_keys(monkeypatch):
    monkeypatch.setenv("ALLOW_BINANCE_TEST", "1")
    monkeypatch.setenv("BINANCE_API_KEY", "")
    monkeypatch.setenv("BINANCE_SECRET_KEY", "")
    from app.api import test_routes as tr

    out = await tr.test_binance_connection()
    assert out["status"] == "error"
    assert "no configuradas" in out["message"]


@pytest.mark.asyncio
async def test_binance_route_success_mocked(monkeypatch):
    monkeypatch.setenv("ALLOW_BINANCE_TEST", "1")
    monkeypatch.setenv("BINANCE_API_KEY", "k")
    monkeypatch.setenv("BINANCE_SECRET_KEY", "s")

    fake_client = MagicMock()
    fake_client.get_account.return_value = {"accountType": "SPOT"}

    with patch("binance.Client", return_value=fake_client):
        from app.api import test_routes as tr

        out = await tr.test_binance_connection()
    assert out["status"] == "success"
    assert out["account_type"] == "SPOT"


@pytest.mark.asyncio
async def test_binance_route_unexpected_and_exception(monkeypatch):
    monkeypatch.setenv("ALLOW_BINANCE_TEST", "1")
    monkeypatch.setenv("BINANCE_API_KEY", "k")
    monkeypatch.setenv("BINANCE_SECRET_KEY", "s")

    fake_client = MagicMock()
    fake_client.get_account.return_value = {"balances": []}
    with patch("binance.Client", return_value=fake_client):
        from app.api import test_routes as tr

        out = await tr.test_binance_connection()
    assert out["status"] == "error"
    assert "inesperada" in out["message"]

    with patch("binance.Client", side_effect=RuntimeError("net")):
        from app.api import test_routes as tr

        out2 = await tr.test_binance_connection()
    assert out2["status"] == "error"
    assert "Error conectando" in out2["message"]


@pytest.mark.asyncio
async def test_telegram_route_paths():
    from app.api import test_routes as tr

    with patch.object(tr, "send_telegram_alert_async", AsyncMock(return_value=True)):
        ok = await tr.test_telegram()
    assert ok["status"] == "success"

    with patch.object(tr, "send_telegram_alert_async", AsyncMock(return_value=False)):
        bad = await tr.test_telegram()
    assert bad["status"] == "error"

    with patch.object(
        tr, "send_telegram_alert_async", AsyncMock(side_effect=RuntimeError("tg"))
    ):
        err = await tr.test_telegram()
    assert err["status"] == "error"
    assert "Error con Telegram" in err["message"]
