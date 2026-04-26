from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.services.reconciliation_service import ReconciliationService  # type: ignore
from app.services.binance_client_singleton import get_binance_client_singleton  # type: ignore
from app.core.circuit_breakers import CircuitBreakers  # type: ignore


router = APIRouter(
    prefix="/api/reconciliation", tags=["reconciliation"]
)  # exported router


@router.get("/summary")
async def reconciliation_summary() -> Dict[str, Any]:
    try:
        client_singleton = get_binance_client_singleton()
        breakers: CircuitBreakers | None = getattr(router, "breakers", None)
        if breakers is None:
            breakers = CircuitBreakers()

        svc = ReconciliationService(client_singleton.client, breakers)
        result = await svc.run_reconciliation_cycle()
        if result.get("status") != "ok":
            raise HTTPException(status_code=500, detail=result)
        result["timestamp"] = datetime.now().isoformat()
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo resumen: {e}")
