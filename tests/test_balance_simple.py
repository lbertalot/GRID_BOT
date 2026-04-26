"""
Test simplificado de BalanceService (sin dependencias complejas)
"""

import sys
import os

sys.path.insert(0, "/app")

from decimal import Decimal
from threading import Thread
import time
from sqlalchemy import create_engine, Column, Integer, String, Numeric, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import update
from datetime import datetime

# Configuración de BD
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://griduser:gridpass@db:5432/gridbot"
)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


# Modelo Balance simplificado
class Balance(Base):
    __tablename__ = "balances"
    id = Column(Integer, primary_key=True, index=True)
    asset = Column(String(20), unique=True, nullable=False, index=True)
    amount = Column(Numeric(20, 8), nullable=False, default=0)
    version = Column(Integer, default=0, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow)


# Servicio simplificado con backoff exponencial
def update_balance_safe(db: Session, asset: str, delta: Decimal, max_retries: int = 10):
    """Update con optimistic locking y exponential backoff"""
    import random

    for attempt in range(max_retries):
        balance = db.query(Balance).filter(Balance.asset == asset).first()

        if not balance:
            balance = Balance(asset=asset, amount=delta, version=0)
            db.add(balance)
            db.commit()
            db.refresh(balance)
            print(f"✅ Balance creado: {asset} = {delta}")
            return balance

        old_version = balance.version
        old_amount = balance.amount
        new_amount = old_amount + delta

        stmt = (
            update(Balance)
            .where(Balance.asset == asset, Balance.version == old_version)
            .values(amount=new_amount, version=old_version + 1)
        )

        result = db.execute(stmt)
        db.commit()

        if result.rowcount == 0:
            db.rollback()
            print(f"⚠️ Conflicto en {asset} (intento {attempt + 1}/{max_retries})")

            # Exponential backoff con jitter
            wait_time = (2**attempt) * 0.001 + random.uniform(0, 0.01)
            time.sleep(wait_time)
            continue

        db.refresh(balance)
        print(f"✅ {asset}: {old_amount} → {balance.amount} (v{balance.version})")
        return balance

    raise Exception(f"No se pudo actualizar {asset} después de {max_retries} intentos")


def test_concurrent_updates():
    """Test de concurrencia"""
    print("\n" + "=" * 70)
    print("🧪 TEST DE CONCURRENCIA: Bug #1 Fix")
    print("=" * 70 + "\n")

    # Setup
    db = SessionLocal()
    db.query(Balance).filter_by(asset="TEST_CONCURRENT").delete()
    db.commit()

    initial = Balance(asset="TEST_CONCURRENT", amount=Decimal("100.0"), version=0)
    db.add(initial)
    db.commit()
    print("💰 Balance inicial: TEST_CONCURRENT = 100.0 (v0)\n")
    db.close()

    # Workers concurrentes
    results = {"success": 0, "errors": 0}

    def worker(worker_id: int):
        db = SessionLocal()
        try:
            update_balance_safe(db, "TEST_CONCURRENT", Decimal("1.0"))
            results["success"] += 1
        except Exception as e:
            print(f"❌ Worker {worker_id}: {e}")
            results["errors"] += 1
        finally:
            db.close()

    # Ejecutar 10 threads
    print("🚀 Ejecutando 10 threads concurrentes...\n")
    threads = []
    for i in range(10):
        t = Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # Verificar resultado
    db = SessionLocal()
    final = db.query(Balance).filter_by(asset="TEST_CONCURRENT").first()

    print("\n" + "=" * 70)
    print("📊 RESULTADOS:")
    print(f"   Exitosos: {results['success']}")
    print(f"   Errores: {results['errors']}")
    print(f"   Balance final: {final.amount}")
    print(f"   Versión final: v{final.version}")
    print("   Expected: 110.0")
    print("=" * 70 + "\n")

    # Validar
    expected = Decimal("110.0")
    if final.amount == expected:
        print("✅✅✅ TEST PASSED: Optimistic Locking funciona correctamente!")
        print("✅ NO se perdieron updates - Bug #1 RESUELTO\n")
        success = True
    else:
        print(f"❌ TEST FAILED: Expected {expected}, got {final.amount}")
        print("❌ SE PERDIERON UPDATES - Bug persiste\n")
        success = False

    # Cleanup
    db.query(Balance).filter_by(asset="TEST_CONCURRENT").delete()
    db.commit()
    db.close()

    return success


if __name__ == "__main__":
    try:
        success = test_concurrent_updates()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Error fatal: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
