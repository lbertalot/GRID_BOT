"""COV-5.8 — binance_client_singleton residual (init / validate / prices / guard).

Paper-only · Client mock · PROMOTE_LIVE: NO.
"""

from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from binance.exceptions import BinanceAPIException

import app.services.binance_client_singleton as mod
from app.core.order_execution_guard import RealOrderBlocked
from app.services.binance_client_singleton import (
    BinanceClientSingleton,
    binance_earn_underlying_asset,
    fallback_ld_prefixed_spot_symbol,
    get_binance_client_singleton,
)

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
    monkeypatch.setenv("BINANCE_API_KEY", "cov58-key")
    monkeypatch.setenv("BINANCE_SECRET_KEY", "cov58-secret")
    monkeypatch.setenv("BINANCE_TESTNET", "false")
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.setenv("FORCE_REAL_MODE", "")
    monkeypatch.setenv("TRADING_ENABLED", "false")
    _reset_singleton()
    yield
    _reset_singleton()


def _fake_client(**extra):
    c = MagicMock(name="Client")
    c.api_key = "cov58-key"
    c.api_secret = "cov58-secret"
    c.get_account.return_value = {
        "balances": [
            {"asset": "USDT", "free": "100", "locked": "0"},
            {"asset": "ETH", "free": "0.1", "locked": "0"},
            {"asset": "BNB", "free": "0", "locked": "0"},
        ]
    }
    c.ping.return_value = {}
    c.get_symbol_ticker.return_value = {"price": "1923.5"}
    c.get_symbol_info.return_value = {"symbol": "ETHUSDT"}
    c.get_exchange_info.return_value = {"symbols": [{"symbol": "ETHUSDT"}]}
    for k, v in extra.items():
        setattr(c, k, v)
    return c


def test_helpers_earn_and_ld_fallback():
    assert binance_earn_underlying_asset("LDUSDT") == "USDT"
    assert binance_earn_underlying_asset("ETH") is None
    assert fallback_ld_prefixed_spot_symbol("LDETHUSDT") == "ETHUSDT"
    assert fallback_ld_prefixed_spot_symbol("LDUSDTUSDT") is None
    assert fallback_ld_prefixed_spot_symbol("ETHUSDT") is None
    assert mod._looks_like_earn_synthetic_symbol("LDUSDT") is True
    assert mod._looks_like_earn_synthetic_symbol("ETHUSDT") is False


def test_initialize_missing_creds_raises(monkeypatch, creds):
    monkeypatch.delenv("BINANCE_API_KEY", raising=False)
    monkeypatch.delenv("BINANCE_SECRET_KEY", raising=False)
    with patch.object(mod, "load_dotenv"), pytest.raises(ValueError, match="Credenciales"):
        BinanceClientSingleton()


def test_initialize_happy_and_testnet(monkeypatch, creds):
    fake = _fake_client()
    with patch.object(mod, "Client", return_value=fake) as C, patch.object(
        mod, "load_dotenv"
    ), patch.object(mod, "get_binance_proxies", return_value=None), patch(
        "app.core.binance_proxy.log_proxy_status"
    ):
        s = BinanceClientSingleton()
    assert s.is_ready() is True
    assert s.client is fake
    C.assert_called()

    _reset_singleton()
    monkeypatch.setenv("BINANCE_API_KEY", "cov58-key")
    monkeypatch.setenv("BINANCE_SECRET_KEY", "cov58-secret")
    monkeypatch.setenv("BINANCE_TESTNET", "true")
    fake2 = _fake_client()
    with patch.object(mod, "Client", return_value=fake2) as C2, patch.object(
        mod, "load_dotenv"
    ), patch.object(
        mod, "get_binance_proxies", return_value={"https": "http://proxy"}
    ), patch(
        "app.core.binance_proxy.log_proxy_status"
    ):
        s2 = BinanceClientSingleton()
    assert s2.is_ready()
    assert any(c.kwargs.get("testnet") is True for c in C2.call_args_list)


def test_initialize_ip_error_notifies_and_keeps_client(monkeypatch, creds):
    fake = _fake_client()
    fake.get_account.side_effect = BinanceAPIException(
        400, "Invalid API-key, IP", code=-2015
    )
    fake.ping.return_value = {}
    notify = MagicMock()
    with patch.object(mod, "Client", return_value=fake), patch.object(
        mod, "load_dotenv"
    ), patch.object(mod, "get_binance_proxies", return_value=None), patch(
        "app.core.binance_proxy.log_proxy_status"
    ), patch.object(
        mod, "_notify_invalid_ip", notify
    ), patch(
        "app.core.metrics.binance_api_errors_total"
    ) as metrics:
        metrics.labels.return_value = MagicMock()
        s = BinanceClientSingleton()
    assert s._client is fake
    notify.assert_called()


def test_client_property_reinit_and_fail(monkeypatch, creds):
    s = BinanceClientSingleton.__new__(BinanceClientSingleton)
    s._initialized = True
    s._client = None
    with patch.object(
        s, "_initialize_client", side_effect=RuntimeError("no-init")
    ):
        assert s.client is None


def test_validate_credentials_paths(monkeypatch, creds):
    s = BinanceClientSingleton.__new__(BinanceClientSingleton)
    s._initialized = True
    s._client = None
    assert s.validate_credentials_and_connectivity()["ok"] is False

    fake = _fake_client()
    s._client = fake
    out = s.validate_credentials_and_connectivity()
    assert out["net_ok"] is True and out["auth_ok"] is True and out["ok"] is True

    fake.get_account.side_effect = BinanceAPIException(400, "Invalid API-key, IP", code=-2015)
    fake.ping.return_value = {}
    ex = MagicMock()
    ex.fetch_balance.return_value = {"total": {}}
    with patch.object(mod, "_notify_invalid_ip"), patch.object(
        mod.ccxt, "binance", return_value=ex
    ), patch("app.core.metrics.binance_api_errors_total") as metrics:
        metrics.labels.return_value = MagicMock()
        out2 = s.validate_credentials_and_connectivity()
    assert out2["auth_ok"] is True

    fake.get_account.side_effect = RuntimeError("auth-boom")
    ex.fetch_balance.side_effect = RuntimeError("ccxt-down")
    with patch.object(mod.ccxt, "binance", return_value=ex):
        out3 = s.validate_credentials_and_connectivity()
    assert out3["auth_ok"] is False


def test_get_account_info_circuit_and_failures(monkeypatch, creds):
    s = BinanceClientSingleton.__new__(BinanceClientSingleton)
    s._initialized = True
    s._client = None
    with patch.object(s, "_initialize_client", side_effect=RuntimeError("no")):
        assert s.get_account_info() == {"balances": []}

    fake = _fake_client()
    s._client = fake
    mod._circuit_open_until_ts = time.time() + 60
    assert s.get_account_info() == {"balances": []}
    mod._circuit_open_until_ts = 0.0

    assert s.get_account_info()["balances"]
    assert s.get_balances()["USDT"] == 100.0

    mod._fail_threshold = 2
    mod._private_fail_count = 0
    fake.get_account.side_effect = BinanceAPIException(
        400, "Invalid API-key, IP", code=-2015
    )
    with patch.object(mod, "_notify_invalid_ip"), patch(
        "app.core.metrics.binance_api_errors_total"
    ) as metrics:
        metrics.labels.return_value = MagicMock()
        assert s.get_account_info() == {"balances": []}
        assert s.get_account_info() == {"balances": []}
    assert mod._circuit_open_until_ts > time.time()

    mod._circuit_open_until_ts = 0.0
    fake.get_account.side_effect = RuntimeError("boom")
    assert s.get_account_info() == {"balances": []}


def test_get_symbol_price_paths(monkeypatch, creds):
    s = BinanceClientSingleton.__new__(BinanceClientSingleton)
    s._initialized = True
    s._client = None
    with patch.object(s, "_initialize_client", side_effect=RuntimeError("no")):
        assert s.get_symbol_price("") == 0.0
        assert s.get_symbol_price("BAD SYMBOL!!") == 0.0
        assert s.get_symbol_price("ETHUSDT") == 0.0

    fake = _fake_client()
    s._client = fake
    assert s.get_symbol_price("eth-usdt") == 1923.5

    # -1121 → LD fallback
    fake.get_symbol_ticker.side_effect = [
        BinanceAPIException(400, "Invalid symbol", code=-1121),
        {"price": "3000.0"},
    ]
    with patch.object(
        mod, "fallback_ld_prefixed_spot_symbol", return_value="ETHUSDT"
    ), patch("app.core.metrics.invalid_symbol_total") as inv:
        inv.labels.return_value = MagicMock()
        assert s.get_symbol_price("LDETHUSDT") == 3000.0

    # earn synthetic skip
    fake.get_symbol_ticker.side_effect = BinanceAPIException(
        400, "Invalid symbol", code=-1121
    )
    with patch.object(mod, "fallback_ld_prefixed_spot_symbol", return_value=None):
        assert s.get_symbol_price("LDUSDT") == 0.0

    # generic Invalid symbol string + fallback fail
    fake.get_symbol_ticker.side_effect = [
        RuntimeError("Invalid symbol"),
        RuntimeError("still bad"),
    ]
    with patch.object(
        mod, "fallback_ld_prefixed_spot_symbol", return_value="ETHUSDT"
    ):
        assert s.get_symbol_price("LDBTCUSDT") == 0.0


def test_create_order_blocked_in_paper(monkeypatch, creds):
    s = BinanceClientSingleton.__new__(BinanceClientSingleton)
    s._initialized = True
    s._client = _fake_client()
    with pytest.raises(RealOrderBlocked):
        s.create_order("ETHUSDT", "BUY", "MARKET", "0.01")


def test_get_symbol_info_and_exchange_info_memory_cache(monkeypatch, creds):
    s = BinanceClientSingleton.__new__(BinanceClientSingleton)
    s._initialized = True
    fake = _fake_client()
    s._client = fake
    assert s.get_symbol_info("ETHUSDT")["symbol"] == "ETHUSDT"

    with patch("app.core.redis_cache.redis_cache") as rc:
        rc.get_exchange_info = MagicMock(side_effect=RuntimeError("no-redis"))
        info = s.get_exchange_info(use_cache=True)
    assert info["symbols"]
    fake.get_exchange_info.assert_called_once()

    # second call hits memory cache
    info2 = s.get_exchange_info(use_cache=True)
    assert info2 is info
    fake.get_exchange_info.assert_called_once()

    fake.get_exchange_info.side_effect = RuntimeError("api-down")
    s._exchange_info_cache_ts = 0
    s._exchange_info_cache = {}
    with patch("app.core.redis_cache.redis_cache") as rc2:
        rc2.get_exchange_info = MagicMock(return_value=None)
        with pytest.raises(RuntimeError, match="api-down"):
            s.get_exchange_info(use_cache=False)


def test_notify_invalid_ip_cooldown_and_alert(monkeypatch, creds):
    mod._last_ip_alert_ts = 0.0
    send = MagicMock()
    with patch.object(
        mod.httpx, "get", return_value=SimpleNamespace(text="1.2.3.4\n")
    ), patch(
        "app.services.telegram_alert.send_telegram_alert", send
    ), patch(
        "app.core.metrics.external_auth_failures"
    ) as ext:
        ext.labels.return_value = MagicMock()
        mod._notify_invalid_ip("Invalid API-key, IP")
        mod._notify_invalid_ip("Invalid API-key, IP")  # cooldown
    assert send.call_count == 1
    assert mod._last_ip_alert_ts > 0

    mod._last_ip_alert_ts = 0.0
    with patch.object(mod.httpx, "get", side_effect=RuntimeError("net")), patch(
        "app.services.telegram_alert.send_telegram_alert",
        side_effect=RuntimeError("tg-down"),
    ):
        mod._notify_invalid_ip("451 restricted location Eligibility")


def test_get_binance_client_singleton_dummy_on_fail(monkeypatch, creds):
    monkeypatch.delenv("BINANCE_API_KEY", raising=False)
    monkeypatch.delenv("BINANCE_SECRET_KEY", raising=False)
    _reset_singleton()
    with patch.object(mod, "load_dotenv"):
        s = get_binance_client_singleton()
    assert s is not None
    assert s._client is None
    assert s.is_ready() is False
