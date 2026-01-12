"""
Test de Lock Distribuido para Celery Tasks
"""
import sys
sys.path.insert(0, '/app')

import time
import threading
from app.core.distributed_lock import with_distributed_lock, check_lock_status, force_release_lock


# Función de prueba con lock
call_count = 0
concurrent_calls = 0
max_concurrent = 0


@with_distributed_lock("test_lock", timeout=5, blocking=False)
def test_function():
    """Función de prueba que simula trabajo"""
    global call_count, concurrent_calls, max_concurrent
    
    call_count += 1
    concurrent_calls += 1
    
    if concurrent_calls > max_concurrent:
        max_concurrent = concurrent_calls
    
    print(f"✅ Función ejecutada (call #{call_count}, concurrent: {concurrent_calls})")
    
    # Simular trabajo
    time.sleep(2)
    
    concurrent_calls -= 1
    return {"status": "ok", "call_number": call_count}


def worker(worker_id):
    """Worker que intenta ejecutar la función"""
    print(f"Worker {worker_id} iniciando...")
    result = test_function()
    print(f"Worker {worker_id} resultado: {result}")


def test_distributed_lock():
    """Test principal de lock distribuido"""
    global call_count, concurrent_calls, max_concurrent
    
    print("\n" + "="*70)
    print("🧪 TEST DE LOCK DISTRIBUIDO")
    print("="*70 + "\n")
    
    # Reset contadores
    call_count = 0
    concurrent_calls = 0
    max_concurrent = 0
    
    # Limpiar locks previos
    force_release_lock("test_lock")
    
    # Verificar estado inicial
    status = check_lock_status("test_lock")
    print(f"📊 Estado inicial del lock: {status}")
    assert status['status'] == 'free', "Lock debería estar libre inicialmente"
    
    print(f"\n🚀 Lanzando 5 workers concurrentes...\n")
    
    # Crear 5 threads que intentan ejecutar la función al mismo tiempo
    threads = []
    for i in range(5):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()
    
    # Esperar a que todos terminen
    for t in threads:
        t.join()
    
    print(f"\n" + "="*70)
    print("📊 RESULTADOS:")
    print(f"   Total de workers: 5")
    print(f"   Llamadas ejecutadas: {call_count}")
    print(f"   Máximo concurrente: {max_concurrent}")
    print("="*70 + "\n")
    
    # Verificaciones
    if call_count == 1:
        print("✅✅✅ TEST PASSED: Solo 1 ejecución (lock funcionó)")
        print("✅ Los otros 4 workers fueron bloqueados correctamente\n")
        success = True
    else:
        print(f"❌ TEST FAILED: Se ejecutaron {call_count} veces (esperado: 1)")
        print(f"❌ Lock NO previno ejecuciones concurrentes\n")
        success = False
    
    if max_concurrent > 1:
        print(f"❌ CONCURRENT EXECUTION DETECTED: {max_concurrent} ejecuciones simultáneas")
        success = False
    else:
        print("✅ No hubo ejecuciones simultáneas\n")
    
    # Verificar estado final
    time.sleep(1)  # Esperar a que se libere el lock
    status = check_lock_status("test_lock")
    print(f"📊 Estado final del lock: {status}")
    
    if status['status'] == 'free':
        print("✅ Lock liberado correctamente después de la ejecución\n")
    else:
        print(f"⚠️ Lock aún activo: TTL {status.get('ttl_seconds')}s\n")
    
    # Cleanup
    force_release_lock("test_lock")
    
    return success


def test_lock_blocking_mode():
    """Test de modo blocking (espera a que se libere)"""
    print("\n" + "="*70)
    print("🧪 TEST DE LOCK EN MODO BLOCKING")
    print("="*70 + "\n")
    
    force_release_lock("test_lock_blocking")
    
    results = []
    
    @with_distributed_lock("test_lock_blocking", timeout=10, blocking=True, blocking_timeout=15)
    def blocking_function(worker_id):
        print(f"✅ Worker {worker_id} ejecutando")
        time.sleep(3)  # Simular trabajo
        results.append(worker_id)
        return {"worker_id": worker_id}
    
    def blocking_worker(worker_id):
        print(f"Worker {worker_id} iniciando (modo blocking)...")
        result = blocking_function(worker_id)
        print(f"Worker {worker_id} resultado: {result}")
    
    # Lanzar 3 workers en modo blocking
    print("🚀 Lanzando 3 workers en modo BLOCKING...\n")
    threads = []
    for i in range(3):
        t = threading.Thread(target=blocking_worker, args=(i,))
        threads.append(t)
        t.start()
        time.sleep(0.1)  # Pequeño delay para asegurar orden
    
    for t in threads:
        t.join()
    
    print(f"\n📊 Resultados: {len(results)} workers ejecutados")
    print(f"   Orden de ejecución: {results}")
    
    if len(results) == 3:
        print("✅✅✅ TEST PASSED: Los 3 workers se ejecutaron secuencialmente")
        print("✅ Modo blocking funcionó correctamente\n")
        success = True
    else:
        print(f"❌ TEST FAILED: Solo {len(results)} workers ejecutados (esperado: 3)\n")
        success = False
    
    force_release_lock("test_lock_blocking")
    return success


if __name__ == "__main__":
    try:
        # Test 1: Modo non-blocking (skip si lock está tomado)
        test1_passed = test_distributed_lock()
        
        # Test 2: Modo blocking (espera a que se libere)
        test2_passed = test_lock_blocking_mode()
        
        # Resultado final
        if test1_passed and test2_passed:
            print("🎉🎉🎉 TODOS LOS TESTS PASARON 🎉🎉🎉")
            print("✅ Lock Distribuido funciona correctamente")
            print("✅ Bug #2 RESUELTO\n")
            sys.exit(0)
        else:
            print("❌ ALGUNOS TESTS FALLARON")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Error fatal en tests: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

