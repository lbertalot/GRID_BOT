"""CEO overview endpoints (slice S3 — ADR-005 / RFC-004).

Read-only: este router no arma live, no firma el gate y no cambia allocations
(AC-S3.6). Sólo lee y muestra.

Exposición: por defecto exige el mismo Bearer que el resto de los endpoints
financieros. `CEO_DASHBOARD_PUBLIC=true` lo abre en modo lectura para
despliegues detrás de red confiable (VPN / túnel), nunca con secrets adentro.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.core.auth import get_api_key
from app.core.ceo_overview import (
    STATUS_OK,
    STATUS_STALE,
    STATUS_UNAVAILABLE,
    build_ceo_overview,
)

router = APIRouter(prefix="/api/ceo", tags=["ceo"])

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


def _is_public() -> bool:
    return os.getenv("CEO_DASHBOARD_PUBLIC", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def ceo_access(request: Request) -> Optional[str]:
    """Auth por defecto; lectura abierta sólo si se declaró explícitamente.

    En modo público la credencial sigue siendo útil: quien la presenta ve el
    detalle del gate (firmantes, `config_hash`, bloqueos), que Track D protegió
    en `/api/gates/live-status`. Quien no la presenta ve sólo el badge.
    """
    if _is_public():
        try:
            return get_api_key(request)
        except HTTPException:
            return None
    return get_api_key(request)


# ─────────────────────────────────────────────────────────────────────────────
# Presentación (el template no calcula nada)
# ─────────────────────────────────────────────────────────────────────────────

_CARDS = [
    ("equity_reconciled", "Equity reconciliado"),
    ("dd_vs_contributed_pct", "DD vs aportado"),
    ("kill_floor", "Kill floor"),
    ("contributed_capital", "Capital aportado"),
    ("pnl_mtd", "PnL MTD"),
    ("daily_pnl_pct", "PnL del día"),
    ("ops_burn_mtd", "Ops burn MTD"),
    ("ops_reserve_remaining", "Reserva ops (restante / techo)"),
    ("ops_reserve_committed", "Ops committed (reduce capital tradable)"),
    ("ops_policy", "Política ops L0"),
    ("breakers", "Breakers abiertos"),
    ("emergency_stop", "EMERGENCY_STOP"),
    ("books", "Books 70/20/10"),
    ("gate", "Live gate (firma dual)"),
]

_MODE_LABEL = {
    "paper": ("PAPER", "mode-paper", "Simulación: ninguna orden real"),
    "real_blocked": ("REAL BLOQUEADO", "mode-blocked", "Config real, trading frenado"),
    "real_armed": ("REAL ARMADO", "mode-armed", "Puede enviar órdenes reales"),
}

# Umbrales sólo de presentación; la política vive en el motor de riesgo (ADR-003).
_DD_ALERT_PCT = Decimal("-15")
_DD_KILL_PCT = Decimal("-25")
_DAILY_FLAT_PCT = Decimal("-3")


def _decimal(value: Any) -> Optional[Decimal]:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _risk_level(key: str, widget: Dict[str, Any], overview: Dict[str, Any]) -> str:
    """Color de la tarjeta: mira el riesgo, no sólo si el dato llegó.

    Un número fresco puede ser una mala noticia (gate sin firmar, DD en alerta)
    y no debe verse verde.
    """
    status = widget.get("status")
    if status == STATUS_UNAVAILABLE:
        return "unknown"

    value = widget.get("value")
    level = "ok"

    if key == "breakers":
        level = "danger" if value else "ok"
    elif key == "emergency_stop":
        level = "danger" if value else "ok"
    elif key == "gate":
        level = "ok" if (value or {}).get("signed") else "warn"
    elif key == "ops_policy":
        if (value or {}).get("l0_policy_violation"):
            level = "danger"
        elif (value or {}).get("committed_driven_by_burn"):
            level = "warn"
    elif key == "dd_vs_contributed_pct":
        drawdown = _decimal(value)
        if drawdown is not None:
            if drawdown <= _DD_KILL_PCT:
                level = "danger"
            elif drawdown <= _DD_ALERT_PCT:
                level = "warn"
    elif key == "daily_pnl_pct":
        daily = _decimal(value)
        if daily is not None and daily <= _DAILY_FLAT_PCT:
            level = "warn"
    elif key == "equity_reconciled":
        equity = _decimal(value)
        floor = _decimal((overview.get("kill_floor") or {}).get("value"))
        if equity is not None and floor is not None and equity <= floor:
            level = "danger"

    # Un dato viejo nunca se pinta verde, aunque su valor sea bueno.
    if status == STATUS_STALE and level == "ok":
        level = "warn"
    return level


def _format_as_of(raw: Any) -> Optional[str]:
    if not raw:
        return None
    try:
        moment = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return str(raw)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    moment = moment.astimezone(timezone.utc)
    minutes = int((datetime.now(timezone.utc) - moment).total_seconds() // 60)
    age = "recién" if minutes < 1 else f"hace {minutes} min"
    return f"{moment.strftime('%d/%m %H:%M')} UTC · {age}"


def _format_value(key: str, widget: Dict[str, Any], overview: Dict[str, Any]) -> str:
    value = widget.get("value")
    if value is None:
        return "Sin datos"

    if key == "ops_reserve_remaining":
        # El techo es contexto, no lo comprometido: se muestran juntos pero
        # rotulados distinto (Track B / PR #36).
        total = (overview.get("ops_reserve_total") or {}).get("value")
        return f"USD {value} / {total}" if total else f"USD {value}"

    if key == "ops_policy":
        if value.get("l0_policy_violation"):
            return "Violación de política L0"
        if value.get("committed_driven_by_burn"):
            return "Committed empujado por burn"
        return "Sin alertas"

    if key == "breakers":
        return "Ninguno" if not value else ", ".join(str(item) for item in value)

    if key == "emergency_stop":
        return "ACTIVO" if value else "Inactivo"

    if key == "gate":
        label = "Firmado" if value.get("signed") else "Sin firma dual"
        if value.get("detail_requires_auth"):
            return f"{label} · detalle con autenticación"
        signers = ", ".join(value.get("signers") or []) or "sin firmas"
        return f"{label} ({signers})"

    if key == "books":
        books = value.get("books") if isinstance(value, dict) else value
        if not books:
            return "Sin allocation declarada"
        return " · ".join(
            f"{book.get('name', '?')} {book.get('allocation_pct', '?')}%"
            for book in books
            if isinstance(book, dict)
        )

    unit = widget.get("unit")
    if unit == "usd":
        return f"USD {value}"
    if unit == "pct":
        return f"{value} %"
    return str(value)


def _build_cards(overview: Dict[str, Any]) -> List[Dict[str, Any]]:
    cards = []
    for key, label in _CARDS:
        widget = overview.get(key) or {}
        status = widget.get("status", "unavailable")
        risk = _risk_level(key, widget, overview)
        cards.append(
            {
                "key": key,
                "label": label,
                "status": status,
                "css": f"status-{status} risk-{risk}",
                "display": _format_value(key, widget, overview),
                "as_of": _format_as_of(widget.get("as_of")),
                "reason": widget.get("reason"),
                "source": widget.get("source"),
            }
        )
    return cards


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/overview")
async def ceo_overview(
    api_key: Optional[str] = Depends(ceo_access),
) -> Dict[str, Any]:
    """Pantallazo agregado del CEO. Degrada a `unavailable` en vez de mentir."""
    return build_ceo_overview(include_sensitive_detail=api_key is not None)


@router.get("/dashboard", response_class=HTMLResponse)
async def ceo_dashboard(
    request: Request, api_key: Optional[str] = Depends(ceo_access)
) -> HTMLResponse:
    """Vista de una pantalla, legible en móvil, con semáforo por widget."""
    authenticated = api_key is not None
    overview = build_ceo_overview(include_sensitive_detail=authenticated)
    mode = overview["effective_mode"]
    mode_label, mode_css, mode_hint = _MODE_LABEL.get(
        mode, (mode.upper(), "mode-blocked", "Modo desconocido")
    )

    return templates.TemplateResponse(
        "ceo_dashboard.html",
        {
            "request": request,
            "overview": overview,
            "cards": _build_cards(overview),
            "mode_label": mode_label,
            "mode_css": mode_css,
            "mode_hint": mode_hint,
            "gate_ready": overview["gate_ready"],
            "gate_badge": (
                "Gate: firmado" if overview["live_gate_signed"] else "Gate: sin firma"
            ),
            "gate_badge_css": (
                "gate-signed" if overview["live_gate_signed"] else "gate-unsigned"
            ),
            "authenticated": authenticated,
            "blocking_reasons": overview["blocking_reasons"],
        },
    )
