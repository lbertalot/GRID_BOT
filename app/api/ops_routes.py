"""Endpoints de la reserva de ops (ADR-008 / RFC-001, enmienda CEO-01).

GET públicos: los consume el dashboard del CEO (`ops_burn_mtd`,
`ops_reserve_remaining`) y el risk engine (`ops_reserve_committed`). No exponen
secrets ni datos de exchange.
POST protegido con el patrón de auth del repo (Bearer + `require_auth`); las
categorías excluidas en L0 (`llm`) se rechazan con 400.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.auth import require_auth
from app.core.ops_cap_alerts import emit_ops_cap_alerts
from app.core.ops_ledger import (
    CURRENCY,
    OPS_CATEGORIES,
    OpsLedgerError,
    OpsLedgerStorageError,
    get_ops_ledger,
    serialize_entry,
    serialize_summary,
)

router = APIRouter(prefix="/api/ops", tags=["ops"])

_MONTH_PATTERN = r"^\d{4}-\d{2}$"


class OpsEntryIn(BaseModel):
    """Gasto operativo a imputar contra la reserva."""

    date: str = Field(..., description="Fecha ISO YYYY-MM-DD")
    category: str = Field(
        ...,
        description=(
            f"Una de: {', '.join(OPS_CATEGORIES)}. Las excluidas por política L0 "
            "(llm) se rechazan con 400."
        ),
    )
    amount_usd: Decimal = Field(..., description="Importe USD > 0 (Decimal)")
    note: str = Field("", max_length=500)


def _ledger():
    try:
        return get_ops_ledger()
    except OpsLedgerError as exc:
        raise HTTPException(
            status_code=500, detail=f"Configuración de ops ledger inválida: {exc}"
        )


@router.get("/summary")
async def ops_summary() -> Dict[str, Any]:
    """Agregados de burn/reserva. Dinero como string decimal de 2 posiciones.

    `ops_reserve_total` es el techo; `ops_reserve_committed` es lo devengado a
    hoy y el único campo que el risk engine debe restar al capital aportado.
    """
    ledger = _ledger()
    try:
        summary = ledger.summary()
    except OpsLedgerStorageError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    # B20 / ADR-008: métricas Prometheus + Telegram en rising-edge.
    emit_ops_cap_alerts(summary)
    return serialize_summary(summary)


@router.get("/ledger")
async def ops_ledger_entries(
    month: Optional[str] = Query(
        None, pattern=_MONTH_PATTERN, description="Filtro por mes ISO YYYY-MM"
    ),
) -> Dict[str, Any]:
    ledger = _ledger()
    try:
        entries = ledger.list_entries(month=month)
    except OpsLedgerStorageError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except OpsLedgerError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "month": month,
        "count": len(entries),
        "currency": CURRENCY,
        "entries": [serialize_entry(entry) for entry in entries],
    }


@router.post("/ledger", status_code=201)
async def add_ops_entry(
    payload: OpsEntryIn, _api_key: str = Depends(require_auth)
) -> Dict[str, Any]:
    ledger = _ledger()
    try:
        entry = ledger.add_entry(
            date=payload.date,
            category=payload.category,
            amount_usd=payload.amount_usd,
            note=payload.note,
        )
    except OpsLedgerStorageError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except OpsLedgerError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    summary = ledger.summary()
    # POST puede disparar cap/reserva; emitir en el mismo path que GET /summary.
    emit_ops_cap_alerts(summary)
    return {
        "entry": serialize_entry(entry),
        "summary": serialize_summary(summary),
    }
