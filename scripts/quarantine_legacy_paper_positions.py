#!/usr/bin/env python3
"""Mitiga WARNING: posiciones legacy no importadas al ledger MtM.

El archivo `paper_trading_state.json` es **legacy** (floats, sin fees). La SoT
paper L0 es `paper_telemetry/paper_equity_ledger.json`. Posiciones en el JSON
legacy **no** se importan (evita contaminar E_0 / inventario MtM).

Esta herramienta:
- Mueve `positions` → `_quarantined_positions` con motivo + UTC.
- **No** toca `paper_telemetry/` ni hace wipe de serie válida.
- **No** importa inventario al ledger (L0 arranca cash-only / fills reales).

Uso:
  python3.11 scripts/quarantine_legacy_paper_positions.py --dry-run
  python3.11 scripts/quarantine_legacy_paper_positions.py --write

Paper-only.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE = ROOT / "paper_trading_state.json"


def quarantine(path: Path, *, write: bool) -> dict:
    if not path.exists():
        return {"ok": True, "action": "noop", "reason": f"{path} ausente"}

    data = json.loads(path.read_text())
    positions = data.get("positions") or {}
    already = data.get("_quarantined_positions") or {}

    if not positions:
        return {
            "ok": True,
            "action": "noop",
            "reason": "sin positions activas en legacy",
            "quarantined_count": len(already.get("positions") or already)
            if isinstance(already, dict)
            else 0,
        }

    payload = {
        "quarantined_at": datetime.now(timezone.utc).isoformat(),
        "reason": (
            "pre-L0 legacy floats; SoT = PaperEquityLedger MtM; "
            "no importar a inventario paper (evitar contaminar E_0)"
        ),
        "source_of_truth": "app.core.paper_equity_ledger",
        "positions": positions,
    }
    result = {
        "ok": True,
        "action": "dry_run" if not write else "quarantined",
        "path": str(path),
        "position_symbols": list(positions.keys()),
        "count": len(positions),
        "payload_preview": {
            "quarantined_at": payload["quarantined_at"],
            "reason": payload["reason"],
            "symbols": list(positions.keys()),
        },
    }
    if not write:
        result["reason"] = "dry-run: no se modificó el archivo"
        return result

    data["_quarantined_positions"] = payload
    data["positions"] = {}
    data["source_of_truth"] = "app.core.paper_equity_ledger"
    data["legacy_positions_reconciled"] = True
    path.write_text(json.dumps(data, indent=2) + "\n")
    result["reason"] = (
        "positions movidas a _quarantined_positions; warning load_state silenciado"
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--path",
        type=Path,
        default=DEFAULT_STATE,
        help="Ruta al paper_trading_state.json",
    )
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    write = bool(args.write) and not args.dry_run
    out = quarantine(args.path, write=write)
    print(json.dumps(out, indent=2))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
