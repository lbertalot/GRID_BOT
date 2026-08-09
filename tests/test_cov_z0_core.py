"""S-COV-85 Z0 — core pure modules (precision, logging, errors). Paper-only."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.usefixtures("paper_env")


# ── precision ───────────────────────────────────────────────────────────────


def _exchange_info(symbols=None):
    if symbols is None:
        symbols = [
            {
                "symbol": "BTCUSDT",
                "filters": [
                    {
                        "filterType": "PRICE_FILTER",
                        "tickSize": "0.01",
                        "minPrice": "0.01",
                        "maxPrice": "1000000",
                    },
                    {
                        "filterType": "LOT_SIZE",
                        "stepSize": "0.00001",
                        "minQty": "0.00001",
                        "maxQty": "9000",
                    },
                    {"filterType": "MIN_NOTIONAL", "minNotional": "10"},
                ],
            },
            {
                "symbol": "ZEROTICK",
                "filters": [
                    {
                        "filterType": "PRICE_FILTER",
                        "tickSize": "0",
                        "minPrice": "0",
                        "maxPrice": "0",
                    },
                    {
                        "filterType": "LOT_SIZE",
                        "stepSize": "0",
                        "minQty": "0",
                        "maxQty": "0",
                    },
                ],
            },
            {"symbol": "", "filters": []},
        ]
    return {"symbols": symbols}


def test_precision_round_and_notional():
    from app.core.precision import PrecisionNormalizer

    client = MagicMock()
    client.get_exchange_info.return_value = _exchange_info()
    n = PrecisionNormalizer(client, ttl_seconds=900)

    assert n.round_price("btcusdt", 50123.456) == 50123.45
    assert n.round_quantity("BTCUSDT", 0.123456) == 0.12345
    assert n.validate_notional("BTCUSDT", 50000.0, 0.001) is True
    assert n.validate_notional("BTCUSDT", 1.0, 1.0) is False

    # cache hit — no second fetch
    n.round_price("BTCUSDT", 100.0)
    assert client.get_exchange_info.call_count == 1

    # unknown symbol → passthrough / True
    assert n.round_price("NOSYM", 1.23) == 1.23
    assert n.round_quantity("NOSYM", 2.0) == 2.0
    assert n.validate_notional("NOSYM", 1.0, 1.0) is True

    # zero tick/step → passthrough
    assert n.round_price("ZEROTICK", 9.99) == 9.99
    assert n.round_quantity("ZEROTICK", 1.5) == 1.5


def test_precision_ttl_reload_and_symbol_filter():
    from app.core.precision import PrecisionNormalizer

    client = MagicMock()
    client.get_exchange_info.return_value = _exchange_info()
    n = PrecisionNormalizer(client, ttl_seconds=0)
    n._ensure_loaded(symbols=["BTCUSDT"])
    assert "BTCUSDT" in n._cache
    assert "ZEROTICK" not in n._cache
    # ttl=0 forces reload
    n._ensure_loaded()
    assert client.get_exchange_info.call_count >= 2


def test_precision_double_checked_lock_inner_return():
    """Outer TTL looks expired; inside lock cache is still fresh → early return."""
    import time

    from app.core.precision import PrecisionNormalizer

    client = MagicMock()
    client.get_exchange_info.return_value = _exchange_info()
    n = PrecisionNormalizer(client, ttl_seconds=900)
    n._cache = {
        "BTCUSDT": {
            "tickSize": 0.01,
            "minPrice": 0.0,
            "maxPrice": 0.0,
            "stepSize": 0.0,
            "minQty": 0.0,
            "maxQty": 0.0,
            "minNotional": 0.0,
        }
    }
    n._last_load = 100.0
    calls = {"n": 0}

    def fake_time():
        calls["n"] += 1
        return 1000.0 if calls["n"] == 1 else 150.0

    with patch.object(time, "time", fake_time):
        n._ensure_loaded()
    client.get_exchange_info.assert_not_called()


# ── logging_config ──────────────────────────────────────────────────────────


def test_setup_logging_and_filters(tmp_path, monkeypatch):
    from app.core import logging_config as lc

    monkeypatch.chdir(tmp_path)
    (tmp_path / "logs").mkdir()
    logger = lc.setup_logging()
    assert logger.name == "app.core.logging_config"

    dup = lc.DuplicateFilter(timeout=60)
    rec = logging.LogRecord("t", logging.INFO, __file__, 1, "same", (), None)
    assert dup.filter(rec) is True
    assert dup.filter(rec) is False  # duplicate within timeout
    dup.last_log["t:same"] = datetime.now() - timedelta(seconds=120)
    assert dup.filter(rec) is True

    tsf = lc.TradingSummaryFilter()
    rec2 = logging.LogRecord(
        "t", logging.INFO, __file__, 1, "Resumen del ciclo ok", (), None
    )
    assert tsf.filter(rec2) is True
    rec3 = logging.LogRecord("t", logging.INFO, __file__, 1, "other", (), None)
    assert tsf.filter(rec3) is True


# ── structured_logger ───────────────────────────────────────────────────────


def test_structured_logger_methods(caplog):
    from app.core.structured_logger import StructuredLogger, trading_logger

    sl = StructuredLogger("z0_structured")
    sl.set_correlation_id("corr-1")
    with caplog.at_level(logging.INFO, logger="z0_structured"):
        sl.info("hello", {"a": 1})
        sl.warning("warn")
        sl.error("err")
        sl.trading_event("FILL", "BTCUSDT", "BUY", 0.1, 50000.0, {"oid": 1})
        sl.trading_summary({"trades": 1})
        sl.error_event("X", "boom", {"ctx": True})

    assert trading_logger is not None
    assert any("Trading event" in r.message for r in caplog.records)
    assert any("Error: X" in r.message for r in caplog.records)


# ── trading_logger ──────────────────────────────────────────────────────────


def test_trading_logger_branches():
    from app.core.trading_logger import TradingLogger

    tl = TradingLogger()
    tl.log_trading_cycle({"trades_executed": 0, "mode": "PAPER"})
    # second call within 5min, no trades → skip
    tl.log_trading_cycle({"trades_executed": 0})
    assert tl.cycle_summary.get("mode") == "PAPER"
    # trades force log
    tl.log_trading_cycle({"trades_executed": 2, "total_trades": 2})
    assert tl.cycle_summary["trades_executed"] == 2
    # age > 300s
    tl.last_summary_time = datetime.now() - timedelta(seconds=400)
    tl.log_trading_cycle({"trades_executed": 0, "success_rate": 1.0})
    assert tl.cycle_summary["success_rate"] == 1.0

    tl.log_balance_check({"USDT": 100.0}, has_issues=False)
    tl.log_balance_check({"USDT": 0.0}, has_issues=True)
    tl.log_order_execution("BTCUSDT", "BUY", 0.01, 50000.0, True)
    tl.log_order_execution("BTCUSDT", "SELL", 0.01, 50000.0, False)
    tl.log_profit_loss("BTCUSDT", 10.0, 0.1)
    tl.log_profit_loss("BTCUSDT", -5.0, -0.05)
    tl.log_profit_loss("BTCUSDT", 0.0, 0.0)


# ── trading_errors ──────────────────────────────────────────────────────────


def test_trading_errors_factories_and_handle():
    from app.core.trading_errors import (
        ErrorSeverity,
        InsufficientFundsError,
        create_binance_api_error,
        create_commission_error,
        create_validation_error,
        handle_trading_error,
    )

    ce = create_commission_error(100.0, "bad commission", {"x": 1})
    assert ce.code == "INVALID_COMMISSION_CALCULATION"
    assert ce.timestamp  # set in __post_init__

    ve = create_validation_error("qty", "x", "float", "bad qty")
    assert ve.field == "qty"
    assert ve.severity == ErrorSeverity.LOW

    be = create_binance_api_error(-1003, "rate", "/api/v3/order")
    assert be.retryable is True
    be2 = create_binance_api_error(-2010, "reject", "/order")
    assert be2.retryable is False

    funds = InsufficientFundsError(
        code="NO_FUNDS",
        message="short",
        severity=ErrorSeverity.HIGH,
        context={},
        required_amount=10.0,
        available_amount=1.0,
        asset="USDT",
    )
    handled = handle_trading_error(funds)
    assert handled["error"] is True
    assert handled["code"] == "NO_FUNDS"
    assert handled["severity"] == "high"
