#!/usr/bin/env python3
"""Reset paper-safe de la ventana L0 (próximo T0).

Copia el SoT vigente a un archivo, escribe ledger/serie L0-A (E0=1000,
deployed=200, costos 10+2 bps) y deja `system_integrity` intacto salvo flag
explícito N10. **No** es `scripts/reset_testing_state.py` (legacy: resetea
circuit breakers a lo bruto).

Paper-only. PROMOTE_LIVE: NO. No toca `.env` ni live.

Uso:
  python3.11 scripts/reset_paper_l0_window.py \\
    --telemetry-dir /tmp/tel --archive-dir /tmp/arch --dry-run
  python3.11 scripts/reset_paper_l0_window.py \\
    --telemetry-dir /tmp/tel --archive-dir /tmp/arch --config-hash HASH
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.paper_equity_ledger import (  # noqa: E402
    PaperCostModel,
    PaperEquityLedger,
    PaperEquitySeries,
    reset_paper_telemetry,
    resolve_grid_config_hash,
)

L0_INITIAL_CASH = Decimal("1000")
L0_DEPLOYED_CAPITAL = Decimal("200")

TELEMETRY_BASENAMES = (
    "paper_equity_ledger.json",
    "paper_equity_series.json",
    "last_portfolio_snapshot.json",
)

SI_N10_NOTE = (
    "N10 restart de ventana: cierre explícito de system_integrity al abrir "
    "una ventana paper nueva. No es AS-10 (AS-10 prohíbe auto-clear de SI "
    "por PnL / pérdidas consecutivas / IC-2)."
)

SI_SKIP_NOTE = (
    "system_integrity no se toca por defecto. AS-10 prohíbe auto-clear de SI "
    "por PnL. N10 restart de ventana requiere flag explícito "
    "reset_si_for_new_window=True y breakers inyectado (no Redis implícito)."
)


def _archive_existing(telemetry_dir: Path, archive_dir: Path) -> List[str]:
    """Copia a dest_archive/ solo los JSON de telemetría que existan."""
    archive_dir.mkdir(parents=True, exist_ok=True)
    archived: List[str] = []
    for name in TELEMETRY_BASENAMES:
        src = telemetry_dir / name
        if not src.is_file():
            continue
        shutil.copy2(src, archive_dir / name)
        archived.append(name)
    return archived


def _write_fresh_ledger(telemetry_dir: Path) -> PaperEquityLedger:
    """Ledger L0-A vacío: cash=1000, deployed=200, modelo 10+2 bps (Decimal)."""
    telemetry_dir.mkdir(parents=True, exist_ok=True)
    ledger = PaperEquityLedger(
        initial_cash=L0_INITIAL_CASH,
        deployed_capital=L0_DEPLOYED_CAPITAL,
        cost_model=PaperCostModel(
            maker_fee_bps=Decimal("10"),
            taker_fee_bps=Decimal("10"),
            adverse_selection_bps=Decimal("2"),
        ),
        storage_path=telemetry_dir / "paper_equity_ledger.json",
    )
    ledger.save()
    return ledger


def _write_fresh_series(
    telemetry_dir: Path,
    *,
    config_hash: Optional[str],
    seed_e0_sample: bool,
) -> PaperEquitySeries:
    """Serie nueva con hash de freeze; 0 samples o un E0=1000 si se pide."""
    series = PaperEquitySeries(
        config_hash=config_hash,
        deployed_capital=L0_DEPLOYED_CAPITAL,
        storage_path=telemetry_dir / "paper_equity_series.json",
    )
    if seed_e0_sample:
        series.record(
            L0_INITIAL_CASH,
            cash=L0_INITIAL_CASH,
            inventory_value=Decimal("0"),
            deployed_capital=L0_DEPLOYED_CAPITAL,
            config_hash=config_hash,
        )
    else:
        series.save()
    return series


def _maybe_reset_si(
    *,
    reset_si_for_new_window: bool,
    breakers: Any,
) -> Dict[str, Any]:
    """SI intacto salvo N10 explícito. Fail-closed si no hay breakers mock."""
    if not reset_si_for_new_window:
        return {
            "reset_si_for_new_window": False,
            "si_action": "skipped",
            "si_note": SI_SKIP_NOTE,
        }
    if breakers is None:
        raise ValueError(
            "reset_si_for_new_window=True requiere breakers inyectado "
            "(N10 restart de ventana, no AS-10; tests no pegan Redis)"
        )
    deactivate = getattr(breakers, "deactivate_breaker", None)
    if deactivate is None:
        return {
            "reset_si_for_new_window": True,
            "si_action": "error",
            "si_note": SI_N10_NOTE,
            "si_error": "no_deactivate",
        }
    if asyncio.iscoroutinefunction(deactivate):
        asyncio.run(deactivate("system_integrity"))
    else:
        deactivate("system_integrity")
    return {
        "reset_si_for_new_window": True,
        "si_action": "deactivated",
        "si_note": SI_N10_NOTE,
    }


def reset_paper_l0_window(
    *,
    telemetry_dir: Path,
    archive_dir: Path,
    dry_run: bool = False,
    config_hash: Optional[str] = None,
    seed_e0_sample: bool = False,
    reset_process_singletons: bool = False,
    reset_si_for_new_window: bool = False,
    breakers: Any = None,
) -> Dict[str, Any]:
    """Archiva telemetría paper y deja SoT L0 limpio. No escribe en dry-run.

    `reset_si_for_new_window` default False: no desactiva `system_integrity`.
    Si True, es N10 restart de ventana (no AS-10) y exige `breakers` inyectado.
    `reset_process_singletons` default False: no llama `reset_paper_telemetry()`.
    """
    telemetry_dir = Path(telemetry_dir)
    archive_dir = Path(archive_dir)
    if telemetry_dir.resolve() == archive_dir.resolve():
        raise ValueError("archive_dir no puede ser el mismo que telemetry_dir")

    hash_value = config_hash if config_hash is not None else resolve_grid_config_hash()
    present = [name for name in TELEMETRY_BASENAMES if (telemetry_dir / name).is_file()]

    result: Dict[str, Any] = {
        "ok": True,
        "dry_run": dry_run,
        "promote_live": "NO",
        "telemetry_dir": str(telemetry_dir),
        "archive_dir": str(archive_dir),
        "config_hash": hash_value,
        "seed_e0_sample": seed_e0_sample,
        "reset_process_singletons": reset_process_singletons,
        "cost_model_bps": {"maker": "10", "adverse_selection": "2"},
        "initial_cash": str(L0_INITIAL_CASH),
        "deployed_capital": str(L0_DEPLOYED_CAPITAL),
    }

    if dry_run:
        result["archived"] = []
        result["would_archive"] = present
        result.update(
            _maybe_reset_si(
                reset_si_for_new_window=False,
                breakers=None,
            )
        )
        result["si_note"] = (
            SI_SKIP_NOTE
            if not reset_si_for_new_window
            else SI_N10_NOTE + " Dry-run: no se desactiva SI."
        )
        result["reset_si_for_new_window"] = reset_si_for_new_window
        return result

    archived = _archive_existing(telemetry_dir, archive_dir)
    ledger = _write_fresh_ledger(telemetry_dir)
    series = _write_fresh_series(
        telemetry_dir,
        config_hash=hash_value,
        seed_e0_sample=seed_e0_sample,
    )

    if reset_process_singletons:
        reset_paper_telemetry()

    result["archived"] = archived
    result["ledger_path"] = str(ledger.storage_path)
    result["series_path"] = str(series.storage_path)
    result["samples"] = len(series.samples)
    result.update(
        _maybe_reset_si(
            reset_si_for_new_window=reset_si_for_new_window,
            breakers=breakers,
        )
    )
    return result


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI: `--archive-dir`, `--telemetry-dir`, `--dry-run`. Dry-run no escribe."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--telemetry-dir",
        required=True,
        help="Directorio de telemetría paper (tmp en tests; nunca el de ops por accidente)",
    )
    parser.add_argument(
        "--archive-dir",
        required=True,
        help="Destino de la copia (mkdir). No puede coincidir con --telemetry-dir",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Planificar sin copiar ni escribir JSON",
    )
    parser.add_argument(
        "--config-hash",
        default=None,
        help="Hash de freeze; default resolve_grid_config_hash()",
    )
    parser.add_argument(
        "--seed-e0-sample",
        action="store_true",
        help="Escribir un sample E0=1000 (si no, serie con 0 samples)",
    )
    parser.add_argument(
        "--reset-process-singletons",
        action="store_true",
        help="Llamar reset_paper_telemetry() (no usar en tests de ops)",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    # SI no se toca desde CLI: N10 exige breakers inyectado en la función
    # (tests mockean; este CLI no abre Redis). No es AS-10.
    out = reset_paper_l0_window(
        telemetry_dir=Path(args.telemetry_dir),
        archive_dir=Path(args.archive_dir),
        dry_run=args.dry_run,
        config_hash=args.config_hash,
        seed_e0_sample=args.seed_e0_sample,
        reset_process_singletons=args.reset_process_singletons,
        reset_si_for_new_window=False,
        breakers=None,
    )
    print(json.dumps(out, indent=2, default=str))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
