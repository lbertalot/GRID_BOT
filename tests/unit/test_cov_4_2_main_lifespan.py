"""COV-4.2 — main.py lifespan paper + middleware security gaps.

Paper-only · no live · PROMOTE_LIVE: NO.
Lifespan mockeado (sin Binance/red); middleware en mini-app aislada.
"""

from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.error import URLError

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

pytestmark = [pytest.mark.usefixtures("paper_env")]


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _close_coro(coro):
    """Evita 'coroutine was never awaited' al stubbear create_task."""
    if asyncio.iscoroutine(coro):
        coro.close()
    return MagicMock(name="task")


# ── logging + lifespan ───────────────────────────────────────────────────────


def test_configure_logging_dev_and_access(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("ACCESS_LOG", "false")
    monkeypatch.setenv("NOISY_MODULE_LOG_LEVEL", "ERROR")
    from app.main import _configure_logging

    log = _configure_logging()
    assert log.name.endswith("main") or log.name == "app.main"


@pytest.mark.anyio
async def test_lifespan_export_openapi_skips_init(monkeypatch):
    monkeypatch.setenv("EXPORT_OPENAPI", "1")
    from app.main import lifespan

    app = FastAPI()
    async with lifespan(app):
        assert True


@pytest.mark.anyio
async def test_lifespan_paper_mocked_success_and_shutdown(monkeypatch):
    monkeypatch.setenv("EXPORT_OPENAPI", "0")
    monkeypatch.setenv("APP_URL", "")
    monkeypatch.delenv("BINANCE_ED25519_API_KEY", raising=False)

    tracker = MagicMock()
    tracker.start_periodic_cleanup = AsyncMock()
    monitor = MagicMock()
    monitor.set_components = MagicMock()
    stream = MagicMock()
    stream.stop = AsyncMock()

    singleton = MagicMock()
    singleton.client = MagicMock()
    singleton.validate_credentials_and_connectivity.return_value = {
        "net_ok": True,
        "auth_ok": True,
    }

    from app.main import lifespan

    app = FastAPI()
    with patch("app.main.BalanceValidator", return_value=MagicMock()), patch(
        "app.main.OperationTracker", return_value=tracker
    ), patch("app.main.IntegrityMonitor", return_value=monitor), patch(
        "threading.Thread"
    ) as Thr, patch(
        "app.main.asyncio.create_task", side_effect=_close_coro
    ), patch(
        "app.main.get_binance_client_singleton", return_value=singleton
    ), patch(
        "app.main.ReconciliationService", return_value=MagicMock(start=AsyncMock())
    ):
        Thr.return_value.start = MagicMock()
        async with lifespan(app):
            app.state.binance_user_stream = stream
        stream.stop.assert_awaited()


@pytest.mark.anyio
async def test_lifespan_integrity_init_failure_continues(monkeypatch):
    monkeypatch.setenv("EXPORT_OPENAPI", "0")
    monkeypatch.setenv("APP_URL", "http://localhost:8000")
    monkeypatch.setenv("BINANCE_ED25519_API_KEY", "ed25519-test-key")

    singleton = MagicMock()
    singleton.client = MagicMock()
    singleton.validate_credentials_and_connectivity.return_value = {
        "net_ok": False,
        "auth_ok": False,
    }

    from app.main import lifespan
    import app.main as main_mod

    app = FastAPI()
    with patch(
        "app.main.BalanceValidator", side_effect=RuntimeError("no integrity")
    ), patch("threading.Thread") as Thr, patch(
        "app.main.asyncio.create_task", side_effect=_close_coro
    ), patch(
        "app.main.get_binance_client_singleton", return_value=singleton
    ), patch(
        "app.main.ReconciliationService", side_effect=RuntimeError("no recon")
    ), patch(
        "app.services.binance_user_stream.BinanceUserStreamHandler",
        side_effect=RuntimeError("no ws"),
    ), patch.object(
        main_mod.app_breakers, "activate_breaker", new_callable=AsyncMock
    ):
        Thr.return_value.start = MagicMock()
        async with lifespan(app):
            assert main_mod.balance_validator is None


# ── middleware (mini-app; no secrets) ────────────────────────────────────────


def test_security_headers_and_sanitization_and_rate_limit(monkeypatch):
    import app.core.middleware.security_hardening as sh

    monkeypatch.setattr(sh, "_RATE_LIMIT_REQUESTS", 3)
    monkeypatch.setattr(sh, "_RATE_LIMIT_WINDOW", 60)

    app = FastAPI()
    app.add_middleware(sh.SecurityHeadersMiddleware)
    app.add_middleware(sh.RateLimitMiddleware)
    app.add_middleware(sh.InputSanitizationMiddleware)

    @app.get("/health")
    def _health():
        return {"status": "healthy"}

    @app.get("/echo")
    def _echo():
        return {"ok": True}

    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert r.headers.get("X-Request-ID")

    # %2e%2e matchea el regex (../ literal lo re-encodea TestClient a ..%2F)
    assert client.get("/echo?x=%2e%2e/%2e%2e/etc/passwd").status_code == 400

    for _ in range(3):
        assert client.get("/echo").status_code == 200
    limited = client.get("/echo")
    assert limited.status_code == 429
    assert "Retry-After" in limited.headers


@pytest.mark.anyio
async def test_input_sanitization_blocks_sql_query_string():
    from app.core.middleware.security_hardening import InputSanitizationMiddleware

    mw = InputSanitizationMiddleware(app=MagicMock())
    req = MagicMock()
    req.url.path = "/echo"
    req.url.query = "q=union select 1"
    req.method = "GET"
    req.client = MagicMock(host="127.0.0.1")
    resp = await mw.dispatch(req, AsyncMock(return_value=MagicMock()))
    assert resp.status_code == 400
    assert "inválido" in resp.body.decode().lower() or resp.status_code == 400


def test_integrity_guard_blocks_when_breakers_active(monkeypatch):
    from app.core.middleware.integrity_guard import IntegrityGuardMiddleware

    app = FastAPI()
    breakers = MagicMock()
    breakers.get_all_breakers_status.return_value = {
        "total_active": 1,
        "critical_mode": False,
    }
    app.state.breakers = breakers
    app.add_middleware(IntegrityGuardMiddleware)

    @app.post("/api/trade/execute")
    def _exec():
        return {"status": "ok"}

    @app.get("/api/trade/status")
    def _status():
        return {"status": "ok"}

    client = TestClient(app)

    # El middleware bypassea si PYTEST_CURRENT_TEST ∈ environ (import local de os)
    real_getenv = os.getenv

    def _getenv(key, default=None):
        if key == "DISABLE_INTEGRITY_GUARD":
            return "false"
        return real_getenv(key, default)

    class _Env(dict):
        def __contains__(self, item):
            if item == "PYTEST_CURRENT_TEST":
                return False
            return dict.__contains__(self, item)

    fake_env = _Env({k: v for k, v in os.environ.items() if k != "PYTEST_CURRENT_TEST"})

    with patch("os.getenv", side_effect=_getenv), patch("os.environ", fake_env):
        blocked = client.post("/api/trade/execute")
        assert blocked.status_code == 503
        assert blocked.json()["reason"] == "circuit_breaker_active"
        assert client.get("/api/trade/status").status_code == 200


def test_prometheus_http_middleware_sets_correlation(paper_env):
    from app.core.middleware.prometheus_http import PrometheusHTTPMiddleware

    app = FastAPI()
    app.add_middleware(PrometheusHTTPMiddleware)

    @app.get("/x")
    def _x():
        return {"ok": True}

    client = TestClient(app)
    r = client.get("/x", headers={"X-Correlation-ID": "cov-42"})
    assert r.status_code == 200
    assert r.headers.get("X-Correlation-ID") == "cov-42"


# ── main.py endpoint gaps ────────────────────────────────────────────────────


def _clear_app_rate_limit_windows(app) -> None:
    """El RateLimitMiddleware es in-memory y se comparte en toda la suite CI."""
    from app.core.middleware.security_hardening import RateLimitMiddleware

    node = getattr(app, "middleware_stack", None)
    seen: set[int] = set()
    while node is not None and id(node) not in seen:
        seen.add(id(node))
        if isinstance(node, RateLimitMiddleware) and hasattr(node, "_windows"):
            node._windows.clear()
        node = getattr(node, "app", None)


@pytest.fixture
def main_client(paper_env, monkeypatch):
    monkeypatch.setenv("EXPORT_OPENAPI", "1")
    from app.main import app

    _clear_app_rate_limit_windows(app)
    with TestClient(app) as client:
        _clear_app_rate_limit_windows(app)
        yield client


def test_main_ping_health_root_breakers(main_client):
    assert main_client.get("/ping").json()["pong"] is True
    assert main_client.get("/health").json()["status"] == "healthy"
    root = main_client.get("/").json()
    assert root["status"] in ("running", "healthy", "ok") or "trading" in root
    assert main_client.get("/breakers/summary").status_code == 200


@pytest.mark.anyio
async def test_main_breakers_summary_error_path():
    import app.main as main_mod
    from fastapi import HTTPException

    with patch.object(
        main_mod.app_breakers,
        "get_all_breakers_status",
        side_effect=RuntimeError("x"),
    ):
        with pytest.raises(HTTPException) as ei:
            await main_mod.breakers_summary()
    assert ei.value.status_code == 500


def test_main_ip_endpoint_mocked(main_client):
    class _Resp:
        def read(self):
            return b"1.2.3.4"

    with patch("urllib.request.urlopen", return_value=_Resp()):
        body = main_client.get("/ip").json()
    assert body["ip"] == "1.2.3.4"
    assert "api.ipify.org" in body["all_ips"]

    with patch("urllib.request.urlopen", side_effect=URLError("down")):
        fail = main_client.get("/ip").json()
    assert fail["ip"] == "desconocida"


@pytest.mark.anyio
async def test_main_integrity_handlers_direct(monkeypatch):
    """Handlers de main.py (el router /integrity/* exige auth y los sombrea en HTTP)."""
    import app.main as main_mod

    bv = MagicMock()
    bv.get_validation_summary = AsyncMock(return_value={"integrity_score": 95})
    bv.last_validation = None
    bv.validate_balances = AsyncMock()
    bv.integrity_score = 95
    bv.force_validation = AsyncMock()
    ot = MagicMock()
    ot.get_operation_summary = AsyncMock(return_value={"success_rate": 0.98})
    ot.get_failed_operations_summary = AsyncMock(return_value=[{"id": 1}])
    ot.get_partial_fills_summary = AsyncMock(return_value=[])
    ot.force_operation_check = AsyncMock()

    main_mod.balance_validator = bv
    main_mod.operation_tracker = ot
    main_mod.integrity_monitor = MagicMock()

    st = await main_mod.get_integrity_status()
    assert st["status"] == "healthy"

    failed = await main_mod.get_failed_operations()
    assert failed["total_failed"] == 1

    partial = await main_mod.get_partial_fills()
    assert partial["total_partial"] == 0

    disc = await main_mod.get_balance_discrepancies()
    assert "validation_summary" in disc

    main_mod.balance_validator = None
    main_mod.operation_tracker = None
    main_mod.integrity_monitor = None
    with patch(
        "app.main.BalanceValidator", side_effect=RuntimeError("init fail")
    ), pytest.raises(Exception):
        await main_mod.get_integrity_status()


@pytest.mark.anyio
async def test_main_reconciliation_summary_handler(monkeypatch):
    import app.main as main_mod

    singleton = MagicMock()
    singleton.client.get_account.return_value = {
        "balances": [
            {"asset": "USDT", "free": "100", "locked": "0"},
            {"asset": "BTC", "free": "0.01", "locked": "0"},
            {"asset": "LDUSDT", "free": "10", "locked": "0"},
        ]
    }
    singleton.get_symbol_price.return_value = 50000.0
    with patch("app.main.get_binance_client_singleton", return_value=singleton):
        body = await main_mod.reconciliation_summary()
    assert body["status"] == "ok"
    assert body["cash_usdt"] >= 100
