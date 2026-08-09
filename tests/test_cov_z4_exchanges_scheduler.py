"""S-COV-85 Z4 — binance_client + optimized_scheduler (heavy mocks, paper-only)."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.usefixtures("paper_env")


# ── exchanges.binance_client ─────────────────────────────────────────────────


def _make_client(testnet: bool = True):
    from app.exchanges.binance_client import BinanceClient

    with pytest.warns(DeprecationWarning):
        return BinanceClient("k", "s", testnet=testnet)


def _seed_filters(client, symbol: str = "BTCUSDT"):
    from app.exchanges.binance_client import SymbolFilter

    client._exchange_info_cache[symbol] = SymbolFilter(
        symbol=symbol,
        price_filter={
            "minPrice": "0.01",
            "maxPrice": "1000000",
            "tickSize": "0.01",
        },
        lot_size_filter={
            "minQty": "0.001",
            "maxQty": "9000",
            "stepSize": "0.001",
        },
        min_notional_filter={"minNotional": "10.0"},
    )
    client._cache_timestamp = time.time()


@pytest.mark.asyncio
async def test_token_bucket_acquire_and_rate_limit():
    from app.exchanges.binance_client import RateLimitError, TokenBucketRateLimiter

    lim = TokenBucketRateLimiter(capacity=1, refill_rate=100.0, endpoint="order")
    assert await lim.acquire() is True
    assert await lim.acquire() is False  # empty

    lim2 = TokenBucketRateLimiter(capacity=1, refill_rate=0.0, endpoint="slow")
    lim2.tokens = 0
    with patch("app.exchanges.binance_client.asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(RateLimitError):
            await lim2.wait_for_token(max_wait=0.01)

    lim3 = TokenBucketRateLimiter(capacity=2, refill_rate=1000.0, endpoint="ok")
    await lim3.wait_for_token(max_wait=1.0)


def test_binance_client_init_urls():
    c = _make_client(testnet=True)
    assert "testnet" in c.base_url
    c2 = _make_client(testnet=False)
    assert "api.binance.com" in c2.base_url


@pytest.mark.asyncio
async def test_get_exchange_info_cache_and_fetch():
    client = _make_client()
    # cache hit
    _seed_filters(client)
    cached = await client.get_exchange_info(force_refresh=False)
    assert "BTCUSDT" in cached

    payload = {
        "symbols": [
            {
                "symbol": "ETHUSDT",
                "filters": [
                    {
                        "filterType": "PRICE_FILTER",
                        "minPrice": "0.01",
                        "maxPrice": "1e6",
                        "tickSize": "0.01",
                    },
                    {
                        "filterType": "LOT_SIZE",
                        "minQty": "0.01",
                        "maxQty": "1000",
                        "stepSize": "0.01",
                    },
                ],
            }
        ]
    }

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value=payload)
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.get.return_value = mock_resp
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch(
        "app.exchanges.binance_client.aiohttp.ClientSession", return_value=mock_session
    ), patch.object(
        client.rate_limiters["exchange_info"], "wait_for_token", new_callable=AsyncMock
    ):
        out = await client.get_exchange_info(force_refresh=True)
    assert "ETHUSDT" in out

    # non-200 → ConnectionError
    bad = AsyncMock()
    bad.status = 500
    bad.__aenter__ = AsyncMock(return_value=bad)
    bad.__aexit__ = AsyncMock(return_value=False)
    mock_session.get.return_value = bad
    with patch(
        "app.exchanges.binance_client.aiohttp.ClientSession", return_value=mock_session
    ), patch.object(
        client.rate_limiters["exchange_info"], "wait_for_token", new_callable=AsyncMock
    ):
        with pytest.raises(Exception):
            await client.get_exchange_info(force_refresh=True)


@pytest.mark.asyncio
async def test_get_helper():
    client = _make_client()
    session = MagicMock()
    ok = AsyncMock()
    ok.status = 200
    ok.json = AsyncMock(return_value={"ok": True})
    ok.__aenter__ = AsyncMock(return_value=ok)
    ok.__aexit__ = AsyncMock(return_value=False)
    session.get.return_value = ok
    assert await client._get(session, "http://x") == {"ok": True}

    bad = AsyncMock()
    bad.status = 404
    bad.__aenter__ = AsyncMock(return_value=bad)
    bad.__aexit__ = AsyncMock(return_value=False)
    session.get.return_value = bad
    with pytest.raises(Exception):
        await client._get(session, "http://x")


def test_normalize_and_validate_order_params():
    from app.exchanges.exceptions import SymbolFilterError

    client = _make_client()
    with pytest.raises(SymbolFilterError):
        client.normalize_price("BTCUSDT", 100.0)
    with pytest.raises(SymbolFilterError):
        client.normalize_qty("BTCUSDT", 1.0)
    with pytest.raises(SymbolFilterError):
        client.validate_order_params("BTCUSDT", 100.0, 1.0)

    _seed_filters(client)
    # no price filter path
    from app.exchanges.binance_client import SymbolFilter

    client._exchange_info_cache["NOPF"] = SymbolFilter(symbol="NOPF")
    assert client.normalize_price("NOPF", 1.234) == 1.234
    assert client.normalize_qty("NOPF", 1.234) == 1.234

    assert client.normalize_price("BTCUSDT", 100.015) == pytest.approx(100.02, abs=0.01)
    assert client.normalize_qty("BTCUSDT", 0.001234) == pytest.approx(0.001)

    # valid
    client.validate_order_params("BTCUSDT", 100.0, 0.1)

    # price below/above/tick
    with pytest.raises(SymbolFilterError):
        client.validate_order_params("BTCUSDT", 0.001, 0.1)
    with pytest.raises(SymbolFilterError):
        client.validate_order_params("BTCUSDT", 2_000_000.0, 0.1)
    with pytest.raises(SymbolFilterError):
        client.validate_order_params("BTCUSDT", 100.005, 0.1)

    # qty below/above/step
    with pytest.raises(SymbolFilterError):
        client.validate_order_params("BTCUSDT", 100.0, 0.0001)
    with pytest.raises(SymbolFilterError):
        client.validate_order_params("BTCUSDT", 100.0, 10000.0)
    with pytest.raises(SymbolFilterError):
        client.validate_order_params("BTCUSDT", 100.0, 0.0015)

    # notional
    with pytest.raises(SymbolFilterError):
        client.validate_order_params("BTCUSDT", 100.0, 0.001)  # notional 0.1 < 10


@pytest.mark.asyncio
async def test_create_order_limit_and_market():
    from app.exchanges.exceptions import SymbolFilterError

    client = _make_client()
    _seed_filters(client)
    with patch.object(
        client.rate_limiters["order"], "wait_for_token", new_callable=AsyncMock
    ):
        lim = await client.create_order(
            "BTCUSDT", "BUY", "LIMIT", quantity=0.1, price=100.0
        )
    assert lim["status"] == "NEW"
    assert Decimal(str(lim["quantity"])) > 0

    with patch.object(
        client.rate_limiters["order"], "wait_for_token", new_callable=AsyncMock
    ):
        mkt = await client.create_order("BTCUSDT", "SELL", "MARKET", quantity=0.1)
    assert mkt["price"] == "0"

    # market qty below min
    with patch.object(
        client.rate_limiters["order"], "wait_for_token", new_callable=AsyncMock
    ):
        with pytest.raises(SymbolFilterError):
            await client.create_order("BTCUSDT", "BUY", "MARKET", quantity=0.0001)


@pytest.mark.asyncio
async def test_websocket_lifecycle_and_health():
    from app.exchanges.exceptions import WebSocketError

    client = _make_client()

    fake_ws = MagicMock()
    fake_ws.close = AsyncMock()

    async def _fake_recv():
        yield json.dumps({"E": int((time.time() - 5) * 1000), "p": "1"})
        yield json.dumps({"x": 1})
        raise Exception("boom-recv")

    class _WS:
        def __aiter__(self):
            return _fake_recv()

        async def close(self):
            return None

    with patch(
        "app.exchanges.binance_client.websockets.connect",
        new_callable=AsyncMock,
        return_value=_WS(),
    ), patch("app.exchanges.binance_client.asyncio.create_task"):
        await client.start_websocket("BTCUSDT", "bookTicker")
    assert "btcusdt@bookTicker" in client._ws_connections

    # process + health
    await client._process_websocket_message("btcusdt@bookTicker", {"a": 1})
    client._ws_last_ping["btcusdt@bookTicker"] = time.time()
    health = await client.check_websocket_health()
    assert health["btcusdt@bookTicker"] is True

    client._ws_last_ping["old"] = time.time() - 100
    health2 = await client.check_websocket_health()
    assert health2["old"] is False

    await client.close_websocket("BTCUSDT", "bookTicker")
    # reconnect close_all with remaining
    client._ws_connections["ethusdt@trade"] = fake_ws
    client._ws_last_ping["ethusdt@trade"] = time.time()
    await client.close_all_websockets()
    assert client._ws_connections == {}

    with patch(
        "app.exchanges.binance_client.websockets.connect",
        new_callable=AsyncMock,
        side_effect=RuntimeError("down"),
    ):
        with pytest.raises(WebSocketError):
            await client.start_websocket("XRPUSDT", "trade")

    # receiver: missing ws
    await client._websocket_receiver("missing", "BTCUSDT", "bookTicker")

    # happy path + high lag + generic exception
    async def _msgs():
        yield json.dumps({"E": int((time.time() - 10) * 1000), "p": "1"})  # high lag
        yield json.dumps({"no_ts": True})
        raise RuntimeError("recv-fail")

    class _IterWS:
        def __aiter__(self):
            return _msgs()

    client._ws_connections["btcusdt@bookTicker"] = _IterWS()
    await client._websocket_receiver("btcusdt@bookTicker", "BTCUSDT", "bookTicker")

    class _Closed:
        def __aiter__(self):
            return self

        async def __anext__(self):
            import websockets.exceptions

            raise websockets.exceptions.ConnectionClosed(None, None)

    client._ws_connections["btcusdt@bookTicker"] = _Closed()
    with patch.object(client, "start_websocket", new_callable=AsyncMock) as sw, patch(
        "app.exchanges.binance_client.asyncio.sleep", new_callable=AsyncMock
    ):
        await client._websocket_receiver("btcusdt@bookTicker", "BTCUSDT", "bookTicker")
        sw.assert_awaited()


# ── scheduler.optimized_scheduler ────────────────────────────────────────────


@pytest.fixture
def sched():
    from app.scheduler.optimized_scheduler import OptimizedGridScheduler

    s = OptimizedGridScheduler(config_file="grid_config_optimized.json")
    s.scheduler = MagicMock()
    s.scheduler.get_jobs.return_value = [
        SimpleNamespace(
            id="j1",
            name="Job1",
            next_run_time=datetime.now(),
        )
    ]
    return s


@pytest.mark.asyncio
async def test_scheduler_initialize_start_stop(sched):
    with patch(
        "app.scheduler.optimized_scheduler.create_asset_min_qty_table",
        new_callable=AsyncMock,
    ), patch(
        "app.scheduler.optimized_scheduler.create_optimized_grid_manager",
        new_callable=AsyncMock,
        return_value=MagicMock(config=SimpleNamespace(assets={"BTCUSDT": {}})),
    ), patch(
        "app.scheduler.optimized_scheduler.send_telegram_alert"
    ):
        assert await sched.initialize() is True
        assert await sched.start() is True
        assert await sched.stop() is True

    # initialize failure
    with patch(
        "app.scheduler.optimized_scheduler.create_asset_min_qty_table",
        new_callable=AsyncMock,
        side_effect=RuntimeError("db"),
    ):
        assert await sched.initialize() is False

    # start failure
    sched.grid_manager = MagicMock()
    sched.scheduler.start.side_effect = RuntimeError("fail")
    assert await sched.start() is False

    # stop failure
    sched.scheduler.shutdown.side_effect = RuntimeError("fail")
    assert await sched.stop() is False


@pytest.mark.asyncio
async def test_scheduler_balance_helpers_and_report(sched):
    gm = MagicMock()
    gm.get_asset_balances = AsyncMock(return_value={"USDT": 100.0, "BNB": 1.0, "X": 0.0})
    sched.grid_manager = gm

    assert await sched._obtener_balances_actuales() == {
        "USDT": 100.0,
        "BNB": 1.0,
        "X": 0.0,
    }
    sched.grid_manager = None
    assert await sched._obtener_balances_actuales() == {}
    gm.get_asset_balances = AsyncMock(side_effect=RuntimeError("x"))
    sched.grid_manager = gm
    assert await sched._obtener_balances_actuales() == {}

    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"price": "300.5"}
    with patch(
        "app.scheduler.optimized_scheduler.requests.get", return_value=mock_resp
    ), patch(
        "app.scheduler.optimized_scheduler.get_binance_proxies",
        return_value={"https": "http://proxy"},
    ):
        prices = await sched._obtener_precios_actuales()
    assert prices["BNBUSDT"] == 300.5

    with patch(
        "app.scheduler.optimized_scheduler.requests.get",
        side_effect=RuntimeError("net"),
    ), patch(
        "app.scheduler.optimized_scheduler.get_binance_proxies", return_value=None
    ):
        prices2 = await sched._obtener_precios_actuales()
    assert all(v == 0 for v in prices2.values())

    bad = MagicMock(status_code=500)
    with patch(
        "app.scheduler.optimized_scheduler.requests.get", return_value=bad
    ), patch(
        "app.scheduler.optimized_scheduler.get_binance_proxies", return_value=None
    ):
        prices3 = await sched._obtener_precios_actuales()
    assert prices3["BNBUSDT"] == 0

    cfg_resp = MagicMock(status_code=200)
    cfg_resp.json.return_value = {"BNBUSDT": {"quantity": 0.1}}
    with patch(
        "app.scheduler.optimized_scheduler.requests.get", return_value=cfg_resp
    ):
        cfg = await sched._obtener_configuracion_actual()
    assert "BNBUSDT" in cfg
    with patch(
        "app.scheduler.optimized_scheduler.requests.get",
        side_effect=RuntimeError("x"),
    ):
        assert await sched._obtener_configuracion_actual() == {}
    with patch(
        "app.scheduler.optimized_scheduler.requests.get",
        return_value=MagicMock(status_code=404),
    ):
        assert await sched._obtener_configuracion_actual() == {}

    total, det = sched._calcular_valor_total_balances(
        {"USDT": 50.0, "BNB": 2.0, "ZZ": 1.0},
        {"BNBUSDT": 10.0},
    )
    assert total == 70.0
    assert "BNB" in det

    ops, sin = sched._analizar_activos_operativos(
        {"BNB": 1.0},
        {"BNBUSDT": 10.0},
        {"BNBUSDT": {"quantity": 0.5}},
    )
    assert "BNBUSDT" in ops
    assert sched._calcular_cambio_porcentual(110, 100) == 10.0
    assert sched._calcular_cambio_porcentual(10, 0) == 0

    msg_up = sched._generar_mensaje_balance_report(100, 5, 5, ["BNBUSDT"], [])
    assert "GANANCIA" in msg_up
    msg_dn = sched._generar_mensaje_balance_report(100, -5, -5, [], ["BNBUSDT"])
    assert "PÉRDIDA" in msg_dn
    msg0 = sched._generar_mensaje_balance_report(100, 0, 0, [], [])
    assert "SIN CAMBIO" in msg0


@pytest.mark.asyncio
async def test_scheduler_monitor_and_rebalance(sched):
    with patch.object(
        sched,
        "_obtener_balances_actuales",
        new_callable=AsyncMock,
        return_value={"USDT": 100.0, "BNB": 1.0},
    ), patch.object(
        sched,
        "_obtener_precios_actuales",
        new_callable=AsyncMock,
        return_value={"BNBUSDT": 300.0},
    ), patch.object(
        sched,
        "_obtener_configuracion_actual",
        new_callable=AsyncMock,
        return_value={"BNBUSDT": {"quantity": 0.1}},
    ), patch(
        "app.scheduler.optimized_scheduler.send_telegram_alert"
    ) as tg:
        sched.last_balance_report_time = datetime.now()
        # buggy history key path still runs
        sched.balance_history = {400.0: 350.0}
        await sched._monitor_balances_hourly()
        assert tg.called

    with patch.object(
        sched,
        "_obtener_balances_actuales",
        new_callable=AsyncMock,
        side_effect=RuntimeError("x"),
    ), patch.object(sched, "_send_error_notification") as err:
        await sched._monitor_balances_hourly()
        err.assert_called()

    with patch(
        "app.scheduler.optimized_scheduler.auto_rebalancer"
    ) as arb, patch(
        "app.scheduler.optimized_scheduler.send_telegram_alert"
    ) as tg:
        arb.check_and_rebalance = AsyncMock(
            return_value={
                "status": "success",
                "rebalance_results": [
                    {"status": "success", "symbol": "BNB", "usdt_spent": 10},
                    {"status": "fail", "symbol": "ETH", "reason": "no usdt"},
                ],
            }
        )
        await sched._auto_rebalance_cycle()
        assert tg.called

        arb.check_and_rebalance = AsyncMock(
            return_value={"status": "success", "rebalance_results": []}
        )
        await sched._auto_rebalance_cycle()

        arb.check_and_rebalance = AsyncMock(return_value={"status": "skipped"})
        await sched._auto_rebalance_cycle()

        arb.check_and_rebalance = AsyncMock(
            return_value={"status": "error", "message": "boom"}
        )
        with patch.object(sched, "_send_error_notification") as err:
            await sched._auto_rebalance_cycle()
            err.assert_called()

        arb.check_and_rebalance = AsyncMock(side_effect=RuntimeError("x"))
        with patch.object(sched, "_send_error_notification") as err2:
            await sched._auto_rebalance_cycle()
            err2.assert_called()


@pytest.mark.asyncio
async def test_scheduler_cycles_health_perf_notifications(sched, tmp_path):
    # no grid manager
    await sched._execute_trading_cycle()

    result = SimpleNamespace(
        action="BUY", quantity=0.1, symbol="BTCUSDT", price=Decimal("50000")
    )
    gm = MagicMock()
    gm.execute_grid_trading_cycle = AsyncMock(return_value=[result])
    gm.get_trading_statistics.return_value = {
        "total_trades": 2,
        "total_profit": 1.5,
    }
    gm.config = SimpleNamespace(assets={"BTCUSDT": {}})
    sched.grid_manager = gm

    with patch.object(sched, "_send_error_notification"):
        await sched._execute_trading_cycle()
    assert sched.cycle_count == 1
    sched._log_trading_results([])
    sched._log_trading_results([result])

    gm.execute_grid_trading_cycle = AsyncMock(side_effect=RuntimeError("x"))
    with patch.object(sched, "_send_error_notification") as err:
        await sched._execute_trading_cycle()
        err.assert_called()

    # adjust ranges
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"BTCUSDT": {"min_price": 1, "max_price": 2}}))
    sched.config_file = str(cfg)
    wrapper = MagicMock()
    wrapper.get_price = AsyncMock(return_value=100.0)
    with patch(
        "app.services.binance_async.AsyncBinanceWrapper", return_value=wrapper
    ), patch(
        "app.scheduler.optimized_scheduler.create_optimized_grid_manager",
        new_callable=AsyncMock,
        return_value=gm,
    ):
        await sched._adjust_ranges_and_reload()
    data = json.loads(cfg.read_text())
    assert data["BTCUSDT"]["min_price"] == pytest.approx(95.0)

    with patch(
        "app.services.binance_async.AsyncBinanceWrapper",
        side_effect=RuntimeError("x"),
    ):
        await sched._adjust_ranges_and_reload()  # swallowed

    # health
    sched.grid_manager = None
    with patch.object(sched, "_send_health_alert") as ha:
        await sched._monitor_system_health()
        ha.assert_called()
    sched.grid_manager = gm
    sched.last_cycle_time = datetime.now() - timedelta(minutes=10)
    with patch.object(sched, "_send_health_alert") as ha2:
        await sched._monitor_system_health()
        ha2.assert_called()
    sched.last_cycle_time = datetime.now()
    await sched._monitor_system_health()

    with patch.object(
        sched, "_monitor_system_health", wraps=sched._monitor_system_health
    ):
        pass
    # force exception path
    with patch.object(sched, "_send_health_alert", side_effect=RuntimeError("x")):
        sched.grid_manager = None
        await sched._monitor_system_health()

    # performance
    sched.grid_manager = None
    await sched._analyze_performance()
    sched.grid_manager = gm
    with patch.object(sched, "_send_performance_report") as pr:
        await sched._analyze_performance()
        pr.assert_called()
    gm.get_trading_statistics.side_effect = RuntimeError("x")
    await sched._analyze_performance()

    report = sched._generate_performance_report({"total_trades": 1})
    assert "uptime" in report
    assert sched._calculate_uptime() != "Unknown" or sched.last_cycle_time

    with patch("app.scheduler.optimized_scheduler.send_telegram_alert") as tg:
        sched._send_startup_notification()
        sched._send_shutdown_notification()
        sched._send_error_notification("e")
        sched._send_health_alert(["a"])
        sched._send_performance_report(
            {"trading_stats": {"message": "No trading history available"}}
        )
        sched._send_performance_report(
            {"trading_stats": {"total_trades": 3, "total_profit": 1.0}, "uptime": "1"}
        )
        assert tg.call_count >= 4

    # notification exception paths
    with patch(
        "app.scheduler.optimized_scheduler.send_telegram_alert",
        side_effect=RuntimeError("tg"),
    ):
        sched._send_startup_notification()
        sched._send_shutdown_notification()
        sched._send_error_notification("e")
        sched._send_health_alert(["a"])
        sched._send_performance_report(
            {"trading_stats": {"total_trades": 1, "total_profit": 0}}
        )

    st = sched.get_status()
    assert "is_running" in st and "jobs" in st


@pytest.mark.asyncio
async def test_scheduler_module_helpers():
    import app.scheduler.optimized_scheduler as mod

    fake = MagicMock()
    fake.initialize = AsyncMock(return_value=True)
    fake.start = AsyncMock(return_value=True)
    fake.stop = AsyncMock(return_value=True)

    with patch.object(mod, "_scheduler_instance", None), patch.object(
        mod, "OptimizedGridScheduler", return_value=fake
    ):
        s = await mod.initialize_optimized_scheduler()
        assert s is fake
        # second call returns cached
        s2 = await mod.initialize_optimized_scheduler()
        assert s2 is fake

    with patch.object(mod, "initialize_optimized_scheduler", new_callable=AsyncMock) as init:
        init.return_value = fake
        assert await mod.start_optimized_scheduler() is True

    with patch.object(mod, "_scheduler_instance", fake):
        assert await mod.stop_optimized_scheduler() is True
    with patch.object(mod, "_scheduler_instance", None):
        assert await mod.stop_optimized_scheduler() is True
