"""COV-70.B — ops paper: tracker, snapshot, pipeline health, breaker, lock.

Paper-only · Redis/HTTP/DB mockeados · Decimal · PROMOTE_LIVE: NO.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from redis.exceptions import RedisError

from app.core.auto_circuit_breaker import AutoCircuitBreaker
from app.core.distributed_lock import (
    check_lock_status,
    force_release_lock,
    get_redis_client,
    reset_redis_client,
    with_distributed_lock,
)
from app.core.operation_tracker import (
    OperationStatus,
    OperationTracker,
)
from app.services import pipeline_health_tasks as ph
from app.services import portfolio_snapshot_service as pss

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("paper_env")]


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ── operation_tracker ────────────────────────────────────────────────────────


def _tracker() -> OperationTracker:
    t = OperationTracker.__new__(OperationTracker)
    t.config = MagicMock()
    t.binance_client = MagicMock()
    t.db = MagicMock()
    t.db.insert_operation_record = AsyncMock()
    t.db.update_operation_status = AsyncMock()
    t.telegram_bot = MagicMock()
    t.telegram_bot.send_alert = AsyncMock(return_value=True)
    t.grafana_metrics = MagicMock()
    t.grafana_metrics.record_metric = AsyncMock(return_value=True)
    t.circuit_breakers = MagicMock()
    t.track_slippage = True
    t.track_fees = True
    t.track_partial_fills = True
    t.track_failed_operations = True
    t.slippage_alert_threshold = Decimal("0.002")
    t.fee_alert_threshold = Decimal("0.005")
    t.failure_rate_alert_threshold = Decimal("0.05")
    t.active_operations = {}
    t.operation_history = []
    t.failed_operations = []
    t.partial_fills = []
    t.total_operations = 0
    t.successful_operations = 0
    t.failed_operations_count = 0
    t.partial_fills_count = 0
    t.total_slippage = Decimal("0")
    t.total_fees = Decimal("0")
    return t


def _intent(**overrides):
    base = {
        "asset": "ETHUSDT",
        "type": "GRID_BUY",
        "side": "BUY",
        "quantity": "0.01",
        "price": "2000",
        "user_id": "u1",
        "strategy_id": "s1",
        "grid_level": 2,
        "metadata": {"paper": True},
    }
    base.update(overrides)
    return base


async def test_tracker_intended_completed_failed_partial(decimal_money):
    t = _tracker()
    op_id = await t.track_operation(_intent())
    assert op_id.startswith("GRIDBOT_")
    assert op_id in t.active_operations
    assert t.active_operations[op_id]["quantity"] == decimal_money("0.01")
    assert t.active_operations[op_id]["intended_value"] == decimal_money("20.00")

    with pytest.raises(KeyError):
        await t.track_operation({"asset": "ETHUSDT"})

    await t.update_operation_status("missing-id", OperationStatus.SUBMITTED, {"x": 1})
    t.db.update_operation_status.assert_awaited()

    await t.update_operation_status(
        op_id,
        OperationStatus.COMPLETED,
        {
            "executed_price": "2010",
            "executed_quantity": "0.01",
            "fees": "0.02",
        },
    )
    assert op_id not in t.active_operations
    assert t.successful_operations == 1
    assert t.total_fees == decimal_money("0.02")
    assert t.total_slippage > 0

    fail_id = await t.track_operation(_intent(price="1990", metadata={"n": 2}))
    await t.update_operation_status(
        fail_id,
        OperationStatus.FAILED,
        {"failure_reason": "MIN_NOTIONAL", "failure_code": -1013},
    )
    assert fail_id not in t.active_operations
    assert t.failed_operations_count == 1
    t.telegram_bot.send_alert.assert_awaited()

    part_id = await t.track_operation(_intent(quantity="0.02", price="2000"))
    await t.update_operation_status(
        part_id,
        OperationStatus.PARTIALLY_FILLED,
        {
            "executed_price": "2000",
            "executed_quantity": "0.01",
            "remaining_quantity": "0.01",
            "fees": "0.001",
        },
    )
    assert t.partial_fills_count == 1
    assert t.total_operations >= 4  # remainder crea otra INTENDED


async def test_tracker_zero_intended_price_alerts_and_summaries(decimal_money):
    t = _tracker()
    t.slippage_alert_threshold = Decimal("0.0001")
    t.fee_alert_threshold = Decimal("0.0001")
    op_id = await t.track_operation(_intent(price="0"))
    await t.process_completed_operation(
        op_id,
        {"executed_price": "1", "executed_quantity": "0.01", "fees": "1"},
    )
    assert op_id not in t.active_operations
    assert t.operation_history[-1]["slippage"] == 0

    live_id = await t.track_operation(_intent(price="100"))
    await t.check_slippage_and_fee_alerts(
        live_id, Decimal("0.05"), Decimal("1")
    )
    t.telegram_bot.send_alert.assert_awaited()

    t.telegram_bot.send_alert.side_effect = RuntimeError("tg")
    await t.check_slippage_and_fee_alerts(live_id, Decimal("1"), Decimal("1"))
    await t.check_and_send_alerts(live_id, "INTENDED", OperationStatus.FAILED)
    await t.check_and_send_alerts(
        live_id, "INTENDED", OperationStatus.PARTIALLY_FILLED
    )

    t.grafana_metrics.record_metric.side_effect = RuntimeError("prom")
    await t.update_grafana_metrics()

    empty = _tracker()
    summary0 = await empty.get_operation_summary()
    assert summary0["success_rate"] == 1.0
    assert summary0["average_slippage"] == 0.0

    t.total_operations = 10
    t.successful_operations = 8
    t.failed_operations_count = 2
    t.total_slippage = Decimal("0.08")
    t.total_fees = Decimal("0.16")
    t.grafana_metrics.record_metric.side_effect = None
    t.grafana_metrics.record_metric = AsyncMock(return_value=True)
    await t.update_grafana_metrics()
    summary = await t.get_operation_summary()
    assert summary["failure_rate"] == 0.2
    assert summary["average_fees"] == pytest.approx(0.02)

    t.failed_operations = [{"id": i} for i in range(3)]
    t.partial_fills = [{"id": i} for i in range(2)]
    assert len(await t.get_failed_operations_summary()) == 3
    assert len(await t.get_partial_fills_summary()) == 2


async def test_tracker_process_exceptions_force_check_cleanup():
    t = _tracker()
    t.active_operations["bad"] = None
    await t.process_completed_operation("bad", {})
    await t.process_failed_operation("bad", {})
    await t.process_partial_fill("bad", {})

    t.db.update_operation_status.side_effect = RuntimeError("db")
    t.active_operations["x"] = {
        "status": "INTENDED",
        "asset": "ETHUSDT",
        "operation_type": "BUY",
        "intended_price": Decimal("1"),
    }
    await t.update_operation_status("x", OperationStatus.SUBMITTED, None)

    t.db.update_operation_status.side_effect = None
    t.db.update_operation_status = AsyncMock()
    live = await t.track_operation(_intent())
    await t.force_operation_check()
    assert live not in t.active_operations
    assert t.successful_operations >= 1

    oid = t.generate_operation_id()
    assert oid.startswith("OP_")

    now = datetime.now().isoformat()
    old = (datetime.now() - timedelta(days=90)).isoformat()
    t.operation_history = [{"timestamp": old}, {"timestamp": now}]
    t.failed_operations = [{"timestamp": old}]
    t.partial_fills = [{"timestamp": "not-a-date"}]
    await t.cleanup_old_operations(days_old=30)
    # timestamp inválido dispara except y no muta listas a medias de forma segura
    t.partial_fills = [{"timestamp": old}, {"timestamp": now}]
    await t.cleanup_old_operations(days_old=30)
    assert all(
        datetime.fromisoformat(op["timestamp"]) > datetime.now() - timedelta(days=40)
        for op in t.operation_history
    )

    sleeps = {"n": 0}

    async def _sleep(_seconds):
        sleeps["n"] += 1
        if sleeps["n"] >= 2:
            raise asyncio.CancelledError()
        return None

    with patch.object(t, "cleanup_old_operations", new=AsyncMock()) as cleaned:
        with patch("app.core.operation_tracker.asyncio.sleep", _sleep):
            with pytest.raises(asyncio.CancelledError):
                await t.start_periodic_cleanup(cleanup_interval=0)
    cleaned.assert_awaited()

    sleeps["n"] = 0

    async def _sleep_err(_seconds):
        sleeps["n"] += 1
        if sleeps["n"] >= 3:
            raise asyncio.CancelledError()
        return None

    with patch.object(
        t, "cleanup_old_operations", new=AsyncMock(side_effect=RuntimeError("wipe"))
    ):
        with patch("app.core.operation_tracker.asyncio.sleep", _sleep_err):
            with pytest.raises(asyncio.CancelledError):
                await t.start_periodic_cleanup(cleanup_interval=0)


# ── portfolio_snapshot_service ───────────────────────────────────────────────


def test_snapshot_history_queries():
    db = MagicMock()
    rows = [
        SimpleNamespace(total_value_usdt=Decimal("100.50")),
        SimpleNamespace(total_value_usdt=Decimal("101.25")),
    ]
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = (
        rows
    )
    hist = pss.get_portfolio_value_history(db, days=7)
    assert hist == [100.50, 101.25]

    snap = SimpleNamespace(id=3)
    db.query.return_value.order_by.return_value.first.return_value = snap
    assert pss.get_latest_snapshot(db) is snap

    db.query.return_value.scalar.return_value = 4
    assert pss.get_snapshot_count(db) == 4
    db.query.return_value.scalar.return_value = None
    assert pss.get_snapshot_count(db) == 0


def test_compute_portfolio_value_live_and_errors(monkeypatch):
    monkeypatch.setattr(pss, "paper_equity_is_source_of_truth", lambda: True)
    with patch.object(pss, "compute_paper_portfolio_value", return_value={"total_value_usdt": 10}):
        assert pss._compute_portfolio_value_sync()["total_value_usdt"] == 10

    monkeypatch.setattr(pss, "paper_equity_is_source_of_truth", lambda: False)
    singleton = MagicMock()
    singleton.is_ready.return_value = False
    with patch.object(pss, "get_binance_client_singleton", return_value=singleton):
        assert pss._compute_portfolio_value_sync() is None

    singleton.is_ready.return_value = True
    client = MagicMock()
    client.create_order.side_effect = AssertionError("no create_order")
    client.get_account.side_effect = RuntimeError("acct")
    singleton.client = client
    with patch.object(pss, "get_binance_client_singleton", return_value=singleton):
        assert pss._compute_portfolio_value_sync() is None

    def _ticker(*, symbol):
        if symbol in {"BTCUSDT"}:
            return {"price": "50000"}
        if symbol in {"SOLUSDT"}:
            return {"price": "100"}
        if symbol in {"ETHUSDT"}:
            return {"price": "2000"}
        raise RuntimeError("no pair")

    client.get_account.side_effect = None
    client.get_account.return_value = {
        "balances": [
            {"asset": "USDT", "free": "80", "locked": "20"},
            {"asset": "USDC", "free": "5", "locked": "0"},
            {"asset": "BTC", "free": "0.001", "locked": "0"},
            {"asset": "ETH", "free": "0", "locked": "0"},
            {"asset": "LDUSDT", "free": "10", "locked": "0"},
            {"asset": "LDBTC", "free": "0.002", "locked": "0"},
            {"asset": "LDETH", "free": "0.5", "locked": "0"},
            {"asset": "LDUNK", "free": "1", "locked": "0"},
            {"asset": "SOL", "free": "2", "locked": "0"},
            {"asset": "DOGE", "free": "10", "locked": "0"},
        ]
    }
    client.get_symbol_ticker.side_effect = _ticker
    with patch.object(pss, "get_binance_client_singleton", return_value=singleton):
        data = pss._compute_portfolio_value_sync()
    assert data is not None
    assert data["usdt_free"] == pytest.approx(115.0)  # 100 + 5 + 10 LDUSDT
    assert data["btc_value_usdt"] == pytest.approx(150.0)  # 0.001+0.002 * 50000
    assert data["other_assets_usdt"] == pytest.approx(1200.0)  # 2*100 SOL + 0.5*2000 LDETH
    assert data["btc_price"] == pytest.approx(50000.0)


def test_save_snapshot_and_celery_task(monkeypatch):
    payload = {
        "total_value_usdt": 250.0,
        "usdt_free": 100.0,
        "btc_value_usdt": 100.0,
        "other_assets_usdt": 50.0,
        "btc_price": 50000.0,
        "primary_symbol": "ETHUSDT",
    }
    monkeypatch.setattr(pss, "_compute_portfolio_value_sync", lambda: None)
    assert pss.save_portfolio_snapshot() is None

    snap = MagicMock()
    snap.id = 42
    snap.total_value_usdt = 250.0
    snap.captured_at = datetime.now()  # naive → rama tzinfo is None
    db = MagicMock()
    monkeypatch.setattr(pss, "_compute_portfolio_value_sync", lambda: payload)
    with patch.object(pss, "SessionLocal", return_value=db), patch.object(
        pss, "PortfolioSnapshot", return_value=snap
    ), patch("app.core.obs_gauges.publish_obs_gauges"):
        out = pss.save_portfolio_snapshot()
    assert out is snap
    db.commit.assert_called()

    snap.captured_at = datetime.now(timezone.utc)
    db.commit.side_effect = None
    with patch.object(pss, "SessionLocal", return_value=db), patch.object(
        pss, "PortfolioSnapshot", return_value=snap
    ), patch(
        "app.core.obs_gauges.publish_obs_gauges",
        side_effect=RuntimeError("obs"),
    ):
        assert pss.save_portfolio_snapshot() is snap

    snap.captured_at = datetime.now(timezone.utc)
    db.commit.side_effect = RuntimeError("pk")
    with patch.object(pss, "SessionLocal", return_value=db), patch.object(
        pss, "PortfolioSnapshot", return_value=snap
    ):
        assert pss.save_portfolio_snapshot() is None
    db.rollback.assert_called()

    monkeypatch.setattr(pss, "save_portfolio_snapshot", lambda: None)
    skipped = pss.capture_portfolio_snapshot.run()
    assert skipped["status"] == "skipped"

    monkeypatch.setattr(pss, "save_portfolio_snapshot", lambda: snap)
    ok = pss.capture_portfolio_snapshot.run()
    assert ok["status"] == "ok" and ok["snapshot_id"] == 42

    monkeypatch.setattr(
        pss, "save_portfolio_snapshot", MagicMock(side_effect=RuntimeError("celery"))
    )
    with pytest.raises(Exception):
        pss.capture_portfolio_snapshot.run()


def test_startup_enqueue_and_worker_ready(monkeypatch):
    monkeypatch.setattr(pss, "paper_equity_is_source_of_truth", lambda: True)
    monkeypatch.setenv("PORTFOLIO_SNAPSHOT_ON_STARTUP", "true")
    delay = MagicMock()
    monkeypatch.setattr(pss.capture_portfolio_snapshot, "delay", delay)

    redis_cli = MagicMock()
    redis_cli.set.return_value = True
    monkeypatch.setattr("redis.Redis.from_url", lambda *_a, **_k: redis_cli)
    assert pss.enqueue_startup_portfolio_snapshot() is True
    delay.assert_called_once()

    redis_cli.set.return_value = None
    delay.reset_mock()
    assert pss.enqueue_startup_portfolio_snapshot() is False
    delay.assert_not_called()

    monkeypatch.setattr(
        "redis.Redis.from_url",
        MagicMock(side_effect=RuntimeError("no redis")),
    )
    delay.reset_mock()
    assert pss.enqueue_startup_portfolio_snapshot() is True  # fail-open
    delay.assert_called_once()

    monkeypatch.setenv("PORTFOLIO_SNAPSHOT_ON_STARTUP", "false")
    assert pss.should_enqueue_startup_portfolio_snapshot() is False

    monkeypatch.delenv("PORTFOLIO_SNAPSHOT_ON_STARTUP", raising=False)
    monkeypatch.setattr(pss, "paper_equity_is_source_of_truth", lambda: False)
    assert pss.should_enqueue_startup_portfolio_snapshot() is False
    assert pss.enqueue_startup_portfolio_snapshot() is False

    pss._STARTUP_SNAPSHOT_SIGNAL_CONNECTED = True
    pss._connect_worker_ready_startup_snapshot()  # early return

    captured = {}

    class _Sig:
        def connect(self, **_kw):
            def deco(fn):
                captured["fn"] = fn
                return fn

            return deco

    pss._STARTUP_SNAPSHOT_SIGNAL_CONNECTED = False
    with patch("celery.signals.worker_ready", _Sig()):
        pss._connect_worker_ready_startup_snapshot()
    assert pss._STARTUP_SNAPSHOT_SIGNAL_CONNECTED is True
    with patch.object(pss, "enqueue_startup_portfolio_snapshot", return_value=True):
        captured["fn"]()
    with patch.object(
        pss, "enqueue_startup_portfolio_snapshot", side_effect=RuntimeError("boot")
    ):
        captured["fn"]()  # no debe romper worker


# ── pipeline_health_tasks ────────────────────────────────────────────────────


def test_prom_query_error_branches():
    with patch.object(ph.httpx, "get", side_effect=httpx.ConnectError("down")):
        assert ph._prom_query("up") is None

    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"status": "error"}
    with patch.object(ph.httpx, "get", return_value=resp):
        assert ph._prom_query("up") is None

    resp.json.return_value = {"status": "success", "data": None}
    with patch.object(ph.httpx, "get", return_value=resp):
        assert ph._prom_query("up") == 0.0

    resp.json.return_value = {
        "status": "success",
        "data": {"result": []},
    }
    with patch.object(ph.httpx, "get", return_value=resp):
        assert ph._prom_query("up") == 0.0

    resp.json.return_value = {
        "status": "success",
        "data": {"result": [{"metric": {}}]},
    }
    with patch.object(ph.httpx, "get", return_value=resp):
        assert ph._prom_query("up") == 0.0

    resp.json.return_value = {
        "status": "success",
        "data": {"result": [{"value": [1, "3.5"]}]},
    }
    with patch.object(ph.httpx, "get", return_value=resp):
        assert ph._prom_query("up") == pytest.approx(3.5)

    with patch.object(ph, "_prom_query", return_value=4.0) as pq:
        assert ph._check_table_prometheus("trades") == pytest.approx(4.0)
    pq.assert_called_once()


def test_sql_helpers_and_fallback(tmp_path, monkeypatch):
    session = MagicMock()
    session.execute.return_value.fetchone.return_value = None
    assert ph._db_scalar(session, "SELECT 1") is None
    session.execute.return_value.fetchone.return_value = (9,)
    assert ph._db_scalar(session, "SELECT 1") == 9

    session.execute.return_value.fetchall.return_value = [("id",), ("qty",)]
    assert ph._max_ts_column_for_table(session, "trades") == "timestamp"

    now = datetime.now(timezone.utc)

    def _execute(sql, params=None):
        text_sql = str(sql)
        result = MagicMock()
        if "information_schema.columns" in text_sql:
            if params and params.get("t") == "trades":
                result.fetchall.return_value = [("timestamp",)]
            elif params and params.get("t") == "performance_metrics":
                result.fetchall.return_value = [("created_at",)]
            else:
                result.fetchall.return_value = [("updated_at",)]
            return result
        if "portfolio_snapshots" in text_sql:
            result.fetchone.return_value = (now,)
        elif "alerts" in text_sql:
            result.fetchone.return_value = (now,)
        else:
            result.fetchone.return_value = (now - timedelta(minutes=10),)
        return result

    session.execute.side_effect = _execute
    fb = ph._sql_fallback_checks(session)
    assert fb["portfolio_snapshots"]["ok"] is True
    assert fb["alerts"]["ok"] is True
    assert "trades" in fb

    monkeypatch.setattr(ph, "REPORTS_DIR", tmp_path)
    path = ph._write_reports({"ok": True})
    assert path.exists()
    latest = json.loads((tmp_path / "pipeline_health" / "LATEST.json").read_text())
    assert latest["ok"] is True


def _session_max(captured_at):
    db = MagicMock()

    def execute(sql, params=None):
        text_sql = str(sql)
        result = MagicMock()
        if "information_schema.columns" in text_sql:
            result.fetchall.return_value = [("timestamp",), ("updated_at",)]
            return result
        if "portfolio_snapshots" in text_sql:
            result.fetchone.return_value = (captured_at,)
        else:
            result.fetchone.return_value = (captured_at,)
        return result

    db.execute.side_effect = execute
    return db


def test_check_pipeline_db_writes_prom_and_sql_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(ph, "REPORTS_DIR", tmp_path)
    monkeypatch.setattr(ph, "ALERTS_SOFT_ONLY", True)
    now = datetime.now(timezone.utc)
    fresh = now - timedelta(minutes=5)

    with patch.object(ph, "_check_table_prometheus", return_value=2.0), patch.object(
        ph, "SessionLocal", return_value=_session_max(fresh)
    ), patch("app.core.obs_gauges.publish_obs_gauges"):
        ok = ph.check_pipeline_db_writes.run()
    assert ok["ok"] is True and ok["status"] == "ok"

    def _mixed(table):
        if table == "alerts":
            return 0.0
        if table == "trades":
            return None
        return 1.0

    monkeypatch.setenv("PAPER_TRADING", "false")
    with patch.object(ph, "_check_table_prometheus", side_effect=_mixed), patch.object(
        ph, "SessionLocal", return_value=_session_max(fresh)
    ), patch("app.core.obs_gauges.publish_obs_gauges"):
        mixed = ph.check_pipeline_db_writes.run()
    assert mixed["ok"] is False
    assert any("Prometheus sin datos" in f for f in mixed["failures"])

    monkeypatch.setenv("PAPER_TRADING", "true")
    stale = now - timedelta(hours=3)
    with patch.object(ph, "_check_table_prometheus", return_value=None), patch.object(
        ph, "SessionLocal", return_value=_session_max(stale)
    ), patch("app.core.obs_gauges.publish_obs_gauges"):
        degraded = ph.check_pipeline_db_writes.run()
    assert degraded["status"] == "degraded"
    assert any("portfolio_snapshots" in f for f in degraded["failures"])

    with patch.object(ph, "_check_table_prometheus", return_value=None), patch.object(
        ph, "SessionLocal", return_value=_session_max(fresh)
    ), patch(
        "app.core.metrics.pipeline_health_degraded",
        new=MagicMock(set=MagicMock(side_effect=RuntimeError("g"))),
    ), patch(
        "app.core.obs_gauges.publish_obs_gauges",
        side_effect=RuntimeError("obs"),
    ):
        idle = ph.check_pipeline_db_writes.run()
    assert idle["ok"] is True
    assert idle.get("paper_aware") is True

    monkeypatch.setenv("PAPER_TRADING", "false")
    with patch.object(ph, "_check_table_prometheus", return_value=0.0), patch.object(
        ph, "SessionLocal", return_value=_session_max(fresh)
    ), patch("app.core.obs_gauges.publish_obs_gauges"):
        zero_inc = ph.check_pipeline_db_writes.run()
    assert zero_inc["ok"] is False
    assert any("== 0" in f for f in zero_inc["failures"])

    stale = now - timedelta(hours=3)
    with patch.object(ph, "_check_table_prometheus", return_value=None), patch.object(
        ph, "SessionLocal", return_value=_session_max(stale)
    ), patch("app.core.obs_gauges.publish_obs_gauges"):
        sql_hard = ph.check_pipeline_db_writes.run()
    assert sql_hard["ok"] is False
    assert any("fallback SQL" in f for f in sql_hard["failures"])


# ── auto_circuit_breaker ─────────────────────────────────────────────────────


def _breakers_mock():
    b = MagicMock()
    b.activate_breaker = AsyncMock(return_value=True)
    b.activate_critical_mode = AsyncMock(return_value=True)
    b.deactivate_breaker = AsyncMock(return_value=True)
    b.get_all_breakers_status.return_value = {
        "active_breakers": [],
        "total_active": 0,
        "critical_mode": False,
    }
    return b


async def test_auto_cb_breakers_property_and_metrics():
    override = _breakers_mock()
    auto = AutoCircuitBreaker(breakers=override)
    assert auto.breakers is override

    naked = AutoCircuitBreaker()
    assert naked.breakers is not None

    db = MagicMock()
    q = db.query.return_value
    q.filter.return_value.scalar.return_value = -20.0
    with patch(
        "app.core.paper_equity_ledger.paper_equity_is_source_of_truth",
        return_value=False,
    ):
        metrics = await auto._calculate_loss_metrics(db)
        assert metrics["total_loss_usd"] == pytest.approx(20.0)
        assert metrics["daily_loss_pct"] > 0

        db.query.side_effect = RuntimeError("sql")
        zeros = await auto._calculate_loss_metrics(db)
        assert zeros["total_loss_pct"] == 0.0


async def test_auto_cb_thresholds_and_manual():
    b = _breakers_mock()
    auto = AutoCircuitBreaker(breakers=b)
    results = {
        "breakers_activated": [],
        "reasons": [],
        "critical_mode": False,
    }
    hot = {
        "daily_loss_pct": 0.50,
        "total_loss_pct": 0.25,
        "hourly_loss_pct": 0.10,
    }
    await auto._check_daily_loss_threshold(hot, results)
    await auto._check_total_loss_threshold(hot, results)
    await auto._check_hourly_loss_threshold(hot, results)
    await auto._check_critical_loss_threshold(hot, results)
    hourly_only = {"breakers_activated": [], "reasons": []}
    await auto._check_hourly_loss_threshold(hot, hourly_only)
    assert "operation_failure_rate" in hourly_only["breakers_activated"]
    assert "balance_discrepancy" in results["breakers_activated"]
    assert "operation_failure_rate" in results["breakers_activated"]
    assert results["critical_mode"] is True
    b.activate_critical_mode.assert_awaited()

    db = MagicMock()
    losses = [SimpleNamespace(profit_loss=-1.0) for _ in range(6)]
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = (
        losses
    )
    with patch(
        "app.core.paper_equity_ledger.paper_equity_is_source_of_truth",
        return_value=False,
    ):
        await auto._check_consecutive_losses(db, results)
        assert "system_integrity" in results["breakers_activated"]

        db.query.side_effect = RuntimeError("trades")
        await auto._check_consecutive_losses(db, results)

        mixed = [
            SimpleNamespace(profit_loss=-1.0),
            SimpleNamespace(profit_loss=1.0),
        ]
        db.query.side_effect = None
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = (
            mixed
        )
        extra = {"breakers_activated": [], "reasons": []}
        await auto._check_consecutive_losses(db, extra)
        assert extra["breakers_activated"] == []

    db_ok = MagicMock()
    db_ok.query.return_value.filter.return_value.scalar.return_value = 0.0
    db_ok.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = (
        []
    )
    with patch.object(auto, "_calculate_loss_metrics", new=AsyncMock(return_value=hot)):
        with patch("app.core.auto_circuit_breaker.SessionLocal", return_value=db_ok):
            out = await auto.check_and_activate_breakers()
    assert out["breakers_activated"]
    assert "balance_discrepancy" in out["breakers_activated"]

    with patch(
        "app.core.auto_circuit_breaker.SessionLocal",
        side_effect=RuntimeError("db down"),
    ):
        err = await auto.check_and_activate_breakers()
    assert "error" in err

    status = await auto.get_breakers_status()
    assert "active_breakers" in status

    assert await auto.manual_activation("system_integrity", "paper test") is True
    b.activate_breaker.return_value = False
    assert await auto.manual_activation("system_integrity", "no") is False
    b.activate_breaker.side_effect = RuntimeError("act")
    assert await auto.manual_activation("system_integrity", "x") is False

    assert await auto.manual_deactivation("system_integrity") is True
    b.deactivate_breaker.return_value = False
    assert await auto.manual_deactivation("system_integrity") is False
    b.deactivate_breaker.side_effect = RuntimeError("deact")
    assert await auto.manual_deactivation("system_integrity") is False


# ── distributed_lock ─────────────────────────────────────────────────────────


@pytest.fixture
def clean_redis_singleton():
    reset_redis_client()
    yield
    reset_redis_client()


def test_get_redis_client_success_and_error(clean_redis_singleton, monkeypatch):
    fake = MagicMock()
    fake.ping.return_value = True
    with patch("app.core.distributed_lock.Redis.from_url", return_value=fake):
        c1 = get_redis_client()
        c2 = get_redis_client()
    assert c1 is fake and c2 is fake

    reset_redis_client()
    with patch(
        "app.core.distributed_lock.Redis.from_url",
        side_effect=RedisError("down"),
    ):
        with pytest.raises(RedisError):
            get_redis_client()


def test_distributed_lock_decorator_paths(clean_redis_singleton):
    lock = MagicMock()
    lock.acquire.return_value = False
    lock.owned.return_value = False
    client = MagicMock()
    client.lock.return_value = lock

    with patch("app.core.distributed_lock.get_redis_client", return_value=client):
        @with_distributed_lock("cov70_skip", timeout=5, blocking=False)
        def skipped():
            return {"status": "ok"}

        out = skipped()
    assert out["status"] == "skipped" and out["reason"] == "lock_held"

    lock.acquire.return_value = True
    lock.owned.return_value = True
    with patch("app.core.distributed_lock.get_redis_client", return_value=client), patch(
        "app.core.distributed_lock.METRICS_AVAILABLE", True
    ), patch(
        "app.core.distributed_lock.distributed_lock_acquired_total"
    ) as acq, patch(
        "app.core.distributed_lock.distributed_lock_duration_seconds"
    ) as dur:
        acq.labels.side_effect = RuntimeError("prom")
        dur.labels.side_effect = RuntimeError("prom")

        @with_distributed_lock("cov70_ok", timeout=5, blocking=False)
        def work():
            return {"status": "ok", "n": 1}

        assert work()["n"] == 1
    lock.release.assert_called()

    lock.release.side_effect = RedisError("unlock")
    with patch("app.core.distributed_lock.get_redis_client", return_value=client):

        @with_distributed_lock("cov70_unlock", timeout=5, blocking=False)
        def work2():
            return {"status": "ok"}

        assert work2()["status"] == "ok"

    lock.release.side_effect = None
    lock.acquire.return_value = True

    with patch("app.core.distributed_lock.get_redis_client", return_value=client), patch(
        "app.core.distributed_lock.distributed_lock_errors_total"
    ) as err_m:
        err_m.labels.side_effect = RuntimeError("prom")

        @with_distributed_lock("cov70_boom", timeout=5, blocking=False)
        def boom():
            raise ValueError("task-fail")

        with pytest.raises(ValueError, match="task-fail"):
            boom()

    with patch(
        "app.core.distributed_lock.get_redis_client",
        side_effect=RedisError("no-redis"),
    ):

        @with_distributed_lock("cov70_degraded", timeout=5, blocking=False)
        def degraded():
            return {"status": "ran-without-lock"}

        assert degraded()["status"] == "ran-without-lock"

    client.lock.side_effect = RedisError("mid")
    with patch("app.core.distributed_lock.get_redis_client", return_value=client):

        @with_distributed_lock("cov70_mid", timeout=5, blocking=False)
        def mid():
            return {"status": "degraded-mid"}

        assert mid()["status"] == "degraded-mid"


def test_lock_status_and_force_release(clean_redis_singleton):
    client = MagicMock()
    client.exists.return_value = 1
    client.ttl.return_value = 12
    client.delete.return_value = 1
    with patch("app.core.distributed_lock.get_redis_client", return_value=client):
        locked = check_lock_status("cov70")
        assert locked["status"] == "locked" and locked["ttl_seconds"] == 12
        client.exists.return_value = 0
        assert check_lock_status("cov70")["status"] == "free"
        assert force_release_lock("cov70") is True
        client.delete.return_value = 0
        assert force_release_lock("cov70") is False

    with patch(
        "app.core.distributed_lock.get_redis_client",
        side_effect=RedisError("x"),
    ):
        err = check_lock_status("cov70")
        assert err["status"] == "error"
        assert force_release_lock("cov70") is False


def test_lock_skipped_metrics_exception(clean_redis_singleton):
    lock = MagicMock()
    lock.acquire.return_value = False
    lock.owned.return_value = False
    client = MagicMock()
    client.lock.return_value = lock
    with patch("app.core.distributed_lock.get_redis_client", return_value=client), patch(
        "app.core.distributed_lock.METRICS_AVAILABLE", True
    ), patch(
        "app.core.distributed_lock.distributed_lock_skipped_total"
    ) as skipped:
        skipped.labels.side_effect = RuntimeError("prom")

        @with_distributed_lock("cov70_skip_m", timeout=5, blocking=False)
        def fn():
            return {"status": "ok"}

        assert fn()["status"] == "skipped"
