"""
Gating de promoción ML: combina TQS mínimo y (opcional) estudio Monte Carlo drawdown.

Solo lógica pura; sin I/O. El ciclo de trading puede llamar antes de confiar en Hybrid ML.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.research.monte_carlo_paths import MonteCarloDrawdownStudy
from app.research.tqs_minimal import TqsSnapshot


class AfterCostBacktestSnapshot(BaseModel):
    """Métricas escalares de un backtest after-cost (p. ej. persistido o API)."""

    model_config = ConfigDict(frozen=True)

    sharpe_ratio: Optional[float] = Field(
        default=None, description="Sharpe de la corrida after-cost"
    )
    max_drawdown: Optional[float] = Field(
        default=None,
        description="Drawdown como en el motor (vectorbt); se usa abs() para topes.",
    )
    total_return: Optional[float] = Field(
        default=None, description="Retorno total de la corrida after-cost"
    )


class PromotionGateConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    block_if_direction_flat: bool = Field(
        default=True, description="Bloquear si TQS indica mercado lateral"
    )
    min_abs_combined: Optional[float] = Field(
        default=None,
        description="Si |combined| estrictamente menor que este umbral → bloqueo",
    )
    max_p95_drawdown: Optional[float] = Field(
        default=None,
        description="Si hay estudio MC y p95_max_drawdown > este valor → bloqueo [0,1]",
    )
    require_monte_carlo: bool = Field(
        default=False,
        description="Exigir que se haya calculado MonteCarloDrawdownStudy",
    )
    require_after_cost_backtest: bool = Field(
        default=False,
        description="Exigir snapshot after-cost (backtest persistido u override)",
    )
    min_sharpe_after_cost: Optional[float] = Field(
        default=None,
        description="Bloquear si sharpe after-cost existe y es menor (si no hay sharpe, bloqueo)",
    )
    max_backtest_drawdown_magnitude: Optional[float] = Field(
        default=None,
        description="Magnitud máxima permitida abs(drawdown); bloquear si la corrida es peor",
    )
    min_total_return_after_cost: Optional[float] = Field(
        default=None,
        description="Bloquear si total_return after-cost < este umbral (requiere valor conocido)",
    )
    mc_p95_to_backtest_dd_max_ratio: Optional[float] = Field(
        default=None,
        description=(
            "Alineación MC ↔ backtest: bloquear si p95_MC > ratio * abs(dd_backtest). "
            "Sólo si hay MC, snapshot con DD y ratio > 0"
        ),
    )
    min_sentiment_score: Optional[float] = Field(
        default=None,
        description=(
            "Sentimiento en [-1, 1] (p. ej. desde Redis). "
            "Bloquear si el score existe y es estrictamente menor que este umbral."
        ),
    )
    block_if_sentiment_missing: bool = Field(
        default=False,
        description="Si True y no hay score de sentimiento → bloqueo",
    )


class PromotionGateResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    allowed: bool
    block_reasons: tuple[str, ...] = ()


def evaluate_promotion_gate(
    tqs: TqsSnapshot,
    mc_study: MonteCarloDrawdownStudy | None,
    config: PromotionGateConfig,
    after_cost: AfterCostBacktestSnapshot | None = None,
    *,
    sentiment_score: Optional[float] = None,
) -> PromotionGateResult:
    """Evalúa reglas de negocio mínimas para permitir régimen ML híbrido."""
    reasons: list[str] = []

    if config.block_if_direction_flat and tqs.direction == "flat":
        reasons.append("tqs_direction_flat")

    if config.min_abs_combined is not None:
        if abs(tqs.combined_score) < config.min_abs_combined:
            reasons.append("tqs_combined_too_weak")

    if config.require_monte_carlo and mc_study is None:
        reasons.append("monte_carlo_required_missing")

    if config.max_p95_drawdown is not None and mc_study is not None:
        if mc_study.p95_max_drawdown > config.max_p95_drawdown:
            reasons.append("monte_carlo_p95_exceeds_cap")

    if config.require_after_cost_backtest and after_cost is None:
        reasons.append("after_cost_backtest_required_missing")

    if after_cost is not None:
        if config.min_sharpe_after_cost is not None:
            if after_cost.sharpe_ratio is None:
                reasons.append("after_cost_sharpe_unavailable")
            elif after_cost.sharpe_ratio < config.min_sharpe_after_cost:
                reasons.append("after_cost_sharpe_below_min")

        if config.max_backtest_drawdown_magnitude is not None:
            if after_cost.max_drawdown is None:
                reasons.append("after_cost_drawdown_unavailable")
            else:
                dd_mag = abs(float(after_cost.max_drawdown))
                if dd_mag > float(config.max_backtest_drawdown_magnitude):
                    reasons.append("after_cost_drawdown_exceeds_cap")

        if config.min_total_return_after_cost is not None:
            if after_cost.total_return is None:
                reasons.append("after_cost_total_return_unavailable")
            elif after_cost.total_return < config.min_total_return_after_cost:
                reasons.append("after_cost_total_return_below_min")

    if (
        config.mc_p95_to_backtest_dd_max_ratio is not None
        and float(config.mc_p95_to_backtest_dd_max_ratio) > 0
        and mc_study is not None
        and after_cost is not None
        and after_cost.max_drawdown is not None
    ):
        bt_mag = abs(float(after_cost.max_drawdown))
        if bt_mag <= 1e-12:
            reasons.append("after_cost_backtest_dd_too_small_for_mc_alignment")
        elif mc_study.p95_max_drawdown > (
            float(config.mc_p95_to_backtest_dd_max_ratio) * bt_mag
        ):
            reasons.append("mc_p95_exceeds_backtest_dd_ratio")

    if config.block_if_sentiment_missing and sentiment_score is None:
        reasons.append("nlp_sentiment_unavailable")

    if config.min_sentiment_score is not None and sentiment_score is not None:
        if sentiment_score < float(config.min_sentiment_score):
            reasons.append("nlp_sentiment_below_min")

    return PromotionGateResult(
        allowed=len(reasons) == 0,
        block_reasons=tuple(reasons),
    )
