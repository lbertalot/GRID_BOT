#!/usr/bin/env python3
"""
Script de Testing para Sprint 1.4: Optimización de Configuración
"""

import asyncio
import sys
import os
from datetime import datetime

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.config_manager import config_manager, OptimizationRequest, OptimizationStrategy
from app.api.config_routes import get_detailed_market_analysis

async def test_config_manager_basic():
    """Prueba básica del ConfigManager"""
    print("\n🔧 1. Probando ConfigManager básico...")
    
    try:
        # Verificar que el ConfigManager esté inicializado
        if not config_manager:
            print("   ❌ ConfigManager no está inicializado")
            return False
        
        print("   ✅ ConfigManager inicializado correctamente")
        print(f"   📊 Cache de datos de mercado: {len(config_manager.market_data_cache)} elementos")
        print(f"   📈 Historial de optimizaciones: {len(config_manager.optimization_history)} elementos")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error en prueba básica: {e}")
        return False

async def test_market_data_retrieval():
    """Prueba de obtención de datos de mercado"""
    print("\n📊 2. Probando obtención de datos de mercado...")
    
    try:
        test_symbols = ["BTC", "ETH", "BNB"]
        
        for symbol in test_symbols:
            print(f"   🎯 Obteniendo datos para {symbol}...")
            
            market_data = await config_manager._get_market_data(symbol)
            
            print(f"      ✅ Precio actual: ${market_data.current_price:.4f}")
            print(f"      📈 Volatilidad: {market_data.volatility:.2%}")
            print(f"      📊 Volumen 24h: ${market_data.volume_24h/1000000:.1f}M")
            print(f"      📉 Cambio 24h: {market_data.price_change_24h:.2f}%")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error obteniendo datos de mercado: {e}")
        return False

async def test_optimization_strategies():
    """Prueba de estrategias de optimización"""
    print("\n🎯 3. Probando estrategias de optimización...")
    
    try:
        test_symbol = "BTC"
        investment_amount = 1000.0
        
        strategies = [
            OptimizationStrategy.GRID_OPTIMIZATION,
            OptimizationStrategy.VOLATILITY_BASED,
            OptimizationStrategy.VOLUME_BASED,
            OptimizationStrategy.MACHINE_LEARNING
        ]
        
        results = {}
        
        for strategy in strategies:
            try:
                print(f"   🔧 Probando estrategia: {strategy.value}")
                
                request = OptimizationRequest(
                    symbol=test_symbol,
                    strategy=strategy,
                    investment_amount=investment_amount,
                    risk_tolerance=0.5,
                    max_grids=20,
                    time_horizon=7
                )
                
                optimized_config = await config_manager.optimize_parameters(request)
                
                print(f"      ✅ Configuración optimizada:")
                print(f"         - Precio min: ${optimized_config.min_price:.4f}")
                print(f"         - Precio max: ${optimized_config.max_price:.4f}")
                print(f"         - Grids: {optimized_config.grids}")
                print(f"         - Cantidad: {optimized_config.quantity:.6f}")
                print(f"         - Score: {optimized_config.confidence_score:.2%}")
                
                if optimized_config.backtest_results:
                    backtest = optimized_config.backtest_results
                    print(f"         - Backtest: {backtest['total_trades']} trades, {backtest['win_rate']:.2%} win rate")
                    print(f"         - ROI: {backtest['roi']:.2%}, Sharpe: {backtest['sharpe_ratio']:.2f}")
                
                results[strategy.value] = optimized_config
                
            except Exception as e:
                print(f"      ❌ Error con estrategia {strategy.value}: {e}")
                results[strategy.value] = None
        
        # Encontrar la mejor estrategia
        best_strategy = None
        best_score = 0
        
        for strategy_name, result in results.items():
            if result and result.confidence_score > best_score:
                best_score = result.confidence_score
                best_strategy = strategy_name
        
        if best_strategy:
            print(f"   🏆 Mejor estrategia: {best_strategy} (Score: {best_score:.2%})")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error en prueba de estrategias: {e}")
        return False

async def test_detailed_market_analysis():
    """Prueba de análisis detallado de mercado"""
    print("\n📈 4. Probando análisis detallado de mercado...")
    
    try:
        test_symbol = "BTC"
        
        print(f"   🎯 Analizando {test_symbol} en detalle...")
        
        analysis = await get_detailed_market_analysis(test_symbol)
        
        print(f"      ✅ Análisis completado:")
        print(f"         - Precio: ${analysis['current_price']:.4f}")
        print(f"         - Volatilidad: {analysis['volatility']['level']} ({analysis['volatility']['daily']:.2%})")
        print(f"         - Volumen: {analysis['volume_analysis']['volume_level']} (${analysis['volume_analysis']['volume_24h']/1000000:.1f}M)")
        print(f"         - Tendencia: {analysis['price_analysis']['trend']}")
        print(f"         - Sharpe Ratio: {analysis['risk_metrics']['sharpe_ratio']:.2f}")
        print(f"         - Max Drawdown: {analysis['risk_metrics']['max_drawdown']:.2%}")
        print(f"         - Estrategia recomendada: {analysis['recommended_strategy']}")
        
        print(f"      💡 Recomendaciones:")
        for rec in analysis['recommendations']:
            print(f"         - {rec}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error en análisis detallado: {e}")
        return False

async def test_backtesting():
    """Prueba del sistema de backtesting"""
    print("\n🧪 5. Probando sistema de backtesting...")
    
    try:
        test_symbol = "ETH"
        
        print(f"   🎯 Ejecutando backtesting para {test_symbol}...")
        
        # Crear configuración de prueba
        request = OptimizationRequest(
            symbol=test_symbol,
            strategy=OptimizationStrategy.GRID_OPTIMIZATION,
            investment_amount=1000.0,
            risk_tolerance=0.5,
            max_grids=15,
            time_horizon=7
        )
        
        optimized_config = await config_manager.optimize_parameters(request)
        
        if optimized_config.backtest_results:
            backtest = optimized_config.backtest_results
            
            print(f"      ✅ Backtesting completado:")
            print(f"         - Total trades: {backtest['total_trades']}")
            print(f"         - Winning trades: {backtest['winning_trades']}")
            print(f"         - Win rate: {backtest['win_rate']:.2%}")
            print(f"         - Total profit: ${backtest['total_profit']:.2f}")
            print(f"         - ROI: {backtest['roi']:.2%}")
            print(f"         - Sharpe ratio: {backtest['sharpe_ratio']:.2f}")
            print(f"         - Max drawdown: {backtest['max_drawdown']:.2%}")
            print(f"         - Simulation days: {backtest['simulation_days']}")
            print(f"         - Initial investment: ${backtest['initial_investment']:.2f}")
            print(f"         - Final balance: ${backtest['final_balance']:.2f}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error en backtesting: {e}")
        return False

async def test_optimization_history():
    """Prueba del historial de optimizaciones"""
    print("\n📚 6. Probando historial de optimizaciones...")
    
    try:
        test_symbol = "BTC"
        
        print(f"   🎯 Obteniendo historial para {test_symbol}...")
        
        history = await config_manager.get_optimization_history(test_symbol)
        
        if test_symbol in history:
            optimizations = history[test_symbol]
            print(f"      ✅ Historial encontrado: {len(optimizations)} optimizaciones")
            
            for i, opt in enumerate(optimizations[-3:], 1):  # Mostrar las últimas 3
                print(f"         {i}. {opt.optimization_strategy} - Score: {opt.confidence_score:.2%} - {opt.timestamp.strftime('%Y-%m-%d %H:%M')}")
        else:
            print(f"      ℹ️ No hay historial para {test_symbol}")
        
        # Obtener historial general
        all_history = await config_manager.get_optimization_history()
        print(f"      📊 Total de símbolos optimizados: {len(all_history)}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error en historial: {e}")
        return False

async def test_risk_integration():
    """Prueba de integración con sistema de riesgos"""
    print("\n🛡️ 7. Probando integración con sistema de riesgos...")
    
    try:
        test_symbol = "BTC"
        
        print(f"   🎯 Probando optimización con diferentes niveles de riesgo...")
        
        risk_levels = [0.2, 0.5, 0.8]  # Conservador, Moderado, Agresivo
        
        for risk_tolerance in risk_levels:
            print(f"      🔧 Tolerancia al riesgo: {risk_tolerance}")
            
            request = OptimizationRequest(
                symbol=test_symbol,
                strategy=OptimizationStrategy.VOLATILITY_BASED,
                investment_amount=1000.0,
                risk_tolerance=risk_tolerance,
                max_grids=20,
                time_horizon=7
            )
            
            optimized_config = await config_manager.optimize_parameters(request)
            
            print(f"         - Grids: {optimized_config.grids}")
            print(f"         - Cantidad: {optimized_config.quantity:.6f}")
            print(f"         - Score: {optimized_config.confidence_score:.2%}")
            
            if optimized_config.backtest_results:
                backtest = optimized_config.backtest_results
                print(f"         - ROI: {backtest['roi']:.2%}")
                print(f"         - Max drawdown: {backtest['max_drawdown']:.2%}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error en integración de riesgos: {e}")
        return False

async def test_performance_metrics():
    """Prueba de métricas de rendimiento"""
    print("\n⚡ 8. Probando métricas de rendimiento...")
    
    try:
        start_time = datetime.now()
        
        # Ejecutar múltiples optimizaciones para medir rendimiento
        test_symbols = ["BTC", "ETH", "BNB"]
        
        for symbol in test_symbols:
            request = OptimizationRequest(
                symbol=symbol,
                strategy=OptimizationStrategy.GRID_OPTIMIZATION,
                investment_amount=1000.0,
                risk_tolerance=0.5,
                max_grids=15,
                time_horizon=7
            )
            
            await config_manager.optimize_parameters(request)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print(f"   ✅ Optimización de {len(test_symbols)} símbolos completada en {duration:.2f} segundos")
        print(f"   📊 Tiempo promedio por optimización: {duration/len(test_symbols):.2f} segundos")
        
        # Verificar cache
        cache_size = len(config_manager.market_data_cache)
        print(f"   💾 Tamaño del cache: {cache_size} elementos")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error en métricas de rendimiento: {e}")
        return False

async def main():
    """Función principal de testing"""
    print("🚀 INICIANDO TESTING DEL SPRINT 1.4: OPTIMIZACIÓN DE CONFIGURACIÓN")
    print("=" * 80)
    
    tests = [
        test_config_manager_basic,
        test_market_data_retrieval,
        test_optimization_strategies,
        test_detailed_market_analysis,
        test_backtesting,
        test_optimization_history,
        test_risk_integration,
        test_performance_metrics
    ]
    
    passed_tests = 0
    total_tests = len(tests)
    
    for test in tests:
        try:
            result = await test()
            if result:
                passed_tests += 1
        except Exception as e:
            print(f"   ❌ Error ejecutando test: {e}")
    
    print("\n" + "=" * 80)
    print("📊 RESUMEN DE TESTING")
    print("=" * 80)
    print(f"✅ Tests exitosos: {passed_tests}/{total_tests}")
    print(f"📈 Tasa de éxito: {(passed_tests/total_tests)*100:.1f}%")
    
    if passed_tests == total_tests:
        print("🎉 ¡TODOS LOS TESTS PASARON! Sprint 1.4 completado exitosamente.")
        return True
    else:
        print("⚠️ Algunos tests fallaron. Revisar implementación.")
        return False

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n❌ Testing interrumpido por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")
        sys.exit(1) 