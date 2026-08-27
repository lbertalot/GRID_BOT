"""Validación post-calibración: historia 1h larga + Δnivel≥1 vs whipsaw + go/no-go ATR.

  PYTHONPATH=. python3.11 scripts/research/validate_spacing_next_steps.py

PROMOTE_LIVE: NO. No toca freeze ni breakers.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.research.grid_backtest import (  # noqa: E402
    Bar,
    CostModel,
    run_grid_backtest,
    split_regimes,
)


def fetch_klines_paginated(
    symbol: str = "ETHUSDT",
    interval: str = "1h",
    *,
    days: int = 180,
) -> List[Bar]:
    """Paginación pública Binance (máx 1000/req) hacia atrás."""
    end_ms = int(time.time() * 1000)
    start_ms = end_ms - days * 24 * 3600 * 1000
    out: List[Bar] = []
    cursor = start_ms
    while cursor < end_ms:
        url = (
            f"https://api.binance.com/api/v3/klines?symbol={symbol}"
            f"&interval={interval}&limit=1000&startTime={cursor}&endTime={end_ms}"
        )
        with urllib.request.urlopen(url, timeout=30) as resp:
            batch = json.loads(resp.read())
        if not batch:
            break
        for k in batch:
            out.append(
                Bar(
                    ts=k[0] / 1000.0,
                    open=float(k[1]),
                    high=float(k[2]),
                    low=float(k[3]),
                    close=float(k[4]),
                    volume=float(k[5]),
                )
            )
        next_cursor = int(batch[-1][0]) + 1
        if next_cursor <= cursor:
            break
        cursor = next_cursor
        time.sleep(0.15)
    # dedupe by ts
    by_ts = {b.ts: b for b in out}
    return [by_ts[t] for t in sorted(by_ts)]


def _row(r) -> Dict[str, Any]:
    return {
        "mode": r.mode,
        "spacing_bps": r.spacing_bps if not isinstance(r.spacing_bps, str) else r.spacing_bps,
        "atr_k": r.atr_k,
        "n_trades": r.n_trades,
        "gross_pnl": round(r.gross_pnl, 4),
        "net_pnl": round(r.net_pnl, 4),
        "mean_capture_bps": round(r.mean_capture_bps, 2),
        "max_dd_pct": round(r.max_dd * 100, 3),
        "win_rate": round(r.win_rate, 4),
        "params": r.params,
    }


def main() -> int:
    cost = CostModel()
    days = 180
    bars = fetch_klines_paginated(days=days)
    print(f"bars={len(bars)} days≈{days} from={datetime.fromtimestamp(bars[0].ts, tz=timezone.utc)} "
          f"to={datetime.fromtimestamp(bars[-1].ts, tz=timezone.utc)}")

    # 1) Sweep fixed + ATR on long window
    sweep = []
    for sp in (50, 75, 100, 150, 200):
        sweep.append(
            _row(
                run_grid_backtest(
                    bars, spacing_bps=float(sp), cost=cost, mode="fixed", require_level_step=True
                )
            )
        )
    for k in (0.5, 1.0, 1.5):
        r = run_grid_backtest(
            bars,
            spacing_bps=100.0,
            cost=cost,
            mode="atr",
            atr_k=k,
            reanchor_every=24 * 7,  # ~1w en 1h
            require_level_step=True,
        )
        d = _row(r)
        d["spacing_label"] = f"ATR*{k}"
        sweep.append(d)

    # 2) Δnivel≥1 vs whipsaw @ 100 bps
    with_step = run_grid_backtest(
        bars, spacing_bps=100.0, cost=cost, require_level_step=True, mode="fixed"
    )
    whipsaw = run_grid_backtest(
        bars,
        spacing_bps=100.0,
        cost=cost,
        require_level_step=False,
        whipsaw_capture_bps=5.0,
        mode="fixed",
    )

    # 3) Regímenes en la ventana larga
    range_bars, trend_bars, rlab, tlab = split_regimes(bars)
    regime = {
        "range": {
            "label": rlab,
            "n": len(range_bars),
            "fixed_100": _row(
                run_grid_backtest(range_bars, spacing_bps=100.0, cost=cost, require_level_step=True)
            ),
            "atr_1": _row(
                run_grid_backtest(
                    range_bars, spacing_bps=100.0, cost=cost, mode="atr", atr_k=1.0, require_level_step=True
                )
            ),
        },
        "trend": {
            "label": tlab,
            "n": len(trend_bars),
            "fixed_100": _row(
                run_grid_backtest(trend_bars, spacing_bps=100.0, cost=cost, require_level_step=True)
            ),
            "atr_1": _row(
                run_grid_backtest(
                    trend_bars, spacing_bps=100.0, cost=cost, mode="atr", atr_k=1.0, require_level_step=True
                )
            ),
        },
    }

    best_fixed = max(
        [x for x in sweep if x.get("atr_k") is None], key=lambda x: x["net_pnl"]
    )
    best_any = max(sweep, key=lambda x: x["net_pnl"])

    # Go/no-go ATR paper — criterios escritos *antes* de mirar live
    atr_gate = {
        "proposal": "ATR×1.0 paper-only overlay (sin cambiar freeze 100 bps hash)",
        "min_calendar_days": 14,
        "min_closed_cycles": 40,
        "primary_metric": "paper_cycle_edge_net_cum_usdt",
        "pass_if": [
            "mean_capture_bps de ciclos cerrados ≥ 60 (vs costo 24 → colchón ≥ 36 bps)",
            "edge_net_cum > 0 al cierre de la ventana",
            "racha máxima < 5 (no trip SI) y early_streak_warn dispara ≤ 2 veces",
            "net_pnl ATR paper ≥ net_pnl baseline freeze 100 bps en la misma ventana",
        ],
        "fail_if": [
            "mean_capture_bps < 40 (sigue regalando edge a costos)",
            "SI open por consecutive losses",
            "muestra < 40 ciclos o < 14 días → NO DECIDIR (extender)",
        ],
        "explicit_non_goals": [
            "No optimizar por número de trades",
            "No bajar freeze a 75 sin N11 aunque 14d ATR gane",
            "No live / PROMOTE_LIVE: NO",
        ],
    }

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "promote_live": "NO",
        "window": {
            "interval": "1h",
            "days_requested": days,
            "n_bars": len(bars),
            "from": datetime.fromtimestamp(bars[0].ts, tz=timezone.utc).isoformat(),
            "to": datetime.fromtimestamp(bars[-1].ts, tz=timezone.utc).isoformat(),
        },
        "sweep_long_1h": sweep,
        "best_fixed": best_fixed,
        "best_any": best_any,
        "level_step_ablation_100bps": {
            "with_delta_level": _row(with_step),
            "whipsaw_5bps_capture": _row(whipsaw),
            "delta_capture_bps": round(
                with_step.mean_capture_bps - whipsaw.mean_capture_bps, 2
            ),
            "delta_net_pnl": round(with_step.net_pnl - whipsaw.net_pnl, 4),
            "interpretation": (
                "Si with_delta_level.mean_capture ≈ spacing (100) y whipsaw ≈ 5, "
                "el patch explica el salto de captura; no hace falta N11 de spacing "
                "mientras el paper post-patch confirme capture≥60 bps."
            ),
        },
        "regimes": regime,
        "atr_paper_gate": atr_gate,
        "decision_now": {
            "change_freeze_spacing": "NO",
            "keep_100bps": True,
            "priority": "validar Δnivel≥1 en paper con métricas edge neto",
            "atr_trial": "solo tras pasar atr_paper_gate; no adoptar por backtest solo",
        },
    }

    out = ROOT / "Docs" / "ops" / "research" / "grid-spacing-validation-next-2026-08-26.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({
        "out": str(out),
        "best_fixed": best_fixed,
        "best_any": {k: best_any[k] for k in ("mode", "spacing_bps", "atr_k", "net_pnl", "mean_capture_bps", "n_trades")},
        "ablation": payload["level_step_ablation_100bps"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
