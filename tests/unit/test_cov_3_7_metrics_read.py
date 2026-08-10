"""COV-3.7 — metrics_service paths de lectura (mocks, cero red).

Paper-only · no live · PROMOTE_LIVE: NO.
Baseline/ROI/PnL quote conversion + price routes BUSD/BTC/ETH/BNB.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.system_setting import SystemSetting
from app.models.trade import Trade
from app.services.metrics_service import MetricsService

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("paper_env")]


@pytest.fixture
def anyio_backend():
    return "asyncio"


class _Cache:
    def __init__(self):
        self.store: dict = {}

    async def get(self, key: str):
        return self.store.get(key)

    async def set(self, key: str, value, ttl_seconds: int = 0):
        self.store[key] = value


@pytest.fixture
def svc():
    with patch("app.services.metrics_service.get_async_cache", return_value=_Cache()):
        s = MetricsService()
    s._cache = _Cache()
    s._allowed_symbols = {"BTCUSDT", "ETHBTC", "ALTETH", "XBNB", "FOO"}
    return s


def _db_with_setting(setting_value, trade_rows):
    """SessionLocal mock: SystemSetting.first → setting; Trade query → rows."""
    db = MagicMock()

    def _query(*args, **kwargs):
        m = MagicMock()
        m.filter.return_value = m
        m.group_by.return_value = m
        target = args[0] if args else None
        if target is SystemSetting or (
            isinstance(target, type) and target.__name__ == "SystemSetting"
        ):
            if isinstance(setting_value, Exception):
                m.first.side_effect = setting_value
            else:
                m.first.return_value = setting_value
        else:
            m.all.return_value = trade_rows
            m.first.return_value = None
        return m

    db.query.side_effect = _query
    db.close = MagicMock()
    return db


async def test_price_routes_busd_btc_eth_bnb(svc):
    singleton = MagicMock()

    def _px(sym: str):
        return {
            "ALTUSDT": 0.0,
            "ALTBUSD": 2.0,
            "OBTCUSDT": 0.0,
            "OBTCBUSD": 0.0,
            "OBTCBTC": 0.01,
            "BTCUSDT": 0.0,  # force None branch multiply → 0
            "OETHUSDT": 0.0,
            "OETHBUSD": 0.0,
            "OETHBTC": 0.0,
            "OETHETH": 0.5,
            "ETHUSDT": 2000.0,
            "OBNBUSDT": 0.0,
            "OBNBBUSD": 0.0,
            "OBNBBTC": 0.0,
            "OBNBETH": 0.0,
            "OBNBBNB": 0.2,
            "BNBUSDT": 400.0,
        }.get(sym, 0.0)

    singleton.get_symbol_price.side_effect = _px
    with patch(
        "app.services.binance_client_singleton.get_binance_client_singleton",
        return_value=singleton,
    ):
        val = await svc._calculate_portfolio_value(
            {"ALT": 3.0, "OBTC": 1.0, "OETH": 1.0, "OBNB": 1.0, "USDT": 1.0}
        )
    # ALT via BUSD=6; OETH via ETH=1000; OBNB via BNB=80; OBTC via BTC*0=0; USDT=1
    assert val >= 6.0 + 1.0 + 80.0


async def test_total_profit_baseline_cache_and_quotes(svc):
    rows = [
        ("BTCUSDT", 10.0, None, None, None),
        ("ETHBTC", 0.001, None, None, None),
        ("ALTETH", 0.25, None, None, None),
        ("XBNB", 2.0, None, None, None),
        ("FOO", 1.0, None, None, None),
        (None, 1.0, None, None, None),
        ("BTCUSDT", None, None, None, None),
        ("BTCUSDT", 0.0, None, None, None),
    ]
    singleton = MagicMock()
    singleton.get_symbol_price.side_effect = lambda s: {
        "BTCUSDT": 50000.0,
        "ETHUSDT": 2000.0,
        "BNBUSDT": 400.0,
    }.get(s, 0.0)

    # setting raises → cache baseline
    await svc._cache.set(svc._profit_baseline_key, datetime.now().isoformat())
    db = _db_with_setting(RuntimeError("no setting col"), rows)
    with patch("app.services.metrics_service.SessionLocal", return_value=db), patch(
        "app.services.binance_client_singleton.get_binance_client_singleton",
        return_value=singleton,
    ):
        total = await svc._calculate_total_profit()
    assert total > 10.0

    # setting ok + cache miss path for baseline parse fail
    await svc._cache.set(svc._profit_baseline_key, "not-iso")
    db2 = _db_with_setting(SimpleNamespace(value="also-bad"), rows[:2])
    with patch("app.services.metrics_service.SessionLocal", return_value=db2), patch(
        "app.services.binance_client_singleton.get_binance_client_singleton",
        return_value=singleton,
    ):
        t2 = await svc._calculate_total_profit()
    assert t2 >= 10.0

    with patch(
        "app.services.metrics_service.SessionLocal", side_effect=RuntimeError("db")
    ):
        assert await svc._calculate_total_profit() == 0.0


async def test_daily_profit_quotes(svc):
    rows = [
        ("BTCUSDT", -3.0, None, None, None, datetime.now()),
        ("ETHBTC", 0.002, None, None, None, datetime.now()),
        ("ALTETH", 0.1, None, None, None, datetime.now()),
        ("XBNB", 1.0, None, None, None, datetime.now()),
        ("FOO", 1.0, None, None, None, datetime.now()),
        (None, 1.0, None, None, None, datetime.now()),
        ("BTCUSDT", None, None, None, None, datetime.now()),
        ("BTCUSDT", 0.0, None, None, None, datetime.now()),
    ]
    db = MagicMock()
    chain = MagicMock()
    chain.filter.return_value = chain
    chain.all.return_value = rows
    db.query.return_value = chain
    singleton = MagicMock()
    singleton.get_symbol_price.side_effect = lambda s: {
        "BTCUSDT": 50000.0,
        "ETHUSDT": 2000.0,
        "BNBUSDT": 400.0,
    }.get(s, 0.0)
    with patch("app.services.metrics_service.SessionLocal", return_value=db), patch(
        "app.services.binance_client_singleton.get_binance_client_singleton",
        return_value=singleton,
    ):
        daily = await svc._calculate_daily_profit()
    assert daily != 0.0

    with patch(
        "app.services.metrics_service.SessionLocal", side_effect=RuntimeError("db")
    ):
        assert await svc._calculate_daily_profit() == 0.0


async def test_portfolio_baseline_delta_and_roi(svc):
    with patch.object(
        svc, "_get_current_balances", AsyncMock(return_value={"USDT": 100.0})
    ), patch.object(
        svc, "_calculate_portfolio_value", AsyncMock(return_value=1000.0)
    ), patch.object(
        svc, "_calculate_total_profit", AsyncMock(return_value=5.0)
    ), patch.object(
        svc, "_calculate_daily_profit", AsyncMock(return_value=1.0)
    ), patch.object(
        svc, "_calculate_asset_metrics", AsyncMock(return_value={})
    ), patch.object(svc, "_update_prometheus_metrics", MagicMock()):
        db = _db_with_setting(SimpleNamespace(value="800"), [])
        with patch("app.services.metrics_service.SessionLocal", return_value=db), patch(
            "app.services.metrics_service.portfolio_change_usdt"
        ) as g:
            g.labels.return_value = MagicMock()
            out = await svc.calculate_portfolio_metrics()
        assert out["portfolio_value"] == 1000.0
        g.labels.return_value.set.assert_called()

        # no setting → base_val = portfolio_value
        db2 = _db_with_setting(None, [])
        with patch("app.services.metrics_service.SessionLocal", return_value=db2), patch(
            "app.services.metrics_service.portfolio_change_usdt"
        ) as g2:
            g2.labels.return_value = MagicMock()
            await svc.calculate_portfolio_metrics()
        g2.labels.return_value.set.assert_called_with(0.0)

        # outer portfolio_change try fails after metrics built — setting db ok but gauge blows
        db3 = _db_with_setting(SimpleNamespace(value="900"), [])
        with patch("app.services.metrics_service.SessionLocal", return_value=db3), patch(
            "app.services.metrics_service.portfolio_change_usdt.labels",
            side_effect=RuntimeError("gauge"),
        ):
            out3 = await svc.calculate_portfolio_metrics()
        assert out3["portfolio_value"] == 1000.0

    key = f"roi:base:{datetime.utcnow().date().isoformat()}"
    await svc._cache.set(key, "bad")
    assert await svc._calculate_daily_roi(10.0, 100.0) == 10.0
    with patch.object(svc._cache, "get", side_effect=RuntimeError("c")):
        svc.initial_portfolio_value = None
        r = await svc._calculate_daily_roi(5.0, 50.0)
        assert r == 10.0
    assert await svc._calculate_daily_roi(1.0, 0) == 0.0
    with patch.object(svc._cache, "get", side_effect=RuntimeError("c")), patch(
        "app.services.metrics_service.max", side_effect=RuntimeError("x")
    ):
        svc.initial_portfolio_value = 100.0
        assert await svc._calculate_daily_roi(1.0, 100.0) == 0.0


async def test_binance_pnl_update(svc):
    with patch(
        "app.services.binance_trades_pnl.compute_binance_pnl_and_roi",
        return_value=(2.0, 20.0, 10.0),
    ), patch("app.services.metrics_service.profit_total_usdt") as p, patch(
        "app.services.metrics_service.roi_total_percent"
    ) as r:
        p.labels.return_value = MagicMock()
        r.labels.return_value = MagicMock()
        assert (await svc.update_binance_pnl_metrics())["roi_total_percent"] == 10.0
    with patch(
        "app.services.binance_trades_pnl.compute_binance_pnl_and_roi",
        side_effect=RuntimeError("x"),
    ):
        assert "error" in await svc.update_binance_pnl_metrics()
