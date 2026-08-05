"""
Sentimiento opcional para el gate de promoción ML (Fase C, sin tablas G3).

Un worker o proceso externo puede publicar en Redis::

    SET gridbot:tqs_sentiment:BTCUSDT '{"score": 0.12}'

``score`` en ``[-1, 1]``. Sin modelo NLP embebido en el hot path del ciclo.
El caller activa lectura con ``ML_PROMOTION_GATE_NLP_ENABLED`` (gate) y/o
``KELLY_SENTIMENT_SCALE_ENABLED`` (escala Kelly fraccional).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

REDIS_KEY_PREFIX = "gridbot:tqs_sentiment:"


def _parse_score_payload(raw: Any) -> Optional[float]:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        stripped = raw.strip()
        if not stripped:
            return None
        try:
            return float(stripped)
        except ValueError:
            try:
                obj = json.loads(stripped)
                if isinstance(obj, dict) and "score" in obj:
                    return float(obj["score"])
            except (json.JSONDecodeError, TypeError, KeyError, ValueError):
                return None
    if isinstance(raw, dict) and "score" in raw:
        try:
            return float(raw["score"])
        except (TypeError, ValueError):
            return None
    return None


def _clamp_unit_interval_sentiment(value: float) -> float:
    return max(-1.0, min(1.0, value))


async def resolve_promotion_gate_sentiment_score(symbol: str) -> Optional[float]:
    """
    Lee score de sentimiento para el símbolo (Redis), con fallback opcional por env.

    También puede usarse con ``KELLY_SENTIMENT_SCALE_ENABLED=true`` para escalar
    Kelly fraccional. Con el gate NLP, el caller suele leer sólo cuando hace falta
    el score (evita I/O innecesario).
    """
    sym = symbol.strip().upper()
    if not sym:
        return None

    key = f"{REDIS_KEY_PREFIX}{sym}"
    try:
        from app.core.redis_cache import redis_cache

        cached = await redis_cache.get(key)
        score = _parse_score_payload(cached)
        if score is not None:
            return _clamp_unit_interval_sentiment(score)
    except Exception as exc:
        logger.debug(
            "[Cycle] promotion gate sentiment cache read failed",
            extra={"symbol": sym, "error": str(exc)},
        )

    stub = os.getenv("ML_PROMOTION_GATE_NLP_STUB_SCORE", "").strip()
    if not stub:
        return None
    try:
        return _clamp_unit_interval_sentiment(float(stub))
    except ValueError:
        return None


def kelly_multiplier_from_sentiment_score(
    score: Optional[float],
    *,
    mult_at_minus_one: float,
    mult_at_plus_one: float,
    mult_if_missing: float = 1.0,
) -> float:
    """
    Multiplicador acotado para Kelly fraccional a partir de sentimiento en [-1, 1].

    - score -1 → ``mult_at_minus_one``
    - score +1 → ``mult_at_plus_one``
    - interpolación lineal entre ambos
    - ``score is None`` → ``mult_if_missing`` (sin leer Redis aquí)

    Todos los multiplicadores devueltos son > 0 si los argumentos son > 0.
    """
    if mult_at_minus_one <= 0 or mult_at_plus_one <= 0:
        raise ValueError(
            "mult_at_minus_one and mult_at_plus_one must be strictly positive"
        )
    if mult_if_missing <= 0:
        raise ValueError("mult_if_missing must be strictly positive")
    if score is None:
        return float(mult_if_missing)
    clamped = _clamp_unit_interval_sentiment(float(score))
    if clamped <= -1.0:
        return float(mult_at_minus_one)
    if clamped >= 1.0:
        return float(mult_at_plus_one)
    midpoint = (clamped + 1.0) / 2.0
    return float(mult_at_minus_one + midpoint * (mult_at_plus_one - mult_at_minus_one))
