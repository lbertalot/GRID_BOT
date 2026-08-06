"""Gauges de observabilidad paper-aware (S-OBS-P0 / E3).

Emite métricas SoT alineadas a logs desk: mode, equity paper, snapshot age,
pipeline degraded. Paper-only — no activa live.

E3 hotfix: Prometheus scrapea solo el proceso API. El worker publica el gauge
en su proceso (invisible al scrape). Al scrapear, si no hay unixtime explícito,
se hidrata fail-soft desde sidecar compartido o MAX(captured_at) en DB.
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


def _telemetry_dir() -> Path:
    return Path(os.getenv("PAPER_TELEMETRY_DIR", "paper_telemetry"))


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

        if pipeline_degraded is not None:
            m.pipeline_health_degraded.set(1 if pipeline_degraded else 0)
    except Exception as exc:  # noqa: BLE001
        logger.debug("obs_gauges publish failed: %s", exc)


__all__ = ["publish_obs_gauges", "resolve_snapshot_unixtime"]
