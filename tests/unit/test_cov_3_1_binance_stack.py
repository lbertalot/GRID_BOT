"""COV-3.1 — Binance stack paper mocks (cero red).

Paper-only · no live · PROMOTE_LIVE: NO.
Firma/helpers/error taxonomy; sin sleep de red real.
"""

from __future__ import annotations

import sys
import time
import warnings
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import binance_async as basync
from app.services import binance_client_singleton as singleton
from app.services.binance_service import BinanceService

pytestmark = [pytest.mark.anyio]


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def paper_svc(paper_env, monkeypatch):
    monkeypatch.setenv("USE_REAL_BINANCE", "0")
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.setenv("FORCE_REAL_MODE", "")
    svc = BinanceService()
    svc.simulation_mode = True
    svc.force_real_mode = False
    return svc


# ── singleton helpers (puros) ────────────────────────────────────────────────


def test_singleton_earn_and_ld_helpers():
    assert singleton.binance_earn_underlying_asset("LDUSDT") == "USDT"
    assert singleton.binance_earn_underlying_asset("BTC") is None
    assert singleton.binance_earn_underlying_asset("") is None

    assert singleton.fallback_ld_prefixed_spot_symbol("LDBTCUSDT") == "BTCUSDT"
    assert singleton.fallback_ld_prefixed_spot_symbol("LDUSDTUSDT") is None
    assert singleton.fallback_ld_prefixed_spot_symbol("BTCUSDT") is None

    assert singleton._looks_like_earn_synthetic_symbol("LDUSDT") is True
    assert singleton._looks_like_earn_synthetic_symbol("BTCUSDT") is False

    owner = MagicMock()
    owner._last_invalid_symbol_ts = {}
    singleton._rate_limited_debug_skip_earn(owner, "LDUSDT")
    singleton._rate_limited_debug_skip_earn(owner, "LDUSDT")  # cooldown


def test_notify_invalid_ip_mocked_no_network(monkeypatch):
    monkeypatch.setattr(singleton, "_last_ip_alert_ts", 0.0)
    with patch.object(
        singleton.httpx, "get", side_effect=RuntimeError("no net")
    ), patch(
        "app.services.telegram_alert.send_telegram_alert", return_value=True
    ):
        singleton._notify_invalid_ip("Invalid API-key, IP, or permissions")
    singleton._notify_invalid_ip("Invalid API-key, IP, or permissions")


def test_get_binance_client_singleton_callable(paper_env):
    assert callable(singleton.get_binance_client_singleton)


# ── BinanceService paper ─────────────────────────────────────────────────────


def test_binance_service_paper_account_balance_orders(paper_svc, monkeypatch):
    ledger = MagicMock()
    ledger.cost_model.maker_fee_bps = Decimal("10")
    ledger.cost_model.taker_fee_bps = Decimal("10")
    ledger.as_binance_balances.return_value = [
        {"asset": "USDT", "free": "900.00", "locked": "0"},
        {"asset": "BTC", "free": "0.01", "locked": "0"},
    ]

    with patch(
        "app.core.paper_equity_ledger.get_paper_ledger", return_value=ledger
    ):
        acct = paper_svc.get_account_info()
        bal = paper_svc.get_balance("USDT")
        miss = paper_svc.get_balance("XYZ")
    assert acct["accountType"] == "SPOT"
    assert bal["free"] == "900.00"
    assert miss["free"] == "0"
    assert paper_svc.is_simulation_mode() is True

    sim_info = paper_svc._get_simulated_symbol_info("BTCUSDT")
    assert sim_info["symbol"] == "BTCUSDT"
    assert sim_info["baseAsset"] == "BTC"

    v = paper_svc.validate_order_parameters(
        "BTCUSDT", quantity=0.001, side="BUY", order_type="MARKET"
    )
    assert "is_valid" in v
    assert "recommended_quantity" in v

    with patch(
        "app.core.paper_equity_ledger.mark_price_from_client", return_value=50000.0
    ):
        px = paper_svc.get_current_price("BTCUSDT")
        order = paper_svc.execute_trading_order("BTCUSDT", "BUY", "MARKET", 0.001)
    assert px == 50000.0
    assert isinstance(order, dict)

    opens = paper_svc.get_open_orders("BTCUSDT")
    assert isinstance(opens, list)
    cancel = paper_svc.cancel_order("BTCUSDT", 1)
    assert isinstance(cancel, dict)

    analysis = paper_svc.validate_grid_profitability(
        "BTCUSDT", 40000.0, 60000.0, 0.001, 5, 0.5
    )
    assert isinstance(analysis, dict)


# ── AsyncBinanceWrapper + RateLimiter ────────────────────────────────────────


async def test_async_wrapper_price_klines_and_rate_limiter(paper_env, monkeypatch):
    monkeypatch.setenv("USE_REAL_BINANCE", "0")
    cache = MagicMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()

    with patch.object(basync, "get_async_cache", return_value=cache), patch.object(
        basync, "OrderValidator"
    ) as ov:
        ov.return_value.validate_order_parameters.return_value = {
            "is_valid": True,
            "quantity_info": {"adjusted_quantity": 0.001},
            "errors": [],
        }
        wrap = basync.AsyncBinanceWrapper(ttl_seconds=1, rate_per_sec=100.0, burst=10)
        wrap.client = MagicMock()
        wrap.client.get_symbol_ticker.return_value = {"price": "50100.5"}
        wrap.client.get_klines.return_value = [[0, "1", "2", "3", "4", "5", 1]]
        wrap.cache = cache

        price = await wrap.get_price("btcusdt")
        assert price == pytest.approx(50100.5)
        kl = await wrap.get_klines("BTCUSDT", "1h", 2)
        assert isinstance(kl, list)

        # cache hit
        cache.get = AsyncMock(return_value="50200")
        assert await wrap.get_price("BTCUSDT") == 50200.0

        # invalid order
        wrap.validator.validate_order_parameters = MagicMock(
            return_value={"is_valid": False, "errors": ["min_notional"]}
        )
        with pytest.raises(ValueError, match="inválidos"):
            await wrap.create_market_order("BTCUSDT", "BUY", 0.001)

    rl = basync.RateLimiter(rate=0.001, burst=1)
    await rl.acquire()
    with patch.object(basync.asyncio, "sleep", new=AsyncMock()) as slept:
        rl.tokens = 0.0
        rl.timestamp = time.time()
        await rl.acquire()
    slept.assert_awaited()

    # backoff on transient error then success
    wrap2 = basync.AsyncBinanceWrapper.__new__(basync.AsyncBinanceWrapper)
    wrap2.cache = MagicMock()
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("timed out")
        return 42

    with patch.object(basync.asyncio, "sleep", new=AsyncMock()):
        assert await wrap2._with_backoff(flaky) == 42


# ── exchanges BinanceClient (deprecado) con mocks ────────────────────────────


async def test_exchanges_binance_client_normalize_and_rate_limit(paper_env):
    # Evitar Duplicate timeseries de Prometheus al reimportar el módulo deprecado
    for name in ("app.exchanges.binance_client", "app.exchanges"):
        sys.modules.pop(name, None)
    with patch("prometheus_client.Counter", MagicMock()), patch(
        "prometheus_client.Histogram", MagicMock()
    ), patch("prometheus_client.Gauge", MagicMock()), warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        from app.exchanges.binance_client import (
            BinanceClient,
            SymbolFilter,
            TokenBucketRateLimiter,
        )

    from app.exchanges.exceptions import RateLimitError

    rl = TokenBucketRateLimiter(capacity=1, refill_rate=0.001, endpoint="order")
    assert await rl.acquire() is True
    rl.tokens = 0
    assert await rl.acquire() is False
    with patch("app.exchanges.binance_client.asyncio.sleep", new=AsyncMock()):
        with pytest.raises(RateLimitError):
            await rl.wait_for_token(max_wait=0.01)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        client = BinanceClient("k", "s", testnet=True)
    assert "testnet" in client.base_url

    client._exchange_info_cache["BTCUSDT"] = SymbolFilter(
        symbol="BTCUSDT",
        price_filter={"tickSize": "0.01"},
        lot_size_filter={"stepSize": "0.001", "minQty": "0.001"},
        min_notional_filter={"minNotional": "10"},
    )
    assert client.normalize_price("BTCUSDT", 50000.123) == pytest.approx(50000.12)
    assert client.normalize_qty("BTCUSDT", 0.0015) >= 0

    payload = {
        "symbols": [
            {
                "symbol": "ETHUSDT",
                "filters": [
                    {"filterType": "PRICE_FILTER", "tickSize": "0.01"},
                    {"filterType": "LOT_SIZE", "stepSize": "0.001", "minQty": "0.001"},
                ],
            }
        ]
    }

    class _Resp:
        status = 200

        async def json(self):
            return payload

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    class _Session:
        def get(self, *a, **k):
            return _Resp()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    with patch(
        "app.exchanges.binance_client.aiohttp.ClientSession", return_value=_Session()
    ):
        client._cache_timestamp = 0
        info = await client.get_exchange_info(force_refresh=True)
    assert "ETHUSDT" in info
