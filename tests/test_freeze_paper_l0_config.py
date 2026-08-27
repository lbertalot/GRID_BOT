"""Tests for the L0 paper config freeze helper."""

from __future__ import annotations

import importlib.util
import json
import sys
from decimal import ROUND_UP, Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_freeze_module(config_path: Path, hash_path: Path):
    spec = importlib.util.spec_from_file_location(
        "freeze_paper_l0_config", ROOT / "scripts" / "freeze_paper_l0_config.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.CONFIG_PATH = config_path
    mod.HASH_PATH = hash_path
    return mod


def test_freeze_rejects_spacing_below_40(tmp_path):
    cfg = json.loads((ROOT / "grid_config_paper_l0.json").read_text())
    cfg["ETHUSDT"]["spacing_bps"] = 30
    cfg_path = tmp_path / "grid_config_paper_l0.json"
    cfg_path.write_text(json.dumps(cfg))
    mod = _load_freeze_module(cfg_path, tmp_path / "h.hash")
    with pytest.raises(SystemExit, match="40 bps"):
        mod.freeze(Decimal("3500"), write=False)


def test_freeze_writes_hash_and_range(tmp_path):
    cfg_src = json.loads((ROOT / "grid_config_paper_l0.json").read_text())
    cfg_path = tmp_path / "grid_config_paper_l0.json"
    cfg_path.write_text(json.dumps(cfg_src))
    hash_path = tmp_path / "grid_config_paper_l0.hash"
    mod = _load_freeze_module(cfg_path, hash_path)

    out = mod.freeze(Decimal("3500"), write=True)
    written = json.loads(cfg_path.read_text())
    eth = written["ETHUSDT"]
    assert eth["mid_price_at_freeze"] == "3500"
    assert eth["min_price"] == 3325.0
    assert eth["max_price"] == 3675.0
    # ROUND_UP al lot step ETHUSDT (0.0001). 20/3500=0.005714… → 0.0058;
    # nocional nunca por debajo del piso L0 (el motor no puede truncar otra vez).
    lot_step = Decimal("0.0001")
    expected_qty = float(
        (Decimal("20") / Decimal("3500")).quantize(lot_step, rounding=ROUND_UP)
    )
    assert eth["quantity"] == expected_qty
    assert eth["quantity"] * 3500 >= 20
    assert eth["trading_mode"] == "PAPER"
    assert written["system_config"]["force_real_mode"] is False
    assert len(out["config_hash"]) == 64
    assert hash_path.read_text().strip() == out["config_hash"]
