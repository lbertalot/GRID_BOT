"""P1: escala Kelly por sentimiento (función pura + guardas)."""

from __future__ import annotations

import pytest

from app.services.promotion_gate_sentiment import kelly_multiplier_from_sentiment_score


def test_kelly_multiplier_endpoints() -> None:
    m = kelly_multiplier_from_sentiment_score(
        -1.0,
        mult_at_minus_one=0.5,
        mult_at_plus_one=1.5,
    )
    assert m == pytest.approx(0.5)
    m = kelly_multiplier_from_sentiment_score(
        1.0,
        mult_at_minus_one=0.5,
        mult_at_plus_one=1.5,
    )
    assert m == pytest.approx(1.5)


def test_kelly_multiplier_midpoint() -> None:
    m = kelly_multiplier_from_sentiment_score(
        0.0,
        mult_at_minus_one=0.8,
        mult_at_plus_one=1.2,
    )
    assert m == pytest.approx(1.0)


def test_kelly_multiplier_missing_uses_default() -> None:
    m = kelly_multiplier_from_sentiment_score(
        None,
        mult_at_minus_one=0.5,
        mult_at_plus_one=1.5,
        mult_if_missing=0.9,
    )
    assert m == pytest.approx(0.9)


def test_kelly_multiplier_clamps_score() -> None:
    m = kelly_multiplier_from_sentiment_score(
        -5.0,
        mult_at_minus_one=0.7,
        mult_at_plus_one=1.1,
    )
    assert m == pytest.approx(0.7)


def test_kelly_multiplier_rejects_nonpositive() -> None:
    with pytest.raises(ValueError):
        kelly_multiplier_from_sentiment_score(
            0.0,
            mult_at_minus_one=0.0,
            mult_at_plus_one=1.0,
        )
    with pytest.raises(ValueError):
        kelly_multiplier_from_sentiment_score(
            None,
            mult_at_minus_one=1.0,
            mult_at_plus_one=1.0,
            mult_if_missing=0.0,
        )
