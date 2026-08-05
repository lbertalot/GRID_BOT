"""P1: TQS mínimo (ROC + EMA) sin NLP."""

from __future__ import annotations

import pytest

from app.research.tqs_minimal import (
    build_tqs_snapshot,
    compute_ema_cross_score,
    compute_roc_score,
)


def _uptrend_closes(n: int = 40) -> list[float]:
    return [100.0 + float(i) * 0.5 for i in range(n)]


def _flat_closes(n: int = 40) -> list[float]:
    return [100.0] * n


def test_compute_roc_uptrend_positive() -> None:
    closes = _uptrend_closes()
    score = compute_roc_score(closes, lookback=14)
    assert score > 0.2


def test_compute_roc_raises_if_short_series() -> None:
    with pytest.raises(ValueError, match="demasiado cortos"):
        compute_roc_score([100.0, 101.0], lookback=14)


def test_ema_cross_bullish_positive() -> None:
    closes = _uptrend_closes()
    q = compute_ema_cross_score(closes, fast_period=5, slow_period=20)
    assert q > 0.0


def test_build_tqs_snapshot_uptrend_long() -> None:
    snap = build_tqs_snapshot(_uptrend_closes(), direction_threshold=0.05)
    assert snap.direction == "long"
    assert -1.0 <= snap.combined_score <= 1.0


def test_build_tqs_snapshot_flat_is_flat_or_small() -> None:
    snap = build_tqs_snapshot(_flat_closes(), direction_threshold=0.2)
    assert snap.direction == "flat"
    assert abs(snap.combined_score) < 0.05


def test_build_tqs_rejects_bad_threshold() -> None:
    with pytest.raises(ValueError, match="direction_threshold"):
        build_tqs_snapshot(_uptrend_closes(), direction_threshold=0.0)


def test_ema_cross_rejects_fast_ge_slow() -> None:
    with pytest.raises(ValueError, match="rápida"):
        compute_ema_cross_score(_uptrend_closes(), fast_period=20, slow_period=5)
