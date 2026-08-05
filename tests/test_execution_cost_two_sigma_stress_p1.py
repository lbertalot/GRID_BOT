"""P1: estrés +2σ spread/slippage (protocolo Passive Income §5.2)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.services.backtesting_service import (
    BacktestConfig,
    resolve_backtest_simulation_config,
)
from app.services.transaction_cost_model import (
    apply_two_sigma_execution_stress,
    compute_execution_cost_sigma_proxies_from_ohlcv_arrays,
)


def test_apply_two_sigma_raises_on_negative_sigma() -> None:
    with pytest.raises(ValueError, match="negativos"):
        apply_two_sigma_execution_stress(
            spread_bps=1.0,
            slippage_fraction=0.001,
            sigma_spread_bps=-0.1,
            sigma_slippage_fraction=0.0,
        )


def test_apply_two_sigma_clamps_non_negative_outputs() -> None:
    sp, sl = apply_two_sigma_execution_stress(
        spread_bps=1.0,
        slippage_fraction=0.001,
        sigma_spread_bps=10.0,
        sigma_slippage_fraction=0.01,
    )
    assert sp >= 0.0
    assert sl >= 0.0


def test_sigma_proxies_match_hand_calc_simple() -> None:
    high = np.array([102.0, 104.0], dtype=np.float64)
    low = np.array([98.0, 96.0], dtype=np.float64)
    close = np.array([100.0, 100.0], dtype=np.float64)
    open_ = np.array([100.0, 100.0], dtype=np.float64)
    sig_sp, sig_sl = compute_execution_cost_sigma_proxies_from_ohlcv_arrays(
        high, low, close, open_
    )
    spread_bps_per_bar = (high - low) / close * 10000.0
    assert sig_sp == pytest.approx(float(np.std(spread_bps_per_bar, ddof=1)))
    assert sig_sl == 0.0


def test_sigma_proxies_rejects_shape_mismatch() -> None:
    with pytest.raises(ValueError, match="misma forma"):
        compute_execution_cost_sigma_proxies_from_ohlcv_arrays(
            np.array([1.0]),
            np.array([1.0, 2.0]),
            np.array([1.0]),
            np.array([1.0]),
        )


def test_resolve_without_stress_returns_empty_meta() -> None:
    cfg = BacktestConfig(cost_stress_two_sigma=False)
    df = pd.DataFrame(
        {
            "open": [100.0, 101.0],
            "high": [102.0, 103.0],
            "low": [99.0, 100.0],
            "close": [101.0, 102.0],
        }
    )
    out, meta = resolve_backtest_simulation_config(cfg, df)
    assert out is cfg
    assert meta == {}


def test_resolve_with_stress_increases_effective_costs() -> None:
    np.random.seed(7)
    n = 200
    base = 100.0 + np.cumsum(np.random.normal(0, 0.3, n))
    df = pd.DataFrame(
        {
            "open": base,
            "close": base * (1.0 + np.random.normal(0, 0.002, n)),
            "high": base * (1.0 + np.abs(np.random.normal(0, 0.01, n))),
            "low": base * (1.0 - np.abs(np.random.normal(0, 0.01, n))),
        }
    )
    df["high"] = np.maximum(df["high"], np.maximum(df["open"], df["close"]))
    df["low"] = np.minimum(df["low"], np.minimum(df["open"], df["close"]))

    cfg = BacktestConfig(
        cost_stress_two_sigma=True,
        spread_bps=2.0,
        slippage=0.0003,
    )
    stressed, meta = resolve_backtest_simulation_config(cfg, df)
    assert meta.get("cost_stress_two_sigma") is True
    assert stressed.spread_bps >= cfg.spread_bps
    assert stressed.slippage >= cfg.slippage
    assert meta["backtest_spread_bps_effective"] == pytest.approx(stressed.spread_bps)
    assert meta["backtest_slippage_effective"] == pytest.approx(stressed.slippage)
