#!/usr/bin/env python3
"""
Script para probar las optimizaciones implementadas
"""

import sys
import os
import asyncio
from datetime import datetime

# Agregar el directorio app al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

def test_functional_commission():
    """Prueba las funciones puras de comisión"""
    print("🧪 Probando funciones puras de comisión...")
    
    try:
        from services.commission import (
            calculate_commission, 
            calculate_profit_with_commissions,
            validate_minimum_profit,
            CommissionRates
        )
        
        # Prueba 1: Cálculo básico de comisión
        result = calculate_commission(1000.0, 'MARKET')
        assert result.commission_usdt == 1.0, f"Comisión esperada 1.0, obtenida {result.commission_usdt}"
        print("✅ Cálculo básico de comisión: OK")
        
        # Prueba 2: Cálculo con tasas personalizadas
        custom_rates = CommissionRates(maker=0.0005, taker=0.0015)
        result = calculate_commission(1000.0, 'LIMIT', custom_rates)
        assert result.commission_usdt == 0.5, f"Comisión esperada 0.5, obtenida {result.commission_usdt}"
        print("✅ Cálculo con tasas personalizadas: OK")
        
        # Prueba 3: Cálculo de ganancia con comisiones
        profit_data = calculate_profit_with_commissions(
            buy_price=100.0,
            sell_price=101.0,
            quantity=10.0
        )
        assert profit_data['net_profit'] > 0, "Debería haber ganancia neta"
        print("✅ Cálculo de ganancia con comisiones: OK")
        
        # Prueba 4: Validación de ganancia mínima
        is_profitable, details = validate_minimum_profit(
            buy_price=100.0,
            sell_price=101.0,
            quantity=10.0,
            min_profit_percentage=0.5
        )
        assert is_profitable, "Debería ser rentable"
        print("✅ Validación de ganancia mínima: OK")
        
        print("🎉 Todas las pruebas de comisión funcional pasaron!")
        return True
        
    except Exception as e:
        print(f"❌ Error en pruebas de comisión funcional: {e}")
        return False

def test_error_types():
    """Prueba los tipos de error específicos"""
    print("🧪 Probando tipos de error específicos...")
    
    try:
        from core.trading_errors import (
            create_commission_error,
            create_validation_error,
            create_binance_api_error,
            handle_trading_error,
            ErrorSeverity
        )
        
        # Prueba 1: Error de comisión
        error = create_commission_error(1000.0, "Error de prueba")
        assert error.code == "INVALID_COMMISSION_CALCULATION"
        assert error.severity == ErrorSeverity.MEDIUM
        print("✅ Creación de error de comisión: OK")
        
        # Prueba 2: Error de validación
        error = create_validation_error("price", -100, "positive_float", "Precio debe ser positivo")
        assert error.code == "VALIDATION_ERROR"
        assert error.field == "price"
        print("✅ Creación de error de validación: OK")
        
        # Prueba 3: Error de API de Binance
        error = create_binance_api_error(429, "Rate limit exceeded", "/api/v3/order")
        assert error.code == "BINANCE_API_ERROR"
        assert error.retryable == True  # Rate limit es retryable
        print("✅ Creación de error de API: OK")
        
        # Prueba 4: Manejo funcional de errores
        result = handle_trading_error(error)
        assert result["error"] == True
        assert result["retryable"] == True
        print("✅ Manejo funcional de errores: OK")
        
        print("🎉 Todas las pruebas de tipos de error pasaron!")
        return True
        
    except Exception as e:
        print(f"❌ Error en pruebas de tipos de error: {e}")
        return False

def test_improved_schemas():
    """Prueba los schemas mejorados"""
    print("🧪 Probando schemas mejorados...")
    
    try:
        from schemas.simple_validation import (
            TradingOrder,
            GridConfiguration,
            CommissionCalculation,
            TradingResult,
            PortfolioBalance
        )
        
        # Prueba 1: TradingOrder válido
        order = TradingOrder(
            symbol="BTCUSDT",
            side="BUY",
            quantity=0.001,
            order_type="MARKET"
        )
        assert str(order.symbol) == "BTCUSDT"
        print("✅ TradingOrder válido: OK")
        
        # Prueba 2: GridConfiguration válido
        config = GridConfiguration(
            symbol="BTCUSDT",
            min_price=50000,
            max_price=60000,
            num_levels=10,
            quantity_per_level=0.001
        )
        assert config.num_levels == 10
        print("✅ GridConfiguration válido: OK")
        
        # Prueba 3: CommissionCalculation válido
        calc = CommissionCalculation(
            notional_value=1000,
            order_type="MARKET",
            symbol="BTCUSDT"
        )
        assert calc.notional_value == 1000
        print("✅ CommissionCalculation válido: OK")
        
        # Prueba 4: TradingResult válido
        result = TradingResult(
            success=True,
            order_id="12345",
            executed_quantity=0.001,
            executed_price=50000,
            commission_paid=0.05
        )
        assert result.success == True
        print("✅ TradingResult válido: OK")
        
        # Prueba 5: PortfolioBalance válido
        balance = PortfolioBalance(
            asset="BTC",
            free=1.0,
            locked=0.1,
            total=1.1
        )
        assert abs(balance.total - (balance.free + balance.locked)) < 0.000001
        print("✅ PortfolioBalance válido: OK")
        
        print("🎉 Todas las pruebas de schemas pasaron!")
        return True
        
    except Exception as e:
        print(f"❌ Error en pruebas de schemas: {e}")
        return False

def test_performance_utils():
    """Prueba las utilidades de performance"""
    print("🧪 Probando utilidades de performance...")
    
    try:
        from core.performance_utils import (
            MemoryCache,
            cached,
            RateLimiter,
            LazyLoader,
            measure_performance
        )
        import asyncio
        
        # Prueba 1: MemoryCache
        cache = MemoryCache()
        cache.set("test_key", "test_value", 1)
        assert cache.get("test_key") == "test_value"
        print("✅ MemoryCache: OK")
        
        # Prueba 2: RateLimiter
        limiter = RateLimiter(max_calls=2, time_window=1.0)
        
        async def test_rate_limiter():
            assert await limiter.acquire() == True
            assert await limiter.acquire() == True
            assert await limiter.acquire() == False  # Debería fallar
            return True
        
        asyncio.run(test_rate_limiter())
        print("✅ RateLimiter: OK")
        
        # Prueba 3: LazyLoader
        async def test_loader():
            return "data_loaded"
        
        loader = LazyLoader(test_loader)
        data = asyncio.run(loader.get_data())
        assert data == "data_loaded"
        print("✅ LazyLoader: OK")
        
        # Prueba 4: Decorador cached
        call_count = 0
        
        @cached(ttl=1)
        async def test_cached_function():
            nonlocal call_count
            call_count += 1
            return "cached_result"
        
        # Primera llamada
        result1 = asyncio.run(test_cached_function())
        # Segunda llamada (debería usar cache)
        result2 = asyncio.run(test_cached_function())
        
        assert result1 == result2
        assert call_count == 1  # Solo debería llamarse una vez
        print("✅ Decorador cached: OK")
        
        print("🎉 Todas las pruebas de performance pasaron!")
        return True
        
    except Exception as e:
        print(f"❌ Error en pruebas de performance: {e}")
        return False

async def test_api_endpoints():
    """Prueba los endpoints de la API"""
    print("🧪 Probando endpoints de la API...")
    
    try:
        import aiohttp
        import json
        
        # Leer API key del archivo .env
        api_key = None
        try:
            with open('.env', 'r') as f:
                for line in f:
                    if line.startswith('API_KEY='):
                        api_key = line.split('=')[1].strip()
                        break
        except FileNotFoundError:
            print("⚠️ Archivo .env no encontrado, usando API key por defecto")
            api_key = "test_key"
        
        headers = {"Authorization": f"Bearer {api_key}"}
        
        async with aiohttp.ClientSession() as session:
            # Prueba 1: Health check
            async with session.get('http://localhost:8000/health') as response:
                assert response.status == 200
                data = await response.json()
                assert data.get('status') == 'healthy'
            print("✅ Health check: OK")
            
            # Prueba 2: Commission rates
            async with session.get('http://localhost:8000/api/v1/commissions/rates', headers=headers) as response:
                assert response.status == 200
                data = await response.json()
                assert 'maker_commission' in data
            print("✅ Commission rates endpoint: OK")
            
            # Prueba 3: Commission calculation
            calc_data = {
                "symbol": "BTCUSDT",
                "quantity": 0.001,
                "price": 50000,
                "order_type": "MARKET"
            }
            async with session.post(
                'http://localhost:8000/api/v1/commissions/calculate',
                headers={**headers, "Content-Type": "application/json"},
                json=calc_data
            ) as response:
                assert response.status == 200
                data = await response.json()
                assert 'commission_usdt' in data
            print("✅ Commission calculation endpoint: OK")
        
        print("🎉 Todas las pruebas de API pasaron!")
        return True
        
    except Exception as e:
        print(f"❌ Error en pruebas de API: {e}")
        return False

def main():
    """Función principal de pruebas"""
    print("🧪 Ejecutando pruebas de optimizaciones...")
    print("=" * 60)
    
    results = []
    
    # Pruebas síncronas
    results.append(("Funciones puras de comisión", test_functional_commission()))
    results.append(("Tipos de error específicos", test_error_types()))
    results.append(("Schemas mejorados", test_improved_schemas()))
    results.append(("Utilidades de performance", test_performance_utils()))
    
    # Pruebas asíncronas
    try:
        api_result = asyncio.run(test_api_endpoints())
        results.append(("Endpoints de API", api_result))
    except Exception as e:
        print(f"⚠️ No se pudieron ejecutar pruebas de API: {e}")
        results.append(("Endpoints de API", False))
    
    # Resumen de resultados
    print("\n" + "=" * 60)
    print("📊 RESUMEN DE PRUEBAS")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASÓ" if result else "❌ FALLÓ"
        print(f"{test_name:<30} {status}")
        if result:
            passed += 1
    
    print(f"\n🎯 Resultado: {passed}/{total} pruebas pasaron")
    
    if passed == total:
        print("🎉 ¡Todas las optimizaciones están funcionando correctamente!")
        return True
    else:
        print("⚠️ Algunas optimizaciones necesitan ajustes")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
