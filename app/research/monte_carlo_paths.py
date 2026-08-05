"""
Monte Carlo ligero — stress de drawdown vía bootstrap de retornos simples.

Alineado a `Docs/PROTOCOL_PASSIVE_INCOME_BOT_V1_ARCHITECTURE.md` §5.2 (versión mínima
sin dependencias de backtest pesado). Semilla fija para tests reproducibles.
"""

from __future__ import annotations

import math
import random
from typing import Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field

from app.research.monte_carlo_shocks import (
    MonteCarloShockConfig,
    apply_multiplicative_return_shocks,
)


class MonteCarloDrawdownStudy(BaseModel):
    model_config = ConfigDict(frozen=True)

    seed: int
    n_paths: int
    horizon: int
    baseline_max_drawdown: float = Field(
        description="Max drawdown de la serie histórica original (misma longitud que horizon)"
    )
    mean_max_drawdown: float
    p95_max_drawdown: float
    worst_max_drawdown: float
    shock_single_day_gross_multiplier: float | None = Field(
        default=None,
        description="Multiplicador shock día único aplicado en trayectorias (si hubo).",
    )
    shock_three_day_run_gross_multiplier: float | None = Field(
        default=None,
        description="Multiplicador shock racha 3 días (si hubo).",
    )
    bootstrap_mode: Literal["iid", "block"] = Field(
        default="iid",
        description="iid: remuestreo con reemplazo barra a barra; block: bloques contiguos.",
    )
    block_size: int | None = Field(
        default=None,
        description="Longitud de bloque si bootstrap_mode=block; None si iid.",
    )


def _mix_seed(seed: int, path_index: int) -> int:
    """Semilla derivada por trayectoria: shocks no alteran muestreo bootstrap."""
    return (int(seed) ^ (int(path_index) * 0x9E3779B9)) & 0x7FFFFFFF


def _sample_path_iid(
    hist: list[float],
    horizon: int,
    rng: random.Random,
) -> list[float]:
    return [rng.choice(hist) for _ in range(horizon)]


def _sample_path_moving_block(
    hist: list[float],
    horizon: int,
    block_size: int,
    rng: random.Random,
) -> list[float]:
    """Bootstrap por bloques contiguos (moving block); preserva dependencia temporal corta."""
    n = len(hist)
    if block_size < 1:
        raise ValueError("block_size debe ser >= 1")
    if block_size > n:
        raise ValueError("block_size no puede exceder len(historical_returns)")
    max_start = n - block_size
    out: list[float] = []
    while len(out) < horizon:
        start = rng.randint(0, max_start)
        out.extend(hist[start : start + block_size])
    return out[:horizon]


def max_drawdown_from_simple_returns(
    returns: Sequence[float],
    *,
    initial_equity: float = 1.0,
) -> float:
    """
    Drawdown máximo sobre curva de equity multiplicativa (1+r_i).
    Retorna valor en [0, 1] como fracción del pico.
    """
    if initial_equity <= 0.0:
        raise ValueError("initial_equity debe ser positivo")
    if len(returns) == 0:
        raise ValueError("returns no puede ser vacío")

    equity = float(initial_equity)
    peak = equity
    max_dd = 0.0
    for r in returns:
        equity *= 1.0 + float(r)
        if equity > peak:
            peak = equity
        if peak > 0.0:
            dd = (peak - equity) / peak
            if dd > max_dd:
                max_dd = dd
    return float(max_dd)


def _percentile_nearest_rank(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        raise ValueError("lista vacía")
    if not 0.0 <= q <= 1.0:
        raise ValueError("q debe estar en [0, 1]")
    n = len(sorted_values)
    rank = int(math.ceil(q * n)) - 1
    rank = max(0, min(rank, n - 1))
    return sorted_values[rank]


def monte_carlo_max_drawdown_study(
    historical_returns: Sequence[float],
    *,
    n_paths: int,
    horizon: int,
    seed: int,
    shocks: MonteCarloShockConfig | None = None,
    bootstrap_mode: Literal["iid", "block"] = "iid",
    block_size: int | None = None,
) -> MonteCarloDrawdownStudy:
    """
    Remuestreo de retornos con trayectorias de longitud `horizon` y distribución
    empírica de max drawdown.

    - ``bootstrap_mode="iid"``: con reemplazo barra a bara (default).
    - ``bootstrap_mode="block"``: moving block bootstrap (§5.2); requiere ``block_size``.

    ``shocks`` (opcional): perturbaciones §5.2; RNG de shocks por trayectoria no altera
    el stream del bootstrap principal (semilla base idéntica ⇒ mismas muestras IID/block
    antes de aplicar shocks).
    """
    hist = [float(x) for x in historical_returns]
    if len(hist) == 0:
        raise ValueError("historical_returns no puede ser vacío")
    if horizon < 1:
        raise ValueError("horizon debe ser >= 1")
    if n_paths < 1:
        raise ValueError("n_paths debe ser >= 1")
    if len(hist) < horizon:
        raise ValueError(
            "historical_returns debe tener longitud >= horizon para baseline y muestreo"
        )
    if bootstrap_mode == "block":
        if block_size is None:
            raise ValueError("block_size es obligatorio cuando bootstrap_mode='block'")
        if block_size < 1 or block_size > len(hist):
            raise ValueError("block_size debe estar en [1, len(historical_returns)]")
    if bootstrap_mode not in ("iid", "block"):
        raise ValueError("bootstrap_mode debe ser 'iid' o 'block'")

    rng = random.Random(seed)
    paths_dd: list[float] = []
    use_shocks = shocks is not None and (
        shocks.single_day_gross_multiplier is not None
        or shocks.three_day_run_gross_multiplier is not None
    )
    for path_index in range(n_paths):
        if bootstrap_mode == "iid":
            sampled = _sample_path_iid(hist, horizon, rng)
        else:
            sampled = _sample_path_moving_block(hist, horizon, int(block_size), rng)
        if use_shocks and shocks is not None:
            shock_rng = random.Random(_mix_seed(seed, path_index))
            sampled = apply_multiplicative_return_shocks(
                sampled,
                shock_rng,
                single_day_gross_multiplier=shocks.single_day_gross_multiplier,
                three_day_run_gross_multiplier=shocks.three_day_run_gross_multiplier,
            )
        paths_dd.append(max_drawdown_from_simple_returns(sampled))

    baseline_dd = max_drawdown_from_simple_returns(hist[-horizon:])

    paths_dd_sorted = sorted(paths_dd)
    mean_dd = sum(paths_dd) / float(len(paths_dd))
    p95 = _percentile_nearest_rank(paths_dd_sorted, 0.95)
    worst = paths_dd_sorted[-1]

    shock_1 = shocks.single_day_gross_multiplier if shocks is not None else None
    shock_3 = shocks.three_day_run_gross_multiplier if shocks is not None else None
    bs = block_size if bootstrap_mode == "block" else None

    return MonteCarloDrawdownStudy(
        seed=seed,
        n_paths=n_paths,
        horizon=horizon,
        baseline_max_drawdown=baseline_dd,
        mean_max_drawdown=mean_dd,
        p95_max_drawdown=p95,
        worst_max_drawdown=worst,
        shock_single_day_gross_multiplier=shock_1,
        shock_three_day_run_gross_multiplier=shock_3,
        bootstrap_mode=bootstrap_mode,
        block_size=bs,
    )
