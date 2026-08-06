"""Gauges de observabilidad paper-aware (S-OBS-P0 / E3).

Emite métricas SoT alineadas a logs desk: mode, equity paper, snapshot age,
pipeline degraded. Paper-only — no activa live.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

_MODE_LABELS = ("paper", "real_blocked", "real_armed", "unknown")


def _telemetry_dir() -> Path:
    return Path(os.getenv("PAPER_TELEMETRY_DIR", "paper_telemetry"))


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

        if snapshot_unixtime is not None:
            m.portfolio_snapshot_last_unixtime.set(float(snapshot_unixtime))

        if pipeline_degraded is not None:
            m.pipeline_health_degraded.set(1 if pipeline_degraded else 0)
    except Exception as exc:  # noqa: BLE001
        logger.debug("obs_gauges publish failed: %s", exc)


__all__ = ["publish_obs_gauges"]
