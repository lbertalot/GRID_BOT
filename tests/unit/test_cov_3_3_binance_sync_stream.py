"""COV-3.3 — binance_data_sync + binance_user_stream (mocks, cero red/WS).

Paper-only · no live · PROMOTE_LIVE: NO.
Idempotencia DB + reconnect/auth paths mocked (sin sleep real).
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.services.binance_data_sync import BinanceDataSync
from app.services.binance_user_stream import (
    BinanceUserStreamHandler,
    Ed25519Signer,
    default_on_fill,
)

pytestmark = [pytest.mark.anyio]

_ED25519_PEM = (
    Ed25519PrivateKey.generate()
    .private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    .decode()
)

_FILTERS = [
    {
        "filterType": "LOT_SIZE",
        "minQty": "0.001",
        "maxQty": "1000",
        "stepSize": "0.001",
    },
    {
        "filterType": "PRICE_FILTER",
        "tickSize": "0.01",
        "minPrice": "0.01",
        "maxPrice": "1e6",
    },
    {"filterType": "MIN_NOTIONAL", "minNotional": "10"},
]


@pytest.fixture
def anyio_backend():
    return "asyncio"


class _FakeConn:
    def __init__(self) -> None:
        self.inserted_order_ids: set[str] = set()
        self.closed = False

    async def execute(self, query, *args):
        if "insert into trades" in " ".join(str(query).split()).lower():
            oid = str(args[4])
            if oid in self.inserted_order_ids:
                return "INSERT 0 0"
            self.inserted_order_ids.add(oid)
            return "INSERT 0 1"
        return "OK"

    async def fetchrow(self, query, *args):
        if "profit_loss" in str(query).lower():
            return {
                "total_trades": 4,
                "winning_trades": 3,
                "losing_trades": 1,
                "total_profit": 12.5,
                "total_loss": 2.5,
            }
        return None

    async def close(self):
        self.closed = True


def _make_sync(monkeypatch) -> tuple[BinanceDataSync, _FakeConn]:
    monkeypatch.delenv("BINANCE_API_KEY", raising=False)
    monkeypatch.delenv("BINANCE_SECRET_KEY", raising=False)
    sync = BinanceDataSync()
    fake = _FakeConn()
    sync.get_db_connection = lambda: _async_ok(fake)  # type: ignore
    sync.client = MagicMock()
    sync.async_binance = MagicMock()
    sync.async_binance.get_price = AsyncMock(return_value=50000.0)
    sync.async_binance.get_klines = AsyncMock(
        return_value=[
            [1700000000000, "100", "110", "90", "105", "1.5", 1700003600000]
            + ["0"] * 5
        ]
    )
    return sync, fake


async def _async_ok(v):
    return v


# ── BinanceDataSync ──────────────────────────────────────────────────────────


async def test_data_sync_happy_paths_and_idempotency(monkeypatch):
    sync, fake = _make_sync(monkeypatch)
    assert sync._classify_error_type("Invalid API-key -2015") == "auth"
    assert sync._classify_error_type("timed out") == "timeout"
    assert sync._classify_error_type("duplicate key constraint") == "constraint"
    assert sync._classify_error_type("json parse") == "parse"
    assert sync._classify_error_type("x") == "unknown"

    sync.client = None
    for fn in (
        sync.sync_account_info,
        sync.sync_balances,
        sync.sync_symbol_info,
        sync.sync_recent_trades,
        sync.sync_klines_data,
        sync.sync_performance_metrics,
    ):
        assert (await fn())["status"] == "error"

    sync, fake = _make_sync(monkeypatch)
    sync.client.get_account = MagicMock(
        return_value={
            "accountType": "SPOT",
            "makerCommission": 10,
            "takerCommission": 10,
            "balances": [
                {"asset": "USDT", "free": "100", "locked": "0"},
                {"asset": "BTC", "free": "0.01", "locked": "0"},
                {"asset": "DUST", "free": "0", "locked": "0"},
                {"asset": "BAD", "free": "1", "locked": "0"},
            ],
        }
    )
    sync.client.get_symbol_ticker = MagicMock(
        side_effect=lambda symbol: (
            {"price": "50000"}
            if symbol == "BTCUSDT"
            else (_ for _ in ()).throw(RuntimeError("no"))
        )
    )
    sync.client.get_exchange_info = MagicMock(
        return_value={
            "symbols": [
                {
                    "symbol": "BTCUSDT",
                    "baseAsset": "BTC",
                    "quoteAsset": "USDT",
                    "filters": _FILTERS,
                },
                {"symbol": "ETHBTC", "filters": []},
                {"symbol": "ETHUSDT", "filters": _FILTERS},
            ]
        }
    )
    sync.client.get_recent_trades = MagicMock(
        return_value=[
            {
                "id": 111,
                "isBuyerMaker": False,
                "qty": "0.01",
                "price": "100",
                "time": 1700000000000,
            },
            {
                "id": 222,
                "isBuyerMaker": True,
                "qty": "0.02",
                "price": "101",
                "time": 1700000001000,
            },
        ]
    )

    assert (await sync.sync_account_info())["account_type"] == "SPOT"
    bal = await sync.sync_balances()
    assert bal["balances_count"] == 3 and bal["total_value_usdt"] > 0
    assert (await sync.sync_symbol_info(["BTCUSDT"]))["symbols_count"] == 1
    assert (await sync.sync_recent_trades("BTCUSDT", 2))["trades_inserted"] == 2
    assert (await sync.sync_recent_trades("BTCUSDT", 2))["trades_inserted"] == 0
    assert (await sync.sync_klines_data())["klines_inserted"] == 1
    perf = await sync.sync_performance_metrics()
    assert perf["total_trades"] == 4 and perf["win_rate"] == 75.0
    info = await sync._get_symbol_info("BTC")
    assert info and (await sync._get_symbol_info("BTC")) is info
    sync.client = None
    assert await sync._get_symbol_info("ETH") is None
    assert fake.closed

    sync2, _ = _make_sync(monkeypatch)
    stubs = {
        n: AsyncMock(return_value={"status": "ok"})
        for n in (
            "sync_account_info",
            "sync_balances",
            "sync_symbol_info",
            "sync_recent_trades",
            "sync_klines_data",
            "sync_performance_metrics",
        )
    }
    with patch.multiple(sync2, **stubs):
        assert set((await sync2.full_sync())) >= {
            "account_info",
            "balances",
            "symbol_info",
            "recent_trades",
            "klines",
            "performance",
        }


async def test_data_sync_errors_and_client_init(monkeypatch):
    sync, _ = _make_sync(monkeypatch)
    sync._get_pipeline_metrics = lambda: None  # type: ignore
    sync.client.get_account = MagicMock(side_effect=RuntimeError("auth -2015"))
    assert (await sync.sync_account_info())["status"] == "error"
    assert (await sync.sync_balances())["status"] == "error"
    assert (await sync.sync_performance_metrics())["status"] == "error"
    sync.client.get_exchange_info = MagicMock(side_effect=RuntimeError("boom"))
    assert (await sync.sync_symbol_info())["status"] == "error"
    assert await sync._get_symbol_info("BTC") is None
    sync.client.get_recent_trades = MagicMock(side_effect=RuntimeError("timeout"))
    assert (await sync.sync_recent_trades())["status"] == "error"
    sync.async_binance.get_klines = AsyncMock(side_effect=RuntimeError("k"))
    assert (await sync.sync_klines_data())["status"] == "error"

    with patch(
        "app.services.binance_data_sync.asyncpg.connect", side_effect=OSError("db")
    ):
        with pytest.raises(OSError):
            await BinanceDataSync().get_db_connection()

    monkeypatch.setenv("BINANCE_API_KEY", "k")
    monkeypatch.setenv("BINANCE_SECRET_KEY", "s")
    mc = MagicMock()
    mc.get_server_time.return_value = {"serverTime": 1}
    with patch("app.services.binance_data_sync.Client", return_value=mc):
        assert BinanceDataSync().client is mc
    mc.get_server_time.side_effect = RuntimeError("net")
    with patch("app.services.binance_data_sync.Client", return_value=mc):
        assert BinanceDataSync().client is None


# ── User stream ──────────────────────────────────────────────────────────────


def test_ed25519_signer_from_env(monkeypatch, tmp_path):
    monkeypatch.delenv("BINANCE_ED25519_PRIVATE_KEY_PATH", raising=False)
    monkeypatch.delenv("BINANCE_ED25519_PRIVATE_KEY_PEM", raising=False)
    assert Ed25519Signer.from_env() is None
    monkeypatch.setenv("BINANCE_ED25519_PRIVATE_KEY_PEM", "bad")
    assert Ed25519Signer.from_env() is None
    monkeypatch.setenv("BINANCE_ED25519_PRIVATE_KEY_PEM", _ED25519_PEM)
    assert Ed25519Signer.from_env().sign("apiKey=x&timestamp=1")
    monkeypatch.delenv("BINANCE_ED25519_PRIVATE_KEY_PEM", raising=False)
    monkeypatch.setenv(
        "BINANCE_ED25519_PRIVATE_KEY_PATH", str(tmp_path / "missing.pem")
    )
    assert Ed25519Signer.from_env() is None
    pem = tmp_path / "ed.pem"
    pem.write_text(_ED25519_PEM)
    monkeypatch.setenv("BINANCE_ED25519_PRIVATE_KEY_PATH", str(pem))
    assert Ed25519Signer.from_env() is not None


async def test_user_stream_lifecycle_dispatch_reconnect(monkeypatch):
    monkeypatch.setenv("BINANCE_ED25519_API_KEY", "ed-key")
    monkeypatch.setenv("BINANCE_ED25519_PRIVATE_KEY_PEM", _ED25519_PEM)
    monkeypatch.setenv("BINANCE_TESTNET", "true")

    with patch(
        "app.services.binance_user_stream.get_binance_proxy_url", return_value=None
    ), patch(
        "app.services.binance_user_stream.aiohttp.ClientSession",
        return_value=MagicMock(),
    ), patch(
        "app.services.binance_user_stream.asyncio.create_task",
        return_value=MagicMock(),
    ):
        h = BinanceUserStreamHandler(api_key="hmac")
        assert h.api_key == "ed-key" and "testnet" in h.ws_url
        await h.start(on_fill=lambda e: None)
        assert h.running
        await h.start(on_fill=lambda e: None)
        await h.stop()
        assert not h.running

    with patch(
        "app.services.binance_user_stream.get_binance_proxy_url", return_value=None
    ), patch.object(Ed25519Signer, "from_env", return_value=None):
        monkeypatch.delenv("BINANCE_ED25519_API_KEY", raising=False)
        monkeypatch.delenv("BINANCE_API_KEY", raising=False)
        bare = BinanceUserStreamHandler(api_key="")
        await bare.start(on_fill=lambda e: None)
        assert not bare.running
        monkeypatch.setenv("BINANCE_ED25519_API_KEY", "ed-key")
        no_sig = BinanceUserStreamHandler()
        no_sig.signer = None
        await no_sig.start(on_fill=lambda e: None)
        assert not no_sig.running

    monkeypatch.setenv("BINANCE_ED25519_API_KEY", "ed-key")
    monkeypatch.setenv("BINANCE_ED25519_PRIVATE_KEY_PEM", _ED25519_PEM)
    with patch(
        "app.services.binance_user_stream.get_binance_proxy_url", return_value=None
    ):
        h = BinanceUserStreamHandler()

    fills: list = []
    h._on_fill = lambda e: fills.append(e)
    h.ws = MagicMock()
    h.ws.send_str = AsyncMock()

    async def _ok():
        await asyncio.sleep(0)
        await h._dispatch({"id": next(iter(h._pending)), "status": 200, "result": {}})

    t = asyncio.create_task(_ok())
    assert (await h._send_request("session.logon", params={"x": 1}, timeout=1))[
        "status"
    ] == 200
    await t

    with pytest.raises(RuntimeError, match="WS no conectado"):
        await BinanceUserStreamHandler(api_key="k")._send_request("x")

    async def _fail():
        await asyncio.sleep(0)
        await h._dispatch(
            {
                "id": next(iter(h._pending)),
                "status": 400,
                "error": {"code": -1022, "msg": "Signature"},
            }
        )

    t2 = asyncio.create_task(_fail())
    with pytest.raises(RuntimeError, match="fallido"):
        await h._send_request("session.logon", timeout=1)
    await t2

    await h._dispatch({"event": {"e": "executionReport", "s": "BTCUSDT"}})
    await h._dispatch({"e": "outboundAccountPosition"})
    await h._dispatch({"e": "customEvent"})
    await h._dispatch({"pong": 1})
    assert fills
    h._on_fill = lambda _: (_ for _ in ()).throw(RuntimeError("cb"))
    await h._invoke_on_fill({})
    h._on_fill = None
    await h._invoke_on_fill({})
    assert h._canonical_logon_payload(9) == "apiKey=ed-key&timestamp=9"
    with patch.object(h, "_send_request", AsyncMock(return_value={"status": 200})):
        await h._session_logon()
    with patch.object(
        h,
        "_send_request",
        AsyncMock(return_value={"status": 200, "result": {"subscriptionId": "s1"}}),
    ):
        await h._subscribe_user_data()
        assert h.subscription_id == "s1"

    with patch(
        "app.services.binance_user_stream.get_binance_proxy_url",
        return_value="http://proxy",
    ):
        h2 = BinanceUserStreamHandler()
    h2.session = MagicMock()
    sleeps: list[float] = []

    async def _auth_sleep(sec):
        sleeps.append(sec)
        h2.running = False

    h2.running = True
    h2.session.ws_connect = AsyncMock(side_effect=RuntimeError("Invalid API-key"))
    with patch(
        "app.services.binance_user_stream.asyncio.sleep", _auth_sleep
    ), patch("app.services.binance_client_singleton._notify_invalid_ip"):
        await h2._connection_loop()
    assert sleeps == [300]

    sleeps.clear()

    async def _net_sleep(sec):
        sleeps.append(sec)
        h2.running = False

    h2.running = True
    h2.session.ws_connect = AsyncMock(side_effect=RuntimeError("blip"))
    with patch("app.services.binance_user_stream.asyncio.sleep", _net_sleep):
        await h2._connection_loop()
    assert sleeps == [1]

    class _WS:
        def __init__(self):
            self._msgs = [
                SimpleNamespace(
                    type=aiohttp.WSMsgType.TEXT,
                    data=json.dumps({"e": "executionReport", "s": "BTCUSDT"}),
                ),
                SimpleNamespace(type=aiohttp.WSMsgType.CLOSED, data=None),
            ]

        def __aiter__(self):
            return self

        async def __anext__(self):
            if not self._msgs:
                raise StopAsyncIteration
            return self._msgs.pop(0)

        async def close(self):
            return None

    h2._on_fill = lambda e: fills.append(e)
    h2.ws = _WS()
    with pytest.raises(RuntimeError, match="WS cerrado"):
        await h2._reader_loop()

    h2.session.ws_connect = AsyncMock(return_value=_WS())
    h2.running = True

    async def _stop_sleep(_):
        h2.running = False

    with patch.object(h2, "_session_logon", AsyncMock()), patch.object(
        h2, "_subscribe_user_data", AsyncMock()
    ), patch("app.services.binance_user_stream.asyncio.sleep", _stop_sleep):
        await h2._connection_loop()

    db = MagicMock()
    with patch(
        "app.services.binance_user_stream.SessionLocal", return_value=db
    ), patch(
        "app.services.binance_user_stream.BalanceService.update_balance"
    ) as upd:
        await default_on_fill(
            {
                "e": "executionReport",
                "s": "BTCUSDT",
                "S": "BUY",
                "X": "FILLED",
                "l": "0.001",
                "Z": "50",
            }
        )
        await default_on_fill(
            {
                "e": "executionReport",
                "s": "ETHUSDT",
                "S": "SELL",
                "X": "FILLED",
                "l": "0.01",
                "Z": "30",
            }
        )
        await default_on_fill({"X": "NEW"})
        assert upd.call_count == 4
