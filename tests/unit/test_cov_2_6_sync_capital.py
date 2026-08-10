"""COV-2.6 — binance_sync / capital / simulations / test_routes paper contracts.

Paper-only · no live · PROMOTE_LIVE: NO.
Sync endpoints mocked; test_routes no habilita live por defecto.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api import binance_sync_routes as sync
from app.api import capital_routes as capital
from app.api import simulations as sims
from app.api import test_routes as troutes
from app.core.capital_books import CapitalBooksConfigError
from app.schemas.transaction_cost_audit import (
    TransactionCostAuditRequest,
    TransactionCostAuditResponse,
)

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def test_binance_sync_posts_mocked(paper_env):
    mock = MagicMock()
    mock.sync_account_info = AsyncMock(return_value={"ok": True})
    mock.sync_balances = AsyncMock(return_value={"balances": 2})
    mock.sync_symbol_info = AsyncMock(return_value={"symbols": 1})
    mock.sync_recent_trades = AsyncMock(return_value={"trades": []})
    mock.sync_klines_data = AsyncMock(return_value={"klines": []})
    mock.sync_performance_metrics = AsyncMock(return_value={"perf": {}})
    mock.full_sync = AsyncMock(return_value={"full": True})

    with patch.object(sync, "binance_sync", mock):
        assert (await sync.sync_binance_account())["status"] == "success"
        assert (await sync.sync_binance_balances())["status"] == "success"
        assert (await sync.sync_binance_symbols())["status"] == "success"
        assert (await sync.sync_binance_trades())["status"] == "success"
        assert (await sync.sync_binance_klines())["status"] == "success"
        assert (await sync.sync_binance_performance())["status"] == "success"
        full = await sync.sync_binance_full()
        assert full["status"] == "success"
        assert "completa" in full["message"].lower()

    mock.sync_account_info = AsyncMock(side_effect=RuntimeError("down"))
    with patch.object(sync, "binance_sync", mock):
        err = await sync.sync_binance_account()
    assert err.status_code == 500
    assert err.body  # JSONResponse


async def test_binance_data_gets_mocked_asyncpg(paper_env):
    conn = MagicMock()
    conn.fetch = AsyncMock(
        return_value=[
            {"key": "account_type", "value": "SPOT", "description": "t"},
        ]
    )
    conn.fetchrow = AsyncMock(
        return_value={
            "total_trades": 10,
            "winning_trades": 6,
            "losing_trades": 4,
            "total_profit": 1.0,
            "total_loss": 0.5,
            "win_rate": 0.6,
            "timestamp": "2026-08-10",
        }
    )
    conn.close = AsyncMock()

    async def _connect(*_a, **_k):
        return conn

    with patch.dict("sys.modules", {"asyncpg": MagicMock(connect=_connect)}):
        # Patch asyncpg where imported inside functions
        import asyncpg

        with patch.object(asyncpg, "connect", side_effect=_connect):
            acct = await sync.get_binance_account_data()
            bal = await sync.get_binance_balances_data()
            trades = await sync.get_binance_trades_data()
            perf = await sync.get_binance_performance_data()

    assert acct["status"] == "success"
    assert acct["data"]["account_info"]["account_type"] == "SPOT"
    assert bal["status"] == "success"
    assert trades["status"] == "success"
    assert perf["status"] == "success"
    assert perf["data"]["performance"]["total_trades"] == 10

    async def _boom(*_a, **_k):
        raise RuntimeError("no db")

    with patch.dict("sys.modules", {"asyncpg": MagicMock(connect=_boom)}):
        import asyncpg as apg

        with patch.object(apg, "connect", side_effect=_boom):
            bad = await sync.get_binance_account_data()
    assert bad.status_code == 500


async def test_capital_books_ok_and_503(paper_env):
    snap = {"books": [{"name": "trading", "allocation_pct": 70}], "paper": True}
    with patch.object(capital, "get_books_snapshot", return_value=object()), patch.object(
        capital, "serialize_books_snapshot", return_value=snap
    ):
        ok = await capital.get_capital_books()
    assert ok["paper"] is True
    assert "sharpe" not in str(ok).lower()

    with patch.object(
        capital,
        "get_books_snapshot",
        side_effect=CapitalBooksConfigError("broken"),
    ):
        with pytest.raises(Exception) as exc:
            await capital.get_capital_books()
    assert getattr(exc.value, "status_code", None) == 503

    with patch.object(
        capital,
        "validate_capital_books_config",
        side_effect=CapitalBooksConfigError("bad"),
    ):
        capital._log_startup_validation()  # no raise


def test_simulations_dry_run_forces_paper(paper_env, monkeypatch):
    monkeypatch.setenv("API_KEY", "cov-26")
    monkeypatch.delenv("FORCE_REAL_MODE", raising=False)

    svc = MagicMock()
    svc.simulation_mode = False
    svc.validate_order_parameters.return_value = {
        "is_valid": True,
        "recommended_quantity": 0.001,
    }
    svc.execute_trading_order.return_value = {
        "orderId": "paper-1",
        "status": "FILLED",
        "mode": "PAPER",
    }

    with patch.object(sims, "BinanceService", return_value=svc):
        out = sims.dry_run(
            sims.DryRunRequest(
                symbol="BTCUSDT", side="BUY", order_type="MARKET", quantity=0.001
            ),
            api_key="cov-26",
        )
    assert out["success"] is True
    assert out["mode"] == "PAPER"
    assert svc.simulation_mode is True
    import os

    assert os.environ.get("PAPER_TRADING", "").lower() in {"1", "true", "yes"}

    svc.validate_order_parameters.return_value = {
        "is_valid": False,
        "errors": ["min_notional"],
    }
    with patch.object(sims, "BinanceService", return_value=svc):
        bad = sims.dry_run(
            sims.DryRunRequest(symbol="BTCUSDT", quantity=0.001),
            api_key="cov-26",
        )
    assert bad["success"] is False

    svc.validate_order_parameters.side_effect = RuntimeError("boom")
    with patch.object(sims, "BinanceService", return_value=svc), pytest.raises(
        Exception
    ) as exc:
        sims.dry_run(
            sims.DryRunRequest(symbol="BTCUSDT", quantity=0.001),
            api_key="cov-26",
        )
    assert getattr(exc.value, "status_code", None) == 400

    audit = TransactionCostAuditResponse(
        notional_quote="50",
        side="BUY",
        order_type="MARKET",
        spread_bps="0",
        slippage_bps="0",
        commission_usdt="0.05",
        spread_cost_usdt="0",
        slippage_cost_usdt="0",
        total_friction_usdt="0.05",
    )
    with patch.object(sims, "run_transaction_cost_audit_for_api", return_value=audit):
        tca = sims.transaction_cost_audit(
            TransactionCostAuditRequest(notional_quote="50"),
            _api_key="cov-26",
        )
    assert tca.commission_usdt == "0.05"

    with patch.object(
        sims, "run_transaction_cost_audit_for_api", side_effect=ValueError("bad")
    ), pytest.raises(Exception) as exc2:
        sims.transaction_cost_audit(
            TransactionCostAuditRequest(notional_quote="50"),
            _api_key="cov-26",
        )
    assert getattr(exc2.value, "status_code", None) == 400


async def test_test_routes_disabled_by_default_no_live(paper_env, monkeypatch):
    monkeypatch.delenv("ALLOW_BINANCE_TEST", raising=False)
    disabled = await troutes.test_binance_connection()
    assert disabled["status"] == "disabled"

    monkeypatch.setenv("ALLOW_BINANCE_TEST", "1")
    monkeypatch.delenv("BINANCE_API_KEY", raising=False)
    monkeypatch.delenv("BINANCE_SECRET_KEY", raising=False)
    no_keys = await troutes.test_binance_connection()
    assert no_keys["status"] == "error"
    assert "API Keys" in no_keys["message"]

    # Con keys: mock Client — no red real
    monkeypatch.setenv("BINANCE_API_KEY", "k")
    monkeypatch.setenv("BINANCE_SECRET_KEY", "s")
    mock_client = MagicMock()
    mock_client.get_account.return_value = {"accountType": "SPOT"}
    with patch("binance.Client", return_value=mock_client):
        ok = await troutes.test_binance_connection()
    assert ok["status"] == "success"
    assert ok["account_type"] == "SPOT"

    with patch.object(
        troutes, "send_telegram_alert_async", new=AsyncMock(return_value=True)
    ):
        tg = await troutes.test_telegram()
    assert tg["status"] == "success"

    with patch.object(
        troutes, "send_telegram_alert_async", new=AsyncMock(return_value=False)
    ):
        tg_fail = await troutes.test_telegram()
    assert tg_fail["status"] == "error"
