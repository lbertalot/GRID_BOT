"""P1: shocks multiplicativos §5.2 sobre trayectorias de retornos."""

from __future__ import annotations

import random

import pytest

from app.research.monte_carlo_paths import (
    max_drawdown_from_simple_returns,
    monte_carlo_max_drawdown_study,
)
from app.research.monte_carlo_shocks import (
    MonteCarloShockConfig,
    apply_multiplicative_return_shocks,
)


def test_shock_config_rejects_invalid_multiplier() -> None:
    with pytest.raises(ValueError):
        MonteCarloShockConfig(single_day_gross_multiplier=1.5)
    with pytest.raises(ValueError):
        MonteCarloShockConfig(single_day_gross_multiplier=0.0)


def test_apply_shocks_reproducible() -> None:
    base = [0.01, -0.005, 0.02, -0.01, 0.015] * 4
    a = apply_multiplicative_return_shocks(
        list(base),
        random.Random(42),
        single_day_gross_multiplier=0.9,
        three_day_run_gross_multiplier=0.95,
    )
    b = apply_multiplicative_return_shocks(
        list(base),
        random.Random(42),
        single_day_gross_multiplier=0.9,
        three_day_run_gross_multiplier=0.95,
    )
    assert a == b


def test_apply_shocks_skips_run_when_horizon_too_short() -> None:
    base = [0.0, 0.01]
    out = apply_multiplicative_return_shocks(
        list(base),
        random.Random(0),
        three_day_run_gross_multiplier=0.5,
        single_day_gross_multiplier=None,
    )
    assert out == base


def test_monte_carlo_shocks_do_not_change_bootstrap_stream() -> None:
    """Misma semilla e histórico: sin shock y con shock comparten muestreo base."""
    hist = [0.012, -0.008, 0.011, -0.009, 0.01] * 10
    plain = monte_carlo_max_drawdown_study(hist, n_paths=100, horizon=15, seed=777)
    cfg = MonteCarloShockConfig(
        single_day_gross_multiplier=0.92,
        three_day_run_gross_multiplier=0.88,
    )
    stressed = monte_carlo_max_drawdown_study(
        hist, n_paths=100, horizon=15, seed=777, shocks=cfg
    )
    assert stressed.mean_max_drawdown >= plain.mean_max_drawdown - 1e-12
    assert stressed.worst_max_drawdown >= plain.worst_max_drawdown - 1e-12
    assert stressed.shock_single_day_gross_multiplier == 0.92
    assert stressed.shock_three_day_run_gross_multiplier == 0.88
    assert plain.shock_single_day_gross_multiplier is None
    assert plain.shock_three_day_run_gross_multiplier is None
    assert plain.bootstrap_mode == "iid"
    assert plain.block_size is None


def test_study_without_shocks_reports_none_echo_fields() -> None:
    hist = [0.01, -0.01, 0.02] * 15
    s = monte_carlo_max_drawdown_study(
        hist, n_paths=20, horizon=12, seed=3, shocks=None
    )
    assert s.shock_single_day_gross_multiplier is None
    assert s.shock_three_day_run_gross_multiplier is None
