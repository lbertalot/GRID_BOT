#!/usr/bin/env python3
"""Invocado desde `make dry-run` dentro del contenedor `api` (PAPER)."""

from __future__ import annotations

import os
from pprint import pprint

os.environ.setdefault("PAPER_TRADING", "true")

from app.services.binance_service import BinanceService


def main() -> None:
    symbol = os.getenv("SYMBOL")
    qty_raw = os.getenv("QTY")
    side = os.getenv("SIDE", "BUY")
    otype = os.getenv("TYPE", "MARKET")
    if not symbol or not qty_raw:
        raise SystemExit("SYMBOL y QTY son obligatorias")
    qty = float(qty_raw)

    svc = BinanceService()
    svc.simulation_mode = True
    val = svc.validate_order_parameters(symbol, qty, side=side, order_type=otype)
    pprint({"validation": val})
    if val.get("is_valid"):
        order = svc.execute_trading_order(symbol, side, otype, val["recommended_quantity"])
        pprint({"order": order})
    else:
        print("Validation failed:", val.get("errors"))


if __name__ == "__main__":
    main()
