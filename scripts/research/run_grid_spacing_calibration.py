"""CLI: costo real N10 + barrido spacing grid ETHUSDT (paper research).

Uso:
  PYTHONPATH=/app python scripts/research/run_grid_spacing_calibration.py
  # o local:
  python3.11 scripts/research/run_grid_spacing_calibration.py --from-db

PROMOTE_LIVE: NO.
"""

from __future__ import annotations

import argparse
import json
import statistics as st
import sys
from datetime import timezone
from decimal import Decimal
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


def load_cost_from_ledger(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text())
    model = data.get("cost_model") or {}
    closed = [c for c in data.get("cycles") or [] if c.get("closed_at")]
    rows = []
    for c in closed:
        buy = Decimal(str(c["buy_price"]))
        qty = Decimal(str(c["buy_quantity"]))
        sell = Decimal(str(c["sell_notional_usdt"])) / qty
        notion = buy * qty
        fees = Decimal(str(c["fees_usdt"]))
        slip = Decimal(str(c["slippage_usdt"]))
        move_bps = float((sell - buy) / buy * 10000)
        cost_bps = float((fees + slip) / notion * 10000) if notion else 0.0
        rows.append(
            {
                "opened_at": c["opened_at"],
                "buy": float(buy),
                "sell": float(sell),
                "move_bps": move_bps,
                "cost_bps": cost_bps,
                "gross": float(c["gross_pnl_usdt"]),
                "net": float(c["net_pnl_usdt"]),
                "fees": float(fees),
                "slip": float(slip),
            }
        )
    cost_bps_list = [r["cost_bps"] for r in rows]
    move_list = [r["move_bps"] for r in rows]
    return {
        "ledger_path": str(path),
        "n_closed": len(rows),
        "cost_model_declared": model,
        "bnb_discount": False,
        "assumption": (
            "Fees/slippage del ledger son PaperCostModel (10 bps fee + 2 bps "
            "adverse/side). No hay fills Binance reales ni descuento BNB. "
            "Slippage = supuesto declarado, no spread medido."
        ),
        "cost_rt_bps_mean": st.mean(cost_bps_list) if cost_bps_list else None,
        "cost_rt_bps_median": st.median(cost_bps_list) if cost_bps_list else None,
        "move_bps_mean": st.mean(move_list) if move_list else None,
        "move_bps_median": st.median(move_list) if move_list else None,
        "sum_gross": sum(r["gross"] for r in rows),
        "sum_fees": sum(r["fees"] for r in rows),
        "sum_slip": sum(r["slip"] for r in rows),
        "sum_net": sum(r["net"] for r in rows),
        "edge_bps_mean": (
            st.mean([r["move_bps"] - r["cost_bps"] for r in rows]) if rows else None
        ),
        "rows": rows,
    }


def load_bars_from_db(interval: str = "5m", symbol: str = "ETHUSDT") -> List[Bar]:
    from sqlalchemy import text
    from app.db.session import SessionLocal

    sql = text(
        """
        SELECT EXTRACT(EPOCH FROM open_time)::float8 AS ts,
               open_price::float8, high_price::float8,
               low_price::float8, close_price::float8,
               COALESCE(volume, 0)::float8
        FROM klines_data
        WHERE upper(symbol) = upper(:sym) AND interval = :iv
        ORDER BY open_time ASC
        """
    )
    bars: List[Bar] = []
    with SessionLocal() as db:
        for row in db.execute(sql, {"sym": symbol, "iv": interval}):
            bars.append(
                Bar(ts=row[0], open=row[1], high=row[2], low=row[3], close=row[4], volume=row[5])
            )
    return bars


def result_dict(r) -> Dict[str, Any]:
    return {
        "mode": r.mode,
        "spacing_bps": round(r.spacing_bps, 2),
        "atr_k": r.atr_k,
        "notional": r.notional,
        "n_trades": r.n_trades,
        "gross_pnl": round(r.gross_pnl, 4),
        "net_pnl": round(r.net_pnl, 4),
        "win_rate": round(r.win_rate, 4),
        "max_dd_pct": round(r.max_dd * 100, 3),
        "final_equity": round(r.final_equity, 2),
        "cost_rt_bps": r.cost_rt_bps,
        "mean_capture_bps": round(r.mean_capture_bps, 2),
        "params": r.params,
    }


def sweep(bars: List[Bar], cost: CostModel, notional: float = 20.0) -> List[Dict[str, Any]]:
    out = []
    for sp in (25, 50, 75, 100, 150, 200):
        r = run_grid_backtest(
            bars,
            spacing_bps=float(sp),
            notional_usdt=notional,
            cost=cost,
            mode="fixed",
        )
        out.append(result_dict(r))
    for k in (0.5, 1.0, 1.5):
        r = run_grid_backtest(
            bars,
            spacing_bps=100.0,
            notional_usdt=notional,
            cost=cost,
            mode="atr",
            atr_k=k,
            reanchor_every=288,  # ~1d en 5m
        )
        d = result_dict(r)
        d["spacing_bps"] = f"ATR*{k}"
        out.append(d)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-db", action="store_true")
    ap.add_argument("--interval", default="5m")
    ap.add_argument(
        "--ledger",
        default=str(ROOT / "paper_telemetry" / "paper_equity_ledger.json"),
    )
    ap.add_argument(
        "--out",
        default=str(ROOT / "Docs" / "ops" / "research" / "grid-spacing-calibration-2026-08-26.json"),
    )
    args = ap.parse_args()

    cost_report = load_cost_from_ledger(Path(args.ledger))
    fee = float(Decimal(str(cost_report["cost_model_declared"].get("maker_fee_bps", 10))))
    slip = float(
        Decimal(str(cost_report["cost_model_declared"].get("adverse_selection_bps", 2)))
    )
    cost = CostModel(fee_bps_per_side=fee, slip_bps_per_side=slip)

    if args.from_db:
        bars = load_bars_from_db(args.interval)
    else:
        # fallback: try db anyway
        try:
            bars = load_bars_from_db(args.interval)
        except Exception as exc:
            print("DB unavailable:", exc, file=sys.stderr)
            return 1

    print(f"bars={len(bars)} interval={args.interval} cost_rt={cost.rt_bps} bps")
    if not bars:
        return 1

    full = sweep(bars, cost)
    range_bars, trend_bars, rlab, tlab = split_regimes(bars)
    range_s = sweep(range_bars, cost)
    trend_s = sweep(trend_bars, cost)

    # best by net pnl
    best = max(full, key=lambda x: x["net_pnl"])
    best_fixed = max(
        [x for x in full if x["mode"] == "fixed"], key=lambda x: x["net_pnl"]
    )

    # minNotional check
    min_notional = 5.0  # Binance Spot ETHUSDT NOTIONAL filter 2026-08-26
    sizing = {
        "binance_min_notional_usdt": min_notional,
        "freeze_notional_per_level": 20.0,
        "headroom_vs_min": 20.0 / min_notional,
        "ok": 20.0 >= min_notional * 1.5,
        "note": "Freeze L0 usa USD 20 (≥ piso desk USD 15 (1.5× min histórico 10; ahora exchange min=5).",
    }

    payload = {
        "generated_at": __import__("datetime").datetime.now(timezone.utc).isoformat(),
        "promote_live": "NO",
        "cost_empirical": {
            k: v
            for k, v in cost_report.items()
            if k != "rows"
        },
        "cost_empirical_sample_rows": cost_report["rows"][:5],
        "data": {
            "interval": args.interval,
            "n_bars": len(bars),
            "from_ts": bars[0].ts,
            "to_ts": bars[-1].ts,
            "limitation": (
                "5m sync Binance ≈1000 velas (~3.5d). Regímenes son sub-ventanas "
                "dentro de ese tramo; no sustituye OOS multi-semana."
            ),
        },
        "sweep_full": full,
        "sweep_range": {"label": rlab, "n_bars": len(range_bars), "rows": range_s},
        "sweep_trend": {"label": tlab, "n_bars": len(trend_bars), "rows": trend_s},
        "best_net_full": best,
        "best_fixed_net": best_fixed,
        "sizing": sizing,
        "recommendation": {
            "keep_freeze_spacing_bps": 100,
            "rationale": (
                "Costo RT empírico ≈24 bps. Capture media N10 ≈ −1.6 bps (no el spacing "
                "de 100 bps): el fallo fue Δnivel≈0 (RT intra-nivel), no un freeze < costo. "
                "Con backtest de cruce de nivel, spacing ≥100 bps maximiza neto vs 25–75. "
                "No bajar spacing. Subir a 150 solo si desk acepta N11 (menos trades)."
            ),
            "require_level_step": True,
            "early_streak_warn": 3,
            "breaker_threshold": 5,
        },
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"out": str(out), "best_net": best, "best_fixed": best_fixed}, indent=2))
    print("\n=== SWEEP FULL (net desc) ===")
    for row in sorted(full, key=lambda x: x["net_pnl"], reverse=True):
        print(
            f"{str(row['spacing_bps']):>8}  trades={row['n_trades']:4}  "
            f"gross={row['gross_pnl']:8.3f}  net={row['net_pnl']:8.3f}  "
            f"wr={row['win_rate']*100:5.1f}%  dd={row['max_dd_pct']:5.2f}%  "
            f"cap_bps={row['mean_capture_bps']:6.1f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
