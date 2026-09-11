"""
Override temporal y auditado para el breaker ``system_integrity``.

Contexto (RCA `Docs/ops/rca-pnl-dd-2026-08-20.md`): un reset simple de
``system_integrity`` no es sostenible cuando la causa es
"pérdidas consecutivas", porque ``AutoCircuitBreaker`` recalcula la racha
en cada tick a partir de los últimos ciclos *cerrados* del ledger paper
(SoT). Si el bot lleva días bloqueado, esos mismos ciclos perdedores siguen
siendo "los últimos cerrados" y el breaker se reabre de forma
determinística antes de que pueda cerrarse ningún ciclo nuevo — un candado
circular.

Este módulo permite a un humano autorizado (Desk Lead, con RCA firmado)
conceder una ventana acotada en la que, si la evaluación de pérdidas
consecutivas dispararía el breaker, se omite la reactivación para dar
lugar a que un ciclo real se cierre con datos frescos.

Modo legado (RCA puntual): expira al primer close posterior al watermark
o a ``max_ticks`` (default 10).

Modo prueba SI (``trial=True``, ver `Docs/ops/trial-si-5x15-2026-08-29.md`):
constantes cerradas, OR el primero que gane:

- Inercia: 12 h de reloj **o** 720 ticks sin close post-t0 → SI REDUCE_ONLY.
- Techo: 96 h de reloj **o** 5760 ticks desde ``granted_at`` → SI REDUCE_ONLY.
- Primer close ``closed_at > watermark``: se limpia el override; el trip
  queda a cargo de ``PAPER_TRIAL_STREAK_THRESHOLD`` sobre racha post-t0.

No cambia spacing ni sizing del grid. No es una API pública — solo se
otorga vía ``scripts/grant_breaker_override.py`` con referencia al RCA.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import NamedTuple, Optional

logger = logging.getLogger(__name__)

OVERRIDE_REDIS_KEY = "gridbot:breaker_override:v1"

# Prueba SI 5×15 — no son flags de firma; las fija grant_override(trial=True).
TRIAL_MAX_IDLE_HOURS = 12
TRIAL_MAX_IDLE_TICKS = 720
TRIAL_MAX_AGE_HOURS = 96
TRIAL_MAX_AGE_TICKS = 5760


@dataclass
class BreakerOverride:
    breaker_type: str
    granted_at: str
    granted_by: str
    rca_ref: str
    max_ticks: int = 10
    ticks_used: int = 0
    ledger_watermark: Optional[str] = None
    max_idle_hours: Optional[int] = None
    max_age_hours: Optional[int] = None
    max_age_ticks: Optional[int] = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


class OverrideCheckResult(NamedTuple):
    skip_activation: bool
    override: Optional[BreakerOverride]
    force_reduce_only: bool = False


def _opt_int(data: dict, key: str) -> Optional[int]:
    val = data.get(key)
    if val is None or val == "":
        return None
    return int(val)


def _from_mapping(data: dict) -> BreakerOverride:
    return BreakerOverride(
        breaker_type=str(data.get("breaker_type", "")),
        granted_at=str(data.get("granted_at", "")),
        granted_by=str(data.get("granted_by", "")),
        rca_ref=str(data.get("rca_ref", "")),
        max_ticks=int(data.get("max_ticks", 10)),
        ticks_used=int(data.get("ticks_used", 0)),
        ledger_watermark=data.get("ledger_watermark"),
        max_idle_hours=_opt_int(data, "max_idle_hours"),
        max_age_hours=_opt_int(data, "max_age_hours"),
        max_age_ticks=_opt_int(data, "max_age_ticks"),
    )


class _MemoryFallback:
    """Fallback en proceso si Redis no responde (fail-soft, paper-safe)."""

    _store: dict = {}


def _redis():
    from app.core.distributed_lock import get_redis_client

    return get_redis_client()


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def grant_override(
    breaker_type: str,
    *,
    granted_by: str,
    rca_ref: str,
    max_ticks: int = 10,
    ledger_watermark: Optional[datetime] = None,
    trial: bool = False,
) -> BreakerOverride:
    """Concede el override. Debe llamarse solo desde un script auditado."""
    idle_hours: Optional[int] = None
    age_hours: Optional[int] = None
    age_ticks: Optional[int] = None
    if trial:
        max_ticks = TRIAL_MAX_IDLE_TICKS
        idle_hours = TRIAL_MAX_IDLE_HOURS
        age_hours = TRIAL_MAX_AGE_HOURS
        age_ticks = TRIAL_MAX_AGE_TICKS
    override = BreakerOverride(
        breaker_type=breaker_type,
        granted_at=datetime.now(timezone.utc).isoformat(),
        granted_by=granted_by,
        rca_ref=rca_ref,
        max_ticks=max_ticks,
        ticks_used=0,
        ledger_watermark=ledger_watermark.isoformat() if ledger_watermark else None,
        max_idle_hours=idle_hours,
        max_age_hours=age_hours,
        max_age_ticks=age_ticks,
    )
    _save(override)
    logger.warning(
        "🔓 Override RCA concedido para '%s' por %s (ref=%s, trial=%s, "
        "max_ticks=%s, idle_h=%s, age_h=%s, age_ticks=%s, watermark=%s)",
        breaker_type,
        granted_by,
        rca_ref,
        trial,
        max_ticks,
        idle_hours,
        age_hours,
        age_ticks,
        override.ledger_watermark,
    )
    return override


def get_override(breaker_type: str) -> Optional[BreakerOverride]:
    try:
        raw = _redis().hget(OVERRIDE_REDIS_KEY, breaker_type)
    except Exception as exc:  # noqa: BLE001 — fail-soft
        logger.warning("breaker_override Redis read failed: %s", exc)
        raw = _MemoryFallback._store.get(breaker_type)
        return _from_mapping(json.loads(raw)) if raw else None
    if not raw:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    try:
        return _from_mapping(json.loads(raw))
    except Exception as exc:  # noqa: BLE001
        logger.warning("breaker_override corrupto: %s", exc)
        return None


def clear_override(breaker_type: str) -> None:
    try:
        _redis().hdel(OVERRIDE_REDIS_KEY, breaker_type)
    except Exception as exc:  # noqa: BLE001
        logger.warning("breaker_override Redis clear failed: %s", exc)
    _MemoryFallback._store.pop(breaker_type, None)


def _save(override: BreakerOverride) -> None:
    try:
        _redis().hset(OVERRIDE_REDIS_KEY, override.breaker_type, override.to_json())
    except Exception as exc:  # noqa: BLE001
        logger.warning("breaker_override Redis write failed: %s", exc)
        _MemoryFallback._store[override.breaker_type] = override.to_json()


def check_and_consume_override(
    breaker_type: str,
    *,
    ledger_latest_closed_at: Optional[datetime] = None,
    now: Optional[datetime] = None,
) -> OverrideCheckResult:
    """Evalúa el override este tick.

    ``skip_activation=True``: no reactivar SI (ventana vigente).
    ``force_reduce_only=True``: prueba SI — expiró sin close post-t0; reabrir REDUCE_ONLY.
    Siempre falla seguro hacia no-skip / no-force si no hay override.
    """
    override = get_override(breaker_type)
    if override is None:
        return OverrideCheckResult(False, None, False)

    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=timezone.utc)

    watermark = _parse_iso(override.ledger_watermark)
    latest = ledger_latest_closed_at
    if latest is not None and latest.tzinfo is None:
        latest = latest.replace(tzinfo=timezone.utc)

    if latest and watermark and latest > watermark:
        logger.warning(
            "🔓 Override '%s' consumido: ciclo nuevo cerrado (%s) posterior al watermark (%s, ref=%s) — retoma evaluación normal",
            breaker_type,
            latest.isoformat(),
            watermark.isoformat(),
            override.rca_ref,
        )
        clear_override(breaker_type)
        return OverrideCheckResult(False, override, False)

    granted_at = _parse_iso(override.granted_at)
    hours_elapsed: Optional[float] = None
    if granted_at is not None:
        hours_elapsed = (clock - granted_at).total_seconds() / 3600.0

    trial_mode = override.max_idle_hours is not None or override.max_age_hours is not None

    def _expire(*, force: bool, why: str) -> OverrideCheckResult:
        logger.warning(
            "🔓 Override '%s' expiró (%s, ticks=%s/%s, ref=%s) — resume evaluación normal",
            breaker_type,
            why,
            override.ticks_used,
            override.max_ticks,
            override.rca_ref,
        )
        clear_override(breaker_type)
        return OverrideCheckResult(False, override, force)

    if (
        override.max_age_hours is not None
        and hours_elapsed is not None
        and hours_elapsed >= override.max_age_hours
    ):
        return _expire(force=True, why=f"techo {override.max_age_hours}h de reloj")

    if (
        override.max_age_ticks is not None
        and override.ticks_used >= override.max_age_ticks
    ):
        return _expire(
            force=True, why=f"techo {override.max_age_ticks} ticks absolutos"
        )

    if (
        override.max_idle_hours is not None
        and hours_elapsed is not None
        and hours_elapsed >= override.max_idle_hours
    ):
        return _expire(force=True, why=f"inercia {override.max_idle_hours}h sin close post-t0")

    if override.ticks_used >= override.max_ticks:
        return _expire(
            force=trial_mode,
            why=f"inercia {override.max_ticks} ticks sin close nuevo",
        )

    override.ticks_used += 1
    _save(override)
    logger.warning(
        "🔓 Override RCA activo para '%s' — se omite reactivación este ciclo (%s/%s ticks, ref=%s)",
        breaker_type,
        override.ticks_used,
        override.max_ticks,
        override.rca_ref,
    )
    return OverrideCheckResult(True, override, False)
