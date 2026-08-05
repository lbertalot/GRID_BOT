#!/usr/bin/env python3
"""Opción B — capturar sample E_0 (cierre diario 00:00 UTC ±30 min) paper-safe.

Solo persiste un sample en `paper_telemetry/paper_equity_series.json` cuando el
reloj UTC está dentro de `DAILY_CLOSE_TOLERANCE` (±30 min de medianoche).

- Usa el mismo path que Celery: `compute_paper_portfolio_value()` + feed real.
- **No** inventa mid / equity.
- **No** altera `config_hash` / freeze.
- **No** hace wipe de `paper_telemetry` (solo append vía `PaperEquitySeries.record`).

Uso:
  # Ver si estamos en ventana (sin escribir)
  python3.11 scripts/capture_paper_e0_daily_close.py --dry-run

  # Dentro de ±30m 00:00 UTC — append sample con daily_close_at
  python3.11 scripts/capture_paper_e0_daily_close.py --write

  # En Docker (worker, mismo volume paper_telemetry):
  docker compose -f docker-compose.local.yml exec -T worker \\
    python scripts/capture_paper_e0_daily_close.py --write

Si fuera de ventana: exit 2 + instrucciones (esperar medianoche o task Celery).

Paper-only. No FORCE_REAL_MODE. No PROMOTE_LIVE.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def window_status(now: datetime | None = None) -> dict:
    """Estado de la ventana de cierre diario (I-13)."""
    from app.core.paper_equity_ledger import (
        DAILY_CLOSE_TOLERANCE,
        daily_close_anchor,
    )

    moment = now or _now_utc()
    anchor = daily_close_anchor(moment)
    midnight = moment.replace(hour=0, minute=0, second=0, microsecond=0)
    next_midnight = midnight + timedelta(days=1)
    # Próximo borde de ventana: 23:30 del día o 00:00 si aún no pasó medianoche.
    if moment < midnight + DAILY_CLOSE_TOLERANCE and moment >= midnight:
        opens_at = midnight - DAILY_CLOSE_TOLERANCE
        closes_at = midnight + DAILY_CLOSE_TOLERANCE
        next_open = opens_at
    elif moment >= next_midnight - DAILY_CLOSE_TOLERANCE:
        opens_at = next_midnight - DAILY_CLOSE_TOLERANCE
        closes_at = next_midnight + DAILY_CLOSE_TOLERANCE
        next_open = opens_at
    else:
        opens_at = next_midnight - DAILY_CLOSE_TOLERANCE
        closes_at = next_midnight + DAILY_CLOSE_TOLERANCE
        next_open = opens_at

    return {
        "now": moment.isoformat(),
        "in_window": anchor is not None,
        "anchor": anchor.isoformat() if anchor else None,
        "tolerance_minutes": int(DAILY_CLOSE_TOLERANCE.total_seconds() // 60),
        "next_window_opens_at": next_open.isoformat(),
        "next_window_closes_at": closes_at.isoformat(),
        "seconds_until_open": max(0, int((next_open - moment).total_seconds()))
        if not anchor
        else 0,
    }


def capture(*, write: bool, now: datetime | None = None) -> dict:
    """Toma marca MtM real si hay ventana; dry-run solo reporta."""
    from app.core.paper_equity_ledger import (
        compute_paper_portfolio_value,
        get_mark_price_feed,
        get_paper_equity_series,
        get_paper_ledger,
        resolve_grid_config_hash,
    )
    from app.core.trading_mode import get_trading_mode_snapshot

    status = window_status(now)
    mode = get_trading_mode_snapshot()
    if mode.get("effective_mode") != "paper":
        raise SystemExit(
            f"ABORT: effective_mode={mode.get('effective_mode')!r} "
            "(solo paper; no live)"
        )

    result = {
        "action": "dry_run" if not write else "write",
        "window": status,
        "effective_mode": mode.get("effective_mode"),
        "config_hash": resolve_grid_config_hash(),
    }

    if not status["in_window"]:
        result["ok"] = False
        result["reason"] = (
            "fuera de ventana ±30 min 00:00 UTC — no se escribe sample; "
            "esperar next_window_opens_at o dejar que Celery "
            "capture_portfolio_snapshot corra en esa ventana"
        )
        return result

    # Feed real: fall-closed si no hay mid (MarkPriceUnavailable → None).
    moment = now or _now_utc()
    if not write:
        try:
            mid = get_mark_price_feed().get_price("ETHUSDT")
            result["mark_ethusdt"] = str(mid)
        except Exception as exc:  # noqa: BLE001 — reporte dry-run
            result["mark_ethusdt"] = None
            result["mark_error"] = type(exc).__name__
        result["ok"] = True
        result["reason"] = "en ventana; dry-run (no se appendió sample)"
        return result

    payload = compute_paper_portfolio_value(at=moment, record=True)
    if payload is None:
        result["ok"] = False
        result["reason"] = (
            "snapshot omitido: MarkPriceUnavailable (no se inventa mid)"
        )
        return result

    series = get_paper_equity_series()
    sample = series.samples[-1] if series.samples else None
    result["ok"] = bool(sample and sample.get("daily_close_at"))
    result["sample"] = sample
    result["portfolio"] = {
        k: payload.get(k)
        for k in ("total_value_usdt", "usdt_free", "btc_value_usdt", "other_assets_usdt")
    }
    ledger = get_paper_ledger().to_dict()
    result["ledger_fees"] = ledger.get("fees_total_usdt")
    result["ledger_slippage"] = ledger.get("slippage_total_usdt")
    if not result["ok"]:
        result["reason"] = "sample escrito pero daily_close_at sigue null (bug I-13)"
    else:
        result["reason"] = "E_0 anclado (daily_close_at set); serie append-only"
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="Persistir sample MtM si estamos en ventana (default: dry-run)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo reportar ventana / mid (default si no hay --write)",
    )
    args = parser.parse_args(argv)
    write = bool(args.write) and not args.dry_run

    out = capture(write=write)
    print(json.dumps(out, indent=2, default=str))

    if not out.get("window", {}).get("in_window"):
        print(
            "\n# Esperar ventana (host):\n"
            "#   until date -u +%H:%M | grep -E '^(23:3|23:4|00:0|00:1|00:2)'; "
            "do sleep 30; done\n"
            "# Luego:\n"
            "#   docker compose -f docker-compose.local.yml exec -T worker \\\n"
            "#     python scripts/capture_paper_e0_daily_close.py --write\n"
            "# O dejar beat/Celery capture_portfolio_snapshot (cada 900s) "
            "tomar la marca sola.\n",
            file=sys.stderr,
        )
        return 2
    if write and not out.get("ok"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
