"""TDD: decide_grid_action — tolerancia = fracción del spacing + Δnivel ≥ 1.

MM 2026-08-26 / RCA §18: range×10% permitía RT intra-nivel (cost_ratio absurdo).
Paper-only. PROMOTE_LIVE: NO.
"""

from __future__ import annotations

from app.services.grid_strategy import (
    calculate_grid_levels,
    decide_grid_action,
    DEFAULT_TOL_FRAC_OF_SPACING,
)


# N10-like: ±5% around 2459.72 → ~10 levels, spacing ~100 bps
N10_LEVELS = calculate_grid_levels(2336.73, 2582.70, 10)


def test_tolerance_default_is_frac_of_spacing_not_range():
    assert DEFAULT_TOL_FRAC_OF_SPACING == 0.25
    # range×0.10 ≈ spacing entero; con 0.25×spacing la zona es 4× más chica
    spacing = N10_LEVELS[5] - N10_LEVELS[4]
    range_size = N10_LEVELS[-1] - N10_LEVELS[0]
    assert spacing * 0.25 < range_size * 0.10 * 0.5


def test_after_buy_same_level_no_sell():
    """Tras BUY en L_i, precio aún en L_i ± 0.3·spacing → no SELL."""
    buy_level = N10_LEVELS[4]
    spacing = N10_LEVELS[5] - N10_LEVELS[4]
    price = buy_level + 0.2 * spacing
    out = decide_grid_action(
        price, N10_LEVELS, last_action="BUY", last_level=buy_level
    )
    assert out["action"] is None


def test_after_buy_next_level_sells():
    """Tras BUY en L_i, precio en L_{i+1} → SELL."""
    buy_level = N10_LEVELS[4]
    next_level = N10_LEVELS[5]
    out = decide_grid_action(
        next_level, N10_LEVELS, last_action="BUY", last_level=buy_level
    )
    assert out["action"] == "SELL"
    assert out["level"] == next_level


def test_oscillation_half_spacing_zero_closes():
    """Oscilación < 0.5 spacing tras BUY → 0 señales de cierre."""
    buy_level = N10_LEVELS[4]
    spacing = N10_LEVELS[5] - N10_LEVELS[4]
    for delta in (-0.4 * spacing, -0.1 * spacing, 0.0, 0.1 * spacing, 0.4 * spacing):
        price = buy_level + delta
        if price < N10_LEVELS[0] or price > N10_LEVELS[-1]:
            continue
        out = decide_grid_action(
            price, N10_LEVELS, last_action="BUY", last_level=buy_level
        )
        assert out["action"] is None, f"price={price} unexpected {out}"


def test_full_spacing_move_allows_gross_capture_path():
    """≥1 spacing arriba del BUY → SELL (gross de diseño ~100 bps antes de costos)."""
    buy_level = N10_LEVELS[3]
    sell_level = N10_LEVELS[4]
    assert sell_level > buy_level
    out = decide_grid_action(
        sell_level, N10_LEVELS, last_action="BUY", last_level=buy_level
    )
    assert out["action"] == "SELL"
    bps = (sell_level / buy_level - 1.0) * 10_000
    assert bps > 80  # ~100 bps log-spacing


def test_after_sell_requires_level_down_for_buy():
    sell_level = N10_LEVELS[5]
    same = decide_grid_action(
        sell_level, N10_LEVELS, last_action="SELL", last_level=sell_level
    )
    assert same["action"] is None
    down = N10_LEVELS[4]
    out = decide_grid_action(
        down, N10_LEVELS, last_action="SELL", last_level=sell_level
    )
    assert out["action"] == "BUY"
    assert out["level"] == down


def test_outside_range_none():
    assert decide_grid_action(1000.0, N10_LEVELS)["action"] is None


def test_no_history_near_level_opens_by_side():
    level = N10_LEVELS[4]
    spacing = N10_LEVELS[5] - N10_LEVELS[4]
    buy = decide_grid_action(level - 0.1 * spacing, N10_LEVELS, last_action=None)
    assert buy["action"] == "BUY"
    sell = decide_grid_action(level + 0.1 * spacing, N10_LEVELS, last_action=None)
    assert sell["action"] == "SELL"


def test_legacy_hydrate_path_with_last_level_1900():
    """Compat test_last_action: BUY en 1900, precio ~1910 → SELL (Δnivel=1)."""
    levels = [1900.0, 1910.0, 1920.0]
    out = decide_grid_action(1909.0, levels, last_action="BUY", last_level=1900.0)
    assert out["action"] == "SELL"
    assert out["level"] == 1910.0
    same = decide_grid_action(1909.0, levels, last_action="BUY", last_level=1910.0)
    assert same["action"] is None
