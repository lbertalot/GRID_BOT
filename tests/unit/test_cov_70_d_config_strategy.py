"""COV-70.D — unified_config / risk_metrics / blacklist / collector / strategy / sentiment / paths.

Paper-only · no live · PROMOTE_LIVE: NO.
Configs en tmp_path; collectors HTTP/Binance mockeados; Decimal en PnL de riesgo.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

pytestmark = pytest.mark.usefixtures("paper_env")


# ── unified_config ───────────────────────────────────────────────────────────


def _unified(tmp_path: Path, payload: dict | None = None):
    from app.core.unified_config import UnifiedConfig

    cfg_path = tmp_path / "unified_tmp.json"
    if payload is not None:
        cfg_path.write_text(json.dumps(payload), encoding="utf-8")
    return UnifiedConfig(config_file=str(cfg_path)), cfg_path


def test_unified_config_load_missing_corrupt_and_save_error(tmp_path):
    from app.core.unified_config import UnifiedConfig

    missing = tmp_path / "nope" / "missing.json"
    # parent no existe → load warning + default (save crea el archivo si el dir existe)
    # usamos path en tmp_path para que save funcione
    cfg, path = _unified(tmp_path)
    assert path.exists()
    assert cfg.get_system_settings().get("paper_trading") is True
    assert cfg.get_system_settings().get("trading_enabled") is False

    bad = tmp_path / "corrupt.json"
    bad.write_text("{not-json", encoding="utf-8")
    broken = UnifiedConfig(config_file=str(bad))
    assert "BTCUSDT" in broken.get_all_assets()

    cfg.config["_system_settings"] = {"paper_trading": True, "trading_enabled": False}
    with patch("builtins.open", side_effect=OSError("disk full")):
        cfg.save_config()  # except logueado, no raise


def test_unified_config_asset_system_safety_monitoring_crud(tmp_path):
    cfg, _ = _unified(tmp_path)

    assert cfg.get_asset_config("NOPE") is None
    eth = cfg.get_asset_config("ETHUSDT")
    assert eth is not None and eth["symbol"] == "ETHUSDT"

    cfg.update_asset_config(
        "ETHUSDT",
        {**eth, "is_active": True, "grids": 8, "quantity": 0.01},
    )
    assert cfg.get_active_assets()["ETHUSDT"]["is_active"] is True

    cfg.update_system_settings(
        {
            "trading_enabled": False,
            "paper_trading": True,
            "max_concurrent_trades": 3,
            "emergency_stop_enabled": True,
        }
    )
    assert cfg.get_system_settings()["paper_trading"] is True

    cfg.update_safety_limits({"max_total_loss": 0.08, "max_daily_loss": 0.99})
    limits = cfg.get_safety_limits()
    assert limits["max_total_loss"] == 0.08
    assert limits["max_daily_loss"] != 0.99  # SoT override

    cfg.update_monitoring_settings({"alerts_enabled": True, "log_level": "DEBUG"})
    assert cfg.get_monitoring_settings()["log_level"] == "DEBUG"

    cfg.add_asset(
        "SOLUSDT",
        {
            "symbol": "SOLUSDT",
            "is_active": False,
            "min_price": 100,
            "max_price": 200,
            "grids": 4,
            "quantity": 1,
        },
    )
    assert "SOLUSDT" in cfg.get_all_assets()
    cfg.remove_asset("SOLUSDT")
    assert "SOLUSDT" not in cfg.get_all_assets()
    cfg.remove_asset("DOESNOTEXIST")  # warning branch

    cfg.enable_trading()
    assert cfg.get_system_settings()["trading_enabled"] is True
    cfg.disable_trading()
    assert cfg.get_system_settings()["trading_enabled"] is False
    cfg.enable_paper_trading()
    assert cfg.get_system_settings()["paper_trading"] is True
    cfg.disable_paper_trading()
    assert cfg.get_system_settings()["paper_trading"] is False
    cfg.enable_paper_trading()

    summary = cfg.get_config_summary()
    assert summary["assets_summary"]["total_assets"] >= 2
    assert "ETHUSDT" in summary["active_assets"]

    ok, errs = cfg.validate_config()
    assert ok is True and errs == []


def test_unified_config_validate_errors_and_module_helpers(tmp_path):
    from app.core import unified_config as uc

    payload = {
        "_system_settings": {"max_concurrent_trades": "cinco", "paper_trading": True},
        "_safety_limits": {"max_total_loss": -1, "max_trade_loss": "x"},
        "FOOUSDT": {
            "symbol": "FOOUSDT",
            "is_active": "yes",
            "min_price": "low",
            "max_price": None,
        },
    }
    cfg, _ = _unified(tmp_path, payload)
    ok, errors = cfg.validate_config()
    assert ok is False
    assert any("max_concurrent_trades" in e for e in errors)
    assert any("is_active" in e for e in errors)
    assert any("min_price" in e for e in errors)
    assert any("max_price" in e for e in errors)

    assert uc.get_config() is uc.unified_config
    assert isinstance(uc.get_system_settings(), dict)
    assert "max_daily_loss" in uc.get_safety_limits()
    # puede ser None si el JSON global no tiene el símbolo
    _ = uc.get_asset_config("BTCUSDT")


# ── risk_metrics_engine ──────────────────────────────────────────────────────


def _pnl_rows(n: int = 15, start: date | None = None, include_today: bool = True):
    start = start or (date.today() - timedelta(days=n - 1))
    rows = []
    for i in range(n):
        d = start + timedelta(days=i)
        # mix de ganancias/pérdidas en Decimal (normalización a float en el engine)
        pnl = Decimal("12.50") if i % 3 else Decimal("-8.25")
        if include_today and d == date.today():
            pnl = Decimal("3.10")
        rows.append(SimpleNamespace(fecha=d, pnl_diario=pnl))
    return rows


def _db(rows=None, error=None):
    db = MagicMock()
    q = MagicMock()
    db.query.return_value = q
    q.filter.return_value = q
    q.group_by.return_value = q
    q.order_by.return_value = q
    if error is not None:
        q.all.side_effect = error
    else:
        q.all.return_value = list(rows or [])
    return db


def test_risk_metrics_fetch_and_fallbacks(decimal_money):
    from app.services.risk_metrics_engine import (
        RiskMetricsEngine,
        _fetch_daily_pnl_series,
        risk_metrics_engine,
    )

    assert decimal_money("12.50") == Decimal("12.50")
    empty = _fetch_daily_pnl_series(_db([]), dias=30, symbol="btcusdt")
    assert empty.empty
    err = _fetch_daily_pnl_series(_db(error=RuntimeError("db down")), dias=10)
    assert err.empty

    series = _fetch_daily_pnl_series(_db(_pnl_rows(15)), dias=90)
    assert len(series) == 15
    assert series.dtype == float

    eng = RiskMetricsEngine(rf_rate=0.0, ann_factor=365, min_dias=10)
    short = pd.Series([1.0, 2.0], name="pnl_diario")
    assert eng.calcular_volatilidad(short, 1000.0) == 0.05
    assert eng.calcular_volatilidad(series, 0.0) == 0.05
    assert eng.calcular_sharpe(short, 1000.0) == 0.0
    assert eng.calcular_max_drawdown(short.iloc[:1]) == 0.05
    assert eng.calcular_var_historico(short) == 0.0
    assert eng.calcular_cvar(short) == 0.0
    assert eng.calcular_pnl_hoy(pd.Series(dtype=float)) == 0.0

    constant = pd.Series([1.0] * 12)
    with patch.object(pd.Series, "std", return_value=0.0):
        assert eng.calcular_sharpe(constant, 1000.0) == 0.0
    with patch.object(pd.Series, "std", return_value=float("nan")):
        assert eng.calcular_volatilidad(constant, 1000.0) == 0.05
    vol = eng.calcular_volatilidad(series, 10_000.0)
    assert vol >= 0 and vol != 0.05
    sharpe = eng.calcular_sharpe(series, 10_000.0)
    assert isinstance(sharpe, float)
    dd = eng.calcular_max_drawdown(series)
    assert dd >= 0
    # curva sin drawdown → fallback 0.05
    rising = pd.Series(range(1, 20), dtype=float)
    assert eng.calcular_max_drawdown(rising) == 0.05

    inf_series = pd.Series([float("inf")] * 12)
    assert eng.calcular_volatilidad(inf_series, 100.0) == 0.05
    assert eng.calcular_sharpe(inf_series, 100.0) == 0.0

    var = eng.calcular_var_historico(series, 0.95)
    cvar = eng.calcular_cvar(series, 0.95)
    assert isinstance(var, float) and isinstance(cvar, float)
    with patch.object(eng, "calcular_var_historico", return_value=1e12):
        assert eng.calcular_cvar(series) == 1e12  # cola vacía → var

    today_idx = pd.Timestamp(date.today())
    with_today = series.copy()
    with_today.index = pd.to_datetime(with_today.index)
    if today_idx not in with_today.index:
        with_today.loc[today_idx] = 3.1
    assert isinstance(eng.calcular_pnl_hoy(with_today), float)

    bad = MagicMock()
    bad.empty = False
    bad.get.side_effect = RuntimeError("idx")
    assert eng.calcular_pnl_hoy(bad) == 0.0

    low = risk_metrics_engine.resumen_completo(_db([]), portfolio_value=1000.0)
    assert low["datos_insuficientes"] is True
    full = eng.resumen_completo(
        _db(_pnl_rows(20)), portfolio_value=5_000.0, symbol="ETHUSDT"
    )
    assert full["dias_analizados"] == 20
    assert full["datos_insuficientes"] is False
    assert full["pnl_total_usdt"] != 0.0


# ── strategy_blacklist ───────────────────────────────────────────────────────


def test_strategy_blacklist_io_queries_and_block(tmp_path):
    from app.core.strategy_blacklist import StrategyBlacklist

    path = tmp_path / "bl.json"
    bl = StrategyBlacklist(config_file=str(path))
    assert path.exists()
    assert bl.is_symbol_blacklisted("SPKUSDT")
    assert bl.get_blacklist_reason("SPKUSDT")
    assert bl.get_blacklist_reason("ETHUSDT") is None
    assert bl.is_strategy_blacklisted("NoSuch") is False
    assert bl.is_strategy_blacklisted("GridTrading") is True  # sin símbolo
    assert bl.is_strategy_blacklisted("GridTrading", "SPKUSDT") is True
    assert bl.is_strategy_blacklisted("GridTrading", "ETHUSDT") is False

    blocked, reason = bl.should_block_trading("SPKUSDT", "GridTrading")
    assert blocked is True and "blacklist" in reason
    blocked, reason = bl.should_block_trading("ETHUSDT", "GridTrading")
    assert blocked is False
    blocked, reason = bl.should_block_trading("ETHUSDT", "GridTrading")
    # ETH no está en symbols de GridTrading → permitido
    assert blocked is False

    # estrategia bloqueada para símbolo listado (símbolo no blacklisted)
    bl.blacklist["symbols"].pop("BNBUSDT", None)
    blocked, reason = bl.should_block_trading("BNBUSDT", "GridTrading")
    assert blocked is True and "Estrategia" in reason

    bl.add_symbol_to_blacklist("TESTUSDT", "paper loss", -40.0)
    assert bl.remove_symbol_from_blacklist("TESTUSDT") is True
    assert bl.remove_symbol_from_blacklist("TESTUSDT") is False

    status = bl.get_blacklist_status()
    assert status["symbols_count"] >= 1 and status["active"] is True
    assert "SPKUSDT" in bl.get_blacklisted_symbols()
    summary = bl.get_blacklist_summary()
    assert "BLACKLIST SUMMARY" in summary and "GridTrading" in summary
    assert bl.is_blacklist_active() is True

    bl.blacklist = None
    assert bl.is_blacklist_active() is False  # except → False

    # load except → default
    junk = tmp_path / "junk.json"
    junk.write_text("{bad", encoding="utf-8")
    bl2 = StrategyBlacklist(config_file=str(junk))
    assert "SPKUSDT" in bl2.blacklist["symbols"]

    with patch("builtins.open", side_effect=OSError("ro")):
        bl2._save_blacklist({"symbols": {}, "strategies": {}})


@pytest.mark.asyncio
async def test_strategy_blacklist_auto_analyze(tmp_path):
    from app.core.strategy_blacklist import StrategyBlacklist

    bl = StrategyBlacklist(config_file=str(tmp_path / "auto.json"))
    already = "SPKUSDT"
    add_me = "NEWUSDT"
    skip_small = "TINYUSDT"
    rows = [
        (already, -500.0, 80),
        (add_me, -150.0, 60),
        (skip_small, -10.0, 5),
    ]
    db = MagicMock()
    q = MagicMock()
    db.query.return_value = q
    q.filter.return_value = q
    q.group_by.return_value = q
    q.all.return_value = rows

    with patch("app.core.strategy_blacklist.SessionLocal", return_value=db):
        added = await bl.auto_analyze_and_blacklist()
    assert add_me in added["symbols"]
    assert already not in added["symbols"]
    assert skip_small not in added["symbols"]
    db.close.assert_called()

    with patch(
        "app.core.strategy_blacklist.SessionLocal",
        side_effect=RuntimeError("no db"),
    ):
        failed = await bl.auto_analyze_and_blacklist()
    assert failed == {"symbols": [], "reasons": []}


# ── market_data_collector ────────────────────────────────────────────────────


@pytest.fixture
def collector(mock_binance):
    cache = AsyncMock()
    binance = MagicMock()
    binance.get_price = AsyncMock(return_value=50000.0)
    binance.get_klines = AsyncMock(
        return_value=[
            [1_700_000_000_000, "100", "101", "99", "100.5", "10", 1_700_000_060_000]
        ]
    )
    with patch(
        "app.services.market_data_collector.get_async_cache", return_value=cache
    ), patch(
        "app.services.market_data_collector.AsyncBinanceWrapper", return_value=binance
    ):
        from app.services.market_data_collector import MarketDataCollector

        c = MarketDataCollector(ttl_seconds=5)
        c.binance = binance
        c.cache = cache
        yield c


@pytest.mark.asyncio
async def test_market_data_collector_price_validate_and_klines_db(collector):
    assert await collector.get_price("BTCUSDT") == 50000.0
    kl = await collector.get_klines("BTCUSDT", "1m", 1)
    assert isinstance(kl, list) and kl

    validator = MagicMock()
    validator.validate_order_parameters.return_value = {
        "valid": True,
        "recommended_quantity": 0.001,
    }
    fake_client = MagicMock()
    with patch(
        "app.services.market_data_collector.Client", return_value=fake_client
    ), patch(
        "app.services.market_data_collector.OrderValidator", return_value=validator
    ):
        client = await collector._ensure_client()
        assert client is fake_client
        # segunda vez no re-inicia
        assert await collector._ensure_client() is fake_client

    out = await collector.validate_order("BTCUSDT", 0.001, order_type="MARKET")
    assert out["recommended_quantity"] == 0.001

    assert await collector.save_klines_to_db("BTCUSDT", "1m", []) == 0

    conn = AsyncMock()
    conn.execute = AsyncMock()
    conn.close = AsyncMock()
    klines = [
        [1_700_000_000_000, "100", "101", "99", "100.5", "12.5", 1_700_000_060_000],
        [1_700_000_060_000, "100.5", "102", "100", "101", "8.0", 1_700_000_120_000],
    ]
    with patch(
        "app.services.market_data_collector.asyncpg.connect",
        new=AsyncMock(return_value=conn),
    ):
        n = await collector.save_klines_to_db("BTCUSDT", "1m", klines)
    assert n == 2
    conn.close.assert_awaited()

    with patch(
        "app.services.market_data_collector.asyncpg.connect",
        new=AsyncMock(side_effect=RuntimeError("pg down")),
    ):
        assert await collector.save_klines_to_db("BTCUSDT", "1m", klines) == 0


# ── strategy_manager ─────────────────────────────────────────────────────────


class _DummyML:
    def __init__(self, label: int = 1, proba: float = 0.7, error: Exception | None = None):
        self.label = label
        self.proba = proba
        self.error = error

    async def predict_regime(self, symbol: str, interval: str = "1m", limit: int = 60):
        if self.error:
            raise self.error
        return SimpleNamespace(label=self.label, proba=self.proba)


def _asset(symbol="BTCUSDT", grids=6, qty=0.02):
    return SimpleNamespace(
        symbol=symbol,
        grids=grids,
        quantity=qty,
        min_price=90.0,
        max_price=110.0,
        is_active=True,
    )


def _mgr(assets=None, history=None):
    return SimpleNamespace(
        config=SimpleNamespace(assets=assets or {"BTCUSDT": _asset()}),
        trading_history=history or [],
    )


@pytest.mark.asyncio
async def test_strategy_manager_adapt_drawdown_ml_and_guards():
    from app.services.strategy_manager import AdaptationPolicy, StrategyManager

    sm = StrategyManager(policy=AdaptationPolicy(), ml_engine=_DummyML())
    assert await sm.adapt_manager(SimpleNamespace()) == {}

    missing = _mgr({"BTCUSDT": _asset()})
    changes = await sm.adapt_manager(missing, symbols=["NOPE"])
    assert changes == {}

    # snapshot except
    class Boom(dict):
        def get(self, *_a, **_k):
            raise RuntimeError("cfg")

    sm._snapshot_baseline_if_needed(
        SimpleNamespace(config=SimpleNamespace(assets=Boom())), "BTCUSDT"
    )
    assert "BTCUSDT" not in sm._baseline

    history = [
        SimpleNamespace(symbol="BTCUSDT", profit=-12.0),
        SimpleNamespace(symbol="BTCUSDT", profit=1.0),
        SimpleNamespace(symbol=None, profit=5.0),
        SimpleNamespace(symbol="ETHUSDT", profit=2.0),
    ]
    mgr = _mgr({"BTCUSDT": _asset(), "ETHUSDT": _asset("ETHUSDT")}, history)
    # sin history → flags vacíos
    assert sm._compute_drawdown_flag(_mgr(history=[])) == {}

    sm_dd = StrategyManager(policy=AdaptationPolicy(), ml_engine=_DummyML(label=1, proba=0.9))
    reverted = await sm_dd.adapt_manager(mgr)
    assert "BTCUSDT" in reverted
    assert mgr.config.assets["BTCUSDT"].min_price == 90.0

    sm_err = StrategyManager(ml_engine=_DummyML(error=RuntimeError("ml down")))
    quiet = _mgr({"BTCUSDT": _asset()}, history=[])
    assert await sm_err.adapt_manager(quiet) == {}

    sm_low = StrategyManager(ml_engine=_DummyML(label=1, proba=0.4))
    assert await sm_low.adapt_manager(_mgr()) == {}

    sm_bull = StrategyManager(ml_engine=_DummyML(label=1, proba=0.8))
    bull_mgr = _mgr()
    bull = await sm_bull.adapt_manager(bull_mgr)
    assert bull["BTCUSDT"]["grids"] >= 6

    sm_bear = StrategyManager(ml_engine=_DummyML(label=0, proba=0.8))
    bear_mgr = _mgr()
    bear = await sm_bear.adapt_manager(bear_mgr)
    assert bear["BTCUSDT"]["grids"] <= 6


# ── promotion_gate_sentiment ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_promotion_gate_sentiment_parse_redis_stub(monkeypatch):
    from app.services import promotion_gate_sentiment as pgs

    assert pgs._parse_score_payload(None) is None
    assert pgs._parse_score_payload(0.2) == 0.2
    assert pgs._parse_score_payload(1) == 1.0
    assert pgs._parse_score_payload("  ") is None
    assert pgs._parse_score_payload("0.42") == pytest.approx(0.42)
    assert pgs._parse_score_payload('{"score": -0.3}') == pytest.approx(-0.3)
    assert pgs._parse_score_payload("not-a-number") is None
    assert pgs._parse_score_payload({"score": "nope"}) is None
    assert pgs._parse_score_payload({"score": 0.1}) == pytest.approx(0.1)
    assert pgs._parse_score_payload({"x": 1}) is None

    async def boom(_key: str):
        raise RuntimeError("redis")

    monkeypatch.delenv("ML_PROMOTION_GATE_NLP_STUB_SCORE", raising=False)
    monkeypatch.setattr("app.core.redis_cache.redis_cache.get", boom)
    assert await pgs.resolve_promotion_gate_sentiment_score("BTCUSDT") is None

    async def none_get(_key: str):
        return None

    monkeypatch.setattr("app.core.redis_cache.redis_cache.get", none_get)
    monkeypatch.setenv("ML_PROMOTION_GATE_NLP_STUB_SCORE", "")
    assert await pgs.resolve_promotion_gate_sentiment_score("ETHUSDT") is None
    monkeypatch.setenv("ML_PROMOTION_GATE_NLP_STUB_SCORE", "not-float")
    assert await pgs.resolve_promotion_gate_sentiment_score("ETHUSDT") is None
    monkeypatch.setenv("ML_PROMOTION_GATE_NLP_STUB_SCORE", "0.25")
    assert await pgs.resolve_promotion_gate_sentiment_score("ETHUSDT") == pytest.approx(
        0.25
    )

    m = pgs.kelly_multiplier_from_sentiment_score(
        0.0, mult_at_minus_one=0.5, mult_at_plus_one=1.5
    )
    assert m == pytest.approx(1.0)
    assert pgs.kelly_multiplier_from_sentiment_score(
        None, mult_at_minus_one=0.5, mult_at_plus_one=1.5, mult_if_missing=0.9
    ) == pytest.approx(0.9)
    assert pgs.kelly_multiplier_from_sentiment_score(
        -2.0, mult_at_minus_one=0.4, mult_at_plus_one=1.6
    ) == pytest.approx(0.4)
    assert pgs.kelly_multiplier_from_sentiment_score(
        2.0, mult_at_minus_one=0.4, mult_at_plus_one=1.6
    ) == pytest.approx(1.6)
    with pytest.raises(ValueError):
        pgs.kelly_multiplier_from_sentiment_score(
            0.0, mult_at_minus_one=0.0, mult_at_plus_one=1.0
        )
    with pytest.raises(ValueError):
        pgs.kelly_multiplier_from_sentiment_score(
            None, mult_at_minus_one=1.0, mult_at_plus_one=1.0, mult_if_missing=0.0
        )

    async def hit(_key: str):
        return {"score": 0.5}

    monkeypatch.setattr("app.core.redis_cache.redis_cache.get", hit)
    assert await pgs.resolve_promotion_gate_sentiment_score("  btcusdt ") == pytest.approx(
        0.5
    )
    assert await pgs.resolve_promotion_gate_sentiment_score("   ") is None


# ── paths ────────────────────────────────────────────────────────────────────


def test_paths_heroku_fallback_and_helpers(tmp_path, monkeypatch):
    from app.core import paths as paths_mod

    monkeypatch.setenv("DYNO", "web.1")
    heroku = paths_mod.get_writable_path(str(tmp_path / "grid-data"))
    assert heroku.parent == Path("/tmp")
    monkeypatch.delenv("DYNO", raising=False)

    writable = paths_mod.get_writable_path(str(tmp_path / "ok"))
    assert writable.exists()

    with pytest.raises((PermissionError, OSError)):
        paths_mod.get_writable_path("/dev/null/not_a_dir", fallback_to_tmp=False)

    fallback = paths_mod.get_writable_path("/dev/null/not_a_dir", fallback_to_tmp=True)
    assert fallback.parent == Path("/tmp")

    # mkdir ok, write_test falla → fallback o raise
    ro = tmp_path / "ro_dir"
    ro.mkdir()
    with patch.object(Path, "write_text", side_effect=PermissionError("ro")):
        out = paths_mod.get_writable_path(str(ro), fallback_to_tmp=True)
        assert out.parent == Path("/tmp") or out == ro
        with pytest.raises(PermissionError):
            paths_mod.get_writable_path(str(ro), fallback_to_tmp=False)

    monkeypatch.setenv("MONITORING_DIR", str(tmp_path / "mon"))
    monkeypatch.setenv("REPORTS_DIR", str(tmp_path / "rep"))
    monkeypatch.setenv("LOG_FILE_PATH", str(tmp_path / "logs" / "app.log"))
    assert paths_mod.get_monitoring_dir().exists()
    assert paths_mod.get_reports_dir().exists()
    logs = paths_mod.get_logs_dir()
    assert logs.exists()
    assert logs.name != "app.log"
