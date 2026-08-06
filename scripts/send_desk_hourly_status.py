#!/usr/bin/env python3
"""Envía ahora el digest desk (CEO + áreas) por Telegram. Paper-only.

Uso:
  DESK_HOURLY_STATUS_ENABLED=true python3.11 scripts/send_desk_hourly_status.py
  docker compose -f docker-compose.local.yml exec -T worker \\
    python scripts/send_desk_hourly_status.py [--eod]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Permitir dry-run local sin setear env en shell si compose ya lo inyecta
os.environ.setdefault("DESK_HOURLY_STATUS_ENABLED", "true")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--eod",
        action="store_true",
        help="Genera action plan Día N+1 + Telegram resumen",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Imprime payload; no envía Telegram",
    )
    args = parser.parse_args()

    if args.eod:
        from app.services.desk_status_tasks import send_desk_eod_day_plan
        from app.core.desk_hourly_status import build_live_digest, write_day2_action_plan

        if args.dry_run:
            d = build_live_digest()
            path = write_day2_action_plan(d)
            print(path.read_text(encoding="utf-8"))
            print(json.dumps({"path": str(path), "global": d.global_status}, indent=2))
            return 0
        print(json.dumps(send_desk_eod_day_plan(), indent=2, default=str))
        return 0

    from app.core.desk_hourly_status import build_live_digest
    from app.services.desk_status_tasks import send_desk_hourly_digest

    if args.dry_run:
        d = build_live_digest()
        print(d.full_telegram_payload())
        print("---")
        print(json.dumps({"day_n": d.day_n, "global": d.global_status}, indent=2))
        return 0

    print(json.dumps(send_desk_hourly_digest(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
