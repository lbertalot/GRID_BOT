"""Tests mínimos del motor de backtest de spacing (paper research)."""

from __future__ import annotations

from app.research.grid_backtest import Bar, CostModel, run_grid_backtest


def _synth_range(n: int = 200, mid: float = 2500.0, amp: float = 0.02) -> list[Bar]:
    """Seno lateral ±amp para forzar RT de grid."""
    import math

    bars = []
    for i in range(n):
        phase = 2 * math.pi * i / 40
        c = mid * (1.0 + amp * math.sin(phase))
        h = c * 1.002
        lo = c * 0.998
        bars.append(Bar(ts=float(i * 300), open=c, high=h, low=lo, close=c))
    return bars


def test_wider_spacing_beats_subcost_spacing_on_net():
    bars = _synth_range()
    cost = CostModel(10.0, 2.0)  # 24 bps RT
    thin = run_grid_backtest(bars, spacing_bps=25.0, cost=cost, notional_usdt=20.0)
    wide = run_grid_backtest(bars, spacing_bps=100.0, cost=cost, notional_usdt=20.0)
    assert wide.mean_capture_bps >= 99.0
    assert thin.cost_rt_bps == 24.0
    assert wide.net_pnl > thin.net_pnl


def test_level_step_raises_capture_vs_whipsaw():
    bars = _synth_range(n=300, amp=0.03)
    cost = CostModel()
    stepped = run_grid_backtest(
        bars, spacing_bps=100.0, cost=cost, require_level_step=True
    )
    whip = run_grid_backtest(
        bars,
        spacing_bps=100.0,
        cost=cost,
        require_level_step=False,
        whipsaw_capture_bps=5.0,
    )
    assert stepped.mean_capture_bps >= 99.0
    assert whip.mean_capture_bps <= 6.0
    assert stepped.net_pnl > whip.net_pnl


def test_cost_model_rt_bps():
    assert CostModel().rt_bps == 24.0
