"""COV-2.4 — portfolio / CEO / ops / reconciliation / integrity contracts.

Paper-only · no live · PROMOTE_LIVE: NO.
Payloads paper-honest (sin edge claim); mocks Binance/DB/ledger.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import integrity_routes as ir
from app.api import ops_routes as ops
from app.api import portfolio_routes as pr
from app.api import reconciliation_routes as rr
from app.api import ceo_routes as ceo


# ── integrity ────────────────────────────────────────────────────────────────


@pytest.fixture
def integrity_client(paper_env):
    app = FastAPI()
    app.include_router(ir.router)
    bal = MagicMock()
    bal.get_validation_summary = AsyncMock(
        return_value={"integrity_score": 95, "ok": True}
    )
    bal.force_validation = AsyncMock()
    tracker = MagicMock()
    tracker.get_operation_summary = AsyncMock(
        return_value={"success_rate": 0.98, "total": 10}
    )
    tracker.force_operation_check = AsyncMock()
    tracker.get_failed_operations_summary = AsyncMock(return_value=[{"id": "f1"}])
    tracker.get_partial_fills_summary = AsyncMock(return_value=[])
    with patch.object(ir, "_get_components", return_value=(bal, tracker)):
        yield TestClient(app), bal, tracker


def test_integrity_status_and_actions(integrity_client):
    client, bal, tracker = integrity_client
    st = client.get("/integrity/status")
    assert st.status_code == 200
    body = st.json()
    assert body["status"] == "healthy"
    assert body["overall_integrity_score"] > 90

    assert client.post("/integrity/validate-balances").status_code == 200
    bal.force_validation.assert_awaited_once()
    assert client.post("/integrity/check-operations").status_code == 200
    tracker.force_operation_check.assert_awaited_once()

    failed = client.get("/integrity/operations/failed")
    assert failed.json()["total_failed"] == 1
    partial = client.get("/integrity/operations/partial-fills")
    assert partial.json()["total_partial"] == 0


def test_integrity_init_failure_503(paper_env):
    app = FastAPI()
    app.include_router(ir.router)
    ir._balance_validator = None
    ir._operation_tracker = None
    with patch.object(ir, "BalanceValidator", side_effect=RuntimeError("no redis")):
        client = TestClient(app)
        assert client.get("/integrity/status").status_code == 503


# ── reconciliation ───────────────────────────────────────────────────────────


def test_reconciliation_summary_ok_and_error(paper_env):
    app = FastAPI()
    app.include_router(rr.router)
    client = TestClient(app)

    singleton = MagicMock()
    singleton.client = MagicMock()
    svc = MagicMock()
    svc.run_reconciliation_cycle = AsyncMock(
        return_value={"status": "ok", "diffs": [], "paper": True}
    )
    with patch.object(rr, "get_binance_client_singleton", return_value=singleton), patch.object(
        rr, "get_shared_breakers", return_value=MagicMock()
    ), patch.object(rr, "ReconciliationService", return_value=svc):
        ok = client.get("/api/reconciliation/summary")
    assert ok.status_code == 200
    assert ok.json()["status"] == "ok"
    assert "timestamp" in ok.json()

    svc_bad = MagicMock()
    svc_bad.run_reconciliation_cycle = AsyncMock(
        return_value={"status": "error", "reason": "mismatch"}
    )
    with patch.object(rr, "get_binance_client_singleton", return_value=singleton), patch.object(
        rr, "get_shared_breakers", return_value=MagicMock()
    ), patch.object(rr, "ReconciliationService", return_value=svc_bad):
        bad = client.get("/api/reconciliation/summary")
    assert bad.status_code == 500


# ── ops error paths ──────────────────────────────────────────────────────────


def test_ops_ledger_config_and_storage_errors(paper_env, monkeypatch):
    app = FastAPI()
    app.include_router(ops.router)
    client = TestClient(app)

    with patch.object(
        ops, "get_ops_ledger", side_effect=ops.OpsLedgerError("bad cfg")
    ):
        assert client.get("/api/ops/summary").status_code == 500

    ledger = MagicMock()
    ledger.summary.side_effect = ops.OpsLedgerStorageError("disk")
    with patch.object(ops, "get_ops_ledger", return_value=ledger):
        assert client.get("/api/ops/summary").status_code == 500

    ledger2 = MagicMock()
    ledger2.list_entries.side_effect = ops.OpsLedgerError("bad month")
    with patch.object(ops, "get_ops_ledger", return_value=ledger2):
        assert client.get("/api/ops/ledger?month=2026-08").status_code == 400

    monkeypatch.setenv("API_KEY", "cov-24-ops")
    ledger3 = MagicMock()
    ledger3.add_entry.side_effect = ops.OpsLedgerStorageError("write fail")
    with patch.object(ops, "get_ops_ledger", return_value=ledger3):
        r = client.post(
            "/api/ops/ledger",
            json={
                "date": "2026-08-10",
                "category": "vps",
                "amount_usd": "10.00",
                "note": "test",
            },
            headers={"Authorization": "Bearer cov-24-ops"},
        )
    assert r.status_code == 500


# ── portfolio ────────────────────────────────────────────────────────────────


def test_portfolio_summary_positions_history_snapshot(paper_env):
    app = FastAPI()
    app.include_router(pr.router)

    svc = MagicMock()
    svc.get_account_optimized = AsyncMock(
        return_value={
            "balances": [
                {"asset": "USDT", "free": "900.50", "locked": "0"},
                {"asset": "BTC", "free": "0.01", "locked": "0"},
                {"asset": "DUST", "free": "0.0000001", "locked": "0"},
            ]
        }
    )
    app.dependency_overrides[pr.get_binance_service] = lambda: svc
    client = TestClient(app)
    try:
        summary = client.get("/api/portfolio/summary")
        assert summary.status_code == 200
        data = summary.json()
        assert data["cash_usdt"] == pytest.approx(900.50)
        assert data["portfolio_total_usdt"] == pytest.approx(900.50)
        assert any(a["asset"] == "USDT" for a in data["assets"])
        # paper-honest: no claim de edge / PnL
        assert "sharpe" not in data
        assert "edge" not in data

        pos = client.get("/api/portfolio/positions")
        assert pos.status_code == 200
        assert pos.json() == {"positions": [], "total_count": 0}

        root = client.get("/api/portfolio/")
        assert root.status_code == 200
    finally:
        app.dependency_overrides.clear()

    snap = MagicMock()
    snap.captured_at = datetime(2026, 8, 10, tzinfo=timezone.utc)
    snap.total_value_usdt = Decimal("1000.00")
    snap.usdt_free = Decimal("900.00")
    snap.btc_value_usdt = Decimal("100.00")
    snap.other_assets_usdt = Decimal("0")
    snap.btc_price = Decimal("50000")

    mock_db = MagicMock()
    q = MagicMock()
    mock_db.query.return_value = q
    q.filter.return_value = q
    q.order_by.return_value = q
    q.all.return_value = [snap, snap]

    with patch.object(pr, "SessionLocal", return_value=mock_db), patch.object(
        pr, "get_snapshot_count", return_value=2
    ), patch.object(pr, "get_latest_snapshot", return_value=snap):
        hist = client.get("/api/portfolio/history?days=7")
        latest = client.get("/api/portfolio/snapshot/latest")
    assert hist.status_code == 200
    assert hist.json()["data_available"] is True
    assert latest.status_code == 200
    assert latest.json()["total_value_usdt"] == 1000.0

    with patch.object(pr, "SessionLocal", return_value=mock_db), patch.object(
        pr, "get_latest_snapshot", return_value=None
    ):
        missing = client.get("/api/portfolio/snapshot/latest")
    assert missing.status_code == 404


def test_portfolio_summary_binance_failure(paper_env):
    app = FastAPI()
    app.include_router(pr.router)
    svc = MagicMock()
    svc.get_account_optimized = AsyncMock(return_value={})
    app.dependency_overrides[pr.get_binance_service] = lambda: svc
    try:
        r = TestClient(app).get("/api/portfolio/summary")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 500


# ── CEO presentation helpers (paper-honest labels) ───────────────────────────


def test_ceo_risk_and_format_helpers_paper_honest():
    overview = {
        "kill_floor": {"value": "750"},
        "ops_reserve_total": {"value": "200"},
    }
    assert (
        ceo._risk_level(
            "breakers",
            {"status": ceo.STATUS_OK, "value": ["dd"]},
            overview,
        )
        == "danger"
    )
    assert (
        ceo._risk_level(
            "emergency_stop",
            {"status": ceo.STATUS_OK, "value": False},
            overview,
        )
        == "ok"
    )
    assert (
        ceo._risk_level(
            "gate",
            {"status": ceo.STATUS_OK, "value": {"signed": False}},
            overview,
        )
        == "warn"
    )
    assert (
        ceo._risk_level(
            "dd_vs_contributed_pct",
            {"status": ceo.STATUS_OK, "value": "-26"},
            overview,
        )
        == "danger"
    )
    assert (
        ceo._risk_level(
            "daily_pnl_pct",
            {"status": ceo.STATUS_STALE, "value": "1"},
            overview,
        )
        == "warn"
    )
    assert ceo._decimal("bad") is None
    assert ceo._format_value(
        "ops_reserve_remaining",
        {"value": "150"},
        overview,
    ).startswith("USD")
    assert "Ninguno" in ceo._format_value(
        "breakers", {"value": []}, overview
    )
    assert "ACTIVO" in ceo._format_value(
        "emergency_stop", {"value": True}, overview
    )
    assert "Sin firma" in ceo._format_value(
        "gate", {"value": {"signed": False, "signers": []}}, overview
    )
    cards = ceo._build_cards(
        {
            "equity_reconciled": {
                "status": "ok",
                "value": "1000",
                "unit": "usd",
                "as_of": datetime.now(timezone.utc).isoformat(),
            },
            "breakers": {"status": "ok", "value": []},
            "emergency_stop": {"status": "ok", "value": False},
            "gate": {"status": "ok", "value": {"signed": False, "signers": []}},
            "ops_policy": {
                "status": "ok",
                "value": {"l0_policy_violation": False, "committed_driven_by_burn": False},
            },
            "books": {"status": "ok", "value": {"books": []}},
            "dd_vs_contributed_pct": {"status": "ok", "value": "-1", "unit": "pct"},
            "daily_pnl_pct": {"status": "ok", "value": "0.1", "unit": "pct"},
            "kill_floor": {"status": "ok", "value": "750", "unit": "usd"},
            "contributed_capital": {"status": "ok", "value": "1000", "unit": "usd"},
            "pnl_mtd": {"status": "unavailable", "value": None},
            "ops_burn_mtd": {"status": "ok", "value": "10", "unit": "usd"},
            "ops_reserve_remaining": {"status": "ok", "value": "190"},
            "ops_reserve_committed": {"status": "ok", "value": "10", "unit": "usd"},
            "ops_reserve_total": {"status": "ok", "value": "200"},
        }
    )
    assert len(cards) == len(ceo._CARDS)
    # sin claim de edge en labels
    joined = " ".join(c["display"] for c in cards).lower()
    assert "sharpe" not in joined
    assert "edge" not in joined


def test_ceo_overview_endpoint_mocked(paper_env, monkeypatch):
    monkeypatch.setenv("API_KEY", "cov-24-ceo")
    monkeypatch.setenv("CEO_DASHBOARD_PUBLIC", "false")
    app = FastAPI()
    app.include_router(ceo.router)
    with patch.object(
        ceo,
        "build_ceo_overview",
        return_value={
            "effective_mode": "paper",
            "gate_ready": False,
            "equity_reconciled": {"status": "ok", "value": "1000", "unit": "usd"},
        },
    ):
        r = TestClient(app).get(
            "/api/ceo/overview",
            headers={"Authorization": "Bearer cov-24-ceo"},
        )
    assert r.status_code == 200
    assert r.json()["effective_mode"] == "paper"
    assert r.json()["gate_ready"] is False
