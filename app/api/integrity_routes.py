from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.core.integrity_monitor import IntegrityMonitor  # type: ignore
from app.core.operation_tracker import OperationTracker  # type: ignore
from app.core.balance_validator import BalanceValidator  # type: ignore


router = APIRouter(prefix="/integrity", tags=["integrity"])  # exported router

# Componentes de integridad — se inicializan on-demand al primer uso
_balance_validator: BalanceValidator | None = None
_operation_tracker: OperationTracker | None = None
_integrity_monitor: IntegrityMonitor | None = None


def _get_components() -> tuple[BalanceValidator, OperationTracker]:
    """Devuelve los componentes de integridad, inicializando on-demand si es necesario."""
    global _balance_validator, _operation_tracker, _integrity_monitor
    if _balance_validator is None or _operation_tracker is None:
        try:
            _balance_validator = BalanceValidator()
            _operation_tracker = OperationTracker()
            _integrity_monitor = IntegrityMonitor()
            _integrity_monitor.set_components(_balance_validator, _operation_tracker)
        except Exception as e:
            raise HTTPException(
                status_code=503,
                detail=f"No se pudieron inicializar componentes de integridad: {e}",
            )
    return _balance_validator, _operation_tracker


@router.get("/status")
async def get_integrity_status() -> Dict[str, Any]:
    try:
        balance_validator, operation_tracker = _get_components()

        balance_summary = await balance_validator.get_validation_summary()
        operation_summary = await operation_tracker.get_operation_summary()

        balance_integrity = balance_summary.get("integrity_score", 0)
        operation_integrity = operation_summary.get("success_rate", 0) * 100
        overall_integrity = (balance_integrity + operation_integrity) / 2

        return {
            "status": "healthy"
            if overall_integrity > 90
            else "degraded"
            if overall_integrity > 70
            else "critical",
            "overall_integrity_score": overall_integrity,
            "balance_validation": balance_summary,
            "operation_tracking": operation_summary,
            "timestamp": datetime.now().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {e}")


@router.post("/validate-balances")
async def force_balance_validation() -> Dict[str, Any]:
    try:
        balance_validator, _ = _get_components()
        await balance_validator.force_validation()
        return {
            "message": "Validación de balances forzada exitosamente",
            "timestamp": datetime.now().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {e}")


@router.post("/check-operations")
async def force_operation_check() -> Dict[str, Any]:
    try:
        _, operation_tracker = _get_components()
        await operation_tracker.force_operation_check()
        return {
            "message": "Verificación de operaciones forzada exitosamente",
            "timestamp": datetime.now().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {e}")


@router.get("/operations/failed")
async def get_failed_operations() -> Dict[str, Any]:
    try:
        _, operation_tracker = _get_components()
        failed_ops = await operation_tracker.get_failed_operations_summary()
        return {
            "failed_operations": failed_ops,
            "total_failed": len(failed_ops),
            "timestamp": datetime.now().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {e}")


@router.get("/operations/partial-fills")
async def get_partial_fills() -> Dict[str, Any]:
    try:
        _, operation_tracker = _get_components()
        partial_fills = await operation_tracker.get_partial_fills_summary()
        return {
            "partial_fills": partial_fills,
            "total_partial": len(partial_fills),
            "timestamp": datetime.now().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {e}")
