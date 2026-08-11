"""Desk area actions — map OFF_TRACK/AT_RISK → acción sin CEO (AS-2).

Paper-only. No live. Complementa auto-remediate de breakers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AreaAction:
    code: str
    status: str
    owner: str
    action: str
    auto: bool
    detail: str = ""


# Owners canónicos L0 (retro agentes 2026-08-09)
_OWNER = {
    "RISK": "trader-prop + trading-backend-tdd",
    "DEVOPS": "trading-devops",
    "BE": "trading-backend-tdd",
    "MM": "trader-market-maker",
    "QUANT": "trading-quant-engineer",
    "SEC": "trading-security",
    "FE": "trading-frontend",
    "DL": "trading-desk-lead",
}


def plan_actions_for_areas(
    areas: Sequence[Any],
    *,
    remediation: Optional[Dict[str, Any]] = None,
) -> List[AreaAction]:
    """Deriva acciones desde AreaStatus-like objects (code/status/deviation)."""
    out: List[AreaAction] = []
    rem = remediation or {}
    for a in areas:
        code = str(getattr(a, "code", None) or (a.get("code") if isinstance(a, dict) else "") or "")
        status = str(
            getattr(a, "status", None) or (a.get("status") if isinstance(a, dict) else "") or ""
        )
        if status not in ("AT_RISK", "OFF_TRACK"):
            continue
        deviation = str(
            getattr(a, "deviation", None)
            or (a.get("deviation") if isinstance(a, dict) else "")
            or ""
        )
        owner = _OWNER.get(code, "trading-desk-lead")
        auto = False
        action = f"Revisar {code}: {deviation or status}"
        if code == "RISK":
            if "PAUSE" in deviation:
                action = (
                    "RISK+DL: evaluar EMERGENCY_STOP paper; no reset CB PnL; "
                    "PROMOTE_LIVE NO"
                )
            elif rem.get("acted"):
                action = "Auto-remediate ya ejecutó reset paper-safe; verificar any_open=false"
                auto = True
            elif rem.get("action") == "hold":
                action = "HOLD validate — actualizar IP allowlist Binance (humano)"
                auto = False
            elif rem.get("action") == "hold_trading_reason":
                action = (
                    "HOLD trading/PnL — no auto-clear; RCA consecutive losses/IC "
                    f"({rem.get('breaker_reason') or rem.get('reason') or 'n/a'})"
                )
                auto = False
            else:
                action = "Invocar maybe_remediate_stale_system_integrity / GET breakers"
                auto = True
        elif code == "MM":
            if "PAUSE" in deviation:
                action = (
                    "MM+DL: evaluar EMERGENCY_STOP paper (ΔE0≤-5%); "
                    "no spacing↓/sizing↑; RCA PnL"
                )
            elif "ΔE0" in deviation or "E0=" in deviation:
                action = "MM: RCA PnL/DD + SELL/IC; no bajar spacing; no sizing↑"
            else:
                action = "MM: chequear SELL/24h + IC-1/IC-2; no bajar spacing"
        elif code == "QUANT":
            if "PAUSE" in deviation:
                action = "QUANT: tear inmediato + gaps; sin claim edge (PAUSE ΔE0)"
            elif "ΔE0" in deviation or "E0=" in deviation:
                action = "QUANT: tear Capa A intraday con costos + gaps serie"
            else:
                action = "QUANT: tear Capa A EOD + gaps serie"
        elif code == "DEVOPS":
            action = "DEVOPS: daily_close_at + gaps ≤2h + Health SRE"
        elif code == "BE":
            action = "BE: logs ciclo paper / last_action / fills"
        out.append(
            AreaAction(
                code=code,
                status=status,
                owner=owner,
                action=action,
                auto=auto,
                detail=deviation,
            )
        )
    return out


def format_actions_telegram(actions: List[AreaAction]) -> Optional[str]:
    if not actions:
        return None
    lines = ["🛠️ DESK AUTO · ACCIONES (sin CEO)", "PROMOTE_LIVE: NO"]
    for a in actions:
        tag = "AUTO" if a.auto else "HUMANO"
        lines.append(f"• [{tag}] {a.code} ({a.status}) → {a.action} · owner={a.owner}")
    return "\n".join(lines)


def format_actions_markdown(actions: List[AreaAction]) -> str:
    if not actions:
        return "_Sin áreas AT_RISK/OFF_TRACK — no action._\n"
    rows = [
        "| Área | Status | Auto | Owner | Acción |",
        "|------|--------|------|-------|--------|",
    ]
    for a in actions:
        rows.append(
            f"| {a.code} | {a.status} | {'sí' if a.auto else 'no'} | {a.owner} | {a.action} |"
        )
    return "\n".join(rows) + "\n"


__all__ = [
    "AreaAction",
    "plan_actions_for_areas",
    "format_actions_telegram",
    "format_actions_markdown",
]
