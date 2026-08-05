"""
Inyección de shocks multiplicativos en trayectorias de retornos simples.

Protocolo: `Docs/PROTOCOL_PASSIVE_INCOME_BOT_V1_ARCHITECTURE.md` §5.2
(−X% día único, −Y% tres días consecutivos) modelados como
`(1 + r_t) *= m` con `m ∈ (0, 1]`.
"""

from __future__ import annotations

import random
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MonteCarloShockConfig(BaseModel):
    """Configuración de perturbaciones adversas sobre una trayectoria muestreada."""

    model_config = ConfigDict(frozen=True)

    single_day_gross_multiplier: Optional[float] = Field(
        default=None,
        description="Multiplica (1+r) en un índice aleatorio unico [0, horizon).",
    )
    three_day_run_gross_multiplier: Optional[float] = Field(
        default=None,
        description="Multiplica (1+r) en tres barras consecutivas aleatorias.",
    )

    @field_validator("single_day_gross_multiplier", "three_day_run_gross_multiplier")
    @classmethod
    def _mult_in_open_zero_one(cls, value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        v = float(value)
        if not 0.0 < v <= 1.0:
            raise ValueError("gross multiplier debe estar en (0, 1]")
        return v


def apply_multiplicative_return_shocks(
    path_returns: list[float],
    rng: random.Random,
    *,
    single_day_gross_multiplier: Optional[float] = None,
    three_day_run_gross_multiplier: Optional[float] = None,
) -> list[float]:
    """
    Copia la trayectoria y aplica shocks en retornos simples.

    Orden: primero racha de 3 días (si aplica y horizon >= 3), luego día único.
    Índices aleatorios independientes del mismo `rng` (consumen entropía en orden).
    """
    if single_day_gross_multiplier is not None and not (
        0.0 < float(single_day_gross_multiplier) <= 1.0
    ):
        raise ValueError("single_day_gross_multiplier debe estar en (0, 1]")
    if three_day_run_gross_multiplier is not None and not (
        0.0 < float(three_day_run_gross_multiplier) <= 1.0
    ):
        raise ValueError("three_day_run_gross_multiplier debe estar en (0, 1]")

    out = [float(x) for x in path_returns]
    h = len(out)
    if h == 0:
        return out

    if three_day_run_gross_multiplier is not None and h >= 3:
        mult = float(three_day_run_gross_multiplier)
        start = rng.randint(0, h - 3)
        for j in range(start, start + 3):
            out[j] = (1.0 + out[j]) * mult - 1.0

    if single_day_gross_multiplier is not None:
        mult = float(single_day_gross_multiplier)
        idx = rng.randint(0, h - 1)
        out[idx] = (1.0 + out[idx]) * mult - 1.0

    return out
