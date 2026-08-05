"""P1: moving block bootstrap para Monte Carlo drawdown (protocolo §5.2)."""

from __future__ import annotations

import pytest

from app.research.monte_carlo_paths import monte_carlo_max_drawdown_study


def test_block_bootstrap_requires_block_size() -> None:
    hist = [0.01, -0.02, 0.015] * 10
    with pytest.raises(ValueError, match="block_size"):
        monte_carlo_max_drawdown_study(
            hist,
            n_paths=5,
            horizon=10,
            seed=1,
            bootstrap_mode="block",
        )


def test_block_bootstrap_reproducible() -> None:
    hist = [0.012, -0.008, 0.011, -0.009, 0.01] * 12
    a = monte_carlo_max_drawdown_study(
        hist,
        n_paths=80,
        horizon=15,
        seed=999,
        bootstrap_mode="block",
        block_size=4,
    )
    b = monte_carlo_max_drawdown_study(
        hist,
        n_paths=80,
        horizon=15,
        seed=999,
        bootstrap_mode="block",
        block_size=4,
    )
    assert a.mean_max_drawdown == b.mean_max_drawdown
    assert a.p95_max_drawdown == b.p95_max_drawdown


def test_block_metadata_on_study() -> None:
    hist = [0.01, -0.01, 0.02] * 20
    s = monte_carlo_max_drawdown_study(
        hist,
        n_paths=10,
        horizon=14,
        seed=2,
        bootstrap_mode="block",
        block_size=5,
    )
    assert s.bootstrap_mode == "block"
    assert s.block_size == 5


def test_iid_default_metadata() -> None:
    hist = [0.01, -0.01, 0.02] * 15
    s = monte_carlo_max_drawdown_study(hist, n_paths=5, horizon=10, seed=3)
    assert s.bootstrap_mode == "iid"
    assert s.block_size is None
