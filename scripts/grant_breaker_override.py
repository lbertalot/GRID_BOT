"""
Otorga un override RCA temporal y acotado sobre el breaker `system_integrity`.

Uso (dentro del contenedor worker, requiere RCA firmado):

    docker compose -f docker-compose.local.yml exec -T worker python3 \
        scripts/grant_breaker_override.py \
        --breaker system_integrity \
        --granted-by "Leandro Bertalot (Desk Lead)" \
        --rca-ref "Docs/ops/rca-pnl-dd-2026-08-20.md" \
        --max-ticks 10

No cambia thresholds, spacing ni sizing del grid. Ver `app/core/breaker_override.py`
para el mecanismo de expiración (ciclo nuevo cerrado, o límite de ticks).
"""

import argparse
import sys

from app.core.breaker_override import grant_override
from app.core.paper_equity_ledger import get_paper_ledger, paper_equity_is_source_of_truth


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--breaker", default="system_integrity")
    parser.add_argument("--granted-by", required=True)
    parser.add_argument("--rca-ref", required=True)
    parser.add_argument("--max-ticks", type=int, default=10)
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
    )
    print(
        f"Override concedido: breaker={override.breaker_type} "
        f"max_ticks={override.max_ticks} watermark={override.ledger_watermark} "
        f"rca_ref={override.rca_ref} granted_by={override.granted_by}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
