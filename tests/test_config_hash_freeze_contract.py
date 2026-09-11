"""Contrato A1: sidecar freeze-subset ↔ resolve ↔ sample no-sticky.

Paper-only · PROMOTE_LIVE: NO.
No reescribe paper_telemetry ni toca N10 en disco más allá de leerlo.
Ver Docs/ops/rca-gap126h-hash-drift-2026-09-11.md.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.core.paper_equity_ledger import (
    PaperEquityLedger,
    PaperEquitySeries,
    compute_paper_portfolio_value,
    resolve_grid_config_hash,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
PAPER_L0_JSON = REPO_ROOT / "grid_config_paper_l0.json"
PAPER_L0_HASH = REPO_ROOT / "grid_config_paper_l0.hash"

# Sticky pre-qty-fix label (RCA §16.2) — no debe heredarse tras resolve().
STICKY_PRE_QTY_HASH = (
    "ac1cb59676abbaa42a9e1409809ee3b7009ae5114e15055615a7a1ff63b4b219"
)


def _freeze_subset_hash(config: dict) -> str:
    """Misma canonicalización que scripts/freeze_paper_l0_config.py."""
    eth = config["ETHUSDT"]
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
            if k in eth
        },
        "deployed_capital_usd": config["_config_metadata"]["deployed_capital_usd"],
        "ic_controls": config["_config_metadata"]["ic_controls"],
    }
    return hashlib.sha256(
        json.dumps(hashable, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def test_sidecar_matches_freeze_subset_of_paper_l0_json() -> None:
    cfg = json.loads(PAPER_L0_JSON.read_text(encoding="utf-8"))
    sidecar = PAPER_L0_HASH.read_text(encoding="utf-8").strip()
    assert len(sidecar) == 64
    assert _freeze_subset_hash(cfg) == sidecar
    # El hash full-JSON NO es el sidecar (doble algoritmo documentado en RCA).
    from app.core.paper_equity_ledger import compute_config_hash

    assert compute_config_hash(cfg) != sidecar


def test_resolve_prefers_env_and_matches_sidecar_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    sidecar = PAPER_L0_HASH.read_text(encoding="utf-8").strip()
    monkeypatch.setenv("GRID_CONFIG_HASH", sidecar)
    assert resolve_grid_config_hash() == sidecar


def test_record_uses_resolve_not_sticky_header(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tras cambiar GRID_CONFIG_HASH, el próximo sample no hereda el header viejo."""
    expected = PAPER_L0_HASH.read_text(encoding="utf-8").strip()
    monkeypatch.setenv("GRID_CONFIG_HASH", expected)

    series_path = tmp_path / "paper_equity_series.json"
    series = PaperEquitySeries(
        config_hash=STICKY_PRE_QTY_HASH,
        storage_path=series_path,
    )
    series.record(
        "1000",
        at=datetime(2026, 8, 26, 12, 11, 32, tzinfo=timezone.utc),
        cash="1000",
        inventory_value="0",
        deployed_capital="200",
        config_hash=STICKY_PRE_QTY_HASH,
    )
    assert series.samples[-1]["config_hash"] == STICKY_PRE_QTY_HASH

    # Path de producción: compute_paper_portfolio_value pasa resolve().
    ledger = PaperEquityLedger(initial_cash="1000", deployed_capital="200")

    class _Feed:
        def get_price(self, symbol: str):  # noqa: ARG002
            from decimal import Decimal

            return Decimal("2459.72")

    payload = compute_paper_portfolio_value(
        ledger=ledger,
        price_feed=_Feed(),  # type: ignore[arg-type]
        series=series,
        at=datetime(2026, 9, 11, 18, 0, 0, tzinfo=timezone.utc),
        record=True,
    )
    assert payload is not None
    last = series.samples[-1]
    assert last["config_hash"] == expected
    assert last["config_hash"] != STICKY_PRE_QTY_HASH
