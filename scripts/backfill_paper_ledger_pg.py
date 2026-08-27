"""Backfill explícito, paper-only e idempotente del export JSON a PostgreSQL."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from app.db.session import SessionLocal
from app.services.paper_ledger_backfill import (
    PaperLedgerBackfillError,
    backfill_payload,
    validate_payload,
)

ROOT = Path(__file__).resolve().parents[1]
LEDGER_PATH = ROOT / "paper_telemetry/paper_equity_ledger.json"
SERIES_PATH = ROOT / "paper_telemetry/paper_equity_series.json"


def _load(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--paper-only", action="store_true")
    parser.add_argument("--confirm-source-sha256")
    parser.add_argument("--window-id", default="legacy-json-v1")
    args = parser.parse_args()
    ledger, source_sha = _load(LEDGER_PATH)
    series, _ = _load(SERIES_PATH)
    validate_payload(ledger)
    print(json.dumps({"source_sha256": source_sha, "cycles": len(ledger["cycles"]), "fills": len(ledger["fills"]), "samples": len(series.get("samples", []))}))
    if not args.apply:
        return 0
    if not args.paper_only or args.confirm_source_sha256 != source_sha:
        raise PaperLedgerBackfillError("--apply exige --paper-only y el SHA-256 exacto")
    if os.getenv("PAPER_TRADING", "true").lower() != "true" or os.getenv("FORCE_REAL_MODE"):
        raise PaperLedgerBackfillError("backfill rechazado fuera de PAPER_TRADING")
    db = SessionLocal()
    try:
        result = backfill_payload(db, ledger=ledger, series=series, window_id=args.window_id, source_sha256=source_sha)
        db.commit()
        print(json.dumps(result))
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
