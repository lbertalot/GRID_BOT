"""Gauge de estado actual IP Binance (−2015) para el semáforo CEO.

Paper-only · PROMOTE_LIVE: NO.
El Counter ``binance_api_errors_total`` sigue siendo historial; este gauge
es 0/1 del último validate/get_account (no ``increase()``).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from binance.exceptions import BinanceAPIException
from prometheus_client import generate_latest

import app.services.binance_client_singleton as mod
from app.services.binance_client_singleton import BinanceClientSingleton

pytestmark = [pytest.mark.usefixtures("paper_env")]


def _reset_singleton():
    BinanceClientSingleton._instance = None
    BinanceClientSingleton._client = None
    BinanceClientSingleton._initialized = False
    mod.binance_client_singleton = None
    mod._private_fail_count = 0
    mod._circuit_open_until_ts = 0.0
    mod._last_ip_alert_ts = 0.0


@pytest.fixture
def creds(monkeypatch):
    monkeypatch.setenv("BINANCE_API_KEY", "ip-gauge-key")
    monkeypatch.setenv("BINANCE_SECRET_KEY", "ip-gauge-secret")
    monkeypatch.setenv("BINANCE_TESTNET", "false")
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.setenv("FORCE_REAL_MODE", "")
    monkeypatch.setenv("TRADING_ENABLED", "false")
    _reset_singleton()
    yield
    _reset_singleton()


def _fake_client():
    c = MagicMock(name="Client")
    c.api_key = "ip-gauge-key"
    c.api_secret = "ip-gauge-secret"
    c.get_account.return_value = {
        "balances": [{"asset": "USDT", "free": "100", "locked": "0"}]
    }
    c.ping.return_value = {}
    return c


def _gauge():
    from app.core.metrics import binance_ip_rejected

    return binance_ip_rejected


def test_binance_ip_rejected_is_gauge_without_labels():
    g = _gauge()
    assert g._name == "binance_ip_rejected"
    assert g._type == "gauge"
    assert tuple(g._labelnames) == ()


def test_validate_sets_gauge_1_on_2015_without_auth(creds):
    g = _gauge()
    g.set(0)
    s = BinanceClientSingleton.__new__(BinanceClientSingleton)
    s._initialized = True
    fake = _fake_client()
    fake.get_account.side_effect = BinanceAPIException(
        400, "Invalid API-key, IP, or permissions", code=-2015
    )
    s._client = fake
    ex = MagicMock()
    ex.fetch_balance.side_effect = RuntimeError("ccxt-down")
    with patch.object(mod, "_notify_invalid_ip"), patch.object(
        mod.ccxt, "binance", return_value=ex
    ):
        out = s.validate_credentials_and_connectivity()
    assert out["auth_ok"] is False
    assert g._value.get() == 1


def test_validate_sets_gauge_0_on_auth_ok(creds):
    g = _gauge()
    g.set(1)
    s = BinanceClientSingleton.__new__(BinanceClientSingleton)
    s._initialized = True
    s._client = _fake_client()
    out = s.validate_credentials_and_connectivity()
    assert out["auth_ok"] is True
    assert g._value.get() == 0


def test_validate_2015_then_auth_ok_clears_gauge(creds):
    """CEO: tras reparar IP, auth_ok=true pone el gauge a 0 (no depende de increase)."""
    g = _gauge()
    g.set(0)
    s = BinanceClientSingleton.__new__(BinanceClientSingleton)
    s._initialized = True
    fake = _fake_client()
    s._client = fake
    fake.get_account.side_effect = BinanceAPIException(
        400, "Invalid API-key, IP", code=-2015
    )
    ex = MagicMock()
    ex.fetch_balance.side_effect = RuntimeError("ccxt-down")
    with patch.object(mod, "_notify_invalid_ip"), patch.object(
        mod.ccxt, "binance", return_value=ex
    ):
        assert s.validate_credentials_and_connectivity()["auth_ok"] is False
    assert g._value.get() == 1

    fake.get_account.side_effect = None
    fake.get_account.return_value = {
        "balances": [{"asset": "USDT", "free": "100", "locked": "0"}]
    }
    out = s.validate_credentials_and_connectivity()
    assert out["auth_ok"] is True
    assert g._value.get() == 0


def test_get_account_info_sets_gauge_1_on_2015(creds):
    g = _gauge()
    g.set(0)
    s = BinanceClientSingleton.__new__(BinanceClientSingleton)
    s._initialized = True
    fake = _fake_client()
    fake.get_account.side_effect = BinanceAPIException(
        400, "Invalid API-key, IP", code=-2015
    )
    s._client = fake
    with patch.object(mod, "_notify_invalid_ip"):
        assert s.get_account_info() == {"balances": []}
    assert g._value.get() == 1


def test_get_account_info_sets_gauge_0_on_ok(creds):
    g = _gauge()
    g.set(1)
    s = BinanceClientSingleton.__new__(BinanceClientSingleton)
    s._initialized = True
    s._client = _fake_client()
    assert s.get_account_info()["balances"]
    assert g._value.get() == 0


def test_non_ip_api_error_does_not_set_gauge_1(creds):
    g = _gauge()
    g.set(0)
    s = BinanceClientSingleton.__new__(BinanceClientSingleton)
    s._initialized = True
    fake = _fake_client()
    fake.get_account.side_effect = BinanceAPIException(
        400, "Timestamp for this request is outside of the recvWindow", code=-1021
    )
    s._client = fake
    ex = MagicMock()
    ex.fetch_balance.side_effect = RuntimeError("ccxt-down")
    with patch.object(mod.ccxt, "binance", return_value=ex):
        out = s.validate_credentials_and_connectivity()
    assert out["auth_ok"] is False
    assert g._value.get() == 0


def test_auth_ok_does_not_reset_api_errors_counter(creds):
    from app.core.metrics import binance_api_errors_total

    labeled = binance_api_errors_total.labels(code="-2015", phase="validate")
    before = labeled._value.get()
    labeled.inc()
    after_inc = labeled._value.get()
    assert after_inc == before + 1

    g = _gauge()
    g.set(1)
    s = BinanceClientSingleton.__new__(BinanceClientSingleton)
    s._initialized = True
    s._client = _fake_client()
    assert s.validate_credentials_and_connectivity()["auth_ok"] is True
    assert g._value.get() == 0
    assert labeled._value.get() == after_inc


def test_gauge_published_in_metrics_scrape(creds, client):
    g = _gauge()
    g.set(1)
    with patch("app.core.obs_gauges.publish_obs_gauges"):
        response = client.get("/metrics")
    assert response.status_code == 200
    body = response.text
    assert "binance_ip_rejected" in body
    assert "binance_ip_rejected 1.0" in body or "binance_ip_rejected 1" in body

    # generate_latest del registry (mismo payload que scrape)
    dumped = generate_latest().decode("utf-8")
    assert "binance_ip_rejected" in dumped
