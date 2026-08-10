"""COV-2.5 — metrics / prometheus / alerts / commissions paper contracts.

Paper-only · no live · PROMOTE_LIVE: NO.
Scrapes/metrics no tocan exchange; commission paper-iso vía mocks.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api import alert_routes as alerts
from app.api import commission_routes as commissions
from app.api import metrics as metrics_mod
from app.api import metrics_routes as mroutes
from app.api import prometheus as prom
from app.schemas.transaction_cost_audit import (
    TransactionCostAuditRequest,
    TransactionCostAuditResponse,
)

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def test_alert_format_persist_and_handlers(paper_env):
    msg = alerts._format_alertmanager_message(
        {
            "alerts": [
                {
                    "labels": {"alertname": "HighDD", "instance": "grid"},
                    "annotations": {"summary": "DD warn"},
                    "startsAt": "t0",
                    "endsAt": None,
                }
            ]
        },
        "crítica",
    )
    assert "HighDD" in msg

    empty = alerts._format_alertmanager_message({"message": "fallback"}, "warning")
    assert "fallback" in empty

    db = MagicMock()
    with patch.object(alerts, "SessionLocal", return_value=db), patch.object(
        alerts, "Alert", return_value=MagicMock()
    ):
        alerts._persist_alert("critical", "hello")
    db.commit.assert_called_once()

    db2 = MagicMock()
    db2.commit.side_effect = RuntimeError("fail")
    with patch.object(alerts, "SessionLocal", return_value=db2), patch.object(
        alerts, "Alert", return_value=MagicMock()
    ), pytest.raises(RuntimeError):
        alerts._persist_alert("warning", "boom")
    db2.rollback.assert_called_once()

    req = MagicMock()
    req.json = AsyncMock(return_value={"message": "crit"})
    with patch.object(alerts, "_persist_alert"), patch.object(
        alerts.asyncio, "create_task", return_value=MagicMock()
    ):
        crit = await alerts.telegram_critical_alert(req)
        warn = await alerts.telegram_warning_alert(req)
    assert crit.status_code == 202
    assert warn.status_code == 202

    req.json = AsyncMock(side_effect=RuntimeError("bad json"))
    err = await alerts.telegram_critical_alert(req)
    assert err.status_code == 500


async def test_metrics_module_reads_and_writes(paper_env):
    with patch.object(metrics_mod, "record_api_request"), patch.object(
        metrics_mod, "get_trading_metrics", return_value={"orders": 1}
    ), patch.object(
        metrics_mod, "get_binance_metrics", return_value={"latency_ms": 12}
    ), patch.object(
        metrics_mod, "get_strategy_metrics", return_value={"grid": "ok"}
    ):
        health = await metrics_mod.metrics_health()
        trading = await metrics_mod.trading_metrics()
        binance = await metrics_mod.binance_metrics()
        strat = await metrics_mod.strategy_metrics()
        pbin = await metrics_mod.prometheus_binance_metrics()
        pstrat = await metrics_mod.prometheus_strategy_metrics()
    assert health["status"] == "healthy"
    assert trading["orders"] == 1
    assert binance["latency_ms"] == 12
    assert strat["grid"] == "ok"
    assert pbin["latency_ms"] == 12
    assert pstrat["grid"] == "ok"

    root = await metrics_mod.metrics()
    assert root.media_type.startswith("text/plain")
    ptrading = await metrics_mod.prometheus_trading_metrics()
    assert ptrading.media_type.startswith("text/plain")

    with patch.object(metrics_mod, "record_order_execution") as ok, patch.object(
        metrics_mod, "record_order_failure"
    ) as fail, patch.object(metrics_mod, "update_balance") as bal, patch.object(
        metrics_mod, "update_strategy_status"
    ) as st, patch.object(metrics_mod, "update_profit_loss") as pnl:
        r1 = await metrics_mod.record_order(
            "BTCUSDT", "BUY", "MARKET", "grid", 0.001, 50000.0, True, "", "k"
        )
        r2 = await metrics_mod.record_order(
            "BTCUSDT", "SELL", "MARKET", "grid", 0.001, 51000.0, False, "reject", "k"
        )
        r3 = await metrics_mod.update_balance_metric("USDT", 900.0, 0.0, "k")
        r4 = await metrics_mod.update_strategy_metric("grid", 1, "k")
        r5 = await metrics_mod.update_pnl_metric("BTCUSDT", "grid", 1.5, "k")
    assert "exitosamente" in r1["message"]
    assert "fallida" in r2["message"]
    ok.assert_called_once()
    fail.assert_called_once()
    bal.assert_called_once()
    st.assert_called_once()
    pnl.assert_called_once()
    assert "USDT" in r3["message"]
    assert "grid" in r4["message"]
    assert "PnL" in r5["message"]


async def test_prometheus_scrapes_and_update_pnl_mocked(paper_env):
    with patch("app.core.obs_gauges.publish_obs_gauges"):
        m = await prom.prometheus_metrics()
    assert m.media_type == "text/plain"
    assert (await prom.prometheus_trading_metrics()).media_type == "text/plain"
    assert (await prom.prometheus_binance_metrics())["error"]
    assert (await prom.prometheus_strategy_metrics())["error"]
    assert (await prom.prometheus_pnl_metrics()).media_type == "text/plain"

    with patch.object(prom, "load_dotenv"), patch.object(
        prom.os, "getenv", return_value=""
    ):
        missing = await prom.update_pnl_metrics(api_key="cov")
    assert "Credenciales" in missing["error"]

    mock_client = MagicMock()
    mock_client.get_account.return_value = {
        "balances": [
            {"asset": "USDT", "free": "100", "locked": "0"},
            {"asset": "BTC", "free": "0.01", "locked": "0"},
        ]
    }
    mock_client.get_symbol_ticker.return_value = {"price": "50000"}

    def _getenv(key, default=None):
        return {"BINANCE_API_KEY": "k", "BINANCE_SECRET_KEY": "s"}.get(key, default)

    with patch.object(prom, "Client", return_value=mock_client), patch.object(
        prom, "load_dotenv"
    ), patch.object(prom.os, "getenv", side_effect=_getenv):
        upd = await prom.update_pnl_metrics(api_key="cov")
    assert upd["success"] is True
    assert "total_value_usdt" in upd["data"]


async def test_commission_endpoints_paper_iso(paper_env):
    cm = MagicMock()
    cm.get_commission_rates.return_value = {"maker": 0.001, "taker": 0.001}
    cm.default_maker_commission = 0.001
    cm.default_taker_commission = 0.001
    cm.calculate_commission.return_value = 0.05
    cm.calculate_profit_with_commissions.return_value = {
        "net_profit": 1.2,
        "fees": 0.1,
    }
    cm._update_commission_rates = MagicMock()
    cm.client = None
    cm._commission_cache = {}
    cm._symbol_info_cache = {}

    req = commissions.CommissionValidationRequest(
        symbol="BTCUSDT", quantity=0.001, price=50000, side="BUY", order_type="MARKET"
    )
    grid = commissions.GridProfitabilityRequest(
        symbol="BTCUSDT",
        min_price=40000,
        max_price=60000,
        quantity=0.001,
        num_levels=10,
    )

    with patch.object(commissions, "commission_manager", cm):
        rates = await commissions.get_commission_rates("BTCUSDT", "k")
        calc = await commissions.calculate_commission(req, "k")
        profit = await commissions.calculate_profit_with_commissions(
            "BTCUSDT", 50000.0, 51000.0, 0.001, "MARKET", "MARKET", "k"
        )
        upd = await commissions.update_commission_rates("k")
        st = await commissions.get_commission_status("k")

    assert rates["status"] == "success"
    assert calc["commission_usdt"] == 0.05
    assert profit["status"] == "success"
    assert upd["status"] == "success"
    assert st["commission_manager_initialized"] is False

    binance = MagicMock()
    binance.validate_grid_profitability.return_value = {"viable": True}
    with patch.object(commissions, "commission_manager", cm), patch.object(
        commissions, "BinanceService", return_value=binance
    ):
        val = await commissions.validate_grid_profitability(grid, "k")
    assert val["status"] == "success"

    audit_resp = TransactionCostAuditResponse(
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
    with patch.object(
        commissions, "run_transaction_cost_audit_for_api", return_value=audit_resp
    ):
        body = TransactionCostAuditRequest(notional_quote="50")
        out = await commissions.post_transaction_cost_audit(body, "k")
    assert out.commission_usdt == "0.05"


async def test_metrics_routes_scrapes_and_summary(paper_env, monkeypatch):
    scrape = await mroutes.get_prometheus_metrics()
    assert scrape.media_type

    metrics_payload = {
        "portfolio_value": 1000.0,
        "total_profit": 1.5,
        "daily_profit": 0.5,
        "roi_daily": 0.05,
        "last_update": "2026-08-10T00:00:00Z",
        "asset_metrics": {"BTCUSDT": {"value": 100}},
    }
    with patch.object(
        mroutes.metrics_service,
        "calculate_portfolio_metrics",
        new=AsyncMock(return_value=metrics_payload),
    ):
        prof = await mroutes.get_profitability_metrics(user="u")
        summary = await mroutes.get_metrics_summary(user="u")
        assets = await mroutes.get_asset_metrics(user="u")
    assert prof["success"] is True
    assert "sharpe" not in str(prof).lower()
    assert summary["portfolio_value"] == 1000.0
    assert assets["assets"][0]["asset"] == "BTCUSDT"

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    with patch.object(
        mroutes.metrics_service,
        "calculate_portfolio_metrics",
        new=AsyncMock(return_value={"portfolio_value": 1000.0}),
    ), patch.object(mroutes, "SessionLocal", return_value=mock_db):
        reset = await mroutes.reset_baseline(user="u")
    assert reset["status"] == "ok"

    monkeypatch.setenv("DASH_RESET_TOKEN", "tok")
    with patch.object(
        mroutes.metrics_service,
        "calculate_portfolio_metrics",
        new=AsyncMock(return_value={"portfolio_value": 900.0}),
    ), patch.object(mroutes, "SessionLocal", return_value=mock_db):
        with pytest.raises(Exception):
            await mroutes.reset_baseline_get(token="wrong")
        good = await mroutes.reset_baseline_get(token="tok")
    assert good["status"] == "ok"


def test_optimized_routes_already_covered_smoke(paper_env):
    """COV-2.5 incluye optimized_routes (≥96% suite existente); smoke import-only."""
    from app.api import optimized_routes as opt

    assert opt.router.prefix == "/api/v1"
    assert callable(opt._reject_live_mutations)
