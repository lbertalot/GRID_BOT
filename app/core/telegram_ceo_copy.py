"""Capa de copy Telegram para el CEO (español llano).

Misma verdad que el digest desk / tablero `gridbot-ceo-auto`.
No promete ganancia ni auto-clear de frenos de PnL (AS-10).
Paper-only · PROMOTE_LIVE: NO.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

SEMAFORO_VERDE = 0
SEMAFORO_NARANJA = 1
SEMAFORO_ROJO_CAPITAL = 2
SEMAFORO_ROJO_SISTEMA = 3

_LABEL = {
    SEMAFORO_VERDE: "VERDE",
    SEMAFORO_NARANJA: "NARANJA",
    SEMAFORO_ROJO_CAPITAL: "ROJO CAPITAL",
    SEMAFORO_ROJO_SISTEMA: "ROJO SISTEMA",
}

_ACCION = {
    SEMAFORO_VERDE: "Prueba andando. No hagas nada.",
    SEMAFORO_NARANJA: (
        "Aviso. Cuenta de ensayo un poco abajo y/o el bot pausó por racha de pérdidas. "
        "No pases a dinero real. No resetear el freno."
    ),
    SEMAFORO_ROJO_CAPITAL: (
        "Caída fuera de aviso. El equipo interviene. No pases a dinero real."
    ),
    SEMAFORO_ROJO_SISTEMA: (
        "Máquina o IP. Revisá el servidor / la lista de IPs. El ensayo está a ciegas."
    ),
}

REDIS_KEY_PREFIX = "gridbot:tg:ceo:"
HOLD_PNL_MIN_REPEAT_S = 6 * 3600  # recordatorio 6 h (rango 6–12 vía env)
_HOLD_SI_REPEAT_MIN_S = 6 * 3600
_HOLD_SI_REPEAT_MAX_S = 12 * 3600
DIGEST_MIN_REPEAT_S = 7 * 24 * 3600  # solo si cambia huella, salvo EOD (force)

_mem_store: Dict[str, Tuple[str, float]] = {}


def hold_si_min_repeat_s() -> float:
    """Cadencia de reaviso SI mientras el fingerprint no cambia (6–12 h)."""
    raw = (os.getenv("TELEGRAM_SI_HOLD_REPEAT_S") or "").strip()
    if not raw:
        return float(HOLD_PNL_MIN_REPEAT_S)
    try:
        value = float(raw)
    except ValueError:
        return float(HOLD_PNL_MIN_REPEAT_S)
    return max(_HOLD_SI_REPEAT_MIN_S, min(_HOLD_SI_REPEAT_MAX_S, value))


def classify_si_reason(reason: Optional[str]) -> str:
    """Clasifica el reason de SI para copy (no cambia el breaker)."""
    from app.core.desk_auto_remediation import is_stale_net_auth_integrity_reason

    if is_stale_net_auth_integrity_reason(reason):
        return "auth"
    text = str(reason or "")
    lowered = text.lower()
    if (
        "no-go" in lowered
        or "sin close post-t0" in lowered
        or "idle" in lowered
    ):
        return "trial_nogo"
    if "pérdida" in lowered or "consecutiv" in lowered:
        return "pnl_streak"
    return "integrity"


def ceo_plain_enabled() -> bool:
    raw = (os.getenv("TELEGRAM_CEO_PLAIN") or "true").strip().lower()
    return raw not in ("0", "false", "no", "off")


def desk_verbose_enabled() -> bool:
    raw = (os.getenv("TELEGRAM_DESK_VERBOSE") or "false").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _parse_delta_pct(delta_pct: Optional[str]) -> Optional[float]:
    if delta_pct is None:
        return None
    try:
        return float(str(delta_pct).rstrip("%").strip())
    except (TypeError, ValueError):
        return None


def _dd_band(delta: Optional[float]) -> str:
    from app.core.desk_hourly_status import (
        EQUITY_DD_AT_RISK_PCT,
        EQUITY_DD_OFF_TRACK_PCT,
        EQUITY_DD_PAUSE_PCT,
        _equity_dd_thresholds,
    )

    try:
        at, off, pause = _equity_dd_thresholds()
    except Exception:
        at, off, pause = (
            EQUITY_DD_AT_RISK_PCT,
            EQUITY_DD_OFF_TRACK_PCT,
            EQUITY_DD_PAUSE_PCT,
        )
    if delta is None:
        return "na"
    if delta <= pause or delta <= off:
        return "off"
    if delta <= at:
        return "at"
    return "ok"


def ceo_semaforo(digest: Any) -> int:
    """0 verde · 1 naranja · 2 rojo capital · 3 rojo sistema."""
    mode = str(getattr(digest, "effective_mode", "") or "")
    if mode != "paper":
        return SEMAFORO_ROJO_SISTEMA
    delta = _parse_delta_pct(getattr(digest, "equity_delta_pct", None))
    band = _dd_band(delta)
    if band == "off":
        return SEMAFORO_ROJO_CAPITAL
    if band == "at" or bool(getattr(digest, "any_open_breakers", False)):
        return SEMAFORO_NARANJA
    return SEMAFORO_VERDE


def digest_fingerprint(digest: Any, *, hold_kind: str = "none") -> str:
    mode = str(getattr(digest, "effective_mode", "") or "unknown")
    delta = _parse_delta_pct(getattr(digest, "equity_delta_pct", None))
    return "|".join(
        (
            str(ceo_semaforo(digest)),
            _dd_band(delta),
            mode,
            hold_kind or "none",
        )
    )


def hold_kind_from_remediation(remediation: Optional[Dict[str, Any]]) -> str:
    if not remediation:
        return "none"
    action = str(remediation.get("action") or "")
    if action == "hold_trading_reason":
        return "pnl"
    if action == "hold":
        return "auth"
    if remediation.get("acted"):
        return "none"
    return "none"


def _redis_client():
    url = (os.getenv("REDIS_URL") or os.getenv("CELERY_BROKER_URL") or "").strip()
    if not url:
        return None
    try:
        import redis

        parsed = urlparse(url)
        if parsed.scheme not in ("redis", "rediss"):
            return None
        return redis.Redis.from_url(url, socket_timeout=1.5, decode_responses=True)
    except Exception:
        return None


def _load_last(channel: str) -> Optional[Tuple[str, float]]:
    key = REDIS_KEY_PREFIX + channel
    client = _redis_client()
    if client is not None:
        try:
            raw = client.get(key)
            if raw:
                data = json.loads(raw)
                return str(data.get("fp") or ""), float(data.get("ts") or 0)
        except Exception as exc:
            logger.debug("telegram ceo debounce redis get: %s", exc)
    return _mem_store.get(channel)


def _save_last(channel: str, fingerprint: str, ts: float) -> None:
    _mem_store[channel] = (fingerprint, ts)
    key = REDIS_KEY_PREFIX + channel
    client = _redis_client()
    if client is None:
        return
    try:
        client.setex(
            key,
            int(DIGEST_MIN_REPEAT_S),
            json.dumps({"fp": fingerprint, "ts": ts}),
        )
    except Exception as exc:
        logger.debug("telegram ceo debounce redis set: %s", exc)


def should_emit_ceo(
    channel: str,
    fingerprint: str,
    *,
    force: bool = False,
    min_repeat_s: float = DIGEST_MIN_REPEAT_S,
    now: Optional[float] = None,
) -> bool:
    """True si hay que mandar Telegram CEO (cambio de huella, force, o TTL)."""
    ts = time.time() if now is None else now
    if force:
        _save_last(channel, fingerprint, ts)
        return True
    last = _load_last(channel)
    if last is None:
        _save_last(channel, fingerprint, ts)
        return True
    prev_fp, prev_ts = last
    if prev_fp != fingerprint:
        _save_last(channel, fingerprint, ts)
        return True
    if min_repeat_s > 0 and (ts - prev_ts) >= min_repeat_s:
        _save_last(channel, fingerprint, ts)
        return True
    return False


def reset_debounce_memory() -> None:
    _mem_store.clear()


def _fmt_equity(raw: Optional[str]) -> str:
    if raw is None or raw == "":
        return "no disponible"
    text = str(raw).strip()
    if "." in text:
        whole, frac = text.split(".", 1)
        return f"{whole}.{frac[:2]}"
    return text


def _fmt_delta(delta_pct: Optional[str]) -> str:
    parsed = _parse_delta_pct(delta_pct)
    if parsed is None:
        return "n/a"
    return f"{parsed:.2f}%"


def render_ceo_digest(digest: Any) -> str:
    when = getattr(digest, "when", None)
    hhmm = "??"
    if when is not None:
        try:
            hhmm = when.astimezone(timezone.utc).strftime("%H:%M")
        except Exception:
            hhmm = when.strftime("%H:%M")
    level = ceo_semaforo(digest)
    mode_ok = str(getattr(digest, "effective_mode", "")) == "paper"
    mode_line = (
        "Modo: **Ensayo (paper)** · Dinero real: **NO**"
        if mode_ok
        else f"Modo: {digest.effective_mode} (revisar) · Dinero real: **NO**"
    )
    lines = [
        f"🧭 **Cómo va la prueba** · Día {digest.day_n}/30 · {hhmm} UTC",
        mode_line,
        "",
        f"💰 Balance (ensayo): {_fmt_equity(digest.equity_last)}"
        f"   ·   Cambio vs inicio: {_fmt_delta(digest.equity_delta_pct)}",
        f"Semáforo: {_LABEL[level]}",
        _ACCION[level],
    ]
    if level in (SEMAFORO_NARANJA, SEMAFORO_ROJO_CAPITAL):
        lines.append(
            "Este balance es valor estimado de la cuenta de ensayo, no ganancia realizada."
        )
    if getattr(digest, "any_open_breakers", False) and level != SEMAFORO_ROJO_SISTEMA:
        lines.append(
            "Freno de protección activo — no implica una pérdida nueva. "
            "No resetear el freno."
        )
    return "\n".join(lines)


def utc_stamp_line() -> str:
    """Timestamp UTC para copy CEO / Telegram (el bot corre en UTC)."""
    return datetime.now(timezone.utc).strftime("Reloj: %Y-%m-%d %H:%M UTC")


def _format_triggered_at(
    activated_at: Optional[str],
    now: Optional[float] = None,
) -> str:
    if not activated_at:
        return "n/d"
    stamp = str(activated_at).replace("Z", "+00:00")
    try:
        when = datetime.fromisoformat(stamp)
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        iso = when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        return str(activated_at)[:40]
    ts = time.time() if now is None else now
    age_s = max(0.0, ts - when.timestamp())
    hours = int(age_s // 3600)
    mins = int((age_s % 3600) // 60)
    age = f"hace {hours} h" if hours >= 1 else f"hace {mins} min"
    return f"{iso} ({age})"


def _motivo_estructurado(kind: str, _reason: Optional[str] = None) -> str:
    if kind == "trial_nogo":
        return "NO-GO SI: 0 cierres post-t0; idle vencido"
    if kind == "pnl_streak":
        return "Pérdidas consecutivas en el libro de ensayo (históricas)"
    return "freno de integridad activo; causa en revisión"


def _read_historical_streak() -> Optional[int]:
    """Racha SoT read-only. No resetea ledger ni breakers. Sin default numérico."""
    try:
        from app.core.auto_circuit_breaker import consecutive_losses_from_closed_cycles
        from app.core.paper_equity_ledger import reload_paper_ledger_from_disk

        ledger = reload_paper_ledger_from_disk()
        return int(consecutive_losses_from_closed_cycles(ledger.closed_cycles()))
    except Exception:
        return None


def _streak_copy_line(streak: Optional[int]) -> str:
    if streak is None:
        return (
            "Racha histórica preservada; consultar ledger. "
            "No implica una pérdida nueva"
        )
    return (
        f"Racha histórica preservada: {int(streak)}; "
        "no implica una pérdida nueva"
    )


def render_hold_pnl_telegram(
    reason: Optional[str] = None,
    *,
    operational_state: Optional[str] = None,
    public_state: Optional[str] = None,
    activated_at: Optional[str] = None,
    historical_streak: Optional[int] = None,
    now: Optional[float] = None,
) -> str:
    """Copy SI / hold: causa técnica, sin afirmar una pérdida nueva."""
    kind = classify_si_reason(reason)
    estado = str(public_state or "").strip()
    if not estado:
        ops = str(operational_state or "").strip()
        ops_u = ops.upper()
        if ops_u == "REDUCE_ONLY":
            estado = "OPEN · REDUCE_ONLY"
        elif ops_u in ("", "OPEN", "CLOSED"):
            estado = "OPEN"
        elif ops_u.startswith("OPEN"):
            estado = ops
        else:
            estado = "OPEN"
    if "CLOSED" in estado.upper() and "REDUCE_ONLY" not in estado.upper():
        estado = "OPEN"
    streak = (
        historical_streak
        if historical_streak is not None
        else _read_historical_streak()
    )
    return (
        "🟠 **Freno activo — system_integrity**\n"
        "breaker_type: system_integrity\n"
        f"Estado: {estado}\n"
        f"Desde: {_format_triggered_at(activated_at, now)}\n"
        f"Motivo: {_motivo_estructurado(kind, reason)}\n"
        f"{_streak_copy_line(streak)}\n"
        "Modo: PAPER · Dinero real: NO\n"
        "Acción: No resetear el freno; revisar el acta/tear sheet"
    )


def render_si_cleared_telegram() -> str:
    return (
        "🟢 **Freno de protección levantado**\n"
        "El ensayo puede volver a operar en paper.\n"
        "Modo: PAPER · Dinero real: NO"
    )


def render_hold_auth_telegram() -> str:
    return (
        "🟠 **Freno: no valida red/clave**\n"
        "Suele ser un cambio de IP. Si llegó el aviso rojo de Binance, seguí esos pasos.\n"
        f"{utc_stamp_line()}\n"
        "**Dinero real: NO.**"
    )


def render_remediated_telegram() -> str:
    return (
        "🟢 **Freno de conexión levantado**\n"
        "Red/clave OK; se limpió un freno de *conexión*, no de pérdidas.\n"
        "Seguí en ensayo. **Dinero real: NO.**"
    )


def render_invalid_ip_telegram(public_ip: str, *, location_restricted: bool) -> str:
    ip = public_ip or "desconocida"
    if location_restricted:
        return (
            "🔴 **Binance bloquea esta ubicación**\n"
            "El ensayo no puede hablar con Binance desde esta red.\n"
            f"IP actual: `{ip}`\n"
            "**Tu tarea:** usar una red/servidor en una región permitida, "
            "o avisar al equipo.\n"
            "**Dinero real: NO.**"
        )
    return (
        "🔴 **Binance no acepta esta conexión**\n"
        "El ensayo no puede hablar con Binance porque cambió la IP "
        "(corte de luz / red).\n"
        "**Tu tarea:** en Binance → API → lista de IPs permitidas, agregá:\n"
        f"`{ip}`\n"
        "Sacá IPs viejas si hace falta.\n"
        "No se retoma solo: hay que confirmar auth OK después del cambio.\n"
        "**Dinero real: NO.**"
    )


def render_binance_auth_ip_recovered_telegram() -> str:
    return (
        "🟢 **Binance autenticó de nuevo**\n"
        "La llamada autenticada posterior al incidente IP (−2015) fue OK.\n"
        "Modo: PAPER · Dinero real: NO"
    )


def render_breaker_store_missing_telegram() -> str:
    """Copy P0: HASH de breakers ausente → fail-closed REDUCE_ONLY."""
    return _CEO_ALERT_COPY["BreakerStoreMissingFailClosed"]


def render_eod_ceo(digest: Any, *, tear_ok: bool) -> str:
    level = ceo_semaforo(digest)
    extra = "El informe del día quedó guardado para el equipo." if tear_ok else (
        "El informe del día no se pudo armar; el equipo lo revisa."
    )
    return (
        f"📋 **Cierre del día** · Día {digest.day_n}/30\n"
        f"Modo: Ensayo · Dinero real: **NO**\n"
        f"💰 Balance (ensayo): {_fmt_equity(digest.equity_last)}"
        f"   ·   Cambio vs inicio: {_fmt_delta(getattr(digest, 'equity_delta_pct', None))}\n"
        f"Semáforo: {_LABEL[level]}\n"
        f"{_ACCION[level]}\n"
        f"{extra}"
    )


def render_ceo_actions_ack() -> str:
    return (
        "🟠 El equipo ya tiene las tareas del aviso. Vos no tenés que hacer nada.\n"
        "**Dinero real: NO.**"
    )


# --- Alertmanager → CEO (anti-ruido Flower / epoch Go) ---

_ALERT_CEO_DEBOUNCE_S = 12 * 3600

_CEO_ALERT_COPY = {
    "PaperSnapshotStale20m": (
        "⚠️ **Chequeo de estado retrasado**\n"
        "El valor de la cuenta de ensayo no se actualizó hace más de 20 minutos.\n"
        "El equipo lo mira. **No resetear frenos. Dinero real: NO.**"
    ),
    "TradingModeNotPaper": (
        "🔴 **El ensayo no está en modo ensayo**\n"
        "Pará y avisá al equipo. **Dinero real: NO.**"
    ),
    "BinanceRecvWindowErrors": (
        "🟠 **El reloj del servidor y Binance no coinciden**\n"
        "El ensayo puede verse a ciegas un rato. El equipo lo mira. "
        "**Dinero real: NO.**"
    ),
    "PaperEquityGaugeAbsent": (
        "⚠️ **No hay lectura de balance de ensayo en el tablero**\n"
        "El equipo lo mira. **No resetear frenos. Dinero real: NO.**"
    ),
    "BreakerStoreMissingFailClosed": (
        "🔴 **Freno: se perdió el estado de protección**\n"
        "El candado de la cuenta de ensayo no estaba en la memoria compartida. "
        "El sistema frenó solo (solo puede vender para reducir, no comprar).\n"
        "El equipo lo mira. **No resetear frenos. Dinero real: NO.**"
    ),
}


def _alert_labels(alert: Dict[str, Any]) -> Dict[str, Any]:
    labels = alert.get("labels")
    return labels if isinstance(labels, dict) else {}


def is_flower_snapshot_false_positive(alert: Dict[str, Any]) -> bool:
    """Flower publica unixtime=0 → Prometheus ve 56 años de atraso."""
    labels = _alert_labels(alert)
    name = str(labels.get("alertname") or "")
    if name != "PaperSnapshotStale20m":
        return False
    blob = f"{labels.get('instance') or ''} {labels.get('job') or ''}".lower()
    job = str(labels.get("job") or "")
    return "flower" in blob or job == "gridbot-celery"


def _is_resolved_alert(alert: Dict[str, Any]) -> bool:
    return str(alert.get("status") or "firing").strip().lower() == "resolved"


def format_alertmanager_ceo(
    payload: Dict[str, Any],
    severity: str,
    *,
    now: Optional[float] = None,
) -> Optional[str]:
    """Copy llano para el CEO. None = no mandar Telegram (ruido / debounce)."""
    alerts = payload.get("alerts")
    if not isinstance(alerts, list) or not alerts:
        fallback = payload.get("message") or payload.get("summary")
        if not fallback:
            return None
        return (
            f"⚠️ Aviso del ensayo ({severity})\n"
            f"{fallback}\n"
            "**Dinero real: NO.**"
        )

    kept: list[Dict[str, Any]] = []
    for alert in alerts:
        if not isinstance(alert, dict):
            continue
        if _is_resolved_alert(alert):
            continue
        if is_flower_snapshot_false_positive(alert):
            continue
        kept.append(alert)
    if not kept:
        return None

    names = sorted(
        {
            str(_alert_labels(a).get("alertname") or "aviso")
            for a in kept
        }
    )
    fp = "|".join(names)
    channel = "am:" + (names[0] if len(names) == 1 else "bundle")
    if not should_emit_ceo(
        channel,
        fp,
        min_repeat_s=_ALERT_CEO_DEBOUNCE_S,
        now=now,
    ):
        return None

    if len(names) == 1 and names[0] in _CEO_ALERT_COPY:
        return _CEO_ALERT_COPY[names[0]]

    lines = [
        f"⚠️ Aviso del ensayo ({severity})",
        "El equipo lo mira. **No resetear frenos. Dinero real: NO.**",
    ]
    for alert in kept[:3]:
        annotations = alert.get("annotations") if isinstance(alert.get("annotations"), dict) else {}
        summary = str(
            (annotations or {}).get("summary")
            or (annotations or {}).get("description")
            or ""
        ).strip()
        if summary and "sidecar" not in summary.lower() and "celery" not in summary.lower():
            lines.append(summary)
    return "\n".join(lines)

