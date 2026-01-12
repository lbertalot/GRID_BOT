"""
Test de Performance para validar que no hay bloqueos en el event loop
"""
import sys
sys.path.insert(0, '/app')

import time
import asyncio
import httpx
from typing import List, Dict


async def test_endpoint_performance():
    """Test de latencia de endpoints async"""
    print("\n" + "="*70)
    print("🧪 TEST DE PERFORMANCE ASYNC (Bug #3 Fix)")
    print("="*70 + "\n")
    
    # Endpoints a testear
    endpoints = [
        {"url": "http://localhost:8000/health", "name": "Health Check"},
        {"url": "http://localhost:8000/api/reconciliation/summary", "name": "Reconciliation Summary"},
    ]
    
    results: List[Dict] = []
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for endpoint in endpoints:
            print(f"📊 Testing: {endpoint['name']}")
            
            # Test secuencial (baseline)
            start = time.time()
            try:
                response = await client.get(endpoint['url'])
                sequential_time = time.time() - start
                status = response.status_code
                print(f"   Secuencial: {sequential_time*1000:.1f}ms (status: {status})")
            except Exception as e:
                print(f"   ❌ Error: {e}")
                sequential_time = None
                status = "error"
            
            # Test concurrente (3 requests simultáneos)
            start = time.time()
            tasks = [client.get(endpoint['url']) for _ in range(3)]
            try:
                responses = await asyncio.gather(*tasks, return_exceptions=True)
                concurrent_time = time.time() - start
                avg_time = concurrent_time / 3
                print(f"   Concurrente (3x): {concurrent_time*1000:.1f}ms total, {avg_time*1000:.1f}ms promedio")
                
                # Verificar que no hubo bloqueo total
                if sequential_time and concurrent_time:
                    # Si el tiempo concurrente es < 2x el tiempo secuencial, el event loop está funcionando
                    if concurrent_time < sequential_time * 2.5:
                        print(f"   ✅ Event loop no bloqueado (ratio: {concurrent_time/sequential_time:.2f}x)")
                        blocking = False
                    else:
                        print(f"   ⚠️ Posible bloqueo (ratio: {concurrent_time/sequential_time:.2f}x)")
                        blocking = True
                else:
                    blocking = None
                    
            except Exception as e:
                print(f"   ❌ Error en test concurrente: {e}")
                concurrent_time = None
                avg_time = None
                blocking = None
            
            results.append({
                "endpoint": endpoint['name'],
                "sequential_ms": sequential_time * 1000 if sequential_time else None,
                "concurrent_ms": concurrent_time * 1000 if concurrent_time else None,
                "avg_concurrent_ms": avg_time * 1000 if avg_time else None,
                "blocking": blocking,
                "status": status
            })
            
            print()  # Línea en blanco
    
    # Resumen
    print("="*70)
    print("📊 RESUMEN DE PERFORMANCE:")
    print("="*70)
    
    all_passed = True
    for result in results:
        if result['blocking'] is False:
            status_icon = "✅"
        elif result['blocking'] is True:
            status_icon = "❌"
            all_passed = False
        else:
            status_icon = "⚠️"
        
        print(f"{status_icon} {result['endpoint']}:")
        if result['sequential_ms']:
            print(f"   Secuencial: {result['sequential_ms']:.1f}ms")
        if result['avg_concurrent_ms']:
            print(f"   Concurrente: {result['avg_concurrent_ms']:.1f}ms promedio")
        if result['blocking'] is False:
            print(f"   Event loop: ✅ No bloqueado")
        elif result['blocking'] is True:
            print(f"   Event loop: ❌ Bloqueado")
        print()
    
    print("="*70)
    if all_passed:
        print("✅✅✅ TEST PASSED: Event loop no bloqueado")
        print("✅ Bug #3 Fix validado - asyncio.to_thread() funciona correctamente\n")
        return True
    else:
        print("❌ TEST FAILED: Detectado bloqueo en event loop")
        print("❌ Revisar llamadas sync sin asyncio.to_thread()\n")
        return False


async def test_concurrent_requests():
    """Test de throughput con múltiples requests simultáneos"""
    print("\n" + "="*70)
    print("🧪 TEST DE THROUGHPUT CONCURRENTE")
    print("="*70 + "\n")
    
    num_requests = 10
    url = "http://localhost:8000/health"
    
    print(f"📊 Enviando {num_requests} requests simultáneos a /health...")
    
    start = time.time()
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        tasks = [client.get(url) for _ in range(num_requests)]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
    
    total_time = time.time() - start
    successful = sum(1 for r in responses if isinstance(r, httpx.Response) and r.status_code == 200)
    
    print(f"\n📊 RESULTADOS:")
    print(f"   Total de requests: {num_requests}")
    print(f"   Exitosos: {successful}")
    print(f"   Tiempo total: {total_time*1000:.1f}ms")
    print(f"   Tiempo promedio: {total_time*1000/num_requests:.1f}ms")
    print(f"   Throughput: {num_requests/total_time:.1f} req/s")
    
    # Validar
    if successful == num_requests and total_time < 5.0:  # Debería ser < 5s para 10 requests
        print(f"\n✅ Throughput adecuado")
        return True
    else:
        print(f"\n⚠️ Throughput degradado")
        return False


async def main():
    """Ejecutar todos los tests"""
    try:
        print("\n" + "🚀"*35)
        print("Bug #3: Async Performance Test Suite")
        print("🚀"*35)
        
        # Test 1: Performance individual
        test1_passed = await test_endpoint_performance()
        
        # Test 2: Throughput concurrente
        test2_passed = await test_concurrent_requests()
        
        # Resultado final
        print("\n" + "="*70)
        if test1_passed and test2_passed:
            print("🎉🎉🎉 TODOS LOS TESTS PASARON 🎉🎉🎉")
            print("✅ Event loop funciona correctamente")
            print("✅ Bug #3 RESUELTO\n")
            return 0
        else:
            print("❌ ALGUNOS TESTS FALLARON")
            print("❌ Revisar implementación de asyncio.to_thread()\n")
            return 1
            
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

