"""Motor de backtest de grid spot (ETHUSDT) — paper research.

Costo por defecto = PaperCostModel L0 (24 bps RT: 10+10 fee + 2+2 slip).
Sin live. PROMOTE_LIVE: NO.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple


BPS = 10_000.0


@dataclass(frozen=True)
class CostModel:
    fee_bps_per_side: float = 10.0
    slip_bps_per_side: float = 2.0

    @property
    def rt_bps(self) -> float:
        return 2.0 * (self.fee_bps_per_side + self.slip_bps_per_side)

    def cost_usdt(self, notional: float) -> Tuple[float, float]:
        fee = notional * self.fee_bps_per_side / BPS
        slip = notional * self.slip_bps_per_side / BPS
        return fee, slip


@dataclass
class Bar:
    ts: float  # unix
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass
class ClosedTrade:
    side_open: str
    entry: float
    exit: float
    qty: float
    gross: float
    fees: float
    slip: float
    net: float
    ts_open: float
    ts_close: float


@dataclass
class BacktestResult:
    mode: str
    spacing_bps: float
    atr_k: Optional[float]
    notional: float
    n_trades: int
    gross_pnl: float
    net_pnl: float
    win_rate: float
    max_dd: float
    final_equity: float
    cost_rt_bps: float
    mean_capture_bps: float
    params: Dict[str, float] = field(default_factory=dict)


def atr(bars: Sequence[Bar], period: int = 14) -> List[Optional[float]]:
    out: List[Optional[float]] = [None] * len(bars)
    if len(bars) < period + 1:
        return out
    trs: List[float] = []
    for i in range(1, len(bars)):
        prev_c = bars[i - 1].close
        tr = max(
            bars[i].high - bars[i].low,
            abs(bars[i].high - prev_c),
            abs(bars[i].low - prev_c),
        )
        trs.append(tr)
        if len(trs) >= period:
            out[i] = sum(trs[-period:]) / period
    return out


def build_levels(mid: float, spacing_bps: float, n_levels: int = 10) -> List[float]:
    """Niveles geométricos simétricos alrededor de mid (n_levels total, even)."""
    step = spacing_bps / BPS
    half = n_levels // 2
    levels: List[float] = []
    for i in range(-half, half + 1):
        if i == 0:
            continue
        levels.append(mid * ((1.0 + step) ** i))
    return sorted(levels)


def run_grid_backtest(
    bars: Sequence[Bar],
    *,
    spacing_bps: float,
    notional_usdt: float = 20.0,
    n_levels: int = 10,
    initial_cash: float = 1000.0,
    cost: Optional[CostModel] = None,
    mode: str = "fixed",
    atr_k: Optional[float] = None,
    atr_period: int = 14,
    reanchor_every: int = 0,
    require_level_step: bool = True,
    whipsaw_capture_bps: float = 5.0,
) -> BacktestResult:
    """Grid paper.

    ``require_level_step=True`` (default): SELL solo si high ≥ entry*(1+spacing)
    — equivalente al patch Δnivel≥1.

    ``require_level_step=False``: SELL con captura mínima ``whipsaw_capture_bps``
    (proxy del bug pre-patch: RT intra-nivel / ruido).
    """
    cost = cost or CostModel()
    if len(bars) < 20:
        return BacktestResult(
            mode=mode,
            spacing_bps=spacing_bps,
            atr_k=atr_k,
            notional=notional_usdt,
            n_trades=0,
            gross_pnl=0.0,
            net_pnl=0.0,
            win_rate=0.0,
            max_dd=0.0,
            final_equity=initial_cash,
            cost_rt_bps=cost.rt_bps,
            mean_capture_bps=0.0,
        )

    atr_series = atr(bars, atr_period) if atr_k is not None else None
    mid0 = bars[0].close
    eff_spacing = spacing_bps
    if atr_k is not None and atr_series and atr_series[0]:
        eff_spacing = max(
            40.0,
            (atr_series[min(atr_period, len(bars) - 1)] or 0) / mid0 * BPS * atr_k,
        )

    levels = build_levels(mid0, eff_spacing, n_levels)
    inventory: Dict[float, Tuple[float, float, float, float, float]] = {}
    cash = initial_cash
    equity_curve: List[float] = []
    trades: List[ClosedTrade] = []
    peak = initial_cash
    max_dd = 0.0

    def mark_equity(px: float) -> float:
        inv = sum(q * px for q, _, _, _, _ in inventory.values())
        return cash + inv

    def sell_target(entry_level: float, spacing: float) -> float:
        if require_level_step:
            return entry_level * (1.0 + spacing / BPS)
        return entry_level * (1.0 + whipsaw_capture_bps / BPS)

    for i, bar in enumerate(bars):
        if atr_k is not None and atr_series:
            a = atr_series[i]
            if a and bar.close > 0:
                eff_spacing = max(40.0, a / bar.close * BPS * atr_k)
                if reanchor_every and i > 0 and i % reanchor_every == 0:
                    levels = build_levels(bar.close, eff_spacing, n_levels)

        to_close: List[float] = []
        for lv, (qty, entry, fee_open, slip_open, ts_o) in list(inventory.items()):
            target = sell_target(lv, eff_spacing)
            if bar.high >= target:
                exit_px = target
                notional = qty * exit_px
                fee, slip = cost.cost_usdt(notional)
                gross = (exit_px - entry) * qty
                fees = fee_open + fee
                slips = slip_open + slip
                net = gross - fees - slips
                cash += notional - fee - slip
                trades.append(
                    ClosedTrade(
                        "BUY",
                        entry,
                        exit_px,
                        qty,
                        gross,
                        fees,
                        slips,
                        net,
                        ts_o,
                        bar.ts,
                    )
                )
                to_close.append(lv)
        for lv in to_close:
            del inventory[lv]

        free_buys = [lv for lv in levels if lv not in inventory]
        for lv in free_buys:
            if bar.low <= lv:
                if bar.low > lv:
                    continue
                entry_px = lv
                qty = notional_usdt / entry_px
                notional = qty * entry_px
                fee, slip = cost.cost_usdt(notional)
                if cash < notional + fee + slip:
                    continue
                cash -= notional + fee + slip
                inventory[lv] = (qty, entry_px, fee, slip, bar.ts)
                break

        eq = mark_equity(bar.close)
        equity_curve.append(eq)
        peak = max(peak, eq)
        dd = (peak - eq) / peak if peak > 0 else 0.0
        max_dd = max(max_dd, dd)

    last = bars[-1].close
    final_eq = mark_equity(last)
    if equity_curve:
        peak = max(peak, final_eq)
        max_dd = max(max_dd, (peak - final_eq) / peak if peak > 0 else 0.0)

    n = len(trades)
    wins = sum(1 for t in trades if t.net > 0)
    captures = [(t.exit - t.entry) / t.entry * BPS for t in trades if t.entry > 0]
    return BacktestResult(
        mode=mode if require_level_step else f"{mode}_whipsaw",
        spacing_bps=(
            spacing_bps
            if atr_k is None
            else (sum(captures) / len(captures) if captures else eff_spacing)
        ),
        atr_k=atr_k,
        notional=notional_usdt,
        n_trades=n,
        gross_pnl=sum(t.gross for t in trades),
        net_pnl=sum(t.net for t in trades),
        win_rate=(wins / n) if n else 0.0,
        max_dd=max_dd,
        final_equity=final_eq,
        cost_rt_bps=cost.rt_bps,
        mean_capture_bps=(sum(captures) / len(captures)) if captures else 0.0,
        params={
            "eff_spacing_end": eff_spacing,
            "n_levels": float(n_levels),
            "require_level_step": 1.0 if require_level_step else 0.0,
            "whipsaw_capture_bps": float(whipsaw_capture_bps),
        },
    )


def split_regimes(
    bars: Sequence[Bar],
) -> Tuple[List[Bar], List[Bar], str, str]:
    """Heurística: menor eficiencia de path = range; mayor = trend."""
    if len(bars) < 100:
        mid = len(bars) // 2
        return list(bars[:mid]), list(bars[mid:]), "first_half", "second_half"

    window = max(48, len(bars) // 6)
    scores: List[Tuple[float, int]] = []
    for i in range(0, len(bars) - window, window // 2):
        seg = bars[i : i + window]
        ret = abs(seg[-1].close / seg[0].close - 1.0)
        path = sum(
            abs(seg[j].close / seg[j - 1].close - 1.0) for j in range(1, len(seg))
        )
        eff = ret / path if path > 1e-12 else 0.0
        scores.append((eff, i))
    scores_sorted = sorted(scores, key=lambda x: x[0])
    range_i = scores_sorted[0][1]
    trend_i = scores_sorted[-1][1]
    range_bars = list(bars[range_i : range_i + window])
    trend_bars = list(bars[trend_i : trend_i + window])
    return range_bars, trend_bars, f"range@{range_i}", f"trend@{trend_i}"
