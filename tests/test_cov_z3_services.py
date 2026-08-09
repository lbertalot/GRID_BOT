"""S-COV-85 Z3 — services coverage (mocked Binance/Redis/DB). Paper-only."""

from __future__ import annotations

import asyncio
import json
import math
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest

pytestmark = pytest.mark.usefixtures("paper_env")


# ── adaptive_grid_engine ─────────────────────────────────────────────────────


def test_adaptive_grid_atr_estimate_and_regimes():
    from app.services import adaptive_grid_engine as mod

    db = MagicMock()
    # <5 prices → None
    db.query.return_value.filter.return_value.all.return_value = [
        SimpleNamespace(exit_price=100.0) for _ in range(3)
    ]
    assert mod._estimate_atr_from_trades(db, "btcusdt") is None

    prices = [100 + i * 0.5 for i in range(10)]
    db.query.return_value.filter.return_value.all.return_value = [
        SimpleNamespace(exit_price=p) for p in prices
    ]
    atr = mod._estimate_atr_from_trades(db, "BTCUSDT")
    assert atr is not None and atr > 0

    assert mod._detect_volatility_regime(10.0, 100.0) == "high"  # 0.10
    assert mod._detect_volatility_regime(1.0, 100.0) == "low"  # 0.01
    assert mod._detect_volatility_regime(4.0, 100.0) == "normal"
    assert mod._detect_volatility_regime(1.0, 0.0) == "low"


def test_adaptive_grid_compute_fallback_and_regimes():
    from app.services.adaptive_grid_engine import AdaptiveGridEngine

    eng = AdaptiveGridEngine()
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = []

    cfg = eng.compute_adaptive_config("BTCUSDT", 50000.0, db=db)
    assert cfg["regime"] == "unknown"
    assert cfg["min_price"] < 50000.0 < cfg["max_price"]
    assert 3 <= cfg["grids"] <= 15

    # high vol path
    prices = [50000 * (1 + 0.02 * ((-1) ** i)) for i in range(20)]
    db.query.return_value.filter.return_value.all.return_value = [
        SimpleNamespace(exit_price=p) for p in prices
    ]
    with patch(
        "app.services.adaptive_grid_engine._estimate_atr_from_trades",
        return_value=50000 * 0.08,
    ):
        cfg_h = eng.compute_adaptive_config("ETHUSDT", 3000.0, db=db)
    assert cfg_h["regime"] == "high"

    with patch(
        "app.services.adaptive_grid_engine._estimate_atr_from_trades",
        return_value=3000 * 0.01,
    ):
        cfg_l = eng.compute_adaptive_config("ETHUSDT", 3000.0, db=db)
    assert cfg_l["regime"] == "low"

    with patch(
        "app.services.adaptive_grid_engine._estimate_atr_from_trades",
        return_value=3000 * 0.04,
    ):
        cfg_n = eng.compute_adaptive_config("ETHUSDT", 3000.0, db=db)
    assert cfg_n["regime"] == "normal"

    # own SessionLocal path
    sess = MagicMock()
    with patch(
        "app.services.adaptive_grid_engine.SessionLocal", return_value=sess
    ), patch(
        "app.services.adaptive_grid_engine._estimate_atr_from_trades", return_value=None
    ):
        cfg2 = eng.compute_adaptive_config("BNBUSDT", 400.0, db=None)
    assert cfg2["symbol"] == "BNBUSDT"
    sess.close.assert_called_once()


def test_adaptive_grid_should_readjust_and_levels():
    from app.services.adaptive_grid_engine import AdaptiveGridEngine

    eng = AdaptiveGridEngine()
    assert eng.should_readjust("X", 100, 100, 100) is True  # range_size <= 0
    assert eng.should_readjust("X", 50, 90, 110) is True  # fuera
    assert eng.should_readjust("X", 120, 90, 110) is True
    assert eng.should_readjust("X", 95, 90, 110, threshold_pct=0.30) is True  # extremo
    assert eng.should_readjust("X", 100, 90, 110, threshold_pct=0.30) is False

    levels = eng.compute_grid_levels(100.0, 200.0, 5)
    assert len(levels) == 5
    assert levels[0] == 100.0
    assert levels[-1] == 200.0
    with pytest.raises(ValueError):
        eng.compute_grid_levels(1.0, 2.0, 1)


# ── asset_limit_updater ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_asset_limit_updater_missing_env(monkeypatch):
    from app.services import asset_limit_updater as mod

    for k in (
        "BINANCE_API_KEY",
        "BINANCE_SECRET_KEY",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
    ):
        monkeypatch.delenv(k, raising=False)
    with patch.object(mod, "load_dotenv"):
        await mod.update_asset_limits_in_db()


@pytest.mark.asyncio
async def test_asset_limit_updater_happy_and_skip_and_error(monkeypatch):
    from app.services import asset_limit_updater as mod

    monkeypatch.setenv("BINANCE_API_KEY", "k")
    monkeypatch.setenv("BINANCE_SECRET_KEY", "s")
    monkeypatch.setenv("POSTGRES_USER", "u")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p")
    monkeypatch.setenv("POSTGRES_DB", "d")
    monkeypatch.setenv("POSTGRES_HOST", "localhost")

    good = {
        "symbol": "BTCUSDT",
        "filters": [
            {
                "filterType": "PRICE_FILTER",
                "minPrice": "0.01",
                "maxPrice": "1e6",
                "tickSize": "0.01",
            },
            {
                "filterType": "LOT_SIZE",
                "minQty": "0.001",
                "maxQty": "1000",
                "stepSize": "0.001",
            },
            {"filterType": "MIN_NOTIONAL", "minNotional": "10"},
        ],
    }
    notional_alt = {
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
                "minQty": "0.001",
                "maxQty": "1000",
                "stepSize": "0.001",
            },
            {"filterType": "NOTIONAL", "notional": "5"},
        ],
    }
    incomplete = {"symbol": "BADUSDT", "filters": []}

    client = MagicMock()
    client.get_exchange_info.return_value = {
        "symbols": [good, notional_alt, incomplete]
    }
    conn = MagicMock()
    conn.execute = AsyncMock()
    conn.close = AsyncMock()

    with (
        patch.object(mod, "load_dotenv"),
        patch.object(mod, "Client", return_value=client),
        patch.object(mod.asyncpg, "connect", AsyncMock(return_value=conn)),
    ):
        await mod.update_asset_limits_in_db()
    assert conn.execute.await_count == 2
    conn.close.assert_awaited()

    # exception path
    with (
        patch.object(mod, "load_dotenv"),
        patch.object(mod, "Client", side_effect=RuntimeError("boom")),
    ):
        await mod.update_asset_limits_in_db()


# ── balance_updater ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_balance_updater_missing_keys_and_errors(monkeypatch):
    from app.services import balance_updater as mod

    monkeypatch.delenv("BINANCE_API_KEY", raising=False)
    monkeypatch.delenv("BINANCE_SECRET_KEY", raising=False)
    with patch.object(mod, "load_dotenv"):
        out = await mod.update_balances_in_db()
    assert out["errors"] == 1

    monkeypatch.setenv("BINANCE_API_KEY", "k")
    monkeypatch.setenv("BINANCE_SECRET_KEY", "s")
    with (
        patch.object(mod, "load_dotenv"),
        patch.object(mod.asyncio, "to_thread", AsyncMock(side_effect=RuntimeError("x"))),
    ):
        out = await mod.update_balances_in_db()
    assert out["errors"] == 1

    with (
        patch.object(mod, "load_dotenv"),
        patch.object(
            mod.asyncio,
            "to_thread",
            AsyncMock(side_effect=[None, {"updated": 0, "skipped": 0, "errors": 1}]),
        ),
    ):
        out = await mod.update_balances_in_db()
    assert out["errors"] == 1


@pytest.mark.asyncio
async def test_balance_updater_persist_and_get(monkeypatch):
    from app.services import balance_updater as mod

    monkeypatch.setenv("BINANCE_API_KEY", "k")
    monkeypatch.setenv("BINANCE_SECRET_KEY", "s")

    client_mock = MagicMock()
    client_mock.get_account.return_value = {
        "balances": [
            {"asset": "USDT", "free": "10", "locked": "0"},
            {"asset": "BTC", "free": "0", "locked": "0"},
            {"asset": "ETH", "free": "1", "locked": "0"},
        ]
    }
    with patch.object(mod, "Client", return_value=client_mock):
        bals = mod._get_binance_balances("k", "s")
    assert len(bals) == 3

    db = MagicMock()
    with (
        patch.object(mod, "SessionLocal", return_value=db),
        patch.object(mod.BalanceService, "upsert_from_exchange") as upsert,
    ):
        upsert.side_effect = [None, RuntimeError("upsert fail")]
        # first non-zero USDT ok, ETH fails → errors
        result = mod._persist_balances(
            [
                {"asset": "USDT", "free": "10", "locked": "0"},
                {"asset": "BTC", "free": "0", "locked": "0"},
                {"asset": "ETH", "free": "1", "locked": "0"},
            ]
        )
    assert result["updated"] == 1
    assert result["skipped"] == 1
    assert result["errors"] == 1
    db.commit.assert_called_once()
    db.close.assert_called_once()

    # critical rollback path
    db2 = MagicMock()
    db2.commit.side_effect = RuntimeError("commit boom")
    with (
        patch.object(mod, "SessionLocal", return_value=db2),
        patch.object(mod.BalanceService, "upsert_from_exchange"),
    ):
        result = mod._persist_balances(
            [{"asset": "USDT", "free": "1", "locked": "0"}]
        )
    assert result["errors"] >= 1
    db2.rollback.assert_called()

    with (
        patch.object(mod, "load_dotenv"),
        patch.object(
            mod.asyncio,
            "to_thread",
            AsyncMock(
                side_effect=[
                    [{"asset": "USDT", "free": "5", "locked": "0"}],
                    {"updated": 1, "skipped": 0, "errors": 0},
                ]
            ),
        ),
    ):
        out = await mod.update_balances_in_db()
    assert out["updated"] == 1


# ── binance_trades_pnl ───────────────────────────────────────────────────────


def test_binance_trades_pnl_helpers_and_fifo():
    from app.services import binance_trades_pnl as mod

    assert mod._get_quote_asset("BTCUSDT") == "USDT"
    assert mod._get_quote_asset("ETHBTC") == "BTC"
    assert mod._get_quote_asset("FOO") == "USDT"

    assert mod._convert_to_usdt(0, "BNB") == 0.0
    assert mod._convert_to_usdt(5, "USDT") == 5.0
    singleton = MagicMock()
    singleton.get_symbol_price.return_value = 100.0
    with patch.object(mod, "get_binance_client_singleton", return_value=singleton):
        assert mod._convert_to_usdt(2, "BNB") == 200.0
    singleton.get_symbol_price.side_effect = RuntimeError("px")
    with patch.object(mod, "get_binance_client_singleton", return_value=singleton):
        assert mod._convert_to_usdt(2, "BNB") == 0.0

    assert mod._commission_usdt(0, "USDT", "BTCUSDT", "BUY") == 0.0
    assert mod._commission_usdt(1.5, "USDT", "BTCUSDT", "BUY") == 1.5
    with patch.object(mod, "_convert_to_usdt", return_value=3.0):
        assert mod._commission_usdt(1, "BNB", "BTCUSDT", "SELL") == 3.0

    trades = [
        {
            "time": 2,
            "qty": 1.0,
            "price": 110.0,
            "isBuyer": False,
            "commission": 0.1,
            "commissionAsset": "USDT",
        },
        {
            "time": 1,
            "qty": 2.0,
            "price": 100.0,
            "isBuyer": True,
            "commission": 0.0,
            "commissionAsset": "USDT",
        },
        {
            "time": 3,
            "qty": 0.5,
            "price": 120.0,
            "isBuyer": False,
            "commission": 0.01,
            "commissionAsset": "BNB",
        },
    ]
    with patch.object(mod, "_convert_to_usdt", return_value=0.5):
        profit, invested = mod._fifo_realized_pnl_usdt(trades, "BTCUSDT")
    assert invested > 0
    assert isinstance(profit, float)


def test_compute_binance_pnl_circuit_breaker(monkeypatch):
    from app.services import binance_trades_pnl as mod
    from binance.exceptions import BinanceAPIException

    # reset module globals
    mod._2015_error_count = 0
    mod._2015_circuit_open_until = 0.0
    mod._last_2015_error_ts = 0.0

    singleton = MagicMock()
    singleton.client = None
    with patch.object(mod, "get_binance_client_singleton", return_value=singleton):
        assert mod.compute_binance_pnl_and_roi(["BTCUSDT"]) == (0.0, 0.0, 0.0)

    client = MagicMock()
    singleton.client = client
    client.get_my_trades.return_value = [
        {
            "time": 1,
            "qty": 1,
            "price": 100,
            "isBuyer": True,
            "commission": 0,
            "commissionAsset": "USDT",
        },
        {
            "time": 2,
            "qty": 1,
            "price": 110,
            "isBuyer": False,
            "commission": 0,
            "commissionAsset": "USDT",
        },
    ]
    with patch.object(mod, "get_binance_client_singleton", return_value=singleton):
        p, inv, roi = mod.compute_binance_pnl_and_roi(["BTCUSDT"])
    assert inv > 0 and roi != 0.0

    # circuit already open
    mod._2015_circuit_open_until = 1e12
    with patch.object(mod, "get_binance_client_singleton", return_value=singleton):
        assert mod.compute_binance_pnl_and_roi(["BTCUSDT"]) == (0.0, 0.0, 0.0)
    mod._2015_circuit_open_until = 0.0

    # -2015 errors → breaker
    mod._2015_error_count = 0
    exc = BinanceAPIException(400, "Invalid API-key, IP", code=-2015)

    def _raise(*a, **k):
        raise exc

    client.get_my_trades.side_effect = _raise
    with (
        patch.object(mod, "get_binance_client_singleton", return_value=singleton),
        patch(
            "app.services.binance_client_singleton._notify_invalid_ip",
            create=True,
            side_effect=RuntimeError("notify fail"),
        ),
    ):
        for _ in range(3):
            mod.compute_binance_pnl_and_roi(["BTCUSDT", "ETHUSDT"])
    assert mod._2015_circuit_open_until > 0
    mod._2015_circuit_open_until = 0.0
    mod._2015_error_count = 0

    # other API error + generic
    other = BinanceAPIException(400, "other", code=-1000)
    client.get_my_trades.side_effect = [other, RuntimeError("x")]
    with patch.object(mod, "get_binance_client_singleton", return_value=singleton):
        mod.compute_binance_pnl_and_roi(["AAA", "BBB"])

    # reset counter path (no 2015, old timestamp)
    mod._2015_error_count = 2
    mod._last_2015_error_ts = 0.0
    client.get_my_trades.side_effect = None
    client.get_my_trades.return_value = []
    with patch.object(mod, "get_binance_client_singleton", return_value=singleton):
        mod.compute_binance_pnl_and_roi(["BTCUSDT"])
    assert mod._2015_error_count == 0


# ── metrics_updater ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_metrics_updater_start_stop_and_update():
    from app.services import metrics_updater as mod

    updater = mod.MetricsUpdater()
    updater.update_interval = 0

    loops = 0

    async def _upd():
        nonlocal loops
        loops += 1
        if loops == 1:
            raise RuntimeError("once")
        updater.is_running = False

    with (
        patch.object(updater, "update_metrics", side_effect=_upd),
        patch.object(mod.asyncio, "sleep", AsyncMock()),
    ):
        await updater.start()
    assert loops >= 2

    await updater.stop()
    assert updater.is_running is False

    singleton = MagicMock()
    singleton.get_account_info.return_value = {
        "balances": [
            {"asset": "USDT", "free": "100", "locked": "0"},
            {"asset": "BTC", "free": "0.1", "locked": "0"},
            {"asset": "ETH", "free": "0", "locked": "0"},
            {"asset": "SPK", "free": "10", "locked": "0"},
            {"asset": "DOGE", "free": "1", "locked": "0"},
        ]
    }
    singleton.get_symbol_price.side_effect = lambda s: {
        "BTCUSDT": 50000.0,
        "ETHUSDT": 3000.0,
        "SPKUSDT": 1.0,
    }.get(s, (_ for _ in ()).throw(RuntimeError("no px")))

    with (
        patch(
            "app.services.binance_client_singleton.binance_client_singleton",
            singleton,
        ),
        patch.object(mod.trading_metrics, "update_profit_metrics"),
        patch.object(mod.trading_metrics, "update_bot_status"),
        patch.object(mod.trading_metrics, "update_balances"),
    ):
        await updater.update_metrics()

    singleton.get_account_info.side_effect = RuntimeError("no acct")
    with patch(
        "app.services.binance_client_singleton.binance_client_singleton",
        singleton,
    ):
        await updater.update_metrics()

    # outer exception
    with patch(
        "app.services.binance_client_singleton.binance_client_singleton",
        side_effect=RuntimeError("import fail"),
    ):
        # force failure after import by breaking trading_metrics
        with patch.object(
            mod,
            "trading_metrics",
            MagicMock(
                update_profit_metrics=MagicMock(side_effect=RuntimeError("m")),
            ),
        ):
            # get_account succeeds then update fails — craft via monkeypatch of import path
            pass

    # start/stop helpers
    with (
        patch.object(mod.metrics_updater, "start", AsyncMock()) as st,
        patch.object(mod.metrics_updater, "stop", AsyncMock()) as sp,
    ):
        await mod.start_metrics_updater()
        await mod.stop_metrics_updater()
    st.assert_awaited()
    sp.assert_awaited()


# ── min_qty_updater ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_min_qty_create_table_and_updates(tmp_path, monkeypatch):
    from app.services import min_qty_updater as mod

    monkeypatch.setenv("POSTGRES_USER", "u")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p")
    monkeypatch.setenv("POSTGRES_DB", "d")
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("BINANCE_API_KEY", "k")
    monkeypatch.setenv("BINANCE_SECRET_KEY", "s")

    conn = MagicMock()
    conn.execute = AsyncMock()
    conn.close = AsyncMock()
    conn.fetchrow = AsyncMock(
        side_effect=[
            {"min_notional": 10.0, "step_size": 0.001},
            None,
            {"min_notional": 10.0, "step_size": 0.001},
        ]
    )
    with patch.object(mod.asyncpg, "connect", AsyncMock(return_value=conn)):
        await mod.create_asset_min_qty_table()
    conn.execute.assert_awaited()
    conn.close.assert_awaited()

    cfg = {
        "_meta": {},
        "BTCUSDT": {"quantity": 0.001},
        "ETHUSDT": {"quantity": 0.01},
        "BADUSDT": {"quantity": 1},
    }
    cfg_path = tmp_path / "grid_config_optimized.json"
    cfg_path.write_text(json.dumps(cfg))
    monkeypatch.setattr(mod, "CONFIG_FILE", str(cfg_path))
    monkeypatch.setattr(mod, "PROJECT_ROOT", str(tmp_path))

    client = MagicMock()
    client.get_symbol_ticker.side_effect = [
        {"price": "50000"},
        RuntimeError("ticker fail"),
        {"price": "3000"},
    ]

    # missing env early return
    monkeypatch.delenv("BINANCE_API_KEY", raising=False)
    with patch.object(mod, "load_dotenv"):
        await mod.update_min_qty_in_db()
        await mod.update_min_qty_in_db_and_config()

    monkeypatch.setenv("BINANCE_API_KEY", "k")
    conn2 = MagicMock()
    conn2.execute = AsyncMock()
    conn2.close = AsyncMock()
    conn2.fetchrow = AsyncMock(
        side_effect=[
            {"min_notional": 10.0, "step_size": 0.001},
            None,  # ETH skip row
            {"min_notional": 10.0, "step_size": 0.001},  # unused if BAD skipped by ticker
        ]
    )
    # rebuild config keys order: BTC, ETH, BAD — ticker: ok, skip via None row, ticker fail
    # Actually loop: BTCUSDT row+ticker, ETHUSDT no row, BADUSDT ticker exception
    client.get_symbol_ticker.side_effect = [
        {"price": "50000"},
        RuntimeError("no"),
    ]
    conn2.fetchrow = AsyncMock(
        side_effect=[
            {"min_notional": 10.0, "step_size": 0.001},
            None,
            {"min_notional": 10.0, "step_size": 0.001},
        ]
    )

    with (
        patch.object(mod, "load_dotenv"),
        patch.object(mod, "Client", return_value=client),
        patch.object(mod.asyncpg, "connect", AsyncMock(return_value=conn2)),
    ):
        await mod.update_min_qty_in_db()

    # and_config writes file
    client2 = MagicMock()
    client2.get_symbol_ticker.return_value = {"price": "50000"}
    conn3 = MagicMock()
    conn3.execute = AsyncMock()
    conn3.close = AsyncMock()
    conn3.fetchrow = AsyncMock(
        return_value={"min_notional": 10.0, "step_size": 0.001}
    )
    cfg2 = {"_x": {}, "BTCUSDT": {"quantity": 0.001}}
    cfg_path.write_text(json.dumps(cfg2))
    with (
        patch.object(mod, "load_dotenv"),
        patch.object(mod, "Client", return_value=client2),
        patch.object(mod.asyncpg, "connect", AsyncMock(return_value=conn3)),
    ):
        await mod.update_min_qty_in_db_and_config()
    updated = json.loads(cfg_path.read_text())
    assert "quantity" in updated["BTCUSDT"]
    assert updated["BTCUSDT"]["quantity"] > 0


# ── user_stream_handler ──────────────────────────────────────────────────────


def test_map_execution_report_statuses():
    from app.services.user_stream_handler import map_execution_report_to_status
    from app.core.operation_tracker import OperationStatus

    assert map_execution_report_to_status({"X": "NEW"}) == OperationStatus.ACCEPTED
    assert (
        map_execution_report_to_status({"X": "PARTIALLY_FILLED"})
        == OperationStatus.PARTIALLY_FILLED
    )
    assert map_execution_report_to_status({"X": "FILLED"}) == OperationStatus.COMPLETED
    assert map_execution_report_to_status({"X": "CANCELED"}) == OperationStatus.CANCELLED
    assert map_execution_report_to_status({"X": "EXPIRED"}) == OperationStatus.EXPIRED
    assert map_execution_report_to_status({"X": "REJECTED"}) == OperationStatus.FAILED
    assert map_execution_report_to_status({"X": "OTHER"}) is None


@pytest.mark.asyncio
async def test_start_user_stream_and_track():
    from app.services import user_stream_handler as mod

    started = {}

    class FakeStream:
        def __init__(self, api_key):
            self.api_key = api_key

        async def start(self, on_fill=None):
            started["cb"] = on_fill
            # invoke callback paths
            on_fill({"c": None, "X": "FILLED"})  # no client id
            on_fill({"c": "oid-1", "X": "UNKNOWN"})  # no status
            on_fill(
                {
                    "c": "oid-2",
                    "X": "FILLED",
                    "L": "100.5",
                    "l": "0.01",
                }
            )
            on_fill({"c": "bad"})  # triggers exception path via missing status ok
            # force exception inside try
            with patch.object(
                mod, "map_execution_report_to_status", side_effect=RuntimeError("x")
            ):
                on_fill({"c": "oid-3", "X": "FILLED"})

    tracker = MagicMock()
    tracker.update_operation_status = AsyncMock()

    with (
        patch.object(mod, "BinanceUserStreamHandler", FakeStream),
        patch.object(mod, "OperationTracker", return_value=tracker),
        patch.object(mod.asyncio, "create_task", lambda coro: asyncio.ensure_future(coro)),
    ):
        await mod.start_user_stream_and_track("key")
        await asyncio.sleep(0)  # flush create_task
    assert "cb" in started


# ── strategy_factory ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_strategy_factory_lifecycle():
    from app.services.strategy_factory import StrategyFactory
    from app.strategies.base import StrategyType, TradingResult

    factory = StrategyFactory()

    assert factory.create_strategy(StrategyType.GRID, MagicMock()) is None
    assert factory.create_config(StrategyType.GRID, symbol="X") is None

    from app.strategies.dca_strategy import DCAConfig

    # setdefault(strategy_type) permite construir DCAConfig sin chocar el kwarg
    cfg = factory.create_config(
        StrategyType.DCA, symbol="BTCUSDT", investment_amount=50.0
    )
    assert cfg is not None and cfg.symbol == "BTCUSDT"
    strat = factory.create_strategy(StrategyType.DCA, cfg)
    assert strat is not None

    # create_config exception
    with patch.dict(factory.config_classes, {StrategyType.DCA: MagicMock(side_effect=ValueError("bad"))}):
        assert factory.create_config(StrategyType.DCA, symbol="X") is None

    with patch.dict(
        factory.strategy_classes,
        {StrategyType.DCA: MagicMock(side_effect=RuntimeError("boom"))},
    ):
        assert factory.create_strategy(StrategyType.DCA, cfg) is None

    # Fake config with .value for notifications (Pydantic may store enum as str)
    cfg_ns = SimpleNamespace(
        symbol="BTCUSDT",
        strategy_type=SimpleNamespace(value="dca"),
    )
    strategy = MagicMock()
    strategy.config = cfg_ns
    strategy.validate_config = AsyncMock(return_value=False)
    assert await factory.start_strategy("s1", strategy) is False

    strategy.validate_config = AsyncMock(return_value=True)
    strategy.start = AsyncMock(return_value=False)
    assert await factory.start_strategy("s1", strategy) is False

    strategy.start = AsyncMock(return_value=True)
    with patch.object(factory, "_send_strategy_notification", AsyncMock()):
        assert await factory.start_strategy("s1", strategy) is True
    assert "s1" in factory.active_strategies

    # start exception
    strategy2 = MagicMock()
    strategy2.validate_config = AsyncMock(side_effect=RuntimeError("x"))
    assert await factory.start_strategy("s2", strategy2) is False

    assert await factory.stop_strategy("missing") is False
    strategy.stop = AsyncMock(return_value=False)
    assert await factory.stop_strategy("s1") is False
    strategy.stop = AsyncMock(return_value=True)
    metrics = MagicMock()
    metrics.dict.return_value = {"ok": 1}
    strategy.get_metrics.return_value = metrics
    with patch.object(factory, "_send_strategy_notification", AsyncMock()):
        # re-register
        factory.active_strategies["s1"] = strategy
        factory.strategy_metrics["s1"] = {"executions": 0, "total_profit": 0.0}
        assert await factory.stop_strategy("s1") is True

    factory.active_strategies["s1"] = strategy
    strategy.stop = AsyncMock(side_effect=RuntimeError("stop"))
    assert await factory.stop_strategy("s1") is False

    # execute
    assert await factory.execute_strategy("nope") is None
    factory.active_strategies["s1"] = strategy
    factory.strategy_metrics["s1"] = {
        "executions": 0,
        "total_profit": 0.0,
        "last_execution": None,
    }
    result = TradingResult(
        orders=[], strategy_type=StrategyType.DCA, total_profit=1.5, success=True
    )
    strategy.execute = AsyncMock(return_value=result)
    strategy.update_metrics = AsyncMock()
    out = await factory.execute_strategy("s1")
    assert out.success and factory.strategy_metrics["s1"]["executions"] == 1

    strategy.execute = AsyncMock(side_effect=RuntimeError("exec"))
    assert await factory.execute_strategy("s1") is None

    factory.active_strategies["s1"] = strategy
    strategy.execute = AsyncMock(return_value=result)
    strategy.update_metrics = AsyncMock()
    all_res = await factory.execute_all_strategies()
    assert "s1" in all_res

    # execute_all with exception inside loop (execute_strategy swallows — force raise on result assign)
    factory.active_strategies["sx"] = strategy
    with patch.object(factory, "execute_strategy", AsyncMock(side_effect=RuntimeError("x"))):
        await factory.execute_all_strategies()

    strategy.get_status = AsyncMock(return_value={"state": "ok"})
    factory.active_strategies["s1"] = strategy
    factory.strategy_metrics["s1"] = {"executions": 1}
    st = await factory.get_strategy_status("s1")
    assert st["factory_metrics"]["executions"] == 1
    assert await factory.get_strategy_status("missing") is None
    strategy.get_status = AsyncMock(side_effect=RuntimeError("st"))
    assert await factory.get_strategy_status("s1") is None

    strategy.get_status = AsyncMock(return_value={"state": "ok"})
    statuses = await factory.get_all_strategies_status()
    assert "s1" in statuses

    avail = factory.get_available_strategies()
    assert any(a["type"] == "dca" for a in avail)
    assert "Dollar Cost" in factory._get_strategy_description(StrategyType.DCA)
    assert factory._get_strategy_description(StrategyType.GRID)
    # unknown enum-like
    assert "no disponible" in factory._get_strategy_description(MagicMock())

    fields = factory._get_config_fields(DCAConfig)
    assert isinstance(fields, list)
    # exception path in _get_config_fields
    assert factory._get_config_fields(MagicMock(side_effect=RuntimeError("x"))) == []

    with patch(
        "app.services.strategy_factory.send_telegram_alert", side_effect=RuntimeError("tg")
    ):
        await factory._send_strategy_notification("hi")
    with patch("app.services.strategy_factory.send_telegram_alert") as tg:
        await factory._send_strategy_notification("ok")
        tg.assert_called_once()

    factory.active_strategies.clear()
    factory.strategy_metrics.clear()
    factory.active_strategies["s1"] = strategy
    factory.strategy_metrics["s1"] = {"total_profit": 2.0, "executions": 3}
    summary = factory.get_strategy_summary()
    assert summary["active_strategies"] == 1
    assert summary["total_profit"] == 2.0


# ── auto_rebalancer (deprecated v1) ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_auto_rebalancer_full_paths(tmp_path, monkeypatch):
    from app.services import auto_rebalancer as mod

    client = MagicMock()
    client.get_account.return_value = {
        "balances": [
            {"asset": "USDT", "free": "100", "locked": "0"},
            {"asset": "BTC", "free": "0.001", "locked": "0"},
            {"asset": "ETH", "free": "0", "locked": "0"},
        ]
    }
    client.get_symbol_ticker.return_value = {"price": "50000"}
    client.get_symbol_info.return_value = {
        "filters": [{"filterType": "MIN_NOTIONAL", "minNotional": "10"}]
    }
    client.create_order.return_value = {
        "orderId": 1,
        "status": "FILLED",
    }

    with patch(
        "app.services.binance_client_singleton.get_binance_client_singleton",
        return_value=MagicMock(client=client),
    ):
        rb = mod.AutoRebalancer()
    rb.binance_client = client
    rb.paper_trading = True

    # already rebalancing
    rb.is_rebalancing = True
    assert (await rb.check_and_rebalance())["status"] == "skipped"
    rb.is_rebalancing = False

    bals = await rb.get_current_balances()
    assert bals["USDT"] == 100.0
    client.get_account.side_effect = RuntimeError("acct")
    assert await rb.get_current_balances() == {}
    client.get_account.side_effect = None
    client.get_account.return_value = {
        "balances": [
            {"asset": "USDT", "free": "100", "locked": "0"},
            {"asset": "BTC", "free": "0.001", "locked": "0"},
        ]
    }

    cfg_file = tmp_path / "grid_config_optimized.json"
    cfg_file.write_text(
        json.dumps(
            {
                "_meta": {},
                "system_config": {},
                "BTCUSDT": {
                    "symbol": "BTCUSDT",
                    "min_price": 40000,
                    "max_price": 60000,
                    "grids": 5,
                    "quantity": 0.01,
                    "is_active": True,
                },
                "ETHUSDT": {
                    "symbol": "ETHUSDT",
                    "min_price": 1,
                    "max_price": 2,
                    "grids": 3,
                    "quantity": 1,
                    "is_active": False,
                },
                "BAD": {"symbol": "BAD"},
                "NOT_DICT": "x",
            }
        )
    )
    monkeypatch.chdir(tmp_path)
    gcfg = await rb.get_grid_config()
    assert "BTCUSDT" in gcfg
    assert "ETHUSDT" in gcfg
    assert gcfg["ETHUSDT"].is_active is False

    # broken config file
    (tmp_path / "grid_config_optimized.json").write_text("{bad")
    assert await rb.get_grid_config() == {}
    cfg_file.write_text(
        json.dumps(
            {
                "BTCUSDT": {
                    "symbol": "BTCUSDT",
                    "min_price": 1,
                    "max_price": 2,
                    "grids": 3,
                    "quantity": 0.01,
                    "is_active": True,
                },
                "FAILUSDT": {
                    "symbol": "FAILUSDT",
                    "min_price": 1,
                    "max_price": 2,
                    "grids": 3,
                    "quantity": 1,
                    "is_active": True,
                },
            }
        )
    )
    gcfg = await rb.get_grid_config()

    def ticker_side(symbol):
        if symbol == "FAILUSDT":
            raise RuntimeError("ticker")
        return {"price": "50000"}

    client.get_symbol_ticker.side_effect = ticker_side
    # inactive symbol skipped (line 191)
    inactive = SimpleNamespace(
        is_active=False, quantity=1.0, symbol="ETHUSDT"
    )
    gcfg_with_inactive = {**gcfg, "ETHUSDT": inactive}
    needs = await rb.analyze_rebalance_needs(
        {"USDT": 100, "BTC": 0.0}, gcfg_with_inactive
    )
    assert any(n["symbol"] == "BTCUSDT" for n in needs)
    assert not any(n["symbol"] == "ETHUSDT" for n in needs)

    # execute: insufficient usdt + success + error
    with patch.object(rb, "get_usdt_balance", AsyncMock(return_value=1.0)):
        res = await rb.execute_rebalance(
            [
                {
                    "symbol": "BTCUSDT",
                    "base_asset": "BTC",
                    "needed_quantity": 1,
                    "needed_usdt": 50,
                }
            ]
        )
    assert res[0]["status"] == "failed"

    with (
        patch.object(rb, "get_usdt_balance", AsyncMock(return_value=1000.0)),
        patch.object(
            rb, "execute_buy_order", AsyncMock(return_value={"order_id": 1})
        ),
    ):
        res = await rb.execute_rebalance(
            [
                {
                    "symbol": "BTCUSDT",
                    "base_asset": "BTC",
                    "needed_quantity": 0.01,
                    "needed_usdt": 50,
                }
            ]
        )
    assert res[0]["status"] == "success"

    with (
        patch.object(rb, "get_usdt_balance", AsyncMock(return_value=1000.0)),
        patch.object(rb, "execute_buy_order", AsyncMock(side_effect=RuntimeError("buy"))),
    ):
        res = await rb.execute_rebalance(
            [
                {
                    "symbol": "BTCUSDT",
                    "base_asset": "BTC",
                    "needed_quantity": 0.01,
                    "needed_usdt": 50,
                }
            ]
        )
    assert res[0]["status"] == "error"

    assert await rb.get_usdt_balance() == 100.0
    with patch.object(rb, "get_current_balances", AsyncMock(side_effect=RuntimeError("x"))):
        assert await rb.get_usdt_balance() == 0.0

    # _save_trade_to_db ok + error
    db = MagicMock()
    with patch.object(mod, "SessionLocal", return_value=db), patch.object(
        mod, "Trade", return_value=MagicMock()
    ):
        rb._save_trade_to_db("BTCUSDT", "BUY", 0.01, 50000.0, "1")
    db.commit.assert_called()

    db_bad = MagicMock()
    db_bad.commit.side_effect = RuntimeError("db")
    with patch.object(mod, "SessionLocal", return_value=db_bad), patch.object(
        mod, "Trade", return_value=MagicMock()
    ):
        rb._save_trade_to_db("BTCUSDT", "BUY", 0.01, 50000.0, "1")

    # execute_buy_order success (guard patched) + fail
    client.get_symbol_ticker.side_effect = None
    client.get_symbol_ticker.return_value = {"price": "50000"}
    with (
        patch("app.core.order_execution_guard.assert_real_order_allowed", return_value={}),
        patch.object(rb, "_save_trade_to_db"),
    ):
        out = await rb.execute_buy_order("BTCUSDT", 0.01)
    assert out["status"] == "FILLED"

    with patch(
        "app.core.order_execution_guard.assert_real_order_allowed",
        side_effect=RuntimeError("blocked"),
    ):
        with pytest.raises(RuntimeError):
            await rb.execute_buy_order("BTCUSDT", 0.01)

    # check_and_rebalance paths
    with (
        patch.object(rb, "get_current_balances", AsyncMock(return_value={"USDT": 100})),
        patch.object(rb, "get_grid_config", AsyncMock(return_value={})),
        patch.object(rb, "analyze_rebalance_needs", AsyncMock(return_value=[])),
    ):
        assert (await rb.check_and_rebalance())["status"] == "success"

    with (
        patch.object(rb, "get_current_balances", AsyncMock(return_value={"USDT": 100})),
        patch.object(rb, "get_grid_config", AsyncMock(return_value=gcfg)),
        patch.object(
            rb,
            "analyze_rebalance_needs",
            AsyncMock(return_value=[{"symbol": "BTCUSDT", "needed_usdt": 1}]),
        ),
        patch.object(rb, "execute_rebalance", AsyncMock(return_value=[{"ok": 1}])),
    ):
        out = await rb.check_and_rebalance()
    assert out["status"] == "success" and "rebalance_results" in out

    with patch.object(
        rb, "get_current_balances", AsyncMock(side_effect=RuntimeError("boom"))
    ):
        assert (await rb.check_and_rebalance())["status"] == "error"

    with (
        patch.object(rb, "get_current_balances", AsyncMock(return_value={"USDT": 100})),
        patch.object(rb, "get_grid_config", AsyncMock(return_value=gcfg)),
        patch.object(
            rb,
            "analyze_rebalance_needs",
            AsyncMock(return_value=[{"needed_usdt": 10}]),
        ),
        patch.object(rb, "get_usdt_balance", AsyncMock(return_value=50)),
    ):
        st = await rb.get_rebalance_status()
    assert st["can_rebalance"] is True

    with patch.object(
        rb, "get_current_balances", AsyncMock(side_effect=RuntimeError("e"))
    ):
        st = await rb.get_rebalance_status()
    assert "error" in st

    with (
        patch.object(rb, "get_usdt_balance", AsyncMock(return_value=1.0)),
    ):
        assert (await rb.manual_rebalance("BTCUSDT", 50))["status"] == "error"

    with (
        patch.object(rb, "get_usdt_balance", AsyncMock(return_value=100.0)),
        patch.object(rb, "execute_buy_order", AsyncMock(return_value={"order_id": 9})),
    ):
        assert (await rb.manual_rebalance("BTCUSDT", 50))["status"] == "success"

    with (
        patch.object(rb, "get_usdt_balance", AsyncMock(return_value=100.0)),
        patch.object(rb, "execute_buy_order", AsyncMock(side_effect=RuntimeError("x"))),
    ):
        assert (await rb.manual_rebalance("BTCUSDT", 50))["status"] == "error"


# ── metrics_service ──────────────────────────────────────────────────────────


def _async_cache():
    cache = MagicMock()
    store = {}

    async def get(k):
        return store.get(k)

    async def set(k, v, ttl_seconds=0):
        store[k] = v

    cache.get = get
    cache.set = set
    cache._store = store
    return cache


@pytest.mark.asyncio
async def test_metrics_service_portfolio_and_helpers():
    from app.services.metrics_service import MetricsService

    cache = _async_cache()
    with patch("app.services.metrics_service.get_async_cache", return_value=cache):
        svc = MetricsService()
    svc._cache = cache

    singleton = MagicMock()
    singleton.get_balances.side_effect = [
        RuntimeError("r1"),
        RuntimeError("r2"),
        {"USDT": 100.0, "BTC": 0.01, "ETH": 0.0, "LDUSDT": 5.0, "FOO": 1.0},
    ]
    singleton.get_symbol_price.side_effect = lambda s: {
        "BTCUSDT": 50000.0,
        "ETHUSDT": 0,
        "ETHBUSD": 3000.0,
        "FOOBTC": 0.001,
        "BTCUSDT": 50000.0,
        "FOOETH": None,
        "FOOBNB": None,
        "BNBUSDT": 400.0,
    }.get(s, 0.0)

    # fix: get_symbol_price needs more flexible map
    def price_map(sym):
        mapping = {
            "BTCUSDT": 50000.0,
            "ETHUSDT": 0.0,
            "ETHBUSD": 3000.0,
            "FOOBTC": 0.001,
            "FOOETH": 0.0,
            "FOOBNB": 0.0,
            "BNBUSDT": 400.0,
            "BARBTC": 0.0,
            "BARETH": 0.01,
            "ETHUSDT": 2000.0,  # overwritten — use if
        }
        # clearer
        table = {
            "BTCUSDT": 50000.0,
            "ETHBUSD": 3000.0,
            "FOOBTC": 0.001,
            "BNBUSDT": 400.0,
            "BARETH": 0.01,
            "ETHUSDT": 2000.0,
            "BARBNB": 0.02,
        }
        if sym == "ETHUSDT" and not hasattr(price_map, "eth_direct"):
            return 0.0
        return table.get(sym, 0.0)

    singleton.get_symbol_price.side_effect = price_map

    with patch(
        "app.services.binance_client_singleton.get_binance_client_singleton",
        return_value=singleton,
    ):
        bals = await svc._get_current_balances()
    assert bals["USDT"] == 100.0

    # cache fallback when all retries empty
    singleton.get_balances.side_effect = [None, None, None]
    await cache.set("balances:last", str({"USDT": 9.0}))
    with patch(
        "app.services.binance_client_singleton.get_binance_client_singleton",
        return_value=singleton,
    ):
        bals2 = await svc._get_current_balances()
    assert bals2["USDT"] == 9.0

    # bad cache + outer exception
    await cache.set("balances:last", "not-a-dict")
    with patch(
        "app.services.binance_client_singleton.get_binance_client_singleton",
        return_value=singleton,
    ):
        assert await svc._get_current_balances() == {}

    with patch(
        "app.services.binance_client_singleton.get_binance_client_singleton",
        side_effect=RuntimeError("no client"),
    ):
        assert await svc._get_current_balances() == {}

    # portfolio value paths: stables, earn, direct, busd, via btc, via eth, via bnb, skip
    singleton.get_symbol_price.side_effect = lambda s: {
        "BTCUSDT": 50000.0,
        "ETHUSDT": 0.0,
        "ETHBUSD": 3000.0,
        "XBTC": 0.0,
        "XBUSD": 0.0,
        "XBTC": 0.0,
        "XETH": 0.0,
        "XBNB": 0.0,
        "YBTC": 0.0,
        "YBUSD": 0.0,
        "YETH": 0.002,
        "ETHUSDT": 2000.0,
        "ZBTC": 0.0,
        "ZBUSD": 0.0,
        "ZETH": 0.0,
        "ZBNB": 0.05,
        "BNBUSDT": 400.0,
        "NOPRICEBTC": 0.0,
        "NOPRICEBUSD": 0.0,
        "NOPRICEETH": 0.0,
        "NOPRICEBNB": 0.0,
    }.get(s, 0.0)

    # clearer price function
    def px(sym: str) -> float:
        data = {
            "BTCUSDT": 50000.0,
            "ETHBUSD": 3000.0,
            "YETH": 0.002,
            "ETHUSDT": 2000.0,
            "ZBNB": 0.05,
            "BNBUSDT": 400.0,
        }
        return data.get(sym, 0.0)

    singleton.get_symbol_price.side_effect = px
    with (
        patch(
            "app.services.binance_client_singleton.get_binance_client_singleton",
            return_value=singleton,
        ),
        patch(
            "app.services.binance_client_singleton.STABLECOIN_ASSETS",
            {"USDT", "BUSD", "USDC", "TUSD", "FDUSD", "DAI"},
        ),
        patch(
            "app.services.binance_client_singleton.binance_earn_underlying_asset",
            side_effect=lambda a: "USDT" if a.startswith("LD") else None,
        ),
    ):
        val = await svc._calculate_portfolio_value(
            {
                "USDT": 10.0,
                "LDUSDT": 5.0,
                "BTC": 0.01,
                "ETH": 1.0,  # via BUSD
                "Y": 1.0,  # via ETH
                "Z": 1.0,  # via BNB
                "NOPRICE": 1.0,
                "ZERO": 0.0,
            }
        )
    assert val > 0

    with patch(
        "app.services.binance_client_singleton.get_binance_client_singleton",
        side_effect=RuntimeError("x"),
    ):
        assert await svc._calculate_portfolio_value({"USDT": 1}) == 0.0


@pytest.mark.asyncio
async def test_metrics_service_profits_roi_assets_prometheus():
    from app.services.metrics_service import MetricsService

    cache = _async_cache()
    svc = MetricsService()
    svc._cache = cache

    # rows for total profit
    row_usdt = ("BTCUSDT", 10.0, 1, 2, 1)
    row_btc = ("ETHBTC", 0.001, 1, 2, 1)
    row_eth = ("FOOETH", 0.01, 1, 2, 1)
    row_bnb = ("FOOBNB", 0.1, 1, 2, 1)
    row_none = ("BTCUSDT", None, 1, 2, 1)
    row_unk = ("FOOXXX", 1.0, 1, 2, 1)

    db = MagicMock()
    q = MagicMock()
    db.query.return_value = q
    q.filter.return_value = q
    q.all.return_value = [row_usdt, row_btc, row_eth, row_bnb, row_none, row_unk]
    q.group_by.return_value = q
    q.scalar.return_value = 1

    setting = SimpleNamespace(key="profit:baseline_iso", value=datetime.now().isoformat())
    # SystemSetting query chain for baseline
    setting_q = MagicMock()
    setting_q.filter.return_value.first.return_value = setting

    def query_side(*args, **kwargs):
        # Heuristic: SystemSetting vs Trade
        if args and getattr(args[0], "key", None) is not None or (
            args and hasattr(args[0], "class_")
        ):
            pass
        # Always return chain that supports both patterns
        m = MagicMock()
        m.filter.return_value = m
        m.first.return_value = setting
        m.all.return_value = [row_usdt, row_btc, row_eth, row_bnb, row_none]
        m.group_by.return_value = m
        m.scalar.return_value = 2
        # asset metrics results
        m.all.return_value = [
            row_usdt,
            row_btc,
            row_eth,
            row_bnb,
            row_none,
            ("BTCUSDT", "BUY", 1000.0),
            ("BTCUSDT", "SELL", 1200.0),
            ("ETHUSDT", "BUY", 500.0),
            ("ETHUSDT", "SELL", 400.0),
        ]
        return m

    db.query.side_effect = query_side

    singleton = MagicMock()
    singleton.get_symbol_price.side_effect = lambda s: {
        "BTCUSDT": 50000.0,
        "ETHUSDT": 2000.0,
        "BNBUSDT": 400.0,
    }.get(s, 0.0)

    with (
        patch("app.services.metrics_service.SessionLocal", return_value=db),
        patch(
            "app.services.binance_client_singleton.get_binance_client_singleton",
            return_value=singleton,
        ),
    ):
        total = await svc._calculate_total_profit()
        daily = await svc._calculate_daily_profit()
    assert isinstance(total, float)
    assert isinstance(daily, float)

    # baseline from cache
    await cache.set(svc._profit_baseline_key, datetime.now().isoformat())
    db2 = MagicMock()

    def q2(*a, **k):
        m = MagicMock()
        m.filter.return_value = m
        m.first.return_value = None
        m.all.return_value = [row_usdt]
        return m

    db2.query.side_effect = q2
    with (
        patch("app.services.metrics_service.SessionLocal", return_value=db2),
        patch(
            "app.services.binance_client_singleton.get_binance_client_singleton",
            return_value=singleton,
        ),
    ):
        await svc._calculate_total_profit()

    # exception paths
    with patch(
        "app.services.metrics_service.SessionLocal", side_effect=RuntimeError("db")
    ):
        assert await svc._calculate_total_profit() == 0.0
        assert await svc._calculate_daily_profit() == 0.0

    # ROI paths
    assert await svc._calculate_daily_roi(1.0, 0.0) == 0.0
    roi = await svc._calculate_daily_roi(10.0, 1000.0)
    assert -100 <= roi <= 100
    # cached base
    roi2 = await svc._calculate_daily_roi(5.0, 1100.0)
    assert isinstance(roi2, float)
    # bad float in cache
    date_key = datetime.utcnow().date().isoformat()
    await cache.set(f"roi:base:{date_key}", "bad")
    assert isinstance(await svc._calculate_daily_roi(1.0, 100.0), float)
    # cache get fails → fallback initial
    cache_bad = MagicMock()
    cache_bad.get = AsyncMock(side_effect=RuntimeError("c"))
    cache_bad.set = AsyncMock(side_effect=RuntimeError("c"))
    svc2 = MetricsService()
    svc2._cache = cache_bad
    assert await svc2._calculate_daily_roi(1.0, 50.0) == pytest.approx(2.0)
    # base_value <= 0
    svc2.initial_portfolio_value = 0.0
    assert await svc2._calculate_daily_roi(1.0, 50.0) == 0.0

    with patch.object(svc, "_cache", MagicMock(get=AsyncMock(side_effect=Exception("x")))):
        # force exception in outer try after portfolio_value check — patch datetime? easier:
        pass
    with patch(
        "app.services.metrics_service.datetime",
        side_effect=RuntimeError("dt"),
    ):
        # may still work depending on import site; ensure method returns float
        r = await svc._calculate_daily_roi(1.0, 100.0)
        assert isinstance(r, float)

    # asset metrics
    db_am = MagicMock()

    def q_am(*a, **k):
        m = MagicMock()
        m.filter.return_value = m
        m.group_by.return_value = m
        m.all.return_value = [
            ("BTCUSDT", "BUY", 1000.0),
            ("BTCUSDT", "SELL", 1500.0),
            ("ETHUSDT", "BUY", 200.0),
            ("ETHUSDT", "SELL", 100.0),
            ("BNBUSDT", "BUY", 50.0),
            ("BNBUSDT", "SELL", 50.0),
        ]
        return m

    db_am.query.side_effect = q_am
    with patch("app.services.metrics_service.SessionLocal", return_value=db_am):
        am = await svc._calculate_asset_metrics(
            {"BTC": 0.1, "ETH": 1.0, "BNB": 2.0, "X": 0}
        )
    assert "BTC" in am and am["BTC"]["roi"] > 0

    with patch("app.services.metrics_service.SessionLocal", return_value=db_am):
        assert await svc._calculate_asset_metrics({}) == {}

    with patch(
        "app.services.metrics_service.SessionLocal", side_effect=RuntimeError("x")
    ):
        assert await svc._calculate_asset_metrics({"BTC": 1}) == {}

    # prometheus update
    db_p = MagicMock()

    def q_p(*a, **k):
        m = MagicMock()
        m.group_by.return_value = m
        m.filter.return_value = m
        m.all.return_value = [("BTCUSDT", "BUY", 5), ("BTCUSDT", "SELL", 3)]
        m.scalar.return_value = 2
        return m

    db_p.query.side_effect = q_p
    with (
        patch("app.services.metrics_service.SessionLocal", return_value=db_p),
        patch("app.services.metrics_service.trading_metrics") as tm,
        patch("app.services.metrics_service.profit_daily_usdt") as pd,
        patch("app.services.metrics_service.roi_daily_percent") as rd,
    ):
        tm.trades_executed_total.labels.return_value.inc = MagicMock()
        tm.trades_success_rate.labels.return_value.set = MagicMock()
        pd.labels.return_value.set = MagicMock()
        rd.labels.return_value.set = MagicMock()
        svc._last_trades_count_by_symbol_side = {("BTCUSDT", "BUY"): 2}
        svc._update_prometheus_metrics(
            1.0,
            100.0,
            0.5,
            1.0,
            {"BTC": {"profit": 1.0, "roi": 2.0}},
        )

    # prometheus labels fail + db fail
    with (
        patch("app.services.metrics_service.SessionLocal", side_effect=RuntimeError("p")),
        patch("app.services.metrics_service.trading_metrics") as tm,
        patch(
            "app.services.metrics_service.profit_daily_usdt",
            MagicMock(labels=MagicMock(side_effect=RuntimeError("l"))),
        ),
        patch(
            "app.services.metrics_service.roi_daily_percent",
            MagicMock(labels=MagicMock(side_effect=RuntimeError("l"))),
        ),
    ):
        tm.update_profit_metrics.side_effect = None
        svc._update_prometheus_metrics(1, 1, 1, 1, {})

    with patch(
        "app.services.metrics_service.trading_metrics",
        MagicMock(
            update_profit_metrics=MagicMock(side_effect=RuntimeError("fail")),
            record_error=MagicMock(),
        ),
    ):
        svc._update_prometheus_metrics(1, 1, 1, 1, {})

    # record_trade / balances
    with patch("app.services.metrics_service.trading_metrics") as tm:
        await svc.record_trade_execution("BTCUSDT", "BUY", 0.1, 100.0, True, 0.01)
        tm.record_trade.assert_called()
        tm.record_trade.side_effect = RuntimeError("r")
        await svc.record_trade_execution("BTCUSDT", "BUY", 0.1, 100.0, False, 0.01)
        tm.record_error.assert_called()

    with patch("app.services.metrics_service.trading_metrics") as tm:
        await svc.update_balance_metrics({"USDT": 1, "BTC": 0})
        tm.update_balances.assert_called()
        tm.update_balances.side_effect = RuntimeError("b")
        await svc.update_balance_metrics({"USDT": 1})

    # update_binance_pnl_metrics
    with patch(
        "app.services.binance_trades_pnl.compute_binance_pnl_and_roi",
        return_value=(1.0, 10.0, 10.0),
    ), patch("app.services.metrics_service.profit_total_usdt") as pt, patch(
        "app.services.metrics_service.roi_total_percent"
    ) as rt:
        pt.labels.return_value.set = MagicMock()
        rt.labels.return_value.set = MagicMock()
        out = await svc.update_binance_pnl_metrics()
    assert out["profit_total_usdt"] == 1.0

    with patch(
        "app.services.binance_trades_pnl.compute_binance_pnl_and_roi",
        side_effect=RuntimeError("pnl"),
    ):
        err = await svc.update_binance_pnl_metrics()
    assert "error" in err

    # calculate_portfolio_metrics happy + baseline + error
    with (
        patch.object(svc, "_get_current_balances", AsyncMock(return_value={"USDT": 100})),
        patch.object(svc, "_calculate_portfolio_value", AsyncMock(return_value=100.0)),
        patch.object(svc, "_calculate_total_profit", AsyncMock(return_value=5.0)),
        patch.object(svc, "_calculate_daily_profit", AsyncMock(return_value=1.0)),
        patch.object(svc, "_calculate_daily_roi", AsyncMock(return_value=1.0)),
        patch.object(
            svc, "_calculate_asset_metrics", AsyncMock(return_value={"BTC": {"profit": 1, "roi": 1}})
        ),
        patch.object(svc, "_update_prometheus_metrics"),
        patch("app.services.metrics_service.SessionLocal", return_value=db),
        patch("app.services.metrics_service.portfolio_change_usdt") as pc,
    ):
        pc.labels.return_value.set = MagicMock()
        # portfolio baseline setting
        def q_base(*a, **k):
            m = MagicMock()
            m.filter.return_value = m
            m.first.return_value = SimpleNamespace(value="90")
            return m

        db.query.side_effect = q_base
        out = await svc.calculate_portfolio_metrics()
    assert out["portfolio_value"] == 100.0

    with (
        patch.object(svc, "_get_current_balances", AsyncMock(side_effect=RuntimeError("x"))),
        patch("app.services.metrics_service.trading_metrics") as tm,
    ):
        assert await svc.calculate_portfolio_metrics() == {}
        tm.record_error.assert_called()
