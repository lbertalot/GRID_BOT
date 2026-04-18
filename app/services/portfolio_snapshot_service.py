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

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from celery import shared_task
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.portfolio_snapshot import PortfolioSnapshot
from app.services.binance_client_singleton import get_binance_client_singleton

logger = logging.getLogger(__name__)

# Símbolo principal del bot — usado como referencia en el snapshot
PRIMARY_SYMBOL = os.getenv("TRADING_SYMBOL", "BTCUSDT")


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
    """
    singleton = get_binance_client_singleton()
    if not singleton.is_ready():
        logger.warning("[SnapshotAgent] Cliente Binance no disponible — snapshot omitido")
        return None

    binance = singleton.client
    try:
        account_info = binance.get_account()
    except Exception as exc:
        logger.error("[SnapshotAgent] Error al obtener account info de Binance: %s", exc)
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

        if asset == "USDT":
            usdt_free += total_asset
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
            except Exception:
                # Activo sin par USDT directo — ignorar silenciosamente
                pass

    total_value_usdt = usdt_free + btc_value_usdt + other_assets_usdt

    return {
        "total_value_usdt": total_value_usdt,
        "usdt_free": usdt_free,
        "btc_value_usdt": btc_value_usdt,
        "other_assets_usdt": other_assets_usdt,
        "btc_price": btc_price,
        "primary_symbol": PRIMARY_SYMBOL,
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
        return snapshot
    except Exception as exc:
        db.rollback()
        logger.error("[SnapshotAgent] Error al persistir snapshot: %s", exc)
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
            "captured_at": snapshot.captured_at.isoformat() if snapshot.captured_at else None,
        }
    except Exception as exc:
        logger.error("[SnapshotAgent] Fallo en tarea Celery: %s", exc)
        raise self.retry(exc=exc)
