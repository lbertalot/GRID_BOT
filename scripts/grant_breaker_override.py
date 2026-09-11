"""
Otorga un override RCA temporal y acotado sobre el breaker `system_integrity`.

Uso legado (RCA puntual, max_ticks=10):

    docker compose -f docker-compose.local.yml exec -T worker python3 \
        scripts/grant_breaker_override.py \
        --breaker system_integrity \
        --granted-by "Leandro Bertalot (Desk Lead)" \
        --rca-ref "Docs/ops/rca-pnl-dd-2026-08-20.md"

Uso prueba SI 5×15 (constantes cerradas: idle 12h/720 ticks, techo 96h/5760):

    docker compose -f docker-compose.local.yml exec -T worker python3 \
        scripts/grant_breaker_override.py --trial \
        --breaker system_integrity \
        --granted-by "Leandro Bertalot (Desk Lead)" \
        --rca-ref "Docs/ops/trial-si-5x15-2026-08-29.md + Docs/ops/rca-pnl-dd-2026-08-20.md"

Solo Desk Lead. El EM no ejecuta este script. Ver `app/core/breaker_override.py`.
"""

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.core.breaker_override import (
    TRIAL_MAX_AGE_HOURS,
    TRIAL_MAX_AGE_TICKS,
    TRIAL_MAX_IDLE_HOURS,
    TRIAL_MAX_IDLE_TICKS,
    grant_override,
)
from app.core.paper_equity_ledger import get_paper_ledger, paper_equity_is_source_of_truth


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--breaker", default="system_integrity")
    parser.add_argument("--granted-by", required=True)
    parser.add_argument("--rca-ref", required=True)
    parser.add_argument("--max-ticks", type=int, default=10)
    parser.add_argument(
        "--trial",
        action="store_true",
        help=(
            "Prueba SI 5×15: ignora --max-ticks y fija idle "
            f"{TRIAL_MAX_IDLE_HOURS}h/{TRIAL_MAX_IDLE_TICKS} ticks y techo "
            f"{TRIAL_MAX_AGE_HOURS}h/{TRIAL_MAX_AGE_TICKS} ticks"
        ),
    )
    args = parser.parse_args()

    watermark = None
    if paper_equity_is_source_of_truth():
        closed = get_paper_ledger().closed_cycles()
        closed_ats = [c.closed_at for c in closed if c.closed_at]
        if closed_ats:
            watermark = max(closed_ats)

    override = grant_override(
        args.breaker,
        granted_by=args.granted_by,
        rca_ref=args.rca_ref,
        max_ticks=args.max_ticks,
        ledger_watermark=watermark,
        trial=args.trial,
    )
    print(
        f"Override concedido: breaker={override.breaker_type} "
        f"trial={args.trial} max_ticks={override.max_ticks} "
        f"max_idle_hours={override.max_idle_hours} "
        f"max_age_hours={override.max_age_hours} "
        f"max_age_ticks={override.max_age_ticks} "
        f"watermark={override.ledger_watermark} "
        f"rca_ref={override.rca_ref} granted_by={override.granted_by}"
    )
    if watermark is not None:
        print(
            "PAPER_TRIAL_STARTED_AT debe ser este watermark (closed_at ≤ t0 se ignora). "
            f"Sugerido: {watermark.isoformat()}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
