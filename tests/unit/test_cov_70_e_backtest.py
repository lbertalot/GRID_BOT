"""COV-70.E — backtesting_service ramas públicas (paper, datos sintéticos, mocks).

Paper-only · no red · no ML live · PROMOTE_LIVE: NO.
vectorbt / persistencia / cliente mockeados; OHLCV sintético en proceso.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.core.risk_manager import MarketRegime, RegimePrediction
from app.services.backtesting_service import (
    BacktestConfig,
    BacktestingService,
    resolve_backtest_simulation_config,
)
from app.services.strategy_selector import StrategyParams, StrategySpec, StrategyType

pytestmark = pytest.mark.usefixtures("paper_env")


class _FakeDatetime:
    """datetime.now siempre aware UTC para no romper duration = now - start_time."""

    @staticmethod
    def now(tz=None):
        return datetime(2026, 6, 1, 12, 0, 0, tzinfo=tz or timezone.utc)


def _regime() -> RegimePrediction:
    return RegimePrediction(
        long_regime=MarketRegime.RANGE,
        short_regime=MarketRegime.RANGE,
        long_conf=Decimal("0.7"),
        short_conf=Decimal("0.6"),
    )


def _spec(kind: StrategyType, **params) -> StrategySpec:
    return StrategySpec(
        strategy_name=kind,
        params=StrategyParams(**params),
        confidence=Decimal("0.8"),
        reasoning="paper cov-70.e",
        regime_prediction=_regime(),
    )


def _fake_portfolio(*, final: float = 10500.0, ret: float = 0.05):
    p = MagicMock()
    p.total_return.return_value = ret
    p.max_drawdown.return_value = 0.02
    p.sharpe_ratio.return_value = 1.2
    p.sortino_ratio.return_value = 1.4
    p.win_rate.return_value = 0.55
    p.profit_factor.return_value = 1.3
    p.count.return_value = 8
    dur = MagicMock()
    dur.mean.return_value = timedelta(hours=2)
    p.trades.duration = dur
    p.value = pd.Series([10000.0, final])
    return p


def _fake_vbt():
    class _Ind:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

        @classmethod
        def run(cls, *args, **_kwargs):
            close = args[-1]
            idx = close.index
            if cls.__name__ == "RSI":
                return _Ind(rsi=pd.Series(50.0, index=idx))
            if cls.__name__ == "MACD":
                z = pd.Series(0.0, index=idx)
                return _Ind(macd=z, signal=z)
            if cls.__name__ == "BBANDS":
                return _Ind(upper=close * 1.01, lower=close * 0.99, middle=close)
            if cls.__name__ == "ATR":
                return _Ind(atr=pd.Series(1.0, index=idx))
            return _Ind()

    class RSI(_Ind):
        pass

    class MACD(_Ind):
        pass

    class BBANDS(_Ind):
        pass

    class ATR(_Ind):
        pass

    class Portfolio:
        @staticmethod
        def from_signals(**_kwargs):
            return _fake_portfolio()

        @staticmethod
        def from_holding(**_kwargs):
            return _fake_portfolio(final=10000.0, ret=0.0)

    return SimpleNamespace(
        RSI=RSI, MACD=MACD, BBANDS=BBANDS, ATR=ATR, Portfolio=Portfolio
    )


@pytest.fixture
def bts_mod(monkeypatch):
    import app.services.backtesting_service as mod

    monkeypatch.setattr(mod, "vbt", _fake_vbt())
    monkeypatch.setattr(mod, "datetime", _FakeDatetime)
    return mod


@pytest.fixture
def svc(bts_mod, tmp_path):
    return bts_mod.BacktestingService(results_dir=str(tmp_path / "bt_results"))


def test_backtest_config_and_resolve_stress():
    with pytest.raises(ValueError, match="MARKET o LIMIT"):
        BacktestConfig(backtest_order_type="STOP")
    cfg = BacktestConfig(backtest_order_type="limit", persist_run_to_db=False)
    assert cfg.backtest_order_type == "LIMIT"
    df = pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0],
            "high": [101.0, 103.0, 104.0],
            "low": [99.0, 100.0, 101.0],
            "close": [100.5, 102.0, 103.0],
        }
    )
    same, meta = resolve_backtest_simulation_config(cfg, df)
    assert same is cfg and meta == {}
    stressed_cfg = BacktestConfig(
        cost_stress_two_sigma=True, spread_bps=1.0, slippage=0.0002
    )
    stressed, meta_s = resolve_backtest_simulation_config(stressed_cfg, df)
    assert meta_s["cost_stress_two_sigma"] is True
    assert stressed.spread_bps >= 1.0


def test_init_fees_and_technical_features(svc):
    assert svc.results_dir.endswith("bt_results")
    cfg = BacktestConfig(commission=0.002, slippage=0.0001, spread_bps=5.0)
    fees, slip = svc._vectorbt_fees_slippage(cfg)
    assert fees == 0.002
    assert slip == pytest.approx(0.0001 + 0.0005)

    df = pd.DataFrame(
        {
            "open": [100.0, 101.0, 100.5],
            "high": [101.0, 102.0, 101.5],
            "low": [99.0, 100.0, 100.0],
            "close": [100.5, 101.5, 101.0],
            "volume": [10.0, 11.0, 9.0],
        }
    )
    feat = svc._add_technical_features(df.copy())
    assert "rsi" in feat.columns and "macd" in feat.columns
    assert "atr" in feat.columns and "returns" in feat.columns


@pytest.mark.asyncio
async def test_download_ohlcv_synthetic_and_error(svc, bts_mod):
    start = datetime(2026, 1, 1)
    end = datetime(2026, 1, 3)
    df = await svc.download_ohlcv_data("ETHUSDT", start, end)
    assert len(df) > 10
    assert {"open", "high", "low", "close", "volume", "rsi"} <= set(df.columns)
    assert "ETHUSDT" in svc.historical_data

    with patch.object(bts_mod.pd, "date_range", side_effect=RuntimeError("ccxt down")):
        with pytest.raises(RuntimeError, match="ccxt down"):
            await svc.download_ohlcv_data("BTCUSDT", start, end)


@pytest.mark.asyncio
async def test_run_backtest_strategies_persist_and_errors(svc):
    start = datetime(2026, 1, 1)
    end = datetime(2026, 1, 5)
    cfg = BacktestConfig(
        min_samples=5,
        walk_forward=False,
        persist_run_to_db=False,
        cost_stress_two_sigma=False,
    )

    grid = await svc.run_backtest(
        _spec(StrategyType.GRID_TRADING, grid_spacing_bps=50, grid_levels=4),
        "BTCUSDT",
        start,
        end,
        initial_capital=10_000.0,
        config=cfg,
    )
    assert grid.symbol == "BTCUSDT"
    assert grid.total_trades == 8
    assert "transaction_cost_audit" in grid.metrics_json
    assert grid.initial_capital == 10_000.0

    dca = await svc.run_backtest(
        _spec(StrategyType.DCA, interval=2),
        "ETHUSDT",
        start,
        end,
        config=cfg,
    )
    assert dca.strategy_hash == StrategyType.DCA.value

    scalp = await svc.run_backtest(
        _spec(StrategyType.SCALPING),
        "SOLUSDT",
        start,
        end,
        config=cfg,
    )
    assert scalp.strategy_hash == StrategyType.SCALPING.value

    hold = await svc.run_backtest(
        _spec(StrategyType.HOLD),
        "BNBUSDT",
        start,
        end,
        config=cfg,
    )
    assert hold.total_return == 0.0

    defaulted = await svc.run_backtest(
        _spec(StrategyType.HOLD),
        "ADAUSDT",
        start,
        datetime(2026, 1, 12),
    )
    assert defaulted.symbol == "ADAUSDT"

    tight = BacktestConfig(min_samples=10_000_000, persist_run_to_db=False)
    with pytest.raises(ValueError, match="Insufficient data"):
        await svc.run_backtest(
            _spec(StrategyType.HOLD), "BTCUSDT", start, end, config=tight
        )

    db = MagicMock()
    persist_cfg = BacktestConfig(min_samples=5, persist_run_to_db=True)
    labels = MagicMock()
    labels.inc = MagicMock()
    metric = MagicMock()
    metric.labels.return_value = labels
    with patch("app.core.metrics.gridbot_backtest_run_persist_total", metric), patch(
        "app.db.session.SessionLocal", return_value=db
    ), patch(
        "app.services.backtest_persistence.persist_completed_backtest_run"
    ) as persist:
        ok = await svc.run_backtest(
            _spec(StrategyType.GRID_TRADING, grid_spacing_bps=40, grid_levels=4),
            "BTCUSDT",
            start,
            end,
            config=persist_cfg,
        )
        assert ok.symbol == "BTCUSDT"
        persist.assert_called_once()
        db.commit.assert_called_once()
        db.close.assert_called()

    persist_fail = BacktestConfig(min_samples=5, persist_run_to_db=True)
    with patch("app.core.metrics.gridbot_backtest_run_persist_total", metric), patch(
        "app.db.session.SessionLocal", return_value=db
    ), patch(
        "app.services.backtest_persistence.persist_completed_backtest_run",
        side_effect=RuntimeError("db"),
    ):
        still = await svc.run_backtest(
            _spec(StrategyType.HOLD), "BTCUSDT", start, end, config=persist_fail
        )
        assert still.symbol == "BTCUSDT"
        db.rollback.assert_called()

    with patch("app.core.metrics.gridbot_backtest_run_persist_total", metric), patch(
        "app.db.session.SessionLocal", side_effect=RuntimeError("no session")
    ):
        outer = await svc.run_backtest(
            _spec(StrategyType.HOLD), "BTCUSDT", start, end, config=persist_fail
        )
        assert outer.symbol == "BTCUSDT"

    stress = BacktestConfig(
        min_samples=5, cost_stress_two_sigma=True, persist_run_to_db=False
    )
    stressed = await svc.run_backtest(
        _spec(StrategyType.HOLD), "BTCUSDT", start, end, config=stress
    )
    assert stressed.metrics_json.get("cost_stress_two_sigma") is True


@pytest.mark.asyncio
async def test_walk_forward_save_load_summary(svc):
    start = datetime(2026, 1, 1)
    end = datetime(2026, 1, 5)
    simple_cfg = BacktestConfig(
        min_samples=5,
        walk_forward=False,
        window_size=1,
        step_size=1,
    )
    one = await svc.run_walk_forward_backtest(
        _spec(StrategyType.HOLD), "BTCUSDT", start, end, config=simple_cfg
    )
    assert len(one) == 1
    default_wf = await svc.run_walk_forward_backtest(
        _spec(StrategyType.HOLD), "BTCUSDT", start, start + timedelta(hours=12)
    )
    assert isinstance(default_wf, list)

    wf_cfg = BacktestConfig(
        min_samples=5,
        walk_forward=True,
        window_size=1,
        step_size=1,
    )
    windows = await svc.run_walk_forward_backtest(
        _spec(StrategyType.HOLD), "ETHUSDT", start, end, config=wf_cfg
    )
    assert len(windows) >= 1

    async def _boom(*_a, **_k):
        raise RuntimeError("window fail")

    with patch.object(svc, "run_backtest", side_effect=_boom):
        emptyish = await svc.run_walk_forward_backtest(
            _spec(StrategyType.HOLD), "XUSDT", start, end, config=wf_cfg
        )
    assert emptyish == []

    assert svc.get_backtest_summary([]) == {}
    summary = svc.get_backtest_summary(windows or one)
    assert summary["total_backtests"] >= 1
    assert "avg_sharpe_ratio" in summary
    assert summary["best_return"] >= summary["worst_return"]

    path = svc.save_backtest_results(one)
    assert path.endswith(".json")
    named = svc.save_backtest_results(one, filename="paper_cov70e.json")
    loaded = svc.load_backtest_results(named)
    assert len(loaded) == 1
    assert loaded[0].symbol == "BTCUSDT"


@pytest.mark.asyncio
async def test_simulate_methods_directly(svc):
    idx = pd.date_range("2026-01-01", periods=48, freq="h")
    close = pd.Series(100.0 + (idx.hour % 5), index=idx)
    macd = pd.Series([-0.2] * 24 + [0.2] * 24, index=idx)
    df = pd.DataFrame(
        {
            "open": close,
            "high": close * 1.02,
            "low": close * 0.98,
            "close": close,
            "volume": 1000.0,
            "rsi": 25.0,
            "macd": macd,
            "macd_signal": 0.0,
        },
        index=idx,
    )
    cfg = BacktestConfig(min_samples=5, initial_capital=10_000.0)
    grid_p = svc._simulate_grid_trading(
        df, _spec(StrategyType.GRID_TRADING, grid_spacing_bps=80, grid_levels=6), cfg
    )
    assert grid_p.total_return() == 0.05
    dca_p = svc._simulate_dca_strategy(
        df, _spec(StrategyType.DCA, interval=6), cfg
    )
    assert dca_p.count() == 8
    scalp_p = svc._simulate_scalping_strategy(df, _spec(StrategyType.SCALPING), cfg)
    assert scalp_p.win_rate() == 0.55
