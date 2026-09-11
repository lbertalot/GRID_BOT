"""Gauges de observabilidad paper-aware (S-OBS-P0 / E3).

Emite métricas SoT alineadas a logs desk: mode, equity paper, snapshot age,
pipeline degraded. Paper-only — no activa live.

E3 hotfix: Prometheus scrapea solo el proceso API. El worker publica el gauge
en su proceso (invisible al scrape). Al scrapear, si no hay unixtime explícito,
se hidrata fail-soft desde sidecar compartido o MAX(captured_at) en DB.

E3b: ``pipeline_health_table_ok`` también vive en el worker; al scrape se
hidrata desde ``REPORTS_DIR/pipeline_health/LATEST.json`` (volumen compartido).
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

_MODE_LABELS = ("paper", "real_blocked", "real_armed", "unknown")
_SIDECAR_FILENAME = "last_portfolio_snapshot.json"
_DEFAULT_SIDECAR_MAX_AGE_SEC = 3600.0
_PIPELINE_LATEST = "pipeline_health/LATEST.json"


def _telemetry_dir() -> Path:
    return Path(os.getenv("PAPER_TELEMETRY_DIR", "paper_telemetry"))


def _reports_dir() -> Path:
    return Path(os.getenv("REPORTS_DIR", "reports"))


def _sidecar_path() -> Path:
    return _telemetry_dir() / _SIDECAR_FILENAME


def _sidecar_max_age_sec() -> float:
    raw = os.getenv("OBS_SNAPSHOT_SIDECAR_MAX_AGE_SEC", str(_DEFAULT_SIDECAR_MAX_AGE_SEC))
    try:
        return float(raw)
    except ValueError:
        return _DEFAULT_SIDECAR_MAX_AGE_SEC


def _load_series_meta() -> tuple[Optional[float], int]:
    """(last_equity, n_samples) desde paper_equity_series.json; fail-soft."""
    path = _telemetry_dir() / "paper_equity_series.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        samples = list(data.get("samples") or [])
        if not samples:
            return None, 0
        last = samples[-1]
        equity = last.get("equity")
        return (float(equity) if equity is not None else None), len(samples)
    except Exception as exc:  # noqa: BLE001 — fail-soft obs
        logger.debug("obs_gauges: no se pudo leer serie paper: %s", exc)
        return None, 0


def _write_snapshot_sidecar(unixtime: float) -> None:
    """Persiste last snapshot unixtime para hidratar el proceso API al scrape."""
    path = _sidecar_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {"captured_at_unix": float(unixtime)}
        path.write_text(json.dumps(payload), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001 — fail-soft obs
        logger.debug("obs_gauges: no se pudo escribir sidecar snapshot: %s", exc)


def _hydrate_snapshot_from_sidecar(*, now: Optional[float] = None) -> Optional[float]:
    """Lee sidecar si existe y es fresco; None si ausente/stale/inválido."""
    path = _sidecar_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        raw = data.get("captured_at_unix")
        if raw is None:
            return None
        ts = float(raw)
        age = (now if now is not None else time.time()) - ts
        if age < 0:
            return ts
        if age > _sidecar_max_age_sec():
            return None
        return ts
    except Exception as exc:  # noqa: BLE001 — fail-soft obs
        logger.debug("obs_gauges: sidecar snapshot no usable: %s", exc)
        return None


def _hydrate_snapshot_from_db() -> Optional[float]:
    """SELECT MAX(captured_at) FROM portfolio_snapshots — fail-soft."""
    try:
        from sqlalchemy import text

        from app.db.session import SessionLocal

        db = SessionLocal()
        try:
            row = db.execute(
                text("SELECT MAX(captured_at) FROM portfolio_snapshots")
            ).fetchone()
            if not row or row[0] is None:
                return None
            captured = row[0]
            if isinstance(captured, datetime):
                if captured.tzinfo is None:
                    captured = captured.replace(tzinfo=timezone.utc)
                return float(captured.timestamp())
            return float(captured)
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001 — no romper scrape /metrics
        logger.debug("obs_gauges: DB hydrate snapshot falló: %s", exc)
        return None


def resolve_snapshot_unixtime(
    snapshot_unixtime: Optional[float] = None,
) -> Optional[float]:
    """Resuelve unixtime: explícito > sidecar fresco > DB MAX(captured_at)."""
    if snapshot_unixtime is not None:
        return float(snapshot_unixtime)
    from_sidecar = _hydrate_snapshot_from_sidecar()
    if from_sidecar is not None:
        return from_sidecar
    return _hydrate_snapshot_from_db()


def _load_pipeline_health_latest() -> Optional[dict[str, Any]]:
    """Lee REPORTS_DIR/pipeline_health/LATEST.json — fail-soft."""
    path = _reports_dir() / _PIPELINE_LATEST
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception as exc:  # noqa: BLE001
        logger.debug("obs_gauges: LATEST pipeline_health no usable: %s", exc)
        return None


def hydrate_pipeline_health_gauges(
    *,
    pipeline_degraded: Optional[bool] = None,
) -> None:
    """Publica pipeline_health_* en el proceso del scrape (API).

    Preferencia: argumento explícito para degraded; tablas siempre desde LATEST
    si existe (el worker escribe el JSON en volumen compartido).
    """
    from app.core import metrics as m

    report = _load_pipeline_health_latest()
    if report:
        checks = report.get("checks") or {}
        if isinstance(checks, dict):
            for name, c in checks.items():
                if str(name).startswith("_"):
                    continue
                if isinstance(c, dict) and "ok" in c:
                    m.pipeline_health_table_ok.labels(table=str(name)).set(
                        1 if c.get("ok") else 0
                    )
        if pipeline_degraded is None and "ok" in report:
            pipeline_degraded = not bool(report.get("ok"))

    if pipeline_degraded is not None:
        m.pipeline_health_degraded.set(1 if pipeline_degraded else 0)


def publish_obs_gauges(
    *,
    snapshot_unixtime: Optional[float] = None,
    pipeline_degraded: Optional[bool] = None,
) -> None:
    """Actualiza gauges Prometheus. Nunca debe romper el caller."""
    try:
        from app.core import metrics as m
        from app.core.trading_mode import get_trading_mode_snapshot

        mode = str(get_trading_mode_snapshot().get("effective_mode") or "unknown")
        for label in _MODE_LABELS:
            m.trading_effective_mode.labels(mode=label).set(1 if label == mode else 0)

        equity, n_samples = _load_series_meta()
        if equity is not None:
            m.paper_equity_usdt.set(equity)
        m.paper_equity_samples.set(float(n_samples))

        e0_raw = os.getenv("PAPER_E0_USDT", "1000")
        try:
            m.paper_equity_e0_usdt.set(float(e0_raw))
        except ValueError:
            m.paper_equity_e0_usdt.set(1000.0)

        explicit = snapshot_unixtime is not None
        resolved = resolve_snapshot_unixtime(snapshot_unixtime)
        if resolved is not None:
            m.portfolio_snapshot_last_unixtime.set(float(resolved))
            if explicit:
                _write_snapshot_sidecar(float(resolved))

        hydrate_pipeline_health_gauges(pipeline_degraded=pipeline_degraded)
        _publish_paper_edge_gauges()
        _hydrate_binance_ip_rejected_from_shared()
    except Exception as exc:  # noqa: BLE001
        logger.debug("obs_gauges publish failed: %s", exc)


def _early_streak_threshold() -> int:
    raw = os.getenv("PAPER_EARLY_STREAK_WARN", "3").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 3


def _publish_paper_edge_gauges() -> None:
    """Edge neto por ciclo + racha (validación paper del patch Δnivel)."""
    from app.core import metrics as m
    from app.core.auto_circuit_breaker import (
        consecutive_losses_from_closed_cycles,
        paper_trial_started_at,
    )

    try:
        from app.core.paper_equity_ledger import (
            paper_equity_is_source_of_truth,
            reload_paper_ledger_from_disk,
        )
    except Exception:
        return
    if not paper_equity_is_source_of_truth():
        return
    try:
        ledger = reload_paper_ledger_from_disk()
    except Exception:
        return
    closed = ledger.closed_cycles()
    m.paper_cycle_edge_net_cum_usdt.set(float(ledger.realized_net_pnl_usdt))
    if closed:
        last = max(closed, key=lambda c: c.closed_at or c.opened_at)
        m.paper_cycle_edge_gross_usdt.set(float(last.gross_pnl_usdt or 0))
        m.paper_cycle_edge_net_usdt.set(float(last.net_pnl_usdt or 0))
    streak = consecutive_losses_from_closed_cycles(
        closed, since=paper_trial_started_at()
    )
    m.paper_consecutive_losses.set(float(streak))
    warn_at = _early_streak_threshold()
    m.paper_early_streak_warn.set(1.0 if streak >= warn_at else 0.0)
    if streak >= warn_at:
        _maybe_telegram_early_streak(streak, warn_at)


def _hydrate_binance_ip_rejected_from_shared() -> None:
    """API scrape: worker puede haber marcado −2015 en Redis compartido."""
    try:
        from app.core.binance_auth_ip_watch import load_binance_auth_ip_blocked
        from app.core.metrics import binance_ip_rejected

        if load_binance_auth_ip_blocked():
            binance_ip_rejected.set(1.0)
    except Exception as exc:
        logger.debug("obs_gauges: hydrate binance ip flag: %s", exc)


def _maybe_telegram_early_streak(streak: int, warn_at: int) -> None:
    """Aviso temprano (no abre breaker). Debounce 6h. Silencio si SI ya abierto."""
    try:
        from app.core.auto_circuit_breaker import consecutive_loss_trip_threshold
        from app.core.breaker_ceo_watch import _si_snapshot
        from app.core.telegram_ceo_copy import (
            HOLD_PNL_MIN_REPEAT_S,
            ceo_plain_enabled,
            should_emit_ceo,
        )
        from app.services.telegram_alert import send_telegram_alert

        if not ceo_plain_enabled():
            return
        try:
            si_open, _, _, _ = _si_snapshot()
            if si_open:
                return
        except Exception:
            pass
        fp = f"early_streak|{streak}|{warn_at}"
        if not should_emit_ceo(
            "early_streak",
            fp,
            min_repeat_s=HOLD_PNL_MIN_REPEAT_S,
        ):
            return
        trip = consecutive_loss_trip_threshold()
        send_telegram_alert(
            "🟡 **Aviso temprano de racha (paper)**\n"
            f"Hay {streak} cierres seguidos en pérdida "
            f"(aviso en {warn_at}; el freno duro sigue en {trip}).\n"
            "WARN no abre el breaker. Es señal de revisión desk, no un reset automático.\n"
            "**Dinero real: NO.**"
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("early streak telegram skip: %s", exc)


__all__ = [
    "publish_obs_gauges",
    "resolve_snapshot_unixtime",
    "hydrate_pipeline_health_gauges",
]
