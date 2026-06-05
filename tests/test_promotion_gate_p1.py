"""Tests P1: gating de promoción ML (TQS + Monte Carlo opcional)."""

from __future__ import annotations

from app.research.monte_carlo_paths import MonteCarloDrawdownStudy
from app.research.promotion_gate import (
    AfterCostBacktestSnapshot,
    PromotionGateConfig,
    evaluate_promotion_gate,
)
from app.research.tqs_minimal import TqsSnapshot, build_tqs_snapshot


def _snapshot_uptrend() -> TqsSnapshot:
    closes = [100.0 + i * 0.4 for i in range(30)]
    return build_tqs_snapshot(closes)


def _snapshot_flat() -> TqsSnapshot:
    return build_tqs_snapshot([100.0] * 30)


def test_gate_allows_when_no_rules_trigger() -> None:
    tqs = _snapshot_uptrend()
    cfg = PromotionGateConfig(
        block_if_direction_flat=False,
        min_abs_combined=None,
        max_p95_drawdown=None,
        require_monte_carlo=False,
    )
    r = evaluate_promotion_gate(tqs, None, cfg)
    assert r.allowed is True
    assert r.block_reasons == ()


def test_gate_blocks_flat_when_configured() -> None:
    tqs = _snapshot_flat()
    cfg = PromotionGateConfig(block_if_direction_flat=True)
    r = evaluate_promotion_gate(tqs, None, cfg)
    assert r.allowed is False
    assert "tqs_direction_flat" in r.block_reasons


def test_gate_blocks_weak_combined() -> None:
    tqs = _snapshot_flat()
    cfg = PromotionGateConfig(
        block_if_direction_flat=False,
        min_abs_combined=0.5,
    )
    r = evaluate_promotion_gate(tqs, None, cfg)
    assert r.allowed is False
    assert "tqs_combined_too_weak" in r.block_reasons


def test_gate_blocks_when_mc_required_missing() -> None:
    tqs = _snapshot_uptrend()
    cfg = PromotionGateConfig(
        block_if_direction_flat=False,
        require_monte_carlo=True,
    )
    r = evaluate_promotion_gate(tqs, None, cfg)
    assert r.allowed is False
    assert "monte_carlo_required_missing" in r.block_reasons


def test_gate_blocks_p95_above_cap() -> None:
    tqs = _snapshot_uptrend()
    mc = MonteCarloDrawdownStudy(
        seed=1,
        n_paths=10,
        horizon=5,
        baseline_max_drawdown=0.2,
        mean_max_drawdown=0.2,
        p95_max_drawdown=0.9,
        worst_max_drawdown=0.95,
    )
    cfg = PromotionGateConfig(
        block_if_direction_flat=False,
        max_p95_drawdown=0.5,
    )
    r = evaluate_promotion_gate(tqs, mc, cfg)
    assert r.allowed is False
    assert "monte_carlo_p95_exceeds_cap" in r.block_reasons


def test_gate_allows_p95_below_cap() -> None:
    tqs = _snapshot_uptrend()
    mc = MonteCarloDrawdownStudy(
        seed=1,
        n_paths=10,
        horizon=5,
        baseline_max_drawdown=0.05,
        mean_max_drawdown=0.06,
        p95_max_drawdown=0.08,
        worst_max_drawdown=0.1,
    )
    cfg = PromotionGateConfig(
        block_if_direction_flat=False,
        max_p95_drawdown=0.5,
    )
    r = evaluate_promotion_gate(tqs, mc, cfg)
    assert r.allowed is True


def test_gate_blocks_when_backtest_required_missing() -> None:
    tqs = _snapshot_uptrend()
    cfg = PromotionGateConfig(
        block_if_direction_flat=False,
        require_after_cost_backtest=True,
    )
    r = evaluate_promotion_gate(tqs, None, cfg, after_cost=None)
    assert r.allowed is False
    assert "after_cost_backtest_required_missing" in r.block_reasons


def test_gate_blocks_when_sharpe_below_min() -> None:
    tqs = _snapshot_uptrend()
    ac = AfterCostBacktestSnapshot(sharpe_ratio=0.2, max_drawdown=-0.05)
    cfg = PromotionGateConfig(
        block_if_direction_flat=False,
        min_sharpe_after_cost=0.5,
    )
    r = evaluate_promotion_gate(tqs, None, cfg, after_cost=ac)
    assert r.allowed is False
    assert "after_cost_sharpe_below_min" in r.block_reasons


def test_gate_blocks_when_sharpe_unavailable_but_min_set() -> None:
    tqs = _snapshot_uptrend()
    ac = AfterCostBacktestSnapshot(sharpe_ratio=None)
    cfg = PromotionGateConfig(
        block_if_direction_flat=False,
        min_sharpe_after_cost=0.5,
    )
    r = evaluate_promotion_gate(tqs, None, cfg, after_cost=ac)
    assert r.allowed is False
    assert "after_cost_sharpe_unavailable" in r.block_reasons


def test_gate_mc_p95_exceeds_backtest_dd_ratio() -> None:
    tqs = _snapshot_uptrend()
    mc = MonteCarloDrawdownStudy(
        seed=1,
        n_paths=10,
        horizon=5,
        baseline_max_drawdown=0.05,
        mean_max_drawdown=0.06,
        p95_max_drawdown=0.5,
        worst_max_drawdown=0.6,
    )
    ac = AfterCostBacktestSnapshot(max_drawdown=-0.05)
    cfg = PromotionGateConfig(
        block_if_direction_flat=False,
        mc_p95_to_backtest_dd_max_ratio=3.0,
    )
    r = evaluate_promotion_gate(tqs, mc, cfg, after_cost=ac)
    assert r.allowed is False
    assert "mc_p95_exceeds_backtest_dd_ratio" in r.block_reasons


def test_gate_allows_mc_p95_within_backtest_dd_ratio() -> None:
    tqs = _snapshot_uptrend()
    mc = MonteCarloDrawdownStudy(
        seed=1,
        n_paths=10,
        horizon=5,
        baseline_max_drawdown=0.05,
        mean_max_drawdown=0.06,
        p95_max_drawdown=0.12,
        worst_max_drawdown=0.2,
    )
    ac = AfterCostBacktestSnapshot(max_drawdown=-0.05)
    cfg = PromotionGateConfig(
        block_if_direction_flat=False,
        mc_p95_to_backtest_dd_max_ratio=3.0,
    )
    r = evaluate_promotion_gate(tqs, mc, cfg, after_cost=ac)
    assert r.allowed is True


def test_gate_blocks_sentiment_below_min() -> None:
    tqs = _snapshot_uptrend()
    cfg = PromotionGateConfig(
        block_if_direction_flat=False,
        min_sentiment_score=-0.2,
    )
    r = evaluate_promotion_gate(tqs, None, cfg, sentiment_score=-0.9)
    assert r.allowed is False
    assert "nlp_sentiment_below_min" in r.block_reasons


def test_gate_allows_sentiment_at_min_boundary() -> None:
    tqs = _snapshot_uptrend()
    cfg = PromotionGateConfig(
        block_if_direction_flat=False,
        min_sentiment_score=-0.2,
    )
    r = evaluate_promotion_gate(tqs, None, cfg, sentiment_score=-0.2)
    assert r.allowed is True


def test_gate_blocks_when_sentiment_missing_required() -> None:
    tqs = _snapshot_uptrend()
    cfg = PromotionGateConfig(
        block_if_direction_flat=False,
        block_if_sentiment_missing=True,
    )
    r = evaluate_promotion_gate(tqs, None, cfg, sentiment_score=None)
    assert r.allowed is False
    assert "nlp_sentiment_unavailable" in r.block_reasons


def test_gate_allows_missing_sentiment_when_min_set_but_not_required() -> None:
    tqs = _snapshot_uptrend()
    cfg = PromotionGateConfig(
        block_if_direction_flat=False,
        min_sentiment_score=-0.5,
    )
    r = evaluate_promotion_gate(tqs, None, cfg, sentiment_score=None)
    assert r.allowed is True
