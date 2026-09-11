"""Contrato overlay prueba SI 5×15: no toca N10; mismo mid/spacing; qty piso 15.

Paper-only. PROMOTE_LIVE: NO.
"""

from __future__ import annotations

import json
from decimal import ROUND_UP, Decimal
from pathlib import Path

from app.core.paper_equity_ledger import compute_config_hash

ROOT = Path(__file__).resolve().parents[1]
N10 = ROOT / "grid_config_paper_l0.json"
N10_HASH = ROOT / "grid_config_paper_l0.hash"
TRIAL = ROOT / "grid_config_paper_l0_trial_5x15.json"
TRIAL_HASH = ROOT / "grid_config_paper_l0_trial_5x15.hash"

N10_SIDECAR = "ff6a35fcf84bf91c1da9ea81116265a3789f1d85e5456d19622897c82ed7f5c4"
MID = Decimal("2459.72")
LOT = Decimal("0.0001")
NOTIONAL = Decimal("15")


def test_n10_intacta():
    n10 = json.loads(N10.read_text(encoding="utf-8"))
    assert n10["_config_metadata"]["status"] == "PAPER_FROZEN"
    assert n10["ETHUSDT"]["grids"] == 10
    assert float(n10["ETHUSDT"]["notional_per_level_usd"]) == 20.0
    assert n10["ETHUSDT"]["spacing_bps"] == 100
    assert n10["ETHUSDT"]["mid_price_at_freeze"] == "2459.72"
    assert N10_HASH.read_text(encoding="utf-8").strip() == N10_SIDECAR


def test_overlay_5x15_mismo_mid_spacing_parent_hash():
    trial = json.loads(TRIAL.read_text(encoding="utf-8"))
    n10 = json.loads(N10.read_text(encoding="utf-8"))
    meta = trial["_config_metadata"]
    eth = trial["ETHUSDT"]
    assert meta["status"] == "PAPER_TRIAL_5x15"
    assert meta["parent_hash"] == N10_SIDECAR
    assert meta["spacing_bps"] == 100
    assert meta["levels"] == 5
    assert meta["notional_per_level_usd"] == "15.00"
    assert meta["deployed_capital_usd"] == "75.00"
    assert meta["frozen_at_mid"] == n10["_config_metadata"]["frozen_at_mid"]
    assert eth["grids"] == 5
    assert eth["spacing_bps"] == 100
    assert eth["min_price"] == n10["ETHUSDT"]["min_price"]
    assert eth["max_price"] == n10["ETHUSDT"]["max_price"]
    assert eth["mid_price_at_freeze"] == n10["ETHUSDT"]["mid_price_at_freeze"]
    assert trial["max_concurrent_orders"] == 2
    assert trial["system_config"]["paper_trading"] is True
    assert trial["system_config"]["force_real_mode"] is False


def test_overlay_quantity_es_15_sobre_mid_round_up_lot():
    trial = json.loads(TRIAL.read_text(encoding="utf-8"))
    expected = (NOTIONAL / MID).quantize(LOT, rounding=ROUND_UP)
    qty = Decimal(str(trial["ETHUSDT"]["quantity"]))
    assert qty == expected
    assert qty * MID >= NOTIONAL


def test_overlay_sidecar_hash_coincide_con_compute_config_hash():
    trial = json.loads(TRIAL.read_text(encoding="utf-8"))
    digest = compute_config_hash(trial)
    assert TRIAL_HASH.is_file()
    assert TRIAL_HASH.read_text(encoding="utf-8").strip() == digest
    assert len(digest) == 64
    assert digest != N10_SIDECAR
