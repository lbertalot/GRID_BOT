#!/usr/bin/env python3
"""Freeze the L0 paper-window grid config around a spot mid price.

Desk policy §2.4: ETHUSDT, USD 200 deployed, 10 levels × USD 20, 100 bps,
±5% range, spot 1×. Writes min/max/quantity and a config_hash sidecar.

Usage:
  python3.11 scripts/freeze_paper_l0_config.py --mid 3500.00
  python3.11 scripts/freeze_paper_l0_config.py --mid 3500.00 --write

Paper-only. Does not enable live trading.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from decimal import Decimal, ROUND_DOWN, ROUND_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "grid_config_paper_l0.json"
HASH_PATH = ROOT / "grid_config_paper_l0.hash"


def _d(value: str | float | int) -> Decimal:
    return Decimal(str(value))


def freeze(mid: Decimal, *, write: bool) -> dict:
    if mid <= 0:
        raise SystemExit("--mid must be > 0")

    cfg = json.loads(CONFIG_PATH.read_text())
    eth = cfg["ETHUSDT"]
    deployed = _d(eth["investment_amount"])
    levels = int(eth["grids"])
    per_level = _d(eth["notional_per_level_usd"])
    spacing_bps = int(eth["spacing_bps"])
    range_pct = _d(eth["range_pct"]) / Decimal("100")

    if spacing_bps < 40:
        raise SystemExit("spacing < 40 bps rejected by desk policy")
    if per_level < _d("15"):
        raise SystemExit("notional/level < 15 USD rejected (MIN_NOTIONAL floor)")
    if levels != 10 or deployed != _d("200"):
        raise SystemExit("L0 freeze expects 10 levels and USD 200 deployed")

    half = range_pct
    min_price = (mid * (Decimal("1") - half)).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    max_price = (mid * (Decimal("1") + half)).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    # Redondear HACIA ARRIBA al lot step real del exchange (ETHUSDT stepSize=0.0001,
    # confirmado vía /api/v3/exchangeInfo). Si se redondea hacia abajo a 6 decimales
    # (comportamiento previo), el motor vuelve a truncar al lot step en ejecución y el
    # nocional resultante cae por debajo del piso L0 (USD 20) — bloqueando todo fill
    # cerca del mid (ver Docs/ops/rca-pnl-dd-2026-08-20.md, hallazgo N10 2026-08-26).
    lot_step = Decimal("0.0001")
    quantity = (per_level / mid).quantize(lot_step, rounding=ROUND_UP)

    eth["mid_price_at_freeze"] = str(mid)
    eth["min_price"] = float(min_price)
    eth["max_price"] = float(max_price)
    eth["quantity"] = float(quantity)
    eth["is_active"] = True
    eth["trading_mode"] = "PAPER"
    eth["paper_only"] = True
    cfg["system_config"]["trading_mode"] = "PAPER"
    cfg["system_config"]["paper_trading"] = True
    cfg["system_config"]["force_real_mode"] = False
    cfg["_config_metadata"]["status"] = "PAPER_FROZEN"
    cfg["_config_metadata"]["frozen_at_mid"] = str(mid)

    # Hash without secrets / volatile metadata timestamps that operators might touch.
    hashable = {
        "ETHUSDT": {
            k: eth[k]
            for k in (
                "symbol",
                "grids",
                "quantity",
                "investment_amount",
                "notional_per_level_usd",
                "spacing_bps",
                "range_pct",
                "min_price",
                "max_price",
                "mid_price_at_freeze",
                "trading_mode",
            )
        },
        "deployed_capital_usd": cfg["_config_metadata"]["deployed_capital_usd"],
        "ic_controls": cfg["_config_metadata"]["ic_controls"],
    }
    digest = hashlib.sha256(
        json.dumps(hashable, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    print(f"mid={mid} min={min_price} max={max_price} qty={quantity}")
    print(f"config_hash={digest}")
    print(f"per_level_usd={per_level} levels={levels} spacing_bps={spacing_bps}")

    if write:
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2) + "\n")
        HASH_PATH.write_text(digest + "\n")
        print(f"wrote {CONFIG_PATH}")
        print(f"wrote {HASH_PATH}")
    else:
        print("(dry-run; pass --write to persist)")

    return {"config_hash": digest, "config": cfg}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mid", required=True, help="ETHUSDT mid price at freeze")
    parser.add_argument("--write", action="store_true", help="Persist config + hash")
    args = parser.parse_args()
    freeze(_d(args.mid), write=args.write)


if __name__ == "__main__":
    main()
    sys.exit(0)
