"""
balance-race-condition-fixer: sincronización de balances desde Binance a PostgreSQL.

Correcciones respecto a la versión anterior:
- Eliminado el raw asyncpg con INSERT ... ON CONFLICT DO UPDATE sin versión.
- Ahora usa BalanceService.upsert_from_exchange() que es un UPSERT SQL atómico
  con incremento de version, evitando que dos workers concurrentes se pisen.
- Un solo commit al final para atomicidad de toda la sincronización.
- Logging estructurado con contadores.
"""
import asyncio
import logging
import os
from decimal import Decimal
from typing import Dict

from binance import Client
from dotenv import load_dotenv

from app.db.session import SessionLocal
from app.services.balance_service import BalanceService

logger = logging.getLogger(__name__)


async def update_balances_in_db() -> Dict[str, int]:
    """
    Obtiene los balances de Binance y los sincroniza en PostgreSQL usando
    operaciones atómicas con optimistic locking (UPSERT + version++).

    Retorna dict con contadores: updated, skipped, errors.
    """
    load_dotenv()
    logger.info("[BalanceUpdater] Iniciando sincronización de balances desde Binance...")

    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_SECRET_KEY")

    if not api_key or not api_secret:
        logger.error("[BalanceUpdater] BINANCE_API_KEY / BINANCE_SECRET_KEY no configuradas")
        return {"updated": 0, "skipped": 0, "errors": 1}

    # Obtener balances de Binance (síncrono en thread para no bloquear event loop)
    try:
        client = await asyncio.to_thread(_get_binance_balances, api_key, api_secret)
    except Exception as exc:
        logger.error("[BalanceUpdater] Error al conectar con Binance API: %s", exc)
        return {"updated": 0, "skipped": 0, "errors": 1}

    if not client:
        return {"updated": 0, "skipped": 0, "errors": 1}

    # Persistir en PostgreSQL con UPSERT atómico
    result = await asyncio.to_thread(_persist_balances, client)
    logger.info(
        "[BalanceUpdater] Sincronización completa: updated=%d skipped=%d errors=%d",
        result["updated"], result["skipped"], result["errors"],
    )
    return result


def _get_binance_balances(api_key: str, api_secret: str) -> list:
    """Obtiene la lista de balances desde Binance (síncrono, llama desde thread)."""
    client = Client(api_key, api_secret)
    account_info = client.get_account()
    return account_info.get("balances", [])


def _persist_balances(balances: list) -> Dict[str, int]:
    """
    Persiste todos los balances con saldo usando UPSERT atómico en un solo commit.
    El session-per-sync garantiza que concurrent calls no compartan transacción.
    """
    db = SessionLocal()
    updated = 0
    skipped = 0
    errors = 0

    try:
        for balance in balances:
            asset: str = balance["asset"]
            free = Decimal(str(balance["free"]))
            locked = Decimal(str(balance["locked"]))
            total = free + locked

            if total <= Decimal("0"):
                skipped += 1
                continue

            try:
                # UPSERT atómico con version++ — no hay race condition
                BalanceService.upsert_from_exchange(db, asset=asset, amount=total)
                updated += 1
            except Exception as exc:
                logger.warning(
                    "[BalanceUpdater] Error en upsert de %s: %s", asset, exc
                )
                errors += 1

        # Un único commit para toda la sincronización
        db.commit()

    except Exception as exc:
        db.rollback()
        logger.error("[BalanceUpdater] Error crítico en persistencia: %s", exc)
        errors += 1
    finally:
        db.close()

    return {"updated": updated, "skipped": skipped, "errors": errors}
