from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.core.circuit_breakers import CircuitBreakers  # type: ignore


router = APIRouter(prefix="/breakers", tags=["breakers"])  # exported router


@router.get("/summary")
async def breakers_summary() -> Dict[str, Any]:
    try:
        breakers: CircuitBreakers | None = getattr(router, "breakers", None)
        if breakers is None:
            breakers = CircuitBreakers()
        return breakers.get_all_breakers_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {e}")


