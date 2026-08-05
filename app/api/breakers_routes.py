from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException

from app.core.breaker_visibility import get_breaker_visibility_snapshot  # type: ignore
from app.core.circuit_breakers import (  # type: ignore
    CircuitBreakers,
    get_shared_breakers,
)


router = APIRouter(prefix="/breakers", tags=["breakers"])  # exported router
# Alias bajo /api para clientes del dashboard, que consumen todo bajo /api/*
api_router = APIRouter(prefix="/api/breakers", tags=["breakers"])


def _resolve_breakers() -> CircuitBreakers:
    """Permite inyectar breakers en los routers para tests/ops."""
    injected: Optional[CircuitBreakers] = getattr(router, "breakers", None) or getattr(
        api_router, "breakers", None
    )
    return injected if injected is not None else get_shared_breakers()


async def _summary() -> Dict[str, Any]:
    try:
        return _resolve_breakers().get_all_breakers_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {e}")


async def _status() -> Dict[str, Any]:
    try:
        return get_breaker_visibility_snapshot(_resolve_breakers())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {e}")


@router.get("/summary")
async def breakers_summary() -> Dict[str, Any]:
    return await _summary()


@router.get("/status")
async def breakers_status() -> Dict[str, Any]:
    """Estado consolidado de breakers para el operador (solo lectura)."""
    return await _status()


@api_router.get("/summary")
async def breakers_summary_api() -> Dict[str, Any]:
    return await _summary()


@api_router.get("/status")
async def breakers_status_api() -> Dict[str, Any]:
    return await _status()
