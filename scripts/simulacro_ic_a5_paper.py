#!/usr/bin/env python3
"""Simulacro desk A5 — IC-1 / IC-2 paper-safe (aislado, no muta SoT prod).

DoD L0 §2.4:
1. Forzar mid < piso → IC-1 + cancel BUY pendientes
2. Forzar DD ≥ 10% desplegado → IC-2 + flatten inventario
3. Escribir evidencia en Docs/ops/

Uso:
  cd GRID_BOT && PAPER_TRADING=true python3.11 scripts/simulacro_ic_a5_paper.py

PROMOTE_LIVE: NO — no toca exchange ni paper_telemetry de producción.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("PAPER_TRADING", "true")
os.environ.setdefault("FORCE_REAL_MODE", "")

D = Decimal
FLOOR = D("1826.92")
DEPLOYED = D("200")


def _run() -> dict:
    from app.core.inventory_controls import (
        EVENT_IC1,
        EVENT_IC2,
        IcControlsConfig,
        InventoryControlGuard,
        maybe_flatten_open_inventory_paper,
    )
    from app.core.paper_equity_ledger import PaperEquityLedger
    from app.core.paper_pending_orders import reset_paper_pending_order_book

    when = datetime.now(timezone.utc)
    evidence: dict = {
        "at": when.isoformat(),
        "mode": "paper",
        "promote_live": "NO",
        "steps": {},
    }

    book = reset_paper_pending_order_book()
    book.add_buy(symbol="ETHUSDT", price=D("1800"), quantity=D("0.05"))
    book.add_buy(symbol="ETHUSDT", price=D("1790"), quantity=D("0.05"))

    breaker_trips: list[tuple[str, str]] = []

    def _breaker(name: str, reason: str) -> None:
        breaker_trips.append((name, reason))

    guard = InventoryControlGuard(
        IcControlsConfig(
            enabled_ic1=True,
            enabled_ic2=True,
            symbol="ETHUSDT",
            range_floor=FLOOR,
            deployed_capital=DEPLOYED,
            ic2_threshold_pct=D("10.00"),
        ),
        activate_breaker=_breaker,
    )

    # --- Step 1: IC-1 ---
    d1 = guard.observe(mid=D("1800"), equity_mtm=D("1000"), enforce=True)
    step1 = {
        "ic1_active": d1.ic1_active,
        "allows_core_buy": guard.allows_core_buy(),
        "pending_buys_after": len(book.list_open(side="BUY")),
        "events": [e.get("event") for e in d1.events],
        "cancel_buys_event": any(e.get("cancel_buys") for e in guard.state.last_events),
    }
    assert d1.ic1_active is True
    assert guard.allows_core_buy() is False
    assert step1["pending_buys_after"] == 0
    evidence["steps"]["ic1_force_below_floor"] = {**step1, "pass": True}

    # Recuperar rango para drill IC-2
    guard.observe(mid=D("1923"), equity_mtm=D("1000"), enforce=False)

    # --- Step 2: IC-2 + flatten (ledger TMP only) ---
    with tempfile.TemporaryDirectory() as tmp:
        ledger = PaperEquityLedger(
            initial_cash=D("1000"),
            deployed_capital=DEPLOYED,
            storage_path=Path(tmp) / "ledger.json",
        )
        ledger.record_buy("ETHUSDT", D("0.1"), D("1923"), order_type="LIMIT")
        marks_hi = {"ETHUSDT": D("1923")}
        peak = ledger.equity_breakdown(marks_hi)["equity"]
        # DD 20 USDT = 10% de deployed 200
        target_eq = peak - D("20")
        cash = ledger.cash
        mark = (target_eq - cash) / D("0.1")
        if mark <= D("0"):
            mark = D("1")
        marks_lo = {"ETHUSDT": mark}
        equity_lo = ledger.equity_breakdown(marks_lo)["equity"]

        d2 = guard.observe(
            mid=mark,
            equity_mtm=equity_lo,
            peak_equity=peak,
            enforce=True,
        )
        fills = maybe_flatten_open_inventory_paper(
            positions={"ETHUSDT": ledger.position("ETHUSDT")},
            marks=marks_lo,
            sell=lambda **kw: ledger.record_sell(
                kw["symbol"], kw["quantity"], kw["price"], order_type="MARKET"
            ),
            guard=guard,
        )

        step2 = {
            "peak_equity": str(peak),
            "equity_after": str(equity_lo),
            "mark": str(mark),
            "ic2_active": guard.state.ic2_active,
            "ic2_should_flatten": d2.ic2_should_flatten,
            "flatten_pending_after": guard.state.flatten_pending,
            "armed": guard.state.armed,
            "fills_n": len(fills),
            "open_qty_after": str(ledger.position("ETHUSDT")),
            "breaker_trips": list(breaker_trips),
            "allows_core_buy": guard.allows_core_buy(),
            "events_ic2": any(
                e.get("event") == EVENT_IC2 for e in guard.state.last_events
            ),
        }
        step2["pass"] = bool(
            guard.state.ic2_active
            and not guard.state.armed
            and ledger.position("ETHUSDT") == 0
            and step2["events_ic2"]
            and len(fills) >= 1
        )
        evidence["steps"]["ic2_force_dd_flatten"] = step2
        assert step2["pass"], step2

    evidence["verdict"] = "PASS"
    evidence["events_seen"] = [EVENT_IC1, EVENT_IC2]
    return evidence


def _write_md(evidence: dict, out: Path) -> Path:
    steps = evidence.get("steps") or {}
    s1 = steps.get("ic1_force_below_floor") or {}
    s2 = steps.get("ic2_force_dd_flatten") or {}
    text = f"""# Simulacro IC desk A5 — {evidence.get('at', '')[:10]}

| Campo | Valor |
|-------|-------|
| Generado | {evidence.get('at')} |
| Modo | paper · **PROMOTE_LIVE: NO** |
| Script | `scripts/simulacro_ic_a5_paper.py` |
| Aislamiento | tmp ledger · **no** muta `paper_telemetry/` prod |
| Veredicto | **{evidence.get('verdict')}** |

## 1. IC-1 — mid bajo piso (−5%)

| Check | Resultado |
|-------|-----------|
| `ic1_active` | {s1.get('ic1_active')} |
| `allows_core_buy` | {s1.get('allows_core_buy')} |
| pending BUY after cancel | {s1.get('pending_buys_after')} |
| cancel_buys event | {s1.get('cancel_buys_event')} |
| Pass | **{s1.get('pass')}** |

## 2. IC-2 — DD ≥ 10% desplegado + flatten

| Check | Resultado |
|-------|-----------|
| peak → equity | {s2.get('peak_equity')} → {s2.get('equity_after')} |
| mark forzado | {s2.get('mark')} |
| `ic2_active` / armed | {s2.get('ic2_active')} / {s2.get('armed')} |
| fills flatten | {s2.get('fills_n')} |
| open qty after flatten | {s2.get('open_qty_after')} |
| breaker trips | {s2.get('breaker_trips')} |
| Pass | **{s2.get('pass')}** |

## Go / no-go
- Simulacro A5 código: **{evidence.get('verdict')}**
- Gate live: **NO-GO** · **PROMOTE_LIVE: NO**
- KPI SELL / ventana: ver `IC_SELL_STATUS_*.md` (evidencia separada)

```json
{json.dumps(evidence, indent=2, default=str)}
```
"""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return out


def main() -> int:
    evidence = _run()
    date_s = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out = ROOT / "Docs" / "ops" / f"IC_A5_SIMULACRO_{date_s}.md"
    path = _write_md(evidence, out)
    print(json.dumps({"ok": True, "path": str(path), "verdict": evidence["verdict"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
