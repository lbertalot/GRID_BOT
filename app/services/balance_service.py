"""
Balance Service con Optimistic Locking
GridBot v2.5 - FIX para Bug #1: Race Condition
balance-race-condition-fixer: corrección de set_balance() y upsert_from_exchange()
"""
from decimal import Decimal
from typing import Optional
from sqlalchemy import update, text
from sqlalchemy.orm import Session
from app.models.balance import Balance
from app.db.session import SessionLocal
import logging
import time
import random

logger = logging.getLogger(__name__)


class ConcurrentModificationError(Exception):
    """Excepción cuando hay modificación concurrente"""
    pass


class BalanceService:
    """Servicio para operaciones de balance con optimistic locking"""
    
    @staticmethod
    def get_balance(db: Session, asset: str) -> Optional[Balance]:
        """
        Obtener balance de un asset
        
        Args:
            db: Sesión de BD
            asset: Asset a consultar (ej: "USDT", "ETH")
        
        Returns:
            Balance o None si no existe
        """
        return db.query(Balance).filter(Balance.asset == asset).first()
    
    @staticmethod
    def update_balance(db: Session, asset: str, delta: Decimal, max_retries: int = 10) -> Balance:
        """
        Actualizar balance con optimistic locking
        
        Args:
            db: Sesión de BD
            asset: Asset a actualizar (ej: "USDT", "ETH")
            delta: Cantidad a sumar/restar (positivo para sumar, negativo para restar)
            max_retries: Máximo de reintentos en caso de conflicto
        
        Returns:
            Balance actualizado
        
        Raises:
            ConcurrentModificationError: Si falla después de max_retries
        """
        for attempt in range(max_retries):
            try:
                # 1. Obtener balance actual con su versión
                balance = db.query(Balance).filter(Balance.asset == asset).first()
                
                if not balance:
                    # Crear balance si no existe
                    balance = Balance(asset=asset, amount=delta, version=0)
                    db.add(balance)
                    db.commit()
                    db.refresh(balance)
                    logger.info(f"✅ Balance creado: {asset} = {delta} (v{balance.version})")
                    return balance
                
                old_version = balance.version
                old_amount = balance.amount
                new_amount = old_amount + delta
                
                # 2. Update con verificación de versión (optimistic locking)
                stmt = update(Balance).where(
                    Balance.asset == asset,
                    Balance.version == old_version  # ✅ Verificar que no cambió
                ).values(
                    amount=new_amount,
                    version=old_version + 1  # ✅ Incrementar versión
                )
                
                result = db.execute(stmt)
                db.commit()
                
                # 3. Verificar que se actualizó
                if result.rowcount == 0:
                    # Otra transacción modificó el balance - conflicto detectado!
                    db.rollback()
                    logger.warning(
                        f"⚠️ Conflicto de concurrencia en {asset} "
                        f"(intento {attempt + 1}/{max_retries})"
                    )
                    
                    # Incrementar métrica de conflictos
                    try:
                        from app.core.metrics import balance_update_conflicts_total
                        balance_update_conflicts_total.labels(asset=asset).inc()
                    except Exception:
                        pass
                    
                    # Exponential backoff con jitter para evitar thundering herd
                    wait_time = (2 ** attempt) * 0.001 + random.uniform(0, 0.01)
                    time.sleep(wait_time)
                    
                    continue  # Reintentar
                
                # 4. Éxito - refrescar objeto
                db.refresh(balance)
                logger.info(
                    f"✅ Balance actualizado: {asset} "
                    f"{old_amount} → {balance.amount} (v{balance.version})"
                )
                
                return balance
                
            except Exception as e:
                db.rollback()
                logger.error(f"❌ Error actualizando balance {asset}: {e}")
                if attempt == max_retries - 1:
                    raise
        
        # Si llegamos aquí, fallaron todos los reintentos
        raise ConcurrentModificationError(
            f"No se pudo actualizar {asset} después de {max_retries} intentos"
        )
    
    @staticmethod
    def set_balance(db: Session, asset: str, amount: Decimal, max_retries: int = 5) -> Balance:
        """
        Establecer balance absoluto con optimistic locking.

        balance-race-condition-fixer: versión anterior no verificaba versión en el
        UPDATE, permitiendo que dos workers concurrentes se pisaran mutuamente.
        Ahora usa el mismo patrón CAS de update_balance().
        """
        for attempt in range(max_retries):
            try:
                balance = db.query(Balance).filter(Balance.asset == asset).first()

                if not balance:
                    balance = Balance(asset=asset, amount=amount, version=0)
                    db.add(balance)
                    db.commit()
                    db.refresh(balance)
                    logger.info("✅ Balance creado: %s = %s (v0)", asset, amount)
                    return balance

                old_version = balance.version

                stmt = (
                    update(Balance)
                    .where(Balance.asset == asset, Balance.version == old_version)
                    .values(amount=amount, version=old_version + 1)
                )
                result = db.execute(stmt)
                db.commit()

                if result.rowcount == 0:
                    db.rollback()
                    logger.warning(
                        "⚠️ [set_balance] Conflicto CAS en %s (intento %d/%d)",
                        asset, attempt + 1, max_retries,
                    )
                    wait = (2 ** attempt) * 0.001 + random.uniform(0, 0.005)
                    time.sleep(wait)
                    continue

                db.refresh(balance)
                logger.info("✅ Balance establecido: %s = %s (v%d)", asset, amount, balance.version)
                return balance

            except Exception as exc:
                db.rollback()
                logger.error("❌ Error en set_balance %s: %s", asset, exc)
                if attempt == max_retries - 1:
                    raise

        raise ConcurrentModificationError(
            f"set_balance: no se pudo actualizar {asset} en {max_retries} intentos"
        )

    @staticmethod
    def upsert_from_exchange(db: Session, asset: str, amount: Decimal) -> None:
        """
        UPSERT atómico para sincronizar balances desde Binance.

        balance-race-condition-fixer: usa una sola sentencia SQL atómica
        (INSERT ... ON CONFLICT DO UPDATE con version++) para que dos workers
        de sincronización concurrentes nunca se pisen. Equivale a:

            INSERT INTO balances (asset, amount, version)
            VALUES (:asset, :amount, 0)
            ON CONFLICT (asset) DO UPDATE
            SET amount = :amount,
                version = balances.version + 1,
                updated_at = NOW()

        Este approach evita el read-modify-write que tenía el asyncpg crudo.
        """
        db.execute(
            text(
                """
                INSERT INTO balances (asset, amount, version, updated_at)
                VALUES (:asset, :amount, 0, NOW())
                ON CONFLICT (asset) DO UPDATE
                    SET amount     = :amount,
                        version    = balances.version + 1,
                        updated_at = NOW()
                """
            ),
            {"asset": asset, "amount": str(amount)},
        )
        # No hacer commit aquí; el caller decide el límite de transacción
    
    @staticmethod
    def get_all_balances(db: Session) -> list[Balance]:
        """
        Obtener todos los balances
        
        Returns:
            Lista de balances
        """
        return db.query(Balance).all()

