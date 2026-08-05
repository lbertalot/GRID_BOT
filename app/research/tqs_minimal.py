"""
TQS mínimo (Técnico + Cuantitativo) sin NLP — alineado a protocolo §1.2.

Funciones puras; sin I/O. Los scores están en [-1, 1] aprox.
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TqsSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    technical_score: float = Field(description="Momentum tipo ROC normalizado")
    quantitative_score: float = Field(
        description="Separación EMA rápida vs lenta normalizada"
    )
    combined_score: float
    direction: Literal["long", "short", "flat"]
    n_closes: int
    roc_lookback: int
    ema_fast_period: int
    ema_slow_period: int


def _ema_last(closes: list[float], span: int) -> float:
    alpha = 2.0 / (float(span) + 1.0)
    ema = closes[0]
    for price in closes[1:]:
        ema = alpha * price + (1.0 - alpha) * ema
    return ema


def compute_roc_score(closes: list[float], lookback: int) -> float:
    """ROC relativo con compresión tanh hacia [-1, 1]."""
    if lookback < 1:
        raise ValueError("lookback debe ser >= 1")
    if len(closes) <= lookback:
        raise ValueError("closes demasiado cortos para el lookback ROC")
    old_px = closes[-1 - lookback]
    new_px = closes[-1]
    if old_px <= 0.0 or new_px <= 0.0:
        return 0.0
    roc = (new_px - old_px) / old_px
    return float(math.tanh(roc * 8.0))


def compute_ema_cross_score(
    closes: list[float], fast_period: int, slow_period: int
) -> float:
    if fast_period < 1 or slow_period < 1:
        raise ValueError("periodos EMA deben ser >= 1")
    if fast_period >= slow_period:
        raise ValueError("EMA rápida debe tener periodo menor que la lenta")
    if len(closes) < slow_period:
        raise ValueError("closes demasiado cortos para EMA lenta")
    ema_fast = _ema_last(closes, fast_period)
    ema_slow = _ema_last(closes, slow_period)
    last = closes[-1]
    if last <= 0.0:
        return 0.0
    spread = (ema_fast - ema_slow) / last
    return float(math.tanh(spread * 5.0))


def _direction_from_combined(
    combined: float, threshold: float
) -> Literal["long", "short", "flat"]:
    if combined > threshold:
        return "long"
    if combined < -threshold:
        return "short"
    return "flat"


def build_tqs_snapshot(
    closes: list[float],
    *,
    roc_lookback: int = 14,
    ema_fast_period: int = 5,
    ema_slow_period: int = 20,
    direction_threshold: float = 0.12,
) -> TqsSnapshot:
    """
    Combina capa técnica (ROC) y cuantitativa (EMA multi-escala).

    NLP queda fuera de alcance (Fase C mínima).
    """
    if direction_threshold <= 0.0:
        raise ValueError("direction_threshold debe ser > 0")

    technical = compute_roc_score(closes, roc_lookback)
    quantitative = compute_ema_cross_score(closes, ema_fast_period, ema_slow_period)
    combined = (technical + quantitative) / 2.0
    direction = _direction_from_combined(combined, direction_threshold)

    return TqsSnapshot(
        technical_score=technical,
        quantitative_score=quantitative,
        combined_score=combined,
        direction=direction,
        n_closes=len(closes),
        roc_lookback=roc_lookback,
        ema_fast_period=ema_fast_period,
        ema_slow_period=ema_slow_period,
    )
