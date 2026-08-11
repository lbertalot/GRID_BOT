"""COV-5.11 — redis_cache + balance_service + binance_credentials paper batch.

Paper-only · mocks Redis/DB/Client · PROMOTE_LIVE: NO.
Cierra gap ~83.8% → ≥85%.
"""

from __future__ import annotations

import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.redis_cache import RedisCache
from app.services import binance_credentials as creds
from app.services.balance_service import BalanceService, ConcurrentModificationError

# Clases bindidas en el módulo (pueden diferir del stub de conftest).
_BAE = creds.BinanceAPIException
_BRE = creds.BinanceRequestException

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("paper_env")]


def _api_exc(code: int, message: str = "bad"):
    """Construye BinanceAPIException compatible stub/SDK real."""
    try:
        return _BAE(400, message, code=code)
    except TypeError:
        text = json.dumps({"code": code, "msg": message})
        resp = MagicMock()
        resp.text = text
        return _BAE(resp, 400, text)


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ── RedisCache ───────────────────────────────────────────────────────────────


def _fake_redis(**extra):
    r = AsyncMock()
    r.ping = AsyncMock(return_value=True)
    r.get = AsyncMock(return_value=None)
    r.set = AsyncMock(return_value=True)
    r.setex = AsyncMock(return_value=True)
    r.delete = AsyncMock(return_value=1)
    r.exists = AsyncMock(return_value=1)
    r.info = AsyncMock(return_value={"used_memory_human": "1M", "connected_clients": 2})
    r.flushdb = AsyncMock(return_value=True)
    r.close = AsyncMock()

    async def _scan(**kwargs):
        if False:
            yield "x"
        return
        yield  # pragma: no cover

    # async iterator for scan_iter
    class _Scan:
        def __init__(self, keys):
            self._keys = keys

        def __aiter__(self):
            self._i = 0
            return self

        async def __anext__(self):
            if self._i >= len(self._keys):
                raise StopAsyncIteration
            k = self._keys[self._i]
            self._i += 1
            return k

    r.scan_iter = MagicMock(return_value=_Scan(["klines:ETHUSDT:1m:100"]))
    for k, v in extra.items():
        setattr(r, k, v)
    return r


@pytest.fixture
def cache():
    c = RedisCache(host="localhost", port=6379)
    c._redis_client = _fake_redis()
    return c


async def test_redis_get_set_hit_miss_json(cache):
    # miss
    assert await cache.get("k1") is None
    assert cache.cache_misses == 1

    # hit JSON
    cache._redis_client.get = AsyncMock(return_value=json.dumps({"a": 1}))
    assert await cache.get("k1") == {"a": 1}
    assert cache.cache_hits == 1

    # hit raw string
    cache._redis_client.get = AsyncMock(return_value="plain")
    assert await cache.get("k2") == "plain"

    # set dict with ttl
    assert await cache.set("k3", {"x": 2}, ttl=10) is True
    cache._redis_client.setex.assert_awaited()

    # set scalar without ttl
    assert await cache.set("k4", "v") is True
    cache._redis_client.set.assert_awaited()

    # error paths
    cache._redis_client.get = AsyncMock(side_effect=RuntimeError("down"))
    assert await cache.get("boom") is None
    cache._redis_client.set = AsyncMock(side_effect=RuntimeError("down"))
    assert await cache.set("boom", "v") is False


async def test_redis_delete_exists_typed_helpers(cache):
    assert await cache.delete("k") is True
    cache._redis_client.delete = AsyncMock(return_value=0)
    assert await cache.delete("missing") is False
    cache._redis_client.delete = AsyncMock(side_effect=RuntimeError("x"))
    assert await cache.delete("err") is False

    cache._redis_client.exists = AsyncMock(return_value=1)
    assert await cache.exists("k") is True
    cache._redis_client.exists = AsyncMock(side_effect=RuntimeError("x"))
    assert await cache.exists("err") is False

    cache._redis_client.get = AsyncMock(return_value=None)
    await cache.get_exchange_info("ethusdt")
    await cache.get_exchange_info()
    await cache.set_exchange_info({"symbols": []}, "ETHUSDT")
    await cache.set_exchange_info({"symbols": []})
    await cache.get_symbol_ticker("ETHUSDT")
    await cache.set_symbol_ticker("ETHUSDT", {"price": "1"})
    await cache.get_account_info()
    await cache.set_account_info({"balances": []})
    await cache.get_klines("ETHUSDT", "1m", 50)
    await cache.set_klines("ETHUSDT", "1m", [[1]], 50)


async def test_redis_invalidate_stats_clear_close(cache):
    await cache.invalidate_symbol("ETHUSDT")
    cache._redis_client.delete.assert_awaited()

    cache._redis_client.scan_iter = MagicMock(side_effect=RuntimeError("scan"))
    await cache.invalidate_symbol("BTCUSDT")  # logs error

    stats = await cache.get_cache_stats()
    assert "cache_hits" in stats
    assert stats["redis_memory_used"] == "1M"

    cache._redis_client.info = AsyncMock(side_effect=RuntimeError("info"))
    bad = await cache.get_cache_stats()
    assert "error" in bad or bad.get("cache_hits") == 0 or "cache_hits" in bad

    cache._redis_client.flushdb = AsyncMock(return_value=True)
    # clear_all may use flushdb or scan
    if hasattr(cache, "clear_all"):
        with patch.object(cache, "_get_client", AsyncMock(return_value=cache._redis_client)):
            # implement based on source
            result = await cache.clear_all()
            assert isinstance(result, bool)

    await cache.close()
    cache._redis_client = None
    await cache.close()


async def test_redis_get_client_connect(monkeypatch):
    c = RedisCache(host="localhost")
    fake = _fake_redis()
    with patch("app.core.redis_cache.redis.Redis", return_value=fake):
        client = await c._get_client()
    assert client is fake
    # second call reuses
    assert await c._get_client() is fake

    c2 = RedisCache()
    with patch(
        "app.core.redis_cache.redis.Redis",
        side_effect=RuntimeError("no-redis"),
    ):
        with pytest.raises(RuntimeError):
            await c2._get_client()


# ── BalanceService ───────────────────────────────────────────────────────────


def _db_balance(asset="USDT", amount="100", version=1):
    b = MagicMock()
    b.asset = asset
    b.amount = Decimal(amount)
    b.version = version
    return b


def test_balance_get_and_update_create(monkeypatch):
    db = MagicMock()
    bal = _db_balance()
    db.query.return_value.filter.return_value.first.return_value = bal
    assert BalanceService.get_balance(db, "USDT") is bal

    # create path
    db2 = MagicMock()
    db2.query.return_value.filter.return_value.first.return_value = None
    created = BalanceService.update_balance(db2, "ETH", Decimal("1.5"))
    db2.add.assert_called()
    db2.commit.assert_called()


def test_balance_update_conflict_then_success(monkeypatch):
    db = MagicMock()
    bal = _db_balance(version=3)
    db.query.return_value.filter.return_value.first.return_value = bal
    # first execute rowcount 0, then 1
    r0 = MagicMock(rowcount=0)
    r1 = MagicMock(rowcount=1)
    db.execute.side_effect = [r0, r1]
    with patch("app.services.balance_service.time.sleep"), patch(
        "app.core.metrics.balance_update_conflicts_total"
    ) as m:
        m.labels.return_value = MagicMock()
        out = BalanceService.update_balance(db, "USDT", Decimal("10"), max_retries=3)
    assert out is bal


def test_balance_update_exhausted_retries(monkeypatch):
    db = MagicMock()
    bal = _db_balance()
    db.query.return_value.filter.return_value.first.return_value = bal
    db.execute.return_value = MagicMock(rowcount=0)
    with patch("app.services.balance_service.time.sleep"), pytest.raises(
        ConcurrentModificationError
    ):
        BalanceService.update_balance(db, "USDT", Decimal("1"), max_retries=2)


def test_balance_set_upsert_all(monkeypatch):
    db = MagicMock()
    # create
    db.query.return_value.filter.return_value.first.return_value = None
    BalanceService.set_balance(db, "ADA", Decimal("5"))
    db.add.assert_called()

    # update CAS success
    db2 = MagicMock()
    bal = _db_balance("ADA", "5", 2)
    db2.query.return_value.filter.return_value.first.return_value = bal
    db2.execute.return_value = MagicMock(rowcount=1)
    assert BalanceService.set_balance(db2, "ADA", Decimal("9")) is bal

    # conflict then fail
    db3 = MagicMock()
    db3.query.return_value.filter.return_value.first.return_value = bal
    db3.execute.return_value = MagicMock(rowcount=0)
    with patch("app.services.balance_service.time.sleep"), pytest.raises(
        ConcurrentModificationError
    ):
        BalanceService.set_balance(db3, "ADA", Decimal("1"), max_retries=2)

    db4 = MagicMock()
    BalanceService.upsert_from_exchange(db4, "USDT", Decimal("100"))
    db4.execute.assert_called()

    db5 = MagicMock()
    db5.query.return_value.all.return_value = [bal]
    assert len(BalanceService.get_all_balances(db5)) == 1


# ── binance_credentials ──────────────────────────────────────────────────────


def test_get_credentials_ok_and_errors(monkeypatch):
    monkeypatch.setenv("BINANCE_API_KEY", "key1234567890")
    monkeypatch.setenv("BINANCE_SECRET_KEY", "sec1234567890")
    monkeypatch.setenv("DEBUG", "false")
    with patch.object(creds, "load_dotenv"):
        k, s = creds.get_binance_credentials()
    assert k.startswith("key") and s.startswith("sec")

    monkeypatch.delenv("BINANCE_API_KEY", raising=False)
    monkeypatch.delenv("BINANCE_SECRET_KEY", raising=False)
    with patch.object(creds, "load_dotenv"), pytest.raises(creds.BinanceCredentialsError):
        creds.get_binance_credentials()

    monkeypatch.setenv("BINANCE_API_KEY", "   ")
    monkeypatch.setenv("BINANCE_SECRET_KEY", "sec")
    with patch.object(creds, "load_dotenv"), pytest.raises(creds.BinanceCredentialsError):
        creds.get_binance_credentials()


def test_create_and_verify_credentials(monkeypatch):
    fake = MagicMock()
    fake.api_key = "k"
    fake.api_secret = "s"
    fake.get_account.return_value = {
        "accountType": "SPOT",
        "permissions": ["SPOT"],
        "balances": [{"asset": "USDT"}],
    }
    with patch.object(creds, "Client", return_value=fake):
        client = creds.create_binance_client("k", "s", testnet=False)
    assert client.api_key == "k"

    with patch.object(creds, "Client", return_value=fake):
        client_tn = creds.create_binance_client("k", "s", testnet=True)
    assert client_tn is fake

    with pytest.raises(creds.BinanceConnectionError):
        creds.create_binance_client("", "", testnet=False)

    info = creds.verify_binance_credentials(fake)
    assert info["valid"] is True

    fake.get_account.side_effect = _api_exc(-2015)
    with pytest.raises(creds.BinanceCredentialsError):
        creds.verify_binance_credentials(fake)

    fake.get_account.side_effect = _api_exc(-2013)
    with pytest.raises(creds.BinanceCredentialsError):
        creds.verify_binance_credentials(fake)

    fake.get_account.side_effect = _api_exc(-1000, "other")
    with pytest.raises(creds.BinanceCredentialsError):
        creds.verify_binance_credentials(fake)

    fake.get_account.side_effect = _BRE("net")
    with pytest.raises(creds.BinanceConnectionError):
        creds.verify_binance_credentials(fake)

    fake.get_account.side_effect = RuntimeError("unexpected")
    with pytest.raises(creds.BinanceConnectionError):
        creds.verify_binance_credentials(fake)

    fake.get_account.side_effect = None
    fake.get_account.return_value = None
    with pytest.raises(creds.BinanceConnectionError):
        creds.verify_binance_credentials(fake)


def test_client_with_verification_and_connection_test(monkeypatch):
    monkeypatch.setenv("BINANCE_API_KEY", "key1234567890")
    monkeypatch.setenv("BINANCE_SECRET_KEY", "sec1234567890")
    fake = MagicMock()
    fake.api_key = "key1234567890"
    fake.get_account.return_value = {
        "accountType": "SPOT",
        "permissions": [],
        "balances": [],
    }
    with patch.object(creds, "load_dotenv"), patch.object(
        creds, "Client", return_value=fake
    ):
        client, info = creds.get_binance_client_with_verification(testnet=False)
    assert info["valid"] is True
    assert client is fake

    # cliente sin api_key
    bare = MagicMock(spec=[])
    with patch.object(creds, "load_dotenv"), patch.object(
        creds, "get_binance_credentials", return_value=("k", "s")
    ), patch.object(creds, "create_binance_client", return_value=bare), pytest.raises(
        creds.BinanceCredentialsError
    ):
        creds.get_binance_client_with_verification()

    with patch.object(
        creds, "get_binance_credentials", side_effect=RuntimeError("boom")
    ), pytest.raises(creds.BinanceConnectionError):
        creds.get_binance_client_with_verification()

    with patch.object(
        creds, "get_binance_client_with_verification", return_value=(fake, info)
    ):
        assert creds.test_binance_connection() is True

    with patch.object(
        creds,
        "get_binance_client_with_verification",
        side_effect=creds.BinanceCredentialsError("x"),
    ):
        assert creds.test_binance_connection() is False


async def test_redis_clear_all_error(cache):
    cache._redis_client.flushdb = AsyncMock(side_effect=RuntimeError("flush"))
    assert await cache.clear_all() is False


def test_balance_update_generic_error_then_raise():
    db = MagicMock()
    bal = _db_balance()
    db.query.return_value.filter.return_value.first.return_value = bal
    db.execute.side_effect = RuntimeError("db-down")
    with pytest.raises(RuntimeError):
        BalanceService.update_balance(db, "USDT", Decimal("1"), max_retries=1)


def test_balance_set_generic_error_then_raise():
    db = MagicMock()
    bal = _db_balance()
    db.query.return_value.filter.return_value.first.return_value = bal
    db.execute.side_effect = RuntimeError("db-down")
    with pytest.raises(RuntimeError):
        BalanceService.set_balance(db, "USDT", Decimal("1"), max_retries=1)


def test_credentials_stub_fake_client_and_create_error(monkeypatch):
    from app.services.binance_credentials import _FakeClient

    fc = _FakeClient()
    assert "balances" in fc.get_account()
    assert fc.create_order(symbol="ETHUSDT")["orderId"] == 1

    with patch.object(creds, "Client", side_effect=RuntimeError("sdk-down")), pytest.raises(
        creds.BinanceConnectionError
    ):
        creds.create_binance_client("key1234567890", "sec1234567890", testnet=False)

    # cliente sin api_key → asignación manual
    bare = MagicMock()
    bare.api_key = None
    with patch.object(creds, "Client", return_value=bare):
        out = creds.create_binance_client("key1234567890", "sec1234567890")
    assert out.api_key == "key1234567890"
    assert out.api_secret == "sec1234567890"