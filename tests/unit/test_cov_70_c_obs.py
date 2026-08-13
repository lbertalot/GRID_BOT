"""COV-70-C — observabilidad paper-safe (monitoring / metrics / tracing / alerts).

Paper-only · no live · PROMOTE_LIVE: NO.
HTTP Telegram y OpenTelemetry mockeados; cero red.
"""

from __future__ import annotations

import json
import sys
import time
import types
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("paper_env")]


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def _obs_paper_flags(paper_env, monkeypatch):
    monkeypatch.setenv("CI", "true")
    monkeypatch.setenv("CB_SHARED_STORE", "memory")
    monkeypatch.setenv("FORCE_REAL_MODE", "")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "")
    return paper_env


# --------------------------------------------------------------------------- #
# monitoring.py
# --------------------------------------------------------------------------- #


@pytest.fixture
def monitor(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from app.core.monitoring import MonitoringSystem

    return MonitoringSystem()


def test_monitoring_load_save_and_alert_levels(monitor, tmp_path, decimal_money):
    from app.core.monitoring import MonitoringSystem

    payload = {
        "metrics": {"total_trades": 4, "daily_pnl": 0.0, "current_balance": 80.0},
        "alerts": [{"level": "INFO", "message": "boot"}],
    }
    (tmp_path / "monitoring_data.json").write_text(json.dumps(payload))
    loaded = MonitoringSystem()
    assert loaded.metrics["total_trades"] == 4
    assert loaded.alerts[0]["message"] == "boot"

    (tmp_path / "monitoring_data.json").write_text("{not-json")
    broken = MonitoringSystem()
    assert broken.metrics["total_trades"] == 0

    with patch("app.core.monitoring.json.dump", side_effect=RuntimeError("disk")):
        monitor.save_data()

    monitor.add_alert("INFO", "info-ok", "OPS")
    monitor.add_alert("WARNING", "warn-ok", "OPS")
    monitor.add_alert("ERROR", "err-ok", "FINANCIAL", {"bal": float(decimal_money("10"))})
    monitor.add_alert("CRITICAL", "crit-ok", "FINANCIAL")
    levels = {a["level"] for a in monitor.alerts}
    assert {"INFO", "WARNING", "ERROR", "CRITICAL"} <= levels

    for i in range(101):
        monitor.add_alert("INFO", f"trim-{i}", "OPS")
    assert len(monitor.alerts) == 100


def test_monitoring_thresholds_trades_balance_status(monitor, decimal_money):
    from app.core import monitoring as mon

    monitor.update_metrics(daily_pnl=-0.10, hourly_pnl=-0.05, current_balance=10.0)
    assert any(a["level"] == "CRITICAL" for a in monitor.alerts)
    assert any("hora" in a["message"] for a in monitor.alerts)
    assert any(a["level"] == "ERROR" for a in monitor.alerts)

    monitor.metrics["total_trades"] = 10
    monitor.metrics["failed_trades"] = 8
    monitor._check_thresholds()
    assert any("fallidos" in a["message"] for a in monitor.alerts)

    qty = float(decimal_money("0.01"))
    px = float(decimal_money("50000"))
    monitor.record_trade("BTCUSDT", "BUY", qty, px, True, profit_loss=1.5)
    monitor.record_trade("BTCUSDT", "SELL", qty, px, True, profit_loss=-0.01)
    monitor.record_trade("ETHUSDT", "BUY", qty, px, False, profit_loss=0.0)
    monitor.record_trade("BTCUSDT", "SELL", qty, px, True, profit_loss=-0.50)
    assert monitor.metrics["total_trades"] >= 4
    assert monitor.metrics["failed_trades"] >= 1
    assert monitor.metrics["total_profit"] > 0

    monitor.metrics["current_balance"] = float(decimal_money("100"))
    monitor.update_balance(float(decimal_money("100")))
    monitor.update_balance(float(decimal_money("90")))
    assert monitor.metrics["daily_pnl"] != 0.0

    monitor.alerts = [{"level": "CRITICAL", "message": "x"}]
    assert monitor._get_system_status() == "CRITICAL"
    monitor.alerts = [{"level": "ERROR", "message": f"e{i}"} for i in range(3)]
    assert monitor._get_system_status() == "WARNING"
    monitor.alerts = []
    monitor.metrics["daily_pnl"] = -0.04
    assert monitor._get_system_status() == "WARNING"
    monitor.metrics["daily_pnl"] = 0.0
    assert monitor._get_system_status() == "HEALTHY"

    monitor.reset_daily_metrics()
    assert monitor.metrics["daily_pnl"] == 0.0

    from app.core.monitoring import MonitoringSystem as MS

    bare = MS.__new__(MS)
    bare.metrics = {
        "total_trades": 0,
        "successful_trades": 0,
        "failed_trades": 0,
        "total_profit": 0.0,
        "total_loss": 0.0,
        "current_balance": 0.0,
        "daily_pnl": 0.0,
        "hourly_pnl": 0.0,
    }
    bare.alerts = []
    assert "No hay trades" in bare.get_performance_summary()["message"]

    summary = monitor.get_performance_summary()
    assert "success_rate" in summary
    status = monitor.get_status()
    assert status["system_status"] in {"HEALTHY", "WARNING", "CRITICAL"}

    mon.record_trade_event("BTCUSDT", "BUY", qty, px, True, 0.1)
    mon.update_balance_monitoring(float(decimal_money("120")))
    assert "metrics" in mon.get_monitoring_status()


# --------------------------------------------------------------------------- #
# metrics.py
# --------------------------------------------------------------------------- #


def test_metrics_helpers_success_and_errors(decimal_money):
    from app.core import metrics as m

    m.record_api_request("GET", "/healthz", 200, 0.01)
    blob = m.get_metrics()
    assert blob is not None

    with patch.object(m.gridbot_api_requests_total, "labels", side_effect=RuntimeError("prom")):
        m.record_api_request("GET", "/x", 500, 0.2)

    with patch("prometheus_client.generate_latest", side_effect=RuntimeError("gen")):
        assert m.get_metrics() == ""

    with patch.object(m, "profit_total_usdt") as p, patch.object(
        m, "roi_daily_percent"
    ) as r, patch.object(m, "portfolio_total_value_usdt") as v:
        p._value.get.return_value = 1.0
        r._value.get.return_value = 2.0
        v._value.get.return_value = 3.0
        got = m.get_trading_metrics()
    assert got["profit_total"] == 1.0

    with patch.object(m.profit_total_usdt, "_value", create=True) as val:
        val.get.side_effect = RuntimeError("n")
        assert m.get_trading_metrics() == {}

    with patch.object(m, "gridbot_api_requests_total") as c, patch.object(
        m, "api_request_duration"
    ) as h:
        c._value.get.return_value = 9
        h._value.get.return_value = 0.1
        assert m.get_binance_metrics()["api_requests"] == 9
    with patch.object(m.gridbot_api_requests_total, "_value", create=True) as val:
        val.get.side_effect = RuntimeError("n")
        assert m.get_binance_metrics() == {}

    with patch.object(m, "bot_status") as b, patch.object(
        m, "bot_errors_total"
    ) as e, patch.object(m, "active_positions_count") as a:
        b._value.get.return_value = 1
        e._value.get.return_value = 0
        a._value.get.return_value = 2
        assert m.get_strategy_metrics()["bot_status"] == 1
    with patch.object(m.bot_status, "_value", create=True) as val:
        val.get.side_effect = RuntimeError("n")
        assert m.get_strategy_metrics() == {}

    qty = float(decimal_money("0.002"))
    px = float(decimal_money("50000"))
    m.record_order_execution("COV70BTC", "BUY", "LIMIT", "grid", qty, px)
    with patch.object(m.gridbot_orders_total, "labels", side_effect=RuntimeError("o")):
        m.record_order_execution("X", "BUY", "LIMIT", "grid", 1.0, 1.0)

    m.record_order_failure("COV70BTC", "SELL", "MARKET", "timeout")
    with patch.object(m.trades_failed_total, "labels", side_effect=RuntimeError("f")):
        m.record_order_failure("X", "BUY", "MARKET", "x")

    empty = m.compute_win_loss_and_sharpe([])
    assert empty == {"win_ratio": 0.0, "sharpe": 0.0}
    mixed = m.compute_win_loss_and_sharpe(
        [{"profit_loss": Decimal("10")}, {"profit_loss": Decimal("-2")}, {"profit_loss": 0}]
    )
    assert mixed["win_ratio"] > 0

    m.record_symbol_error("COV70USDT", "invalid_symbol")
    with patch.object(m.bot_errors_total, "labels", side_effect=RuntimeError("s")):
        m.record_symbol_error("Z", "x")

    m.update_balance("USDT", 10.0, 1.0)
    with patch.object(m.trading_metrics, "update_balances", side_effect=RuntimeError("b")):
        m.update_balance("USDT", 1.0, 0.0)

    m.update_strategy_status("grid", 3)
    with patch.object(
        m.trading_metrics, "update_active_positions", side_effect=RuntimeError("st")
    ):
        m.update_strategy_status("grid", 0)

    m.update_profit_loss("COV70BTC", "grid", 1.25)
    with patch.object(m.profit_by_asset_usdt, "labels", side_effect=RuntimeError("pnl")):
        m.update_profit_loss("X", "grid", 1.0)


def test_trading_metrics_class_paths(decimal_money):
    from app.core.metrics import TradingMetrics

    tm = TradingMetrics()
    tm.set_initial_portfolio_value(float(decimal_money("1000")))
    tm.last_update = time.time() - 90_000
    tm.daily_profit_current = 5.0
    tm.update_profit_metrics(12.0, 1012.0, "grid")
    tm.update_asset_profit("COV70ETH", 3.0, 1.5, "grid")
    tm.record_trade("BUY", "COV70AAA", True, 100.0, 0.2, "grid")
    tm.record_trade("SELL", "COV70AAA", False, 50.0, 0.3, "grid")
    tm.update_bot_status(True, "grid")
    tm.update_bot_status(False, "grid")
    tm.record_error("timeout", "grid")
    tm.update_balances({"USDT": float(decimal_money("250")), "BTC": 0.01}, "grid")
    tm.update_active_positions(4, "grid")
    assert tm.portfolio_initial_value == 1000.0


# --------------------------------------------------------------------------- #
# tracing.py
# --------------------------------------------------------------------------- #


def test_tracing_setup_exporters_and_noop():
    from app.core import tracing as tr

    with patch.object(tr, "_instrument_fastapi") as fa, patch.object(
        tr, "_instrument_sqlalchemy"
    ), patch.object(tr, "_instrument_requests"):
        assert tr.setup_tracing() is True
        assert tr.setup_tracing(app=MagicMock()) is True
        fa.assert_called()

        with patch.object(tr, "_build_exporter", return_value=MagicMock()):
            assert tr.setup_tracing() is True
            with patch(
                "opentelemetry.sdk.trace.export.BatchSpanProcessor",
                side_effect=RuntimeError("bsp"),
            ):
                assert tr.setup_tracing() is True

    with patch.dict(
        sys.modules,
        {
            "opentelemetry": None,
            "opentelemetry.sdk": None,
            "opentelemetry.sdk.resources": None,
            "opentelemetry.sdk.trace": None,
            "opentelemetry.sdk.trace.sampling": None,
        },
    ):
        assert tr.setup_tracing() is False

    with patch.object(tr, "EXPORTER", "none"):
        assert tr._build_exporter() is None
    with patch.object(tr, "EXPORTER", "console"):
        exp = tr._build_exporter()
        assert exp is not None
    with patch.object(tr, "EXPORTER", "console"):
        with patch.dict(sys.modules, {"opentelemetry.sdk.trace.export": None}):
            assert tr._build_exporter() is None

    grpc_name = "opentelemetry.exporter.otlp.proto.grpc.trace_exporter"
    http_name = "opentelemetry.exporter.otlp.proto.http.trace_exporter"
    http_mod = types.ModuleType(http_name)

    class _HttpExp:
        def __init__(self, endpoint=None, insecure=True):
            self.endpoint = endpoint

    http_mod.OTLPSpanExporter = _HttpExp
    http_pkg = types.ModuleType("opentelemetry.exporter.otlp.proto.http")
    http_pkg.trace_exporter = http_mod

    with patch.object(tr, "EXPORTER", "otlp"), patch(
        "opentelemetry.exporter.otlp.proto.grpc.trace_exporter.OTLPSpanExporter",
        return_value=MagicMock(name="grpc-exp"),
    ):
        assert tr._build_exporter() is not None

    with patch.object(tr, "EXPORTER", "jaeger"), patch.dict(
        sys.modules,
        {
            grpc_name: None,
            "opentelemetry.exporter.otlp.proto.http": http_pkg,
            http_name: http_mod,
        },
    ):
        exp = tr._build_exporter()
        assert exp is not None
        assert "4318" in exp.endpoint or "traces" in exp.endpoint

    with patch.object(tr, "EXPORTER", "otlp"), patch.dict(
        sys.modules, {grpc_name: None, http_name: None}
    ):
        assert tr._build_exporter() is None

    with patch.object(tr, "EXPORTER", "unknown-backend"):
        assert tr._build_exporter() is None

    with patch(
        "opentelemetry.instrumentation.fastapi.FastAPIInstrumentor"
    ) as fi:
        tr._instrument_fastapi(MagicMock())
        fi.instrument_app.assert_called()
    with patch.dict(sys.modules, {"opentelemetry.instrumentation.fastapi": None}):
        tr._instrument_fastapi(MagicMock())

    with patch(
        "opentelemetry.instrumentation.sqlalchemy.SQLAlchemyInstrumentor"
    ) as si, patch("app.db.session.engine", MagicMock(), create=True):
        tr._instrument_sqlalchemy()
        si.return_value.instrument.assert_called()
    with patch.dict(sys.modules, {"opentelemetry.instrumentation.sqlalchemy": None}):
        tr._instrument_sqlalchemy()

    with patch(
        "opentelemetry.instrumentation.requests.RequestsInstrumentor"
    ) as ri:
        tr._instrument_requests()
        ri.return_value.instrument.assert_called()
    with patch.dict(sys.modules, {"opentelemetry.instrumentation.requests": None}):
        tr._instrument_requests()

    tracer = tr.get_tracer("cov70")
    assert tracer is not None
    with patch.dict(sys.modules, {"opentelemetry": None, "opentelemetry.trace": None}):
        noop = tr.get_tracer("cov70")
    span = noop.start_as_current_span("x")
    span.set_attribute("k", "v")
    span.set_status("ok")
    span.record_exception(RuntimeError("e"))
    with span:
        pass
    span2 = noop.start_span("y")
    span2.__enter__()
    span2.__exit__(None, None, None)


# --------------------------------------------------------------------------- #
# celery_tracing.py
# --------------------------------------------------------------------------- #


def test_celery_tracing_install_handlers_and_inject():
    from app.core import celery_tracing as ct

    captured: dict[str, object] = {}

    def _capture(fn=None, **_kw):
        def _store(f):
            captured[f.__name__] = f
            return f

        if fn is not None:
            return _store(fn)
        return _store

    with patch("celery.signals.task_prerun") as pre, patch(
        "celery.signals.task_postrun"
    ) as post, patch("celery.signals.task_failure") as fail:
        pre.connect.side_effect = _capture
        post.connect.side_effect = _capture
        fail.connect.side_effect = _capture
        assert ct.install_celery_tracing() is True

    task = MagicMock()
    task.name = "app.services.alert_tasks.send_alert"
    task.request.headers = {}
    task.request.delivery_info = {"routing_key": "celery"}

    captured["_on_task_prerun"]("tid-ok", task)
    captured["_on_task_postrun"]("tid-ok")

    captured["_on_task_prerun"]("tid-fail", task)
    captured["_on_task_failure"]("tid-fail", RuntimeError("boom"))

    captured["_on_task_postrun"]("tid-missing")
    captured["_on_task_failure"]("tid-missing", RuntimeError("gone"))

    with patch("opentelemetry.trace.get_tracer", side_effect=RuntimeError("no-tracer")):
        captured["_on_task_prerun"]("tid-err", task)

    from opentelemetry import context as ctx_api

    captured2: dict[str, object] = {}

    def _capture2(fn=None, **_kw):
        def _store(f):
            captured2[f.__name__] = f
            return f

        if fn is not None:
            return _store(fn)
        return _store

    boom_span = MagicMock()
    boom_span.end.side_effect = RuntimeError("end")
    boom_span.set_status.side_effect = RuntimeError("st")
    boom_span.record_exception.side_effect = RuntimeError("re")
    fake_tracer = MagicMock()
    fake_tracer.start_span.return_value = boom_span

    with patch("celery.signals.task_prerun") as pre, patch(
        "celery.signals.task_postrun"
    ) as post, patch("celery.signals.task_failure") as fail, patch(
        "opentelemetry.trace.get_tracer", return_value=fake_tracer
    ), patch("opentelemetry.propagate.extract", return_value=object()), patch(
        "opentelemetry.context.attach", return_value=object()
    ), patch.object(ctx_api, "detach", side_effect=RuntimeError("detach")):
        pre.connect.side_effect = _capture2
        post.connect.side_effect = _capture2
        fail.connect.side_effect = _capture2
        assert ct.install_celery_tracing() is True
        captured2["_on_task_prerun"]("tid-boom", task)
        captured2["_on_task_failure"]("tid-boom", RuntimeError("x"))

    headers = ct.inject_trace_headers()
    assert isinstance(headers, dict)
    with patch.dict(sys.modules, {"opentelemetry.propagate": None}):
        assert ct.inject_trace_headers() == {}

    with patch.dict(
        sys.modules,
        {
            "opentelemetry": None,
            "opentelemetry.propagate": None,
            "celery": None,
            "celery.signals": None,
        },
    ):
        assert ct.install_celery_tracing() is False


# --------------------------------------------------------------------------- #
# grafana_metrics.py
# --------------------------------------------------------------------------- #


async def test_grafana_metrics_buffer_summary_export(tmp_path, monkeypatch):
    from app.core.grafana_metrics import GrafanaMetrics

    g = GrafanaMetrics()
    assert g.get_metrics_summary()["total_metrics"] == 0
    assert await g.record_metric("equity_usdt", 100.5) is True
    assert g.record_metric_sync("equity_usdt", 90.0) is True
    assert g.record_metric_sync("mode", "paper") is True

    g.metrics_buffer = [
        {"timestamp": "t", "metric_name": "x", "value": 1, "type": "int"}
    ] * 1000
    assert await g.record_metric("x", 2) is True
    assert len(g.metrics_buffer) <= 1000
    g.metrics_buffer = [
        {"timestamp": "t", "metric_name": "y", "value": 1, "type": "int"}
    ] * 1000
    assert g.record_metric_sync("y", 3) is True
    assert len(g.metrics_buffer) <= 1000

    summary = g.get_metrics_summary()
    assert summary["total_metrics"] > 0
    assert "unique_metrics" in summary

    with patch("app.core.grafana_metrics.datetime") as dt:
        dt.now.side_effect = RuntimeError("ts")
        assert await g.record_metric("z", 1) is False
        assert g.record_metric_sync("z", 1) is False

    g.clear_metrics()
    assert g.get_metrics_summary()["total_metrics"] == 0
    g.record_metric_sync("pnl", 1.0)

    monkeypatch.chdir(tmp_path)
    assert g.export_metrics() is True
    assert g.export_metrics(str(tmp_path / "grafana_out.json")) is True
    with patch("builtins.open", side_effect=OSError("nope")):
        assert g.export_metrics("x.json") is False


# --------------------------------------------------------------------------- #
# trace_decorator.py
# --------------------------------------------------------------------------- #


async def test_trace_decorator_sync_async_and_errors():
    from app.core.trace_decorator import traced, _record_error, _set_attributes

    @traced()
    def sync_ok(x):
        return x + 1

    @traced("cov.sync.err", attributes={"model": "paper"})
    def sync_err():
        raise ValueError("sync-fail")

    @traced("cov.async.ok")
    async def async_ok():
        return "ok"

    @traced("cov.async.err")
    async def async_err():
        raise RuntimeError("async-fail")

    assert sync_ok(1) == 2
    with pytest.raises(ValueError, match="sync-fail"):
        sync_err()
    assert await async_ok() == "ok"
    with pytest.raises(RuntimeError, match="async-fail"):
        await async_err()

    span = MagicMock()
    span.set_attribute.side_effect = RuntimeError("attr")
    _set_attributes(span, {"a": 1})
    span2 = MagicMock()
    span2.set_status.side_effect = RuntimeError("st")
    _record_error(span2, RuntimeError("orig"))
    with patch.dict(sys.modules, {"opentelemetry.trace": None}):
        _record_error(MagicMock(), RuntimeError("no-status"))


# --------------------------------------------------------------------------- #
# telegram_alert.py
# --------------------------------------------------------------------------- #


def test_telegram_alert_sync_paths(monkeypatch):
    import app.services.telegram_alert as ta

    ta._last_sent.clear()
    monkeypatch.setattr(ta, "_cooldown_seconds", 600)

    assert ta.send_telegram_alert("no-creds") is False
    assert ta._should_send("unique-cov70-a") is True
    assert ta._should_send("unique-cov70-a") is False

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token-not-real")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "0")
    ta._last_sent.clear()

    resp_ok = MagicMock()
    resp_ok.status_code = 200
    with patch.object(ta.requests, "post", return_value=resp_ok) as post:
        assert ta.send_telegram_alert("unique-cov70-ok") is True
        post.assert_called_once()
        assert ta.send_telegram_alert("unique-cov70-ok") is True  # cooldown
        assert post.call_count == 1

    ta._last_sent.clear()
    resp_bad = MagicMock()
    resp_bad.status_code = 500
    resp_bad.text = "fail"
    with patch.object(ta.requests, "post", return_value=resp_bad):
        assert ta.send_telegram_alert("unique-cov70-bad") is False

    ta._last_sent.clear()
    with patch.object(ta.requests, "post", side_effect=RuntimeError("net")):
        assert ta.send_telegram_alert("unique-cov70-exc") is False


class _ACtx:
    def __init__(self, inner):
        self.inner = inner

    async def __aenter__(self):
        return self.inner

    async def __aexit__(self, *exc):
        return False


class _FakeSession:
    def __init__(self, inner, boom: Exception | None = None):
        self.inner = inner
        self.boom = boom

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def post(self, *args, **kwargs):
        if self.boom:
            raise self.boom
        return _ACtx(self.inner)


async def test_telegram_alert_async_paths(monkeypatch):
    import app.services.telegram_alert as ta

    ta._last_sent.clear()
    monkeypatch.setattr(ta, "_cooldown_seconds", 600)
    assert await ta.send_telegram_alert_async("async-no-creds") is False

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token-not-real")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "0")
    ta._last_sent.clear()

    ok = MagicMock()
    ok.status = 200
    ok.text = AsyncMock(return_value="ok")
    with patch.object(ta.aiohttp, "ClientSession", return_value=_FakeSession(ok)):
        assert await ta.send_telegram_alert_async("async-ok") is True
        assert await ta.send_telegram_alert_async("async-ok") is True

    ta._last_sent.clear()
    bad = MagicMock()
    bad.status = 403
    bad.text = AsyncMock(return_value="nope")
    with patch.object(ta.aiohttp, "ClientSession", return_value=_FakeSession(bad)):
        assert await ta.send_telegram_alert_async("async-bad") is False

    ta._last_sent.clear()
    with patch.object(
        ta.aiohttp, "ClientSession", return_value=_FakeSession(ok, boom=RuntimeError("net"))
    ):
        assert await ta.send_telegram_alert_async("async-exc") is False


# --------------------------------------------------------------------------- #
# telegram_bot.py
# --------------------------------------------------------------------------- #


async def test_telegram_bot_simulated_enabled_dedupe_errors(monkeypatch):
    from app.core.telegram_bot import TelegramBot

    sim = TelegramBot()
    assert sim.enabled is False
    assert await sim.send_alert("paper-sim") is True
    assert sim.send_alert_sync("paper-sim-sync") is True

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token-not-real")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "0")
    monkeypatch.setenv("TELEGRAM_DEDUPE_TTL_SECONDS", "600")
    live = TelegramBot()
    assert live.enabled is True
    assert await live.send_alert("paper-live") is True
    assert await live.send_alert("paper-live") is True  # dedupe
    assert live.send_alert_sync("paper-live-sync") is True

    with patch("hashlib.sha256", side_effect=RuntimeError("hash")):
        assert await live.send_alert("x") is False
    with patch.object(live.logger, "info", side_effect=RuntimeError("log")):
        assert live.send_alert_sync("y") is False


# --------------------------------------------------------------------------- #
# alert_tasks.py
# --------------------------------------------------------------------------- #


def test_alert_tasks_send_and_notify(monkeypatch):
    from app.services import alert_tasks as at

    with patch.object(at, "send_telegram_alert", return_value=True) as tg:
        out = at.send_alert.run("ciclo paper ok", "info")
        assert out["status"] == "sent"
        tg.assert_called()

    with patch.object(at, "send_telegram_alert", side_effect=RuntimeError("tg")):
        out = at.send_alert.run("sigue paper", "warning")
        assert out["status"] == "sent"

    with patch.object(at.send_alert, "retry", side_effect=RuntimeError("retried")):
        with patch.object(at.logger, "info", side_effect=RuntimeError("log-fail")):
            with pytest.raises(RuntimeError, match="retried"):
                at.send_alert.run("boom", "error")

    with patch.object(at, "send_telegram_alert") as tg:
        low = at.notify_consecutive_api_failures.run("binance", 2)
        assert low["status"] == "ok"
        tg.assert_not_called()
        high = at.notify_consecutive_api_failures.run("binance", 3)
        assert high["count"] == 3
        tg.assert_called()

    with patch.object(at, "send_telegram_alert", side_effect=RuntimeError("tg")):
        with pytest.raises(RuntimeError, match="tg"):
            at.notify_consecutive_api_failures.run("binance", 4)
