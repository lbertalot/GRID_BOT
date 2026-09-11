"""TDD — incidente Binance −2015 agrupado. Mocks, sin red ni Telegram real."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.core.binance_auth_ip_watch import process_binance_auth_ip_watch
from app.core.telegram_ceo_copy import (
    HOLD_PNL_MIN_REPEAT_S,
    render_invalid_ip_telegram,
    reset_debounce_memory,
)


@pytest.fixture(autouse=True)
def _isolate():
    with patch("app.core.telegram_ceo_copy._redis_client", return_value=None):
        reset_debounce_memory()
        yield
        reset_debounce_memory()


def test_invalid_ip_copy_does_not_promise_auto_resume():
    msg = render_invalid_ip_telegram("148.227.69.131", location_restricted=False)
    assert "148.227.69.131" in msg
    assert "cuando binance acepte" not in msg.lower()
    assert "Dinero real: NO" in msg
    assert "override" not in msg.lower()
    assert "wipe" not in msg.lower()


def test_ip_blocked_emits_once_then_silence_until_6h():
    t0 = 8_000_000.0
    first = process_binance_auth_ip_watch(
        blocked=True, public_ip="1.2.3.4", now=t0
    )
    assert first is not None
    assert "binance_auth_ip" not in first
    assert "1.2.3.4" in first
    assert "cuando binance acepte" not in first.lower()
    assert (
        process_binance_auth_ip_watch(
            blocked=True, public_ip="1.2.3.4", now=t0 + 3600
        )
        is None
    )
    again = process_binance_auth_ip_watch(
        blocked=True, public_ip="1.2.3.4", now=t0 + HOLD_PNL_MIN_REPEAT_S
    )
    assert again is not None


def test_recovery_only_after_python_binance_auth_ok():
    t0 = 9_000_000.0
    assert process_binance_auth_ip_watch(blocked=True, public_ip="9.9.9.9", now=t0)
    assert (
        process_binance_auth_ip_watch(
            blocked=False, python_binance_auth_ok=False, now=t0 + 10
        )
        is None
    )
    recovered = process_binance_auth_ip_watch(
        blocked=False, python_binance_auth_ok=True, now=t0 + 20
    )
    assert recovered is not None
    assert "autenticó de nuevo" in recovered.lower()
    assert "Modo: PAPER" in recovered
    assert "Dinero real: NO" in recovered


def test_ccxt_ok_after_2015_does_not_clear_gauge():
    from unittest.mock import MagicMock

    from binance.exceptions import BinanceAPIException

    import app.services.binance_client_singleton as mod
    from app.core.metrics import binance_ip_rejected
    from app.services.binance_client_singleton import BinanceClientSingleton

    BinanceClientSingleton._instance = None
    BinanceClientSingleton._client = None
    BinanceClientSingleton._initialized = False
    g = binance_ip_rejected
    g.set(0)
    s = BinanceClientSingleton.__new__(BinanceClientSingleton)
    s._initialized = True
    fake = MagicMock()
    fake.ping.return_value = {}
    fake.get_account.side_effect = BinanceAPIException(
        400, "Invalid API-key, IP", code=-2015
    )
    s._client = fake
    ex = MagicMock()
    ex.fetch_balance.return_value = {"USDT": {"free": 1}}
    with (
        patch.object(mod, "_notify_invalid_ip"),
        patch.object(mod.ccxt, "binance", return_value=ex),
        patch.object(mod, "_public_binance_ping_ok", return_value=True),
    ):
        out = s.validate_credentials_and_connectivity()
    assert out["auth_ok"] is False
    assert g._value.get() == 1
