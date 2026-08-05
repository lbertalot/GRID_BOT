"""Read-only capital risk endpoint (ADR-003).

Router propio en vez de extender `app/api/risk_routes.py`: ese módulo está huérfano
(no registrado en `app/main.py`) y expone `POST /emergency-stop` **sin auth**;
registrarlo para colgar este endpoint activaría un stop abierto a cualquiera que
alcance la API. Acá solo hay un `GET`, liviano, `Decimal`-safe y sin secrets.

El equity y el gasto de ops entran por dependencias inyectables para que S6
(`app/core/capital_books.py`) y Track B (`app/core/ops_ledger.py`) solo tengan que
cambiar el default cuando aterricen. Nunca dispara órdenes ni habilita live.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.core.capital_risk import (
    CapitalRiskConfig,
    CapitalRiskInputError,
    EquityProvider,
    OpsProvider,
    evaluate_capital_risk,
    resolve_equity_snapshot,
    resolve_ops_snapshot,
)

router = APIRouter(prefix="/api/risk", tags=["risk"])


def get_equity_provider() -> EquityProvider:
    """Default local seguro (env / estado paper en disco). Sobrescribible por S6."""
    return resolve_equity_snapshot


def get_ops_provider() -> OpsProvider:
    """Default local seguro (env `OPS_RESERVE_USD`). Sobrescribible por Track B."""
    return resolve_ops_snapshot


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _error(status_code: int, error: str, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "data": None,
            "error": error,
            "detail": detail,
            "timestamp": _now_iso(),
        },
    )


@router.get("/capital-status")
async def capital_status(
    equity_provider: EquityProvider = Depends(get_equity_provider),
    ops_provider: OpsProvider = Depends(get_ops_provider),
) -> Any:
    """Riesgo de capital en ambas bases: `dd_trading` (kill) y `dd_pool` (informativa).

    Falla cerrado: si no hay equity reconciliado devuelve 503 en lugar de asumir
    que el book está sano.
    """
    try:
        config = CapitalRiskConfig.from_env()
    except CapitalRiskInputError as exc:
        return _error(500, "invalid_capital_risk_config", str(exc))

    equity_snapshot = equity_provider()
    if equity_snapshot.equity is None:
        return _error(
            503,
            "equity_unavailable",
            "No hay equity de trading reconciliado disponible "
            "(estado paper o CAPITAL_RISK_EQUITY_USD)",
        )

    try:
        status = evaluate_capital_risk(
            equity=equity_snapshot.equity,
            equity_prev_eod=equity_snapshot.equity_prev_eod,
            config=config,
            ops=ops_provider(),
            equity_source=equity_snapshot.source,
        )
    except CapitalRiskInputError as exc:
        return _error(500, "capital_risk_evaluation_failed", str(exc))

    payload: Dict[str, Any] = {
        "success": True,
        "data": status.to_dict(),
        "error": None,
        "timestamp": _now_iso(),
    }
    return payload
