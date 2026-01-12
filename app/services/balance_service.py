"""
Balance Service con Optimistic Locking
GridBot v2.5 - FIX para Bug #1: Race Condition
"""
from decimal import Decimal
from typing import Optional
from sqlalchemy import update
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
    def set_balance(db: Session, asset: str, amount: Decimal) -> Balance:
        """
        Establecer balance absoluto (no incremental)
        Útil para sincronización con Binance
        
        Args:
            db: Sesión de BD
            asset: Asset a establecer
            amount: Cantidad absoluta
        
        Returns:
            Balance actualizado
        """
        balance = db.query(Balance).filter(Balance.asset == asset).first()
        
        if not balance:
            balance = Balance(asset=asset, amount=amount, version=0)
            db.add(balance)
        else:
            balance.amount = amount
            balance.version += 1
        
        db.commit()
        db.refresh(balance)
        logger.info(f"✅ Balance establecido: {asset} = {amount} (v{balance.version})")
        return balance
    
    @staticmethod
    def get_all_balances(db: Session) -> list[Balance]:
        """
        Obtener todos los balances
        
        Returns:
            Lista de balances
        """
        return db.query(Balance).all()

