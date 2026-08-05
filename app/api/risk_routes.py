#!/usr/bin/env python3
"""ORPHAN — no registrar en ``app/main.py``.

Históricamente este módulo exponía ``POST /api/v2/risk/emergency-stop`` y
``POST /reset-emergency-stop`` **sin auth**. Queda deshabilitado a propósito:

- No incluir ``include_router`` desde main (test: ``test_orphan_risk_routes_stay_unregistered``).
- Si alguien lo cablea por error, los mutadores responden **410 Gone** y
  exigen ``require_auth`` (defense-in-depth).
- Capital risk live: ``app/api/capital_risk_routes.py`` (GET only).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import require_auth

router = APIRouter(prefix="/api/v2/risk", tags=["risk-orphan-disabled"])

_GONE_DETAIL = (
    "Orphan risk_routes deshabilitado (sin auth histórico). "
    "Usar breakers/CEO autenticados o capital_risk_routes."
)


def _gone() -> None:
    raise HTTPException(status_code=410, detail=_GONE_DETAIL)


@router.get("/status")
async def get_risk_status(_api_key: str = Depends(require_auth)) -> Dict[str, Any]:
    _gone()
    return {}  # pragma: no cover


@router.post("/emergency-stop")
async def trigger_emergency_stop(
    reason: str = "",
    _api_key: str = Depends(require_auth),
) -> Dict[str, Any]:
    _gone()
    return {}  # pragma: no cover


@router.post("/reset-emergency-stop")
async def reset_emergency_stop(
    _api_key: str = Depends(require_auth),
) -> Dict[str, Any]:
    _gone()
    return {}  # pragma: no cover


@router.post("/update-metrics")
async def update_risk_metrics(
    daily_loss: float = 0.0,
    total_exposure: float = 0.0,
    _api_key: str = Depends(require_auth),
) -> Dict[str, Any]:
    _gone()
    return {}  # pragma: no cover


@router.post("/apply-regime-filter")
async def apply_market_regime_filter(
    regime: str = "",
    _api_key: str = Depends(require_auth),
) -> Dict[str, Any]:
    _gone()
    return {}  # pragma: no cover


@router.get("/circuit-breaker-status")
async def get_circuit_breaker_status(
    _api_key: str = Depends(require_auth),
) -> Dict[str, Any]:
    _gone()
    return {}  # pragma: no cover


@router.post("/calculate-position-size")
async def calculate_position_size(
    _api_key: str = Depends(require_auth),
) -> Dict[str, Any]:
    _gone()
    return {}  # pragma: no cover


@router.post("/calculate-trailing-stop")
async def calculate_trailing_stop(
    _api_key: str = Depends(require_auth),
) -> Dict[str, Any]:
    _gone()
    return {}  # pragma: no cover


@router.post("/update-trailing-stop")
async def update_trailing_stop(
    _api_key: str = Depends(require_auth),
) -> Dict[str, Any]:
    _gone()
    return {}  # pragma: no cover


@router.get("/trailing-stops")
async def get_trailing_stops(_api_key: str = Depends(require_auth)) -> Dict[str, Any]:
    _gone()
    return {
        "disabled_at": datetime.now(timezone.utc).isoformat(),
    }  # pragma: no cover
