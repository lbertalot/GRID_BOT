"""CEO overview aggregation (slice S3 — ADR-005 / RFC-004).

Read-only aggregation for the single-screen CEO dashboard. Most of the data is
owned by other slices (capital risk, ops ledger, live gate, books, breakers)
that ship on their own branches, so every source is consumed through an
optional adapter:

- module missing            -> widget `unavailable`, `value = None`
- adapter raises            -> widget `unavailable`, `value = None`
- data older than threshold -> widget `stale`, value kept with its timestamp

A missing source never becomes a zero: a fabricated number on this screen is
worse than no number at all (RFC-004, AC-S3.4).

Money travels as `Decimal` serialized to string. No secrets are exposed.
"""

from __future__ import annotations

import importlib
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Protocol, Tuple

from app.core.trading_mode import get_trading_mode_snapshot

logger = logging.getLogger(__name__)

STATUS_OK = "ok"
STATUS_STALE = "stale"
STATUS_UNAVAILABLE = "unavailable"

DEFAULT_STALE_SECONDS = 900  # 15 min, alineado con el MTTD exigido por el All Hands

_SENSITIVE_KEY = re.compile(
    r"(api[_-]?key|apikey|secret|token|password|passwd|credential|private[_-]?key|authorization)",
    re.IGNORECASE,
)


# ─────────────────────────────────────────────────────────────────────────────
# Contratos esperados de los otros tracks (documentados como Protocol para que
# el encaje sea explícito en review; ninguno se implementa en este slice).
# ─────────────────────────────────────────────────────────────────────────────


class CapitalRiskSource(Protocol):
    """Track A / ADR-003 — `app.core.capital_risk`."""

    def get_capital_status(self) -> Dict[str, Any]:
        """contributed_capital, equity_reconciled, kill_floor,
        dd_vs_contributed (fracción, negativa = pérdida), risk_state, as_of."""


class OpsLedgerSource(Protocol):
    """Track B / ADR-008 — `app.core.ops_ledger`."""

    def get_ops_summary(self) -> Dict[str, Any]:
        """ops_burn_mtd, ops_reserve_remaining, ops_alert, as_of."""


class LiveGateSource(Protocol):
    """Track D / ADR-007 — `app.core.live_gate`."""

    def get_live_gate_status(self) -> Dict[str, Any]:
        """signed (bool), signers (list[str]), config_hash, reason, as_of."""


class BooksSource(Protocol):
    """Track E / ADR-004 — `app.core.capital_books`."""

    def get_books(self) -> Dict[str, Any]:
        """books: [{name, allocation_pct, notional_cap_usd, ...}], as_of."""


class BreakersSource(Protocol):
    """Track F — `app.core.breakers_status`."""

    def get_breakers_status(self) -> Dict[str, Any]:
        """open_breakers (list), total_active (int), emergency_stop (bool), as_of."""


class PnlSource(Protocol):
    """Ledger de PnL (ADR-004) — `app.core.pnl_ledger`."""

    def get_pnl_summary(self) -> Dict[str, Any]:
        """pnl_mtd (Decimal), daily_pnl_pct (Decimal), as_of."""


@dataclass(frozen=True)
class AdapterSpec:
    module: str
    func: str
    track: str


CAPITAL_RISK = AdapterSpec("app.core.capital_risk", "get_capital_status", "A/ADR-003")
OPS_LEDGER = AdapterSpec("app.core.ops_ledger", "get_ops_summary", "B/ADR-008")
LIVE_GATE = AdapterSpec("app.core.live_gate", "get_live_gate_status", "D/ADR-007")
BOOKS = AdapterSpec("app.core.capital_books", "get_books", "E/ADR-004")
BREAKERS = AdapterSpec("app.core.breakers_status", "get_breakers_status", "F")
PNL = AdapterSpec("app.core.pnl_ledger", "get_pnl_summary", "ADR-004")


# ─────────────────────────────────────────────────────────────────────────────
# Carga defensiva
# ─────────────────────────────────────────────────────────────────────────────


def _import_optional(module_name: str):
    """Importa un módulo si existe; devuelve None si el track aún no está."""
    try:
        return importlib.import_module(module_name)
    except Exception:  # ImportError y cualquier fallo de import time
        return None


def _is_authorization_error(exc: Exception) -> bool:
    """Track D protegió `/api/gates/live-status`: un 401/403 no es un bug."""
    if isinstance(exc, PermissionError):
        return True
    return getattr(exc, "status_code", None) in {401, 403}


def _call_adapter(spec: AdapterSpec) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Devuelve (datos, motivo_de_indisponibilidad)."""
    module = _import_optional(spec.module)
    if module is None:
        return None, f"módulo {spec.module} no disponible (track {spec.track})"

    func = getattr(module, spec.func, None)
    if not callable(func):
        return None, f"{spec.module} no expone {spec.func}()"

    try:
        data = func()
    except Exception as exc:
        # Solo el tipo de excepción: el mensaje puede arrastrar datos sensibles.
        logger.warning("[ceo-overview] %s.%s falló: %s", spec.module, spec.func, exc)
        if _is_authorization_error(exc):
            return None, (
                f"sin autorización para leer {spec.module}"
                " (revisar credencial del adaptador)"
            )
        return None, f"fuente con error ({type(exc).__name__})"

    if not isinstance(data, dict):
        return None, f"{spec.module}.{spec.func}() devolvió un tipo inesperado"
    return data, None


# ─────────────────────────────────────────────────────────────────────────────
# Sanitización y coerción
# ─────────────────────────────────────────────────────────────────────────────


def _scrub(value: Any) -> Any:
    """Elimina cualquier clave sensible de estructuras que vengan de terceros."""
    if isinstance(value, dict):
        return {
            key: _scrub(inner)
            for key, inner in value.items()
            if not _SENSITIVE_KEY.search(str(key))
        }
    if isinstance(value, (list, tuple)):
        return [_scrub(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    return value


def _to_decimal(value: Any) -> Optional[Decimal]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _parse_timestamp(raw: Any) -> Optional[datetime]:
    if isinstance(raw, datetime):
        moment = raw
    elif isinstance(raw, str) and raw:
        try:
            moment = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment


def _stale_after_seconds() -> int:
    try:
        return int(os.getenv("CEO_OVERVIEW_STALE_SECONDS", str(DEFAULT_STALE_SECONDS)))
    except ValueError:
        return DEFAULT_STALE_SECONDS


# ─────────────────────────────────────────────────────────────────────────────
# Widgets
# ─────────────────────────────────────────────────────────────────────────────


def _widget(
    *,
    status: str,
    value: Any = None,
    as_of: Any = None,
    source: str,
    reason: Optional[str] = None,
    unit: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "status": status,
        "value": value,
        "as_of": as_of,
        "source": source,
        "reason": reason,
        "unit": unit,
    }


def unavailable(source: str, reason: str, unit: Optional[str] = None) -> Dict[str, Any]:
    return _widget(
        status=STATUS_UNAVAILABLE, value=None, source=source, reason=reason, unit=unit
    )


def _resolve(
    payload: Optional[Dict[str, Any]],
    reason: Optional[str],
    *,
    keys: List[str],
    source: str,
    unit: Optional[str],
    now: datetime,
    caster,
) -> Dict[str, Any]:
    """Construye un widget a partir de la respuesta cruda de un adaptador."""
    if payload is None:
        return unavailable(source, reason or "fuente no disponible", unit)

    raw = None
    for key in keys:
        if payload.get(key) is not None:
            raw = payload[key]
            break
    if raw is None:
        return unavailable(source, f"la fuente no reporta {keys[0]}", unit)

    value = caster(raw)
    if value is None:
        return unavailable(source, f"valor de {keys[0]} ilegible", unit)

    as_of_raw = payload.get("as_of") or payload.get("timestamp")
    as_of = _parse_timestamp(as_of_raw)
    if as_of is None:
        return _widget(
            status=STATUS_STALE,
            value=value,
            as_of=None,
            source=source,
            reason="dato sin timestamp: no se puede confirmar frescura",
            unit=unit,
        )

    age = (now - as_of).total_seconds()
    if age > _stale_after_seconds():
        return _widget(
            status=STATUS_STALE,
            value=value,
            as_of=_iso(as_of_raw, as_of),
            source=source,
            reason=f"dato de hace {int(age // 60)} min",
            unit=unit,
        )

    return _widget(
        status=STATUS_OK,
        value=value,
        as_of=_iso(as_of_raw, as_of),
        source=source,
        unit=unit,
    )


def _iso(raw: Any, parsed: datetime) -> str:
    return raw if isinstance(raw, str) else parsed.isoformat()


def _money(raw: Any) -> Optional[str]:
    value = _to_decimal(raw)
    return None if value is None else str(value)


def _percent(raw: Any) -> Optional[str]:
    value = _to_decimal(raw)
    return None if value is None else str(value.quantize(Decimal("0.01")))


def _fraction_to_percent(raw: Any) -> Optional[str]:
    value = _to_decimal(raw)
    return None if value is None else str((value * 100).quantize(Decimal("0.01")))


def _passthrough(raw: Any) -> Any:
    return _scrub(raw)


def _flag(raw: Any) -> Optional[bool]:
    return bool(raw) if isinstance(raw, bool) else None


# ─────────────────────────────────────────────────────────────────────────────
# Breakers: Track F si está, si no el estado local ya existente
# ─────────────────────────────────────────────────────────────────────────────


def _local_breakers_status(now: datetime) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        from app.core.circuit_breakers import get_shared_breakers

        summary = get_shared_breakers().get_all_breakers_status()
    except Exception as exc:
        return None, f"breakers locales con error ({type(exc).__name__})"

    return {
        "open_breakers": list(summary.get("active_breakers") or []),
        "total_active": int(summary.get("total_active") or 0),
        "critical_mode": bool(summary.get("critical_mode")),
        "as_of": now.isoformat(),
    }, None


# ─────────────────────────────────────────────────────────────────────────────
# Agregación
# ─────────────────────────────────────────────────────────────────────────────


def build_ceo_overview(
    now: Optional[datetime] = None, *, include_sensitive_detail: bool = True
) -> Dict[str, Any]:
    """Arma el payload del pantallazo CEO. Nunca levanta: degrada.

    `include_sensitive_detail=False` (lector sin credencial) recorta lo que
    Track D protegió en `/api/gates/live-status`: firmantes, `config_hash` y la
    enumeración de controles flojos. El badge de modo y de firma sigue visible.
    """
    now = now or datetime.now(timezone.utc)

    mode = get_trading_mode_snapshot()
    capital, capital_reason = _call_adapter(CAPITAL_RISK)
    ops, ops_reason = _call_adapter(OPS_LEDGER)
    gate, gate_reason = _call_adapter(LIVE_GATE)
    books, books_reason = _call_adapter(BOOKS)
    pnl, pnl_reason = _call_adapter(PNL)

    breakers, breakers_reason = _call_adapter(BREAKERS)
    breakers_source = f"{BREAKERS.module} (track {BREAKERS.track})"
    if breakers is None:
        breakers, breakers_reason = _local_breakers_status(now)
        breakers_source = "app.core.circuit_breakers (fallback local)"

    capital_source = f"{CAPITAL_RISK.module} (track {CAPITAL_RISK.track})"
    ops_source = f"{OPS_LEDGER.module} (track {OPS_LEDGER.track})"
    gate_source = f"{LIVE_GATE.module} (track {LIVE_GATE.track})"
    books_source = f"{BOOKS.module} (track {BOOKS.track})"
    pnl_source = f"{PNL.module} ({PNL.track})"

    def resolve(payload, reason, keys, source, unit, caster):
        return _resolve(
            payload,
            reason,
            keys=keys,
            source=source,
            unit=unit,
            now=now,
            caster=caster,
        )

    overview: Dict[str, Any] = {
        "generated_at": now.isoformat(),
        "effective_mode": mode["effective_mode"],
        "mode": _scrub(mode),
        "equity_reconciled": resolve(
            capital, capital_reason, ["equity_reconciled"], capital_source, "usd", _money
        ),
        "contributed_capital": resolve(
            capital,
            capital_reason,
            ["contributed_capital"],
            capital_source,
            "usd",
            _money,
        ),
        "kill_floor": resolve(
            capital, capital_reason, ["kill_floor"], capital_source, "usd", _money
        ),
        "pnl_mtd": resolve(pnl, pnl_reason, ["pnl_mtd"], pnl_source, "usd", _money),
        "breakers": resolve(
            breakers,
            breakers_reason,
            ["open_breakers"],
            breakers_source,
            None,
            _passthrough,
        ),
        "ops_burn_mtd": resolve(
            ops, ops_reason, ["ops_burn_mtd"], ops_source, "usd", _money
        ),
        # Track B / PR #36: el techo no es lo comprometido. Cada uno con su key,
        # sin fallback cruzado ni lectura del contrato viejo `ops_reserve_usd`.
        "ops_reserve_total": resolve(
            ops, ops_reason, ["ops_reserve_total"], ops_source, "usd", _money
        ),
        "ops_reserve_committed": resolve(
            ops, ops_reason, ["ops_reserve_committed"], ops_source, "usd", _money
        ),
        "ops_reserve_remaining": resolve(
            ops, ops_reason, ["ops_reserve_remaining"], ops_source, "usd", _money
        ),
        "books": resolve(books, books_reason, ["books"], books_source, None, _passthrough),
        "gate": resolve(
            gate, gate_reason, ["signed"], gate_source, None, _gate_value_factory(gate)
        ),
    }

    overview["ops_policy"] = _ops_policy_widget(ops, ops_reason, ops_source, now)
    overview["dd_vs_contributed_pct"] = _drawdown_widget(
        capital, capital_reason, capital_source, now
    )
    overview["daily_pnl_pct"] = _daily_pnl_widget(
        pnl, pnl_reason, pnl_source, capital, capital_reason, capital_source, now
    )
    overview["emergency_stop"] = _emergency_stop_widget(
        breakers, breakers_source, mode, now
    )
    overview["risk_state"] = resolve(
        capital, capital_reason, ["risk_state"], capital_source, None, _passthrough
    )

    gate_ready, blocking_reasons = evaluate_gate_readiness(overview)
    overview["gate_ready"] = gate_ready
    overview["blocking_reasons"] = blocking_reasons
    overview["live_gate_signed"] = _live_gate_badge(mode, gate)

    if not include_sensitive_detail:
        overview["gate"] = _redact_gate(overview["gate"])
        overview["blocking_reasons"] = _redact_reasons(blocking_reasons)
    return overview


def _live_gate_badge(mode: Dict[str, Any], gate: Optional[Dict[str, Any]]) -> bool:
    """Badge público de firma. Fail-closed: sin confirmación explícita, `False`.

    Preferimos el snapshot de `trading_mode` (Track D lo resuelve ahí, igual que
    `/health/trading-mode`) y sólo caemos al adaptador si el snapshot todavía no
    trae el campo en esta branch.
    """
    if isinstance(mode.get("live_gate_signed"), bool):
        return mode["live_gate_signed"]
    if gate is not None and isinstance(gate.get("signed"), bool):
        return gate["signed"]
    return False


def _redact_gate(widget: Dict[str, Any]) -> Dict[str, Any]:
    """Sin credencial se ve el booleano, no los firmantes ni el `config_hash`."""
    redacted = dict(widget)
    value = widget.get("value")
    if isinstance(value, dict):
        redacted["value"] = {
            "signed": bool(value.get("signed")),
            "detail_requires_auth": True,
        }
    return redacted


def _redact_reasons(reasons: List[str]) -> List[str]:
    """La lista de bloqueos es un inventario de controles flojos: no va sin auth."""
    if not reasons:
        return []
    return [
        f"{len(reasons)} bloqueo(s) abierto(s); el detalle requiere autenticación"
    ]


def _gate_value_factory(gate: Optional[Dict[str, Any]]):
    """El widget de gate expone firma + firmantes, no sólo el booleano."""

    def _cast(raw: Any) -> Dict[str, Any]:
        payload = gate or {}
        return {
            "signed": bool(raw),
            "signers": _scrub(list(payload.get("signers") or [])),
            "config_hash": payload.get("config_hash"),
            "reason": payload.get("reason"),
        }

    return _cast


def _ops_policy_widget(ops, reason, source, now) -> Dict[str, Any]:
    """Banderas de política ops: violación L0 y committed empujado por burn."""
    if ops is None:
        return unavailable(source, reason or "fuente no disponible")

    def _cast(raw: Any) -> Dict[str, Any]:
        return {
            "l0_policy_violation": bool(raw),
            "committed_driven_by_burn": bool(ops.get("committed_driven_by_burn")),
            "excluded_categories": _scrub(list(ops.get("excluded_categories") or [])),
            "ops_accrued_to_date": _money(ops.get("ops_accrued_to_date")),
            "ops_accrual_months": ops.get("ops_accrual_months"),
        }

    return _resolve(
        ops,
        reason,
        keys=["l0_policy_violation"],
        source=source,
        unit=None,
        now=now,
        caster=_cast,
    )


def _drawdown_widget(capital, reason, source, now) -> Dict[str, Any]:
    """`dd_vs_contributed_pct`: usa el pct si la fuente lo da, si no convierte
    la fracción de ADR-003 (negativa = pérdida) a porcentaje."""
    if capital is None:
        return unavailable(source, reason or "fuente no disponible", "pct")
    if capital.get("dd_vs_contributed_pct") is not None:
        caster = _percent
        keys = ["dd_vs_contributed_pct"]
    else:
        caster = _fraction_to_percent
        keys = ["dd_vs_contributed"]
    return _resolve(
        capital, reason, keys=keys, source=source, unit="pct", now=now, caster=caster
    )


def _daily_pnl_widget(pnl, pnl_reason, pnl_source, capital, capital_reason, capital_source, now):
    if pnl is not None and pnl.get("daily_pnl_pct") is not None:
        return _resolve(
            pnl,
            pnl_reason,
            keys=["daily_pnl_pct"],
            source=pnl_source,
            unit="pct",
            now=now,
            caster=_percent,
        )
    return _resolve(
        capital,
        capital_reason if capital is None else pnl_reason,
        keys=["daily_pnl_pct"],
        source=capital_source,
        unit="pct",
        now=now,
        caster=_percent,
    )


def _emergency_stop_widget(breakers, breakers_source, mode, now) -> Dict[str, Any]:
    if breakers is not None and isinstance(breakers.get("emergency_stop"), bool):
        return _resolve(
            breakers,
            None,
            keys=["emergency_stop"],
            source=breakers_source,
            unit=None,
            now=now,
            caster=lambda raw: bool(raw),
        )
    # El flag de entorno siempre está disponible y es la fuente de verdad de S1.
    return _widget(
        status=STATUS_OK,
        value=bool(mode.get("emergency_stop")),
        as_of=now.isoformat(),
        source="app.core.trading_mode (flag de entorno)",
        unit=None,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Semáforo go/no-go (AC-S3.5). Es lectura: no arma live ni firma nada.
# ─────────────────────────────────────────────────────────────────────────────

_GATE_CRITICAL_WIDGETS = (
    ("equity_reconciled", "equity reconciliado"),
    ("contributed_capital", "capital aportado"),
    ("kill_floor", "kill floor"),
    ("dd_vs_contributed_pct", "DD vs aportado"),
    ("pnl_mtd", "PnL MTD"),
    ("daily_pnl_pct", "PnL diario"),
    ("ops_burn_mtd", "ops burn MTD"),
    ("ops_reserve_total", "techo de reserva ops"),
    ("ops_reserve_committed", "ops committed"),
    ("ops_reserve_remaining", "reserva ops restante"),
    ("ops_policy", "política ops L0"),
    ("books", "allocation de books"),
    ("breakers", "estado de breakers"),
    ("emergency_stop", "EMERGENCY_STOP"),
    ("gate", "live gate"),
)


def evaluate_gate_readiness(overview: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Devuelve (gate_ready, razones). Sin firma dual nunca es True."""
    reasons: List[str] = []

    for key, label in _GATE_CRITICAL_WIDGETS:
        widget = overview.get(key) or {}
        if widget.get("status") != STATUS_OK:
            reasons.append(
                f"{label}: {widget.get('reason') or widget.get('status', 'desconocido')}"
            )

    gate_value = (overview.get("gate") or {}).get("value") or {}
    if not gate_value.get("signed"):
        signers = ", ".join(gate_value.get("signers") or []) or "ninguna"
        reasons.append(f"live gate sin firma dual CEO + Desk Lead (firmas: {signers})")

    breakers_value = (overview.get("breakers") or {}).get("value")
    if breakers_value:
        reasons.append(f"breakers abiertos: {', '.join(str(b) for b in breakers_value)}")

    if (overview.get("emergency_stop") or {}).get("value") is True:
        reasons.append("EMERGENCY_STOP activo")

    ops_policy = (overview.get("ops_policy") or {}).get("value") or {}
    if ops_policy.get("l0_policy_violation"):
        reasons.append("violación de política ops L0 declarada por el ledger")

    risk_state = (overview.get("risk_state") or {}).get("value")
    if risk_state in {"alert", "flat", "kill"}:
        reasons.append(f"motor de riesgo en estado {risk_state}")

    equity = _to_decimal((overview.get("equity_reconciled") or {}).get("value"))
    floor = _to_decimal((overview.get("kill_floor") or {}).get("value"))
    if equity is not None and floor is not None and equity <= floor:
        reasons.append("equity reconciliado en o por debajo del kill floor")

    return (not reasons), reasons
