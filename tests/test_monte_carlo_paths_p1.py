"""P1: Monte Carlo drawdown bootstrap con semilla fija."""

from __future__ import annotations

import pytest

from app.research.monte_carlo_paths import (
    max_drawdown_from_simple_returns,
    monte_carlo_max_drawdown_study,
)


def test_max_drawdown_no_loss_is_zero() -> None:
    assert max_drawdown_from_simple_returns([0.01, 0.0, 0.02]) == 0.0


def test_max_drawdown_detects_drop() -> None:
    dd = max_drawdown_from_simple_returns([-0.5, 0.0, 0.0])
    assert dd > 0.4


def test_max_drawdown_empty_raises() -> None:
    with pytest.raises(ValueError, match="vacío"):
        max_drawdown_from_simple_returns([])


def test_monte_carlo_reproducible_with_seed() -> None:
    hist = [0.01, -0.02, 0.005, -0.01, 0.02, -0.015, 0.0, 0.01] * 5
    a = monte_carlo_max_drawdown_study(hist, n_paths=200, horizon=30, seed=424242)
    b = monte_carlo_max_drawdown_study(hist, n_paths=200, horizon=30, seed=424242)
    assert a.mean_max_drawdown == b.mean_max_drawdown
    assert a.p95_max_drawdown == b.p95_max_drawdown
    assert a.worst_max_drawdown == b.worst_max_drawdown


def test_monte_carlo_order_statistics() -> None:
    hist = [0.02, -0.03, 0.01, -0.04, 0.015] * 10
    study = monte_carlo_max_drawdown_study(hist, n_paths=500, horizon=25, seed=7)
    assert 0.0 <= study.mean_max_drawdown <= 1.0
    assert 0.0 <= study.p95_max_drawdown <= 1.0
    assert study.worst_max_drawdown >= study.p95_max_drawdown - 1e-12
    assert study.worst_max_drawdown >= study.mean_max_drawdown - 1e-12


def test_monte_carlo_requires_sufficient_history() -> None:
    with pytest.raises(ValueError, match="horizon"):
        monte_carlo_max_drawdown_study([0.01, -0.01], n_paths=10, horizon=50, seed=1)


def test_research_package_exports() -> None:
    from app import research

    assert hasattr(research, "build_tqs_snapshot")
    assert hasattr(research, "monte_carlo_max_drawdown_study")
    assert hasattr(research, "MonteCarloShockConfig")
    assert hasattr(research, "apply_multiplicative_return_shocks")
