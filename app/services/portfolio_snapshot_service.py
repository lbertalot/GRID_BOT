"""
portfolio-snapshot-agent — Captura el valor real del portafolio cada 15 minutos.

Responsabilidades:
- Obtener balances reales desde Binance API
- Convertir todos los activos a USDT usando precios actuales
- Persistir el snapshot en PostgreSQL (tabla portfolio_snapshots)
- Proveer queries para recuperar el historial a performance_analyzer

Este servicio reemplaza completamente los datos simulados con np.random
que existían en performance_analyzer.get_portfolio_value_history().
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from celery import shared_task
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.paper_equity_ledger import (
    compute_paper_portfolio_value,
    paper_equity_is_source_of_truth,
)
from app.core.primary_symbol import resolve_primary_symbol
from app.db.session import SessionLocal
from app.models.portfolio_snapshot import PortfolioSnapshot
from app.services.binance_client_singleton import get_binance_client_singleton
from app.core.metrics import (
    pipeline_filter_drops_total,
    pipeline_persistence_failures_total,
    portfolio_asset_valuation_failures_total,
)

logger = logging.getLogger(__name__)

# Símbolo principal — paper L0 freeze = ETHUSDT (ver resolve_primary_symbol)
PRIMARY_SYMBOL = resolve_primary_symbol()


# ---------------------------------------------------------------------------
# Capa de consulta (sin lógica Binance, pura lectura de DB)
# ---------------------------------------------------------------------------


def get_portfolio_value_history(
    db: Session,
    days: int = 30,
) -> List[float]:
    """
    Recupera el historial real de valores del portafolio desde PostgreSQL.

    Retorna una lista de valores USDT ordenada cronológicamente.
    Si hay menos de 2 snapshots, retorna lista vacía para que el caller
    active su fallback.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        db.query(PortfolioSnapshot.total_value_usdt, PortfolioSnapshot.captured_at)
        .filter(PortfolioSnapshot.captured_at >= since)
        .order_by(PortfolioSnapshot.captured_at.asc())
        .all()
    )
    return [float(r.total_value_usdt) for r in rows]


def get_latest_snapshot(db: Session) -> Optional[PortfolioSnapshot]:
    """Retorna el snapshot más reciente o None si no existen registros."""
    return (
        db.query(PortfolioSnapshot)
        .order_by(PortfolioSnapshot.captured_at.desc())
        .first()
    )


def get_snapshot_count(db: Session) -> int:
    """Cantidad total de snapshots almacenados."""
    return db.query(func.count(PortfolioSnapshot.id)).scalar() or 0


# ---------------------------------------------------------------------------
# Lógica de captura (obtiene datos de Binance y persiste)
# ---------------------------------------------------------------------------


def _compute_portfolio_value_sync() -> Optional[Dict]:
    """
    Calcula el valor total del portafolio de forma síncrona.
    Separa los activos por tipo para el desglose del snapshot.

    Retorna dict con claves:
        total_value_usdt, usdt_free, btc_value_usdt,
        other_assets_usdt, btc_price, primary_symbol
    O None si Binance no está disponible.

    En modo paper la fuente de verdad es `PaperEquityLedger` (S10): la cuenta de
    Binance no refleja el estado del bot simulado, y leer balances del exchange —o
    peor, los balances fijos del simulador— producía una serie de equity ficticia
    (gap I-3). El inventario paper se marca contra ticker real igual que en live.
    """
    if paper_equity_is_source_of_truth():
        return compute_paper_portfolio_value()

    singleton = get_binance_client_singleton()
    if not singleton.is_ready():
        logger.warning(
            "[SnapshotAgent] Cliente Binance no disponible — snapshot omitido"
        )
        pipeline_filter_drops_total.labels(
            stage="portfolio_snapshot",
            reason="binance_client_not_ready",
            table="portfolio_snapshots",
        ).inc()
        return None

    binance = singleton.client
    try:
        account_info = binance.get_account()
    except Exception as exc:
        logger.error(
            "[SnapshotAgent] Error al obtener account info de Binance: %s", exc
        )
        pipeline_filter_drops_total.labels(
            stage="portfolio_snapshot",
            reason="account_info_error",
            table="portfolio_snapshots",
        ).inc()
        return None

    balances = account_info.get("balances", [])
    usdt_free = 0.0
    btc_value_usdt = 0.0
    other_assets_usdt = 0.0
    btc_price: Optional[float] = None

    for balance in balances:
        asset = balance["asset"]
        free = float(balance["free"])
        locked = float(balance["locked"])
        total_asset = free + locked

        if total_asset <= 0:
            continue

        if asset in ("USDT", "USDC", "BUSD", "FDUSD", "DAI", "TUSD"):
            usdt_free += total_asset
        elif asset.startswith("LD"):
            # Activos de Binance Earn (Simple Earn) — LD{ASSET}: mapear al activo subyacente
            underlying = asset[2:] or ""
            if underlying in ("USDT", "USDC", "BUSD", "FDUSD", "DAI", "TUSD"):
                usdt_free += total_asset
            elif underlying:
                symbol = f"{underlying}USDT"
                try:
                    ticker = binance.get_symbol_ticker(symbol=symbol)
                    price = float(ticker["price"])
                    value = total_asset * price
                    if underlying == "BTC":
                        btc_value_usdt += value
                        btc_price = price
                    else:
                        other_assets_usdt += value
                except Exception as exc:
                    logger.warning(
                        "[SnapshotAgent] Fallo valuando LD asset=%s underlying=%s symbol=%s: %s",
                        asset,
                        underlying,
                        symbol,
                        exc,
                    )
                    portfolio_asset_valuation_failures_total.labels(
                        asset=asset,
                        reason="ld_ticker_unavailable",
                    ).inc()
        else:
            symbol = f"{asset}USDT"
            try:
                ticker = binance.get_symbol_ticker(symbol=symbol)
                price = float(ticker["price"])
                value = total_asset * price

                if asset == "BTC":
                    btc_value_usdt += value
                    btc_price = price
                else:
                    other_assets_usdt += value
            except Exception as exc:
                logger.warning(
                    "[SnapshotAgent] Fallo valuando asset=%s con symbol=%s: %s",
                    asset,
                    symbol,
                    exc,
                )
                portfolio_asset_valuation_failures_total.labels(
                    asset=asset,
                    reason="ticker_unavailable_or_invalid_pair",
                ).inc()

    total_value_usdt = usdt_free + btc_value_usdt + other_assets_usdt

    return {
        "total_value_usdt": total_value_usdt,
        "usdt_free": usdt_free,
        "btc_value_usdt": btc_value_usdt,
        "other_assets_usdt": other_assets_usdt,
        "btc_price": btc_price,
        "primary_symbol": resolve_primary_symbol(),
    }


def save_portfolio_snapshot() -> Optional[PortfolioSnapshot]:
    """
    Captura el valor del portafolio desde Binance y lo persiste en PostgreSQL.

    Retorna el objeto PortfolioSnapshot creado, o None en caso de error.
    Esta función es llamada por la tarea Celery cada 15 minutos.
    """
    data = _compute_portfolio_value_sync()
    if data is None:
        return None

    db = SessionLocal()
    try:
        snapshot = PortfolioSnapshot(**data)
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)
        logger.info(
            "[SnapshotAgent] Snapshot guardado: %.2f USDT (id=%s)",
            snapshot.total_value_usdt,
            snapshot.id,
        )
        try:
            from app.core.obs_gauges import publish_obs_gauges

            ts = snapshot.captured_at
            if ts is not None:
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                publish_obs_gauges(snapshot_unixtime=ts.timestamp())
        except Exception:
            pass
        return snapshot
    except Exception as exc:
        db.rollback()
        logger.error("[SnapshotAgent] Error al persistir snapshot: %s", exc)
        pipeline_persistence_failures_total.labels(
            table="portfolio_snapshots",
            reason="db_commit_error",
        ).inc()
        return None
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tarea Celery registrada en beat_schedule
# ---------------------------------------------------------------------------


@shared_task(
    name="app.services.portfolio_snapshot_service.capture_portfolio_snapshot",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def capture_portfolio_snapshot(self) -> Dict:
    """
    Tarea Celery: captura y persiste el valor real del portafolio.
    Se ejecuta cada 15 minutos según beat_schedule.
    """
    try:
        snapshot = save_portfolio_snapshot()
        if snapshot is None:
            return {"status": "skipped", "reason": "binance_unavailable_or_error"}
        return {
            "status": "ok",
            "snapshot_id": snapshot.id,
            "total_value_usdt": snapshot.total_value_usdt,
            "captured_at": snapshot.captured_at.isoformat()
            if snapshot.captured_at
            else None,
        }
    except Exception as exc:
        logger.error("[SnapshotAgent] Fallo en tarea Celery: %s", exc)
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Capture-on-startup (paper-safe) — evita PaperSnapshotStale20m tras recreate
# ---------------------------------------------------------------------------


def should_enqueue_startup_portfolio_snapshot() -> bool:
    """Solo encola al arrancar worker si modo paper y flag no desactivado.

    Paper-safe: no dispara captura de arranque en effective_mode≠paper
    (evita spam get_account al reiniciar workers fuera de paper).
    Kill switch: ``PORTFOLIO_SNAPSHOT_ON_STARTUP=false``.
    """
    import os

    flag = os.getenv("PORTFOLIO_SNAPSHOT_ON_STARTUP", "true").strip().lower()
    if flag in ("0", "false", "no", "off"):
        return False
    return bool(paper_equity_is_source_of_truth())


def enqueue_startup_portfolio_snapshot() -> bool:
    """Encola ``capture_portfolio_snapshot`` si aplica. Returns True si encoló."""
    if not should_enqueue_startup_portfolio_snapshot():
        logger.info(
            "[SnapshotAgent] skip startup capture "
            "(not paper SoT or PORTFOLIO_SNAPSHOT_ON_STARTUP=false)"
        )
        return False

    # Debounce: prefork / doble worker_ready no debe spamear 2 captures.
    try:
        import os

        from redis import Redis

        redis_url = os.getenv("REDIS_URL") or os.getenv(
            "CELERY_BROKER_URL", "redis://localhost:6379/0"
        )
        client = Redis.from_url(redis_url, decode_responses=True)
        got_lock = client.set(
            "gridbot:portfolio_snapshot:startup",
            "1",
            nx=True,
            ex=120,
        )
        if not got_lock:
            logger.info(
                "[SnapshotAgent] skip startup capture (debounce lock held)"
            )
            return False
    except Exception as exc:  # noqa: BLE001 — fail-open: aún encolar una vez
        logger.debug("[SnapshotAgent] startup debounce unavailable: %s", exc)

    capture_portfolio_snapshot.delay()
    logger.info(
        "[SnapshotAgent] enqueued capture_portfolio_snapshot on worker_ready (paper)"
    )
    return True


_STARTUP_SNAPSHOT_SIGNAL_CONNECTED = False


def _connect_worker_ready_startup_snapshot() -> None:
    """Registra handler Celery ``worker_ready`` (idempotente)."""
    global _STARTUP_SNAPSHOT_SIGNAL_CONNECTED
    if _STARTUP_SNAPSHOT_SIGNAL_CONNECTED:
        return
    from celery.signals import worker_ready

    @worker_ready.connect(weak=False)
    def _on_worker_ready_portfolio_snapshot(**_kwargs) -> None:  # noqa: ANN003
        try:
            enqueue_startup_portfolio_snapshot()
        except Exception as exc:  # noqa: BLE001 — never break worker boot
            logger.warning(
                "[SnapshotAgent] startup enqueue failed (non-fatal): %s", exc
            )

    _STARTUP_SNAPSHOT_SIGNAL_CONNECTED = True


_connect_worker_ready_startup_snapshot()
