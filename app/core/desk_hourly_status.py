"""Desk hourly status — digest paper window (día N/30).

Recolecta estado por área, veredicto global ON_TRACK|AT_RISK|OFF_TRACK y
formatea mensajes Telegram. Paper-safe: no toca órdenes ni flags live.

Habilitado con DESK_HOURLY_STATUS_ENABLED=true.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

STATUS_ON = "ON_TRACK"
STATUS_AT = "AT_RISK"
STATUS_OFF = "OFF_TRACK"

_RANK = {STATUS_ON: 0, STATUS_AT: 1, STATUS_OFF: 2}

EXPECTED_HASH_ENV = "GRID_CONFIG_HASH"
WINDOW_ANCHOR_ENV = "DESK_WINDOW_DAY0_ANCHOR"  # YYYY-MM-DD UTC
ENABLED_ENV = "DESK_HOURLY_STATUS_ENABLED"
GAP_WARN_HOURS = 2.0
E0_REFERENCE = "1000"  # acta L0; informativo
# CEO 2026-08-10: umbral digest PnL → AT_RISK/OFF_TRACK + DESK AUTO ACCIONES
EQUITY_DD_AT_RISK_PCT = -1.5
EQUITY_DD_OFF_TRACK_PCT = -3.0
EQUITY_DD_PAUSE_PCT = -5.0  # desk-lead: evaluar emergency_stop paper (no auto)
EQUITY_DD_AT_RISK_ENV = "DESK_EQUITY_DD_AT_RISK_PCT"
EQUITY_DD_OFF_TRACK_ENV = "DESK_EQUITY_DD_OFF_TRACK_PCT"
EQUITY_DD_PAUSE_ENV = "DESK_EQUITY_DD_PAUSE_PCT"


@dataclass
class AreaStatus:
    code: str
    status: str
    plan: str
    done: str
    deviation: str
    next_60m: str
    blocks: str = "nadie"

    def to_telegram_block(self, when: datetime, *, day_n: int) -> str:
        hhmm = when.astimezone(timezone.utc).strftime("%H:%M")
        return (
            f"⏱ {hhmm}Z | {self.code} | Día{day_n}/30\n"
            f"Estado área: {self.status}\n"
            f"Plan: {self.plan}\n"
            f"Hecho: {self.done}\n"
            f"Desvío: {self.deviation}\n"
            f"Next 60m: {self.next_60m}\n"
            f"Bloquea a: {self.blocks}"
        )


@dataclass
class DeskDigest:
    when: datetime
    day_n: int
    global_status: str
    areas: List[AreaStatus] = field(default_factory=list)
    equity_last: Optional[str] = None
    equity_delta_pct: Optional[str] = None
    config_hash: Optional[str] = None
    hash_ok: bool = True
    effective_mode: str = "unknown"
    any_open_breakers: Optional[bool] = None
    notes: List[str] = field(default_factory=list)

    def area_blocks(self) -> str:
        parts = [
            a.to_telegram_block(self.when, day_n=self.day_n) for a in self.areas
        ]
        return "\n---\n".join(parts)

    def ceo_digest_text(self) -> str:
        """Mensaje Telegram CEO (formato compacto, paper-only)."""
        hhmm = self.when.astimezone(timezone.utc).strftime("%H:%M")
        eq = self.equity_last if self.equity_last is not None else "UNAVAILABLE"
        if self.equity_delta_pct is not None:
            try:
                raw = self.equity_delta_pct.rstrip("%")
                delta = f"{float(raw):.2f}%"
            except Exception:
                delta = self.equity_delta_pct
        else:
            delta = "n/a"

        mode_label = (
            "Paper Trading"
            if self.effective_mode == "paper"
            else f"{self.effective_mode} (revisar)"
        )

        off_or_at = [a for a in self.areas if a.status != STATUS_ON]
        on_track = [a for a in self.areas if a.status == STATUS_ON]

        if self.global_status == STATUS_OFF:
            alert_title = "🚨 ALERTA GLOBAL: FUERA DE CURSO (OFF_TRACK)"
        elif self.global_status == STATUS_AT:
            alert_title = "⚠️ ALERTA GLOBAL: EN RIESGO (AT_RISK)"
        else:
            alert_title = "✅ ESTADO GLOBAL: EN CURSO (ON_TRACK)"

        if off_or_at:
            alert_body_lines = []
            for a in off_or_at:
                alert_body_lines.append(
                    f"El área de {a.code} reporta: {a.deviation}."
                )
                alert_body_lines.append(
                    f"👉 Acción requerida: {a.next_60m}."
                )
            alert_body = "\n".join(alert_body_lines)
        else:
            alert_body = "Sin desvíos abiertos."

        if on_track:
            names = ", ".join(a.code for a in on_track)
            if len(on_track) == len(self.areas):
                on_section = (
                    f"✅ Todas las áreas (ON TRACK):\n"
                    f"Las áreas de {names} están operando con normalidad y sin desvíos."
                )
            else:
                on_section = (
                    f"✅ Resto de las áreas (ON TRACK):\n"
                    f"Las áreas de {names} están operando con normalidad y sin desvíos."
                )
        else:
            on_section = "✅ Resto de las áreas (ON TRACK):\nNinguna área en ON_TRACK."

        by = {a.code: a for a in self.areas}
        tech_bits = []
        if "BE" in by and by["BE"].done:
            # ej. samples=29 last_equity=1000
            done = by["BE"].done
            if "samples=" in done:
                n = done.split("samples=")[1].split()[0]
                tech_bits.append(f"Backend registró {n} muestras")
            else:
                tech_bits.append(f"Backend: {done}")
        if "QUANT" in by and by["QUANT"].done:
            done_q = by["QUANT"].done
            if "daily_closes=" in done_q:
                n = done_q.split("daily_closes=")[1].split()[0]
                tech_bits.append(f"Quant lleva {n} cierres diarios")
            else:
                tech_bits.append(f"Quant: {done_q}")
        tech_note = ""
        if tech_bits:
            tech_note = f"\n(Notas técnicas: {' y '.join(tech_bits)})."

        return (
            f"🧭 Reporte CEO | Día {self.day_n}/30 ({hhmm}Z)\n"
            f"⚙️ Modo: {mode_label} | Pase a Live: ❌ NO\n"
            f"\n"
            f"💵 Resumen de Capital:\n"
            f"• Equity Actual: {eq}\n"
            f"• Variación: {delta} (vs. Inicial: {E0_REFERENCE})\n"
            f"\n"
            f"{alert_title}\n"
            f"{alert_body}\n"
            f"\n"
            f"{on_section}"
            f"{tech_note}"
        )

    def full_telegram_payload(self, *, include_area_blocks: bool = False) -> str:
        """Un solo mensaje CEO (límite Telegram ~4096). Áreas van resumidas en el digest."""
        ceo = self.ceo_digest_text()
        if not include_area_blocks:
            return ceo[:4090]
        body = ceo + "\n\n=== ÁREAS (detalle) ===\n" + self.area_blocks()
        if len(body) > 4000:
            compact = "\n".join(
                f"{a.code}:{a.status} — {a.deviation}" for a in self.areas
            )
            body = ceo + "\n\n=== ÁREAS (compact) ===\n" + compact
        return body[:4090]


def _parse_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def is_enabled() -> bool:
    return _parse_bool(os.getenv(ENABLED_ENV), default=False)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(ts: str) -> Optional[datetime]:
    try:
        raw = ts.replace("Z", "+00:00")
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def window_day_number(
    when: Optional[datetime] = None,
    *,
    anchor_date: Optional[str] = None,
) -> int:
    """Día N/30 desde ancla UTC (default env o 2026-08-06)."""
    moment = when or _utcnow()
    anchor = anchor_date or os.getenv(WINDOW_ANCHOR_ENV) or "2026-08-06"
    try:
        y, m, d = (int(x) for x in anchor.split("-")[:3])
        start = datetime(y, m, d, tzinfo=timezone.utc)
    except Exception:
        start = datetime(2026, 8, 6, tzinfo=timezone.utc)
    delta = (moment.date() - start.date()).days + 1
    return max(1, min(30, delta))


def merge_global_status(statuses: Sequence[str]) -> str:
    if not statuses:
        return STATUS_AT
    worst = max((_RANK.get(s, 1) for s in statuses), default=1)
    for name, rank in _RANK.items():
        if rank == worst:
            return name
    return STATUS_AT


def _worse_status(a: str, b: str) -> str:
    return a if _RANK.get(a, 0) >= _RANK.get(b, 0) else b


def _equity_dd_thresholds() -> tuple[float, float, float]:
    at = EQUITY_DD_AT_RISK_PCT
    off = EQUITY_DD_OFF_TRACK_PCT
    pause = EQUITY_DD_PAUSE_PCT
    try:
        raw_at = (os.getenv(EQUITY_DD_AT_RISK_ENV) or "").strip()
        if raw_at:
            at = float(raw_at)
    except Exception:
        at = EQUITY_DD_AT_RISK_PCT
    try:
        raw_off = (os.getenv(EQUITY_DD_OFF_TRACK_ENV) or "").strip()
        if raw_off:
            off = float(raw_off)
    except Exception:
        off = EQUITY_DD_OFF_TRACK_PCT
    try:
        raw_pause = (os.getenv(EQUITY_DD_PAUSE_ENV) or "").strip()
        if raw_pause:
            pause = float(raw_pause)
    except Exception:
        pause = EQUITY_DD_PAUSE_PCT
    return at, off, pause


def _parse_delta_pct(delta_pct: Optional[str]) -> Optional[float]:
    if delta_pct is None:
        return None
    try:
        return float(str(delta_pct).rstrip("%"))
    except Exception:
        return None


def equity_dd_status_from_delta_pct(delta_pct: Optional[str]) -> Optional[str]:
    """Mapea Δ vs E_0 (%) → AT_RISK / OFF_TRACK; None si no aplica o sobre umbral."""
    value = _parse_delta_pct(delta_pct)
    if value is None:
        return None
    at_thr, off_thr, _pause = _equity_dd_thresholds()
    if value <= off_thr:
        return STATUS_OFF
    if value <= at_thr:
        return STATUS_AT
    return None


def equity_dd_pause_recommended(delta_pct: Optional[str]) -> bool:
    """True si ΔE₀ ≤ umbral pausa (−5% default): evaluar emergency_stop paper (humano)."""
    value = _parse_delta_pct(delta_pct)
    if value is None:
        return False
    _at, _off, pause_thr = _equity_dd_thresholds()
    return value <= pause_thr


def _expected_hash() -> Optional[str]:
    return (os.getenv(EXPECTED_HASH_ENV) or "").strip() or None


def collect_desk_digest(
    *,
    when: Optional[datetime] = None,
    series_samples: Optional[List[Dict[str, Any]]] = None,
    trading_snapshot: Optional[Dict[str, Any]] = None,
    any_open_breakers: Optional[bool] = None,
    expected_hash: Optional[str] = None,
) -> DeskDigest:
    """Construye digest a partir de inputs (inyectables en tests)."""
    moment = when or _utcnow()
    day_n = window_day_number(moment)
    exp = expected_hash if expected_hash is not None else _expected_hash()

    snap = trading_snapshot
    if snap is None:
        try:
            from app.core.trading_mode import get_trading_mode_snapshot

            snap = get_trading_mode_snapshot()
        except Exception:
            snap = {}

    mode = str((snap or {}).get("effective_mode") or "unknown")
    paper_ok = mode == "paper"
    force = bool((snap or {}).get("force_real_mode"))
    trading_en = bool((snap or {}).get("trading_enabled"))

    samples = series_samples
    if samples is None:
        samples = _load_series_samples()

    last = samples[-1] if samples else None
    equity_last = str(last.get("equity")) if last else None
    last_hash = (
        str(last.get("config_hash")) if last and last.get("config_hash") else None
    )
    cfg_hash = last_hash or exp
    hash_ok = True
    if exp and last_hash and last_hash != exp:
        hash_ok = False

    gap_hours: Optional[float] = None
    if last and last.get("at"):
        at = _parse_iso(str(last["at"]))
        if at:
            gap_hours = (moment - at).total_seconds() / 3600.0

    delta_pct: Optional[str] = None
    if equity_last is not None:
        try:
            e0 = float(E0_REFERENCE)
            et = float(equity_last)
            if e0 != 0:
                delta_pct = f"{((et - e0) / e0) * 100:.3f}%"
        except Exception:
            delta_pct = None

    sec_status = STATUS_ON
    sec_dev = "ninguno"
    if not paper_ok or force or trading_en:
        sec_status = STATUS_OFF
        sec_dev = f"mode={mode} force_real={force} trading_enabled={trading_en}"
    sec = AreaStatus(
        code="SEC",
        status=sec_status,
        plan="paper-safe flags",
        done=f"effective_mode={mode}",
        deviation=sec_dev,
        next_60m="re-check trading-mode",
        blocks="todos" if sec_status == STATUS_OFF else "nadie",
    )

    mm_status = STATUS_ON
    mm_dev = "ninguno"
    mm_next = "verificar sidecar + samples"
    if not hash_ok:
        mm_status = STATUS_OFF
        mm_dev = f"hash drift last≠expected ({(last_hash or '?')[:12]}…)"
    elif not last_hash and not exp:
        mm_status = STATUS_AT
        mm_dev = "hash no disponible"

    be_status = STATUS_ON
    be_dev = "ninguno"
    if not samples:
        be_status = STATUS_OFF
        be_dev = "sin samples en paper_equity_series"
    elif gap_hours is not None and gap_hours > GAP_WARN_HOURS:
        be_status = STATUS_OFF
        be_dev = f"gap serie {gap_hours:.1f}h > {GAP_WARN_HOURS}h"
    elif gap_hours is not None and gap_hours > 1.0:
        be_status = STATUS_AT
        be_dev = f"último sample hace {gap_hours:.1f}h"
    be = AreaStatus(
        code="BE",
        status=be_status,
        plan="ticks MtM + serie append-only",
        done=(
            f"samples={len(samples)} last_equity={equity_last or 'UNAVAILABLE'}"
            if samples
            else "sin serie"
        ),
        deviation=be_dev,
        next_60m="portfolio-snapshot / capture EOD",
        blocks="QUANT" if be_status != STATUS_ON else "nadie",
    )

    quant_status = STATUS_ON
    quant_dev = "ninguno"
    quant_next = "checklist A1–A8 parcial"
    closes = [s for s in (samples or []) if s.get("daily_close_at")]
    if not closes:
        quant_status = STATUS_AT
        quant_dev = "sin daily_close en serie (ok si pre-cierre)"
    if be_status == STATUS_OFF:
        quant_status = STATUS_OFF
        quant_dev = "Capa A bloqueada por gap/serie"

    # PnL / ΔE₀ (CEO 2026-08-10): no deja falso verde con drawdown material
    notes = []
    pnl_status = equity_dd_status_from_delta_pct(delta_pct)
    pause = equity_dd_pause_recommended(delta_pct)
    if pnl_status is not None:
        dd_label = delta_pct or "n/a"
        pnl_dev = (
            f"ΔE0={dd_label} (umbral AT {EQUITY_DD_AT_RISK_PCT}% / "
            f"OFF {EQUITY_DD_OFF_TRACK_PCT}% / gate_pausa={EQUITY_DD_PAUSE_PCT}%)"
        )
        mm_status = _worse_status(mm_status, pnl_status)
        if "ΔE0" not in mm_dev:
            mm_dev = pnl_dev if mm_dev == "ninguno" else f"{mm_dev}; {pnl_dev}"
        mm_next = "RCA PnL/DD + SELL/IC; no spacing↓ ni sizing↑"
        quant_status = _worse_status(quant_status, pnl_status)
        if "ΔE0" not in quant_dev:
            quant_dev = pnl_dev if quant_dev == "ninguno" else f"{quant_dev}; {pnl_dev}"
        quant_next = "tear Capa A intraday con costos + gaps"

    if pause:
        # No auto emergency_stop: solo OFF + ACCIONES desk-lead (rule 40 / paper-safe)
        pause_dev = (
            f"PAUSE_GATE ΔE0≤{EQUITY_DD_PAUSE_PCT}% — evaluar emergency_stop paper "
            "(humano; no auto; PROMOTE_LIVE NO)"
        )
        mm_status = STATUS_OFF
        quant_status = STATUS_OFF
        if "PAUSE_GATE" not in mm_dev:
            mm_dev = pause_dev if mm_dev == "ninguno" else f"{mm_dev}; {pause_dev}"
        if "PAUSE_GATE" not in quant_dev:
            quant_dev = pause_dev if quant_dev == "ninguno" else f"{quant_dev}; {pause_dev}"
        mm_next = (
            "desk-lead: evaluar EMERGENCY_STOP paper; no spacing↓/sizing↑; RCA MM"
        )
        quant_next = "tear inmediato + gaps; no claim edge"
        notes.append(pause_dev)

    mm = AreaStatus(
        code="MM",
        status=mm_status,
        plan="freeze L0 hash invariable + edge paper",
        done=f"hash={(cfg_hash or 'UNAVAILABLE')[:16]}…",
        deviation=mm_dev,
        next_60m=mm_next,
        blocks="QUANT/BE" if mm_status == STATUS_OFF else "nadie",
    )
    quant = AreaStatus(
        code="QUANT",
        status=quant_status,
        plan="Capa A cobertura / cierres",
        done=f"daily_closes={len(closes)}",
        deviation=quant_dev,
        next_60m=quant_next,
        blocks="DL" if quant_status == STATUS_OFF else "nadie",
    )

    risk_status = STATUS_ON
    risk_dev = "ninguno"
    if any_open_breakers is True:
        risk_status = STATUS_AT
        risk_dev = "breakers abiertos"
        risk_next = "Verificar la causa ejecutando GET /api/breakers/status"
    elif any_open_breakers is None:
        risk_status = STATUS_AT
        risk_dev = "breakers UNAVAILABLE"
        risk_next = "GET /api/breakers/status"
    else:
        risk_next = "GET /api/breakers/status"
    if pause:
        risk_status = STATUS_OFF
        pause_risk = (
            f"PAUSE_GATE ΔE0≤{EQUITY_DD_PAUSE_PCT}% — no reset CB PnL; "
            "desk-lead evalúa emergency_stop paper"
        )
        risk_dev = pause_risk if risk_dev == "ninguno" else f"{risk_dev}; {pause_risk}"
        risk_next = "desk-lead + prop: evaluar EMERGENCY_STOP paper (no auto)"
    risk = AreaStatus(
        code="RISK",
        status=risk_status,
        plan="breakers visibles + gate pausa PnL",
        done=f"any_open={any_open_breakers}",
        deviation=risk_dev,
        next_60m=risk_next,
    )

    devops_status = STATUS_ON
    devops_dev = "ninguno"
    if not paper_ok:
        devops_status = STATUS_OFF
        devops_dev = "stack no reporta paper"
    devops = AreaStatus(
        code="DEVOPS",
        status=devops_status,
        plan="compose healthy + mode paper",
        done="trading-mode consultado",
        deviation=devops_dev,
        next_60m="smoke-observability si AT_RISK",
    )

    fe = AreaStatus(
        code="FE",
        status=STATUS_ON if paper_ok else STATUS_AT,
        plan="UX paper inequívoco",
        done="asumido OK si mode=paper (smoke manual CEO)",
        deviation="ninguno" if paper_ok else "mode≠paper",
        next_60m="CEO dashboard spot-check",
    )

    areas = [devops, be, mm, quant, risk, sec, fe]
    global_status = merge_global_status([a.status for a in areas])

    return DeskDigest(
        when=moment,
        day_n=day_n,
        global_status=global_status,
        areas=areas,
        equity_last=equity_last,
        equity_delta_pct=delta_pct,
        config_hash=cfg_hash,
        hash_ok=hash_ok,
        effective_mode=mode,
        any_open_breakers=any_open_breakers,
        notes=notes,
    )


def _load_series_samples() -> List[Dict[str, Any]]:
    path = Path(os.getenv("PAPER_TELEMETRY_DIR", "paper_telemetry")) / (
        "paper_equity_series.json"
    )
    try:
        import json

        data = json.loads(path.read_text(encoding="utf-8"))
        return list(data.get("samples") or [])
    except Exception:
        return []


def collect_breakers_any_open() -> Optional[bool]:
    try:
        from app.core.breakers_status import get_breakers_status

        payload = get_breakers_status()
        if isinstance(payload, dict) and "any_open" in payload:
            return bool(payload["any_open"])
    except Exception:
        return None
    return None


def build_live_digest(when: Optional[datetime] = None) -> DeskDigest:
    return collect_desk_digest(
        when=when,
        any_open_breakers=collect_breakers_any_open(),
    )


def render_day2_action_plan(digest: DeskDigest) -> str:
    """Markdown action plan para el día siguiente (paper)."""
    next_day = min(30, digest.day_n + 1)
    date_s = digest.when.astimezone(timezone.utc).strftime("%Y-%m-%d")
    offs = [a for a in digest.areas if a.status != STATUS_ON]
    must_lines = [
        "- [ ] Mantener effective_mode=paper y hash freeze",
        f"- [ ] Captura cierre 00:00 UTC ±30m (día {next_day})",
        "- [ ] Revisar gaps serie ≤ 2h",
    ]
    for a in offs:
        must_lines.append(
            f"- [ ] Remediación {a.code}: {a.deviation} (owner {a.code})"
        )
    return (
        f"# Action plan — Día {next_day}/30 (post {date_s} UTC)\n\n"
        f"**Generado:** {digest.when.astimezone(timezone.utc).isoformat()}\n"
        f"**Veredicto Día {digest.day_n}:** {digest.global_status}\n"
        f"**E_last:** {digest.equity_last or 'UNAVAILABLE'} · "
        f"**mode:** {digest.effective_mode}\n"
        f"**PROMOTE_LIVE:** NO\n\n"
        f"## Resumen Día {digest.day_n}\n"
        f"- Hash: `{digest.config_hash or 'UNAVAILABLE'}`\n"
        f"- Δ vs E_0: {digest.equity_delta_pct or 'n/a'}\n"
        f"- Áreas OFF/AT_RISK: "
        + (", ".join(f"{a.code}:{a.status}" for a in offs) or "ninguna")
        + "\n\n"
        f"## Must (Día {next_day})\n"
        + "\n".join(must_lines)
        + "\n\n## Should\n"
        "- [ ] Spot-check Grafana Paper L0 + CEO overview\n"
        "- [ ] Capa A parcial A1/A6/A8 documentada\n"
        "- [ ] IC-WIRE progreso si ≤ 2026-08-13\n\n"
        "## Won't\n"
        "- Live / PROMOTE_LIVE / sizing > 200 / claim de edge\n\n"
        f"## Firma DL\n"
        f"Día {next_day} plan ready — PROMOTE_LIVE=NO\n"
    )


def write_day2_action_plan(
    digest: DeskDigest,
    *,
    root: Optional[Path] = None,
) -> Path:
    base = root or Path(os.getenv("DESK_OPS_DOC_DIR", "Docs/ops"))
    base.mkdir(parents=True, exist_ok=True)
    date_s = digest.when.astimezone(timezone.utc).strftime("%Y-%m-%d")
    path = base / f"day{min(30, digest.day_n + 1)}-action-plan-{date_s}.md"
    path.write_text(render_day2_action_plan(digest), encoding="utf-8")
    return path
