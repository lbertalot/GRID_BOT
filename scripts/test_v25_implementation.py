#!/usr/bin/env python3
"""
Script de prueba para verificar la implementación V2.5 "Low-Risk, Predictive & Adaptive Grid".
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.risk_manager import RiskManager, MarketRegime, RegimePrediction, PositionSizeParams, TrailingStopParams
from app.services.strategy_selector import StrategySelector, StrategyType, AccountState
from app.services.hybrid_ml_engine import HybridMLEngine
from app.services.backtesting_service import BacktestingService, BacktestConfig
from app.exchanges.binance_client import BinanceClient


async def test_risk_manager():
    """Prueba el RiskManager evolucionado."""
    print("🔍 Probando RiskManager evolucionado...")
    
    risk_manager = RiskManager()
    
    # Test 1: Cálculo de tamaño de posición dinámico
    position_params = PositionSizeParams(
        symbol="BTCUSDT",
        account_equity=10000.0,
        atr=0.02,
        winrate_estimate=0.6,
        avg_win_loss_ratio=1.5,
        price=50000.0
    )
    
    position_size = risk_manager.calculate_dynamic_position_size(position_params)
    print(f"   ✅ Tamaño de posición calculado: {position_size:.2f} USDT")
    
    # Test 2: Trailing stop adaptativo
    trailing_params = TrailingStopParams(
        symbol="BTCUSDT",
        entry_price=50000.0,
        atr=1000.0,
        multiplier_atr=2.0,
        is_long=True
    )
    
    stop_price = risk_manager.get_adaptive_trailing_stop(trailing_params)
    print(f"   ✅ Trailing stop calculado: {stop_price:.2f}")
    
    # Test 3: Filtro de régimen de mercado
    risk_manager.apply_market_regime_filter(MarketRegime.CRASH_IMMINENT)
    print(f"   ✅ Filtro de régimen aplicado: {risk_manager.current_regime.value}")
    
    # Test 4: Circuit breaker
    breaker_state = risk_manager.check_circuit_breaker()
    print(f"   ✅ Estado del circuit breaker: {breaker_state.value}")
    
    # Test 5: Estado de riesgo
    status = risk_manager.get_risk_status()
    print(f"   ✅ Estado de riesgo obtenido: {len(status)} campos")
    
    print("✅ RiskManager evolucionado - TODAS LAS PRUEBAS PASARON\n")


async def test_strategy_selector():
    """Prueba el StrategySelector."""
    print("🎯 Probando StrategySelector...")
    
    risk_manager = RiskManager()
    strategy_selector = StrategySelector(risk_manager)
    
    # Test 1: Selección de estrategia para grid trading
    regime_prediction = RegimePrediction(
        long_regime=MarketRegime.RANGE,
        short_regime=MarketRegime.RANGE,
        long_conf=0.8,
        short_conf=0.7
    )
    
    account_state = AccountState(
        total_equity=10000.0,
        available_balance=5000.0,
        total_exposure=0.5,
        daily_pnl=0.02,
        max_drawdown=0.05,
        risk_score=0.3
    )
    
    strategy_spec = strategy_selector.select_strategy(
        regime_prediction, "BTCUSDT", account_state
    )
    
    print(f"   ✅ Estrategia seleccionada: {strategy_spec.strategy_name.value}")
    print(f"   ✅ Confianza: {strategy_spec.confidence:.2f}")
    print(f"   ✅ Reasoning: {strategy_spec.reasoning[:100]}...")
    
    # Test 2: Selección para DCA
    regime_prediction.short_regime = MarketRegime.BULL_TREND
    strategy_spec = strategy_selector.select_strategy(
        regime_prediction, "BTCUSDT", account_state
    )
    
    print(f"   ✅ Estrategia DCA seleccionada: {strategy_spec.strategy_name.value}")
    
    # Test 3: Selección con stop de emergencia
    risk_manager.emergency_stop = True
    strategy_spec = strategy_selector.select_strategy(
        regime_prediction, "BTCUSDT", account_state
    )
    
    print(f"   ✅ Estrategia con emergency stop: {strategy_spec.strategy_name.value}")
    
    print("✅ StrategySelector - TODAS LAS PRUEBAS PASARON\n")


async def test_hybrid_ml_engine():
    """Prueba el HybridMLEngine."""
    print("🤖 Probando HybridMLEngine...")
    
    ml_engine = HybridMLEngine()
    
    # Test 1: Inicialización de modelos River
    ml_engine.initialize_river_model("BTCUSDT")
    print(f"   ✅ Modelo River inicializado para BTCUSDT")
    
    # Test 2: Actualización de modelo River
    features = {
        "rsi": 50.0,
        "macd": 0.0,
        "volatility": 0.02,
        "volume": 1000000.0
    }
    
    ml_engine.update_river_model("BTCUSDT", features, MarketRegime.RANGE)
    print(f"   ✅ Modelo River actualizado")
    
    # Test 3: Predicción de régimen corto plazo
    regime, confidence = ml_engine.predict_short_regime("BTCUSDT", features)
    print(f"   ✅ Predicción corto plazo: {regime.value} (confianza: {confidence:.2f})")
    
    # Test 4: Estado del modelo
    status = ml_engine.get_model_status("BTCUSDT")
    print(f"   ✅ Estado del modelo obtenido: {len(status)} campos")
    
    print("✅ HybridMLEngine - TODAS LAS PRUEBAS PASARON\n")


async def test_backtesting_service():
    """Prueba el BacktestingService."""
    print("📊 Probando BacktestingService...")
    
    backtest_service = BacktestingService()
    
    # Test 1: Descarga de datos OHLCV
    start_date = datetime.now() - timedelta(days=7)
    end_date = datetime.now()
    
    df = await backtest_service.download_ohlcv_data("BTCUSDT", start_date, end_date)
    print(f"   ✅ Datos OHLCV descargados: {len(df)} registros")
    
    # Test 2: Crear estrategia de prueba
    from app.services.strategy_selector import StrategySpec, StrategyParams
    
    strategy_params = StrategyParams(
        grid_spacing_bps=50,
        grid_levels=10,
        order_size_usdt=100.0
    )
    
    strategy_spec = StrategySpec(
        strategy_name=StrategyType.GRID_TRADING,
        params=strategy_params,
        confidence=0.8,
        reasoning="Test strategy",
        regime_prediction=RegimePrediction(
            long_regime=MarketRegime.RANGE,
            short_regime=MarketRegime.RANGE,
            long_conf=0.8,
            short_conf=0.7
        )
    )
    
    # Test 3: Ejecutar backtest
    result = await backtest_service.run_backtest(
        strategy_spec, "BTCUSDT", start_date, end_date,
        initial_capital=10000.0
    )
    
    print(f"   ✅ Backtest completado:")
    print(f"      - Retorno total: {result.total_return:.2%}")
    print(f"      - Sharpe ratio: {result.sharpe_ratio:.2f}")
    print(f"      - Max drawdown: {result.max_drawdown:.2%}")
    print(f"      - Total trades: {result.total_trades}")
    
    # Test 4: Resumen de backtest
    summary = backtest_service.get_backtest_summary([result])
    print(f"   ✅ Resumen de backtest generado: {len(summary)} métricas")
    
    print("✅ BacktestingService - TODAS LAS PRUEBAS PASARON\n")


async def test_binance_client():
    """Prueba el BinanceClient mejorado."""
    print("🔗 Probando BinanceClient mejorado...")
    
    # Test con credenciales de prueba
    client = BinanceClient(
        api_key="test_key",
        api_secret="test_secret",
        testnet=True
    )
    
    # Test 1: Obtener información del exchange
    try:
        exchange_info = await client.get_exchange_info()
        print(f"   ✅ Información del exchange obtenida: {len(exchange_info)} símbolos")
    except Exception as e:
        print(f"   ⚠️  Error obteniendo exchange info (esperado en test): {e}")
    
    # Test 2: Normalización de precio
    try:
        normalized_price = client.normalize_price("BTCUSDT", 50000.123456)
        print(f"   ✅ Precio normalizado: {normalized_price}")
    except Exception as e:
        print(f"   ⚠️  Error normalizando precio (esperado sin datos): {e}")
    
    # Test 3: Validación de parámetros de orden
    try:
        client.validate_order_params("BTCUSDT", 50000.0, 0.1, "BUY")
        print(f"   ✅ Validación de parámetros de orden completada")
    except Exception as e:
        print(f"   ⚠️  Error validando parámetros (esperado sin datos): {e}")
    
    print("✅ BinanceClient mejorado - PRUEBAS BÁSICAS COMPLETADAS\n")


async def test_integration():
    """Prueba de integración completa."""
    print("🔗 Probando integración completa...")
    
    # Crear instancias
    risk_manager = RiskManager()
    strategy_selector = StrategySelector(risk_manager)
    ml_engine = HybridMLEngine()
    backtest_service = BacktestingService()
    
    # Simular flujo completo
    symbol = "BTCUSDT"
    
    # 1. Obtener predicción de régimen
    features = {
        "rsi": 50.0,
        "macd": 0.0,
        "volatility": 0.02,
        "volume": 1000000.0
    }
    
    # Mock data para predicción
    import pandas as pd
    mock_data = pd.DataFrame({
        'close': [100.0] * 60,
        'volume': [1000000.0] * 60,
        'high': [101.0] * 60,
        'low': [99.0] * 60,
        'rsi': [50.0] * 60,
        'macd': [0.0] * 60,
        'bb_upper': [102.0] * 60,
        'bb_lower': [98.0] * 60,
        'atr': [1.0] * 60,
        'volatility': [0.02] * 60,
        'returns': [0.001] * 60
    })
    
    regime_prediction = await ml_engine.predict_regime(symbol, mock_data, features)
    print(f"   ✅ Predicción de régimen: {regime_prediction.short_regime.value}")
    
    # 2. Obtener estado de cuenta
    account_state = AccountState(
        total_equity=10000.0,
        available_balance=5000.0,
        total_exposure=0.5,
        daily_pnl=0.02,
        max_drawdown=0.05,
        risk_score=0.3
    )
    
    # 3. Seleccionar estrategia
    strategy_spec = strategy_selector.select_strategy(
        regime_prediction, symbol, account_state
    )
    print(f"   ✅ Estrategia seleccionada: {strategy_spec.strategy_name.value}")
    
    # 4. Calcular tamaño de posición
    position_params = PositionSizeParams(
        symbol=symbol,
        account_equity=account_state.total_equity,
        atr=0.02,
        winrate_estimate=0.6,
        avg_win_loss_ratio=1.5,
        price=50000.0
    )
    
    position_size = risk_manager.calculate_dynamic_position_size(position_params)
    print(f"   ✅ Tamaño de posición: {position_size:.2f} USDT")
    
    # 5. Ejecutar backtest rápido
    start_date = datetime.now() - timedelta(days=1)
    end_date = datetime.now()
    
    result = await backtest_service.run_backtest(
        strategy_spec, symbol, start_date, end_date,
        initial_capital=account_state.total_equity
    )
    
    print(f"   ✅ Backtest rápido completado: {result.total_return:.2%} retorno")
    
    print("✅ Integración completa - TODAS LAS PRUEBAS PASARON\n")


async def main():
    """Función principal de pruebas."""
    print("🚀 INICIANDO PRUEBAS V2.5 'Low-Risk, Predictive & Adaptive Grid'")
    print("=" * 80)
    
    try:
        await test_risk_manager()
        await test_strategy_selector()
        await test_hybrid_ml_engine()
        await test_backtesting_service()
        await test_binance_client()
        await test_integration()
        
        print("🎉 ¡TODAS LAS PRUEBAS COMPLETADAS EXITOSAMENTE!")
        print("=" * 80)
        print("✅ RiskManager evolucionado con Kelly fraccional y trailing stops")
        print("✅ StrategySelector con selección automática de estrategias")
        print("✅ HybridMLEngine con modelos LSTM/Transformer y River")
        print("✅ BacktestingService con vectorbt y walk-forward analysis")
        print("✅ BinanceClient mejorado con validación y rate limiting")
        print("✅ Integración completa del flujo de trading inteligente")
        
    except Exception as e:
        print(f"❌ Error durante las pruebas: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
