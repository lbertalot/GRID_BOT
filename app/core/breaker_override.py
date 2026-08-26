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
lugar a que un ciclo real se cierre con datos frescos. La ventana expira
sola por:

- Un ciclo nuevo cerrado en el ledger después de otorgado el override
  (éxito: hay evidencia fresca, se limpia y la evaluación normal retoma).
- Un número máximo de ticks sin ciclo nuevo (falla segura: se limpia y el
  breaker vuelve a su comportamiento normal, sin bypass indefinido).

No cambia thresholds, spacing ni sizing del grid. No es una API pública —
solo se otorga vía script auditado (ver ``scripts/grant_breaker_override.py``)
con referencia explícita al RCA.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Optional, Tuple

logger = logging.getLogger(__name__)

OVERRIDE_REDIS_KEY = "gridbot:breaker_override:v1"


@dataclass
class BreakerOverride:
    breaker_type: str
    granted_at: str
    granted_by: str
    rca_ref: str
    max_ticks: int = 10
    ticks_used: int = 0
    ledger_watermark: Optional[str] = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


def _from_mapping(data: dict) -> BreakerOverride:
    return BreakerOverride(
        breaker_type=str(data.get("breaker_type", "")),
        granted_at=str(data.get("granted_at", "")),
        granted_by=str(data.get("granted_by", "")),
        rca_ref=str(data.get("rca_ref", "")),
        max_ticks=int(data.get("max_ticks", 10)),
        ticks_used=int(data.get("ticks_used", 0)),
        ledger_watermark=data.get("ledger_watermark"),
    )


class _MemoryFallback:
    """Fallback en proceso si Redis no responde (fail-soft, paper-safe)."""

    _store: dict = {}


def _redis():
    from app.core.distributed_lock import get_redis_client

    return get_redis_client()


def grant_override(
    breaker_type: str,
    *,
    granted_by: str,
    rca_ref: str,
    max_ticks: int = 10,
    ledger_watermark: Optional[datetime] = None,
) -> BreakerOverride:
    """Concede el override. Debe llamarse solo desde un script auditado."""
    override = BreakerOverride(
        breaker_type=breaker_type,
        granted_at=datetime.now(timezone.utc).isoformat(),
        granted_by=granted_by,
        rca_ref=rca_ref,
        max_ticks=max_ticks,
        ticks_used=0,
        ledger_watermark=ledger_watermark.isoformat() if ledger_watermark else None,
    )
    _save(override)
    logger.warning(
        "🔓 Override RCA concedido para '%s' por %s (ref=%s, max_ticks=%s, watermark=%s)",
        breaker_type,
        granted_by,
        rca_ref,
        max_ticks,
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
) -> Tuple[bool, Optional[BreakerOverride]]:
    """Devuelve ``(skip_activation, override)``.

    ``skip_activation=True`` significa: no reactivar el breaker este tick
    porque hay un override RCA vigente. Siempre falla seguro hacia
    ``False`` (deja que la lógica normal del breaker actúe).
    """
    override = get_override(breaker_type)
    if override is None:
        return False, None

    watermark = (
        datetime.fromisoformat(override.ledger_watermark)
        if override.ledger_watermark
        else None
    )
    if ledger_latest_closed_at and watermark and ledger_latest_closed_at > watermark:
        logger.warning(
            "🔓 Override '%s' consumido: ciclo nuevo cerrado (%s) posterior al watermark (%s, ref=%s) — retoma evaluación normal",
            breaker_type,
            ledger_latest_closed_at.isoformat(),
            watermark.isoformat(),
            override.rca_ref,
        )
        clear_override(breaker_type)
        return False, override

    if override.ticks_used >= override.max_ticks:
        logger.warning(
            "🔓 Override '%s' expiró sin ciclo nuevo cerrado (%s/%s ticks, ref=%s) — resume evaluación normal",
            breaker_type,
            override.ticks_used,
            override.max_ticks,
            override.rca_ref,
        )
        clear_override(breaker_type)
        return False, override

    override.ticks_used += 1
    _save(override)
    logger.warning(
        "🔓 Override RCA activo para '%s' — se omite reactivación este ciclo (%s/%s ticks, ref=%s)",
        breaker_type,
        override.ticks_used,
        override.max_ticks,
        override.rca_ref,
    )
    return True, override
