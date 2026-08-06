"""
Watchdog de ingesta API -- DB: verifica escrituras recientes cada ~15 min.

- Preferencia: PromQL increase(db_writes_total{...}[65m]) via Prometheus HTTP API.
- Fallback si Prometheus no responde: timestamps maximos en PostgreSQL.
- Evidencia: JSON en REPORTS_DIR/pipeline_health/ (LATEST + timestamp).
- Degradacion detectada: loguear WARNING, retornar estado degraded sin RuntimeError
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx

from celery import shared_task
from sqlalchemy import text

from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://127.0.0.1:9090").rstrip("/")
REPORTS_DIR = Path(os.getenv("REPORTS_DIR", "reports")).resolve()
WINDOW = "65m"
SNAPSHOT_MAX_AGE_MIN = int(os.getenv("PIPELINE_HEALTH_SNAPSHOT_MAX_AGE_MIN", "35"))
ALERTS_SOFT_ONLY = os.getenv("PIPELINE_HEALTH_ALERTS_SOFT", "true").lower() in (
    "1",
    "true",
    "yes",
)

# Tablas de trading: en paper idle (0 fills esperados) increase==0 es INFO, no degraded.
_PAPER_IDLE_SOFT_TABLES = frozenset({"trades", "balances", "performance_metrics"})


def _is_paper_trading() -> bool:
    return os.getenv("PAPER_TRADING", "true").lower() in {"1", "true", "yes", "on"}


def _prom_query(query: str, timeout_s: float = 10.0) -> Optional[float]:
    """Ejecuta instant query; devuelve el valor escalar o None si falla."""
    url = f"{PROMETHEUS_URL}/api/v1/query"
    try:
        resp = httpx.get(url, params={"query": query}, timeout=timeout_s)
        resp.raise_for_status()
        body = resp.json()
    except (httpx.HTTPError, OSError, ValueError) as exc:
        logger.warning("[PipelineHealth] Prometheus no disponible (%s): %s", url, exc)
        return None

    if body.get("status") != "success":
        logger.warning(
            "[PipelineHealth] Prometheus respuesta no success: %s", body.get("status")
        )
        return None

    data = body.get("data") or {}
    results = data.get("result") or []
    if not results:
        return 0.0
    try:
        return float(results[0]["value"][1])
    except (KeyError, IndexError, TypeError, ValueError):
        return 0.0


def _db_scalar(session, sql: str, params: Optional[Dict[str, Any]] = None) -> Any:
    row = session.execute(text(sql), params or {}).fetchone()
    return row[0] if row else None


def _max_ts_column_for_table(session, table: str) -> str:
    """Columna de tiempo a usar en MAX() para comprobar actividad reciente."""
    q = text(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = :t
        """
    )
    names = {r[0] for r in session.execute(q, {"t": table}).fetchall()}
    for cand in ("timestamp", "created_at", "updated_at", "executed_at", "captured_at"):
        if cand in names:
            return cand
    return "timestamp"


def _write_reports(payload: Dict[str, Any]) -> Path:
    out = REPORTS_DIR / "pipeline_health"
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path_ts = out / f"health_{stamp}.json"
    path_ts.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    (out / "LATEST.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )

    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    daily = out / f"daily_{day}.jsonl"
    with daily.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, default=str) + "\n")

    return path_ts


def _check_table_prometheus(table: str) -> Optional[float]:
    """sum(increase(db_writes_total{table,status=ok}[WINDOW])) o None si Prom no responde."""
    q = f'sum(increase(db_writes_total{{table="{table}",status="ok"}}[{WINDOW}]))'
    return _prom_query(q)


def _sql_fallback_checks(session) -> Dict[str, Any]:
    """Cuando Prometheus no esta: heuristica por MAX(timestamp) en tablas."""
    out: Dict[str, Any] = {}
    now = datetime.now(timezone.utc)
    cutoff_snap = now - timedelta(minutes=SNAPSHOT_MAX_AGE_MIN)
    cutoff_row = now - timedelta(minutes=65)

    max_cap = _db_scalar(
        session,
        "SELECT MAX(captured_at) FROM portfolio_snapshots",
    )
    snap_ok = max_cap is not None and max_cap >= cutoff_snap
    out["portfolio_snapshots"] = {
        "source": "sql",
        "max_captured_at": str(max_cap) if max_cap else None,
        "ok": bool(snap_ok),
    }

    for table, default_col in (
        ("balances", "updated_at"),
        ("trades", "timestamp"),
        ("performance_metrics", "timestamp"),
    ):
        col = default_col
        if table in ("trades", "performance_metrics"):
            col = _max_ts_column_for_table(session, table)
        elif table == "balances":
            bcols = {
                r[0]
                for r in session.execute(
                    text(
                        """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'balances'
                    """
                    )
                ).fetchall()
            }
            col = "updated_at" if "updated_at" in bcols else default_col
        mx = _db_scalar(session, f"SELECT MAX({col}) FROM {table}")
        row_ok = mx is not None and mx >= cutoff_row
        out[table] = {
            "source": "sql",
            f"max_{col}": str(mx) if mx else None,
            "ok": bool(row_ok),
        }

    max_al = _db_scalar(session, "SELECT MAX(created_at) FROM alerts")
    out["alerts"] = {
        "source": "sql",
        "max_created_at": str(max_al) if max_al else None,
        "ok": True,
        "note": "alerts_soft_in_sql_fallback",
    }
    return out


@shared_task(
    name="app.services.pipeline_health_tasks.check_pipeline_db_writes",
    bind=True,
    max_retries=0,
    acks_late=True,
    reject_on_worker_lost=True,
)
def check_pipeline_db_writes(self) -> Dict[str, Any]:
    """
    Comprueba que haya escrituras db_writes_total en ~65m por tabla critica
    y que portfolio_snapshots tenga captura reciente (SQL).

    E4: con PAPER_TRADING=true, trades/balances/performance_metrics con
    increase==0 (paper idle / 0 fills) son soft/info — no degraded.
    portfolio_snapshots sigue siendo hard requirement.
    """
    started = datetime.now(timezone.utc)
    paper_aware = _is_paper_trading()
    tables_prom = ("trades", "balances", "performance_metrics", "alerts")
    checks: Dict[str, Any] = {}
    failures: List[str] = []
    soft_failures: List[str] = []
    prom_responded = False

    for tbl in tables_prom:
        parsed = _check_table_prometheus(tbl)
        if parsed is not None:
            prom_responded = True
        ok = parsed is not None and parsed > 0
        checks[tbl] = {"source": "prometheus", "increase_sum": parsed, "ok": ok}
        if tbl == "alerts" and ALERTS_SOFT_ONLY:
            checks[tbl]["severity"] = "warning"
            if not ok:
                checks[tbl]["warning"] = "sin escrituras alerts en ventana (no bloquea)"
        elif not ok and paper_aware and tbl in _PAPER_IDLE_SOFT_TABLES:
            checks[tbl]["severity"] = "info"
            checks[tbl]["ok"] = True  # no degrada desk paper idle
            msg = (
                f"{tbl}: increase(db_writes_total status=ok) en [{WINDOW}] == 0 "
                f"(paper idle esperado)"
            )
            checks[tbl]["info"] = msg
            soft_failures.append(msg)
        elif not ok and not (tbl == "alerts" and ALERTS_SOFT_ONLY):
            if parsed is None:
                failures.append(
                    f"{tbl}: Prometheus sin datos para increase en [{WINDOW}]"
                )
            else:
                failures.append(
                    f"{tbl}: increase(db_writes_total status=ok) en [{WINDOW}] == 0"
                )

    db = SessionLocal()
    try:
        max_cap = _db_scalar(
            db,
            "SELECT MAX(captured_at) FROM portfolio_snapshots",
        )
        cutoff = started - timedelta(minutes=SNAPSHOT_MAX_AGE_MIN)
        snap_ok = max_cap is not None and max_cap >= cutoff
        checks["portfolio_snapshots"] = {
            "source": "sql",
            "max_captured_at": str(max_cap) if max_cap else None,
            "ok": bool(snap_ok),
        }
        if not snap_ok:
            failures.append(
                f"portfolio_snapshots: ultima captura antigua o vacia "
                f"(>{SNAPSHOT_MAX_AGE_MIN}m, max={max_cap})"
            )

        if not prom_responded:
            logger.warning(
                "[PipelineHealth] Usando fallback SQL (Prometheus no consultable)"
            )
            fb = _sql_fallback_checks(db)
            checks["_sql_fallback"] = fb
            failures = [f for f in failures if "Prometheus sin datos" not in f]
            for tbl in ("trades", "balances", "performance_metrics"):
                if tbl in fb:
                    checks[tbl]["sql_fallback"] = fb[tbl]
                    if fb[tbl].get("ok"):
                        checks[tbl]["ok"] = True
                    elif paper_aware and tbl in _PAPER_IDLE_SOFT_TABLES:
                        checks[tbl]["ok"] = True
                        checks[tbl]["severity"] = "info"
                        msg = (
                            f"{tbl}: fallback SQL — sin actividad reciente "
                            f"(paper idle esperado)"
                        )
                        checks[tbl]["info"] = msg
                        soft_failures.append(msg)
                    else:
                        checks[tbl]["ok"] = False
                        failures.append(
                            f"{tbl}: fallback SQL — sin actividad reciente "
                            f"(max timestamp > 65m o tabla vacia)"
                        )
    finally:
        db.close()

    hard_failures = list(failures)

    payload: Dict[str, Any] = {
        "checked_at_utc": started.isoformat(),
        "prometheus_url": PROMETHEUS_URL,
        "window": WINDOW,
        "paper_aware": paper_aware,
        "checks": checks,
        "failures": hard_failures,
        "soft_failures": soft_failures,
        "ok": len(hard_failures) == 0,
    }

    path = _write_reports(payload)

    try:
        from app.core.metrics import pipeline_health_degraded, pipeline_health_table_ok

        for name, c in checks.items():
            if name.startswith("_"):
                continue
            if isinstance(c, dict) and "ok" in c:
                pipeline_health_table_ok.labels(table=name).set(1 if c["ok"] else 0)
        pipeline_health_degraded.set(0 if payload["ok"] else 1)
    except Exception as exc:
        logger.debug(
            "[PipelineHealth] No se pudo actualizar pipeline_health gauges: %s", exc
        )

    try:
        from app.core.obs_gauges import publish_obs_gauges

        publish_obs_gauges(pipeline_degraded=not payload["ok"])
    except Exception as exc:
        logger.debug("[PipelineHealth] obs_gauges: %s", exc)

    if hard_failures:
        msg = "; ".join(hard_failures)
        logger.warning(
            "[PipelineHealth] Degradacion detectada: %s",
            msg,
            extra={"failures": hard_failures, "report_path": str(path)},
        )
        return {
            "status": "degraded",
            "report": str(path),
            "checked_at": payload["checked_at_utc"],
            "failures": hard_failures,
            "soft_failures": soft_failures,
            "paper_aware": paper_aware,
            "ok": False,
        }

    if soft_failures:
        logger.info(
            "[PipelineHealth] Healthcheck OK (paper idle soft): %s",
            "; ".join(soft_failures),
            extra={"soft_failures": soft_failures, "report_path": str(path)},
        )
    else:
        logger.info(
            "[PipelineHealth] Healthcheck OK",
            extra={"report": str(path), "checked_at": payload["checked_at_utc"]},
        )
    return {
        "status": "ok",
        "report": str(path),
        "checked_at": payload["checked_at_utc"],
        "soft_failures": soft_failures,
        "paper_aware": paper_aware,
        "ok": True,
    }
