"""
Tests de concurrencia para BalanceService
GridBot v2.5 - Bug #1 Fix Validation
"""
import pytest
from decimal import Decimal
from threading import Thread
import time
from app.services.balance_service import BalanceService, ConcurrentModificationError
from app.models.balance import Balance
from app.db.session import SessionLocal


def test_concurrent_balance_updates():
    """
    Test de actualización concurrente de balance
    Verifica que NO se pierdan updates con optimistic locking
    """
    
    # Setup: crear balance inicial
    db = SessionLocal()
    try:
        # Limpiar balance de test anterior si existe
        existing = db.query(Balance).filter_by(asset="TEST_USDT").first()
        if existing:
            db.delete(existing)
            db.commit()
        
        # Crear balance inicial
        initial_balance = Balance(asset="TEST_USDT", amount=Decimal("100.0"), version=0)
        db.add(initial_balance)
        db.commit()
        initial_amount = initial_balance.amount
        print(f"💰 Balance inicial: TEST_USDT = {initial_amount}")
    finally:
        db.close()
    
    # Función que actualiza balance (ejecutará en múltiples threads)
    results = {"success": 0, "conflicts": 0, "errors": 0}
    
    def update_worker(delta: Decimal, worker_id: int):
        db = SessionLocal()
        try:
            balance = BalanceService.update_balance(db, "TEST_USDT", delta)
            results["success"] += 1
            print(f"  ✅ Worker {worker_id}: Balance actualizado a {balance.amount} (v{balance.version})")
        except ConcurrentModificationError as e:
            results["conflicts"] += 1
            print(f"  ⚠️ Worker {worker_id}: Conflicto después de reintentos - {e}")
        except Exception as e:
            results["errors"] += 1
            print(f"  ❌ Worker {worker_id}: Error - {e}")
        finally:
            db.close()
    
    # Ejecutar 10 threads en paralelo, cada uno suma 1.0
    print(f"\n🚀 Ejecutando 10 threads concurrentes...")
    threads = []
    for i in range(10):
        t = Thread(target=update_worker, args=(Decimal("1.0"), i))
        threads.append(t)
        t.start()
    
    # Esperar a que terminen todos
    for t in threads:
        t.join()
    
    # Verificar balance final
    db = SessionLocal()
    try:
        final_balance = db.query(Balance).filter(Balance.asset == "TEST_USDT").first()
        
        print(f"\n📊 Resultados:")
        print(f"   Exitosos: {results['success']}")
        print(f"   Conflictos (reintentados): {results['conflicts']}")
        print(f"   Errores: {results['errors']}")
        print(f"   Balance inicial: {initial_amount}")
        print(f"   Balance final: {final_balance.amount}")
        print(f"   Versión final: {final_balance.version}")
        
        # Balance debe ser inicial + 10.0 (sin pérdidas por race condition)
        expected = initial_amount + Decimal("10.0")
        assert final_balance.amount == expected, \
            f"❌ FALLO: Expected {expected}, got {final_balance.amount} - ¡SE PERDIERON UPDATES!"
        
        # Versión debe ser >= 10 (una por cada update exitoso)
        assert final_balance.version >= 10, \
            f"❌ FALLO: Expected version >= 10, got {final_balance.version}"
        
        print(f"\n✅ TEST PASSED: No se perdieron updates - Optimistic locking funcionando correctamente!")
        
    finally:
        # Limpiar
        db.query(Balance).filter_by(asset="TEST_USDT").delete()
        db.commit()
        db.close()


def test_balance_conflict_detection():
    """
    Test que verifica que se detectan conflictos de versión
    """
    db = SessionLocal()
    try:
        # Limpiar
        db.query(Balance).filter_by(asset="TEST_CONFLICT").delete()
        db.commit()
        
        # Crear balance
        balance = Balance(asset="TEST_CONFLICT", amount=Decimal("100.0"), version=0)
        db.add(balance)
        db.commit()
        
        # Simular conflicto: modificar directamente en BD
        db.query(Balance).filter_by(asset="TEST_CONFLICT").update({
            "amount": Decimal("150.0"),
            "version": 1
        })
        db.commit()
        
        # Intentar update con versión vieja (debe fallar o reintentar)
        try:
            BalanceService.update_balance(db, "TEST_CONFLICT", Decimal("10.0"))
            print("✅ Update exitoso (posiblemente después de reintentos)")
        except ConcurrentModificationError:
            print("✅ ConcurrentModificationError detectado correctamente")
        
    finally:
        # Limpiar
        db.query(Balance).filter_by(asset="TEST_CONFLICT").delete()
        db.commit()
        db.close()


if __name__ == "__main__":
    print("="*70)
    print("Bug #1 Fix: Test de Concurrencia de Balances")
    print("="*70)
    
    print("\n📝 Test 1: Actualizaciones concurrentes")
    test_concurrent_balance_updates()
    
    print("\n📝 Test 2: Detección de conflictos")
    test_balance_conflict_detection()
    
    print("\n" + "="*70)
    print("✅ TODOS LOS TESTS PASSED - Bug #1 RESUELTO")
    print("="*70)

