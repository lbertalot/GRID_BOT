#!/usr/bin/env python3
"""
Rutas API para Gestión de Estrategias de Trading
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel
import pandas as pd

from app.core.risk_manager import RiskManager, MarketRegime, RegimePrediction
from app.services.hybrid_ml_engine import HybridMLEngine
from app.services.strategy_selector import StrategySelector, StrategySpec, AccountState
from app.services.backtesting_service import BacktestingService, BacktestConfig

router = APIRouter(prefix="/api/v2/strategies", tags=["strategies"])


# Dependencias
def get_risk_manager() -> RiskManager:
    """Obtiene instancia del RiskManager."""
    return RiskManager()


def get_ml_engine() -> HybridMLEngine:
    """Obtiene instancia del HybridMLEngine."""
    return HybridMLEngine()


def get_strategy_selector(
    risk_manager: RiskManager = Depends(get_risk_manager),
) -> StrategySelector:
    """Obtiene instancia del StrategySelector."""
    return StrategySelector(risk_manager)


def get_backtesting_service() -> BacktestingService:
    """Obtiene instancia del BacktestingService."""
    return BacktestingService()


class ExecuteIntelligentRequest(BaseModel):
    """Request para ejecución inteligente de estrategia"""

    symbol: str
    account_state: AccountState
    paper_mode: bool = True
    quick_backtest: bool = True


class BacktestRequest(BaseModel):
    """Request para backtesting"""

    symbol: str
    strategy_spec: StrategySpec
    start_date: datetime
    end_date: datetime
    initial_capital: float = 10000.0
    walk_forward: bool = True
    commission: float = 0.001
    slippage: float = 0.0005
    persist_run_to_db: bool = False


@router.post("/execute_intelligent")
async def execute_intelligent_strategy(
    request: ExecuteIntelligentRequest,
    background_tasks: BackgroundTasks,
    risk_manager: RiskManager = Depends(get_risk_manager),
    ml_engine: HybridMLEngine = Depends(get_ml_engine),
    strategy_selector: StrategySelector = Depends(get_strategy_selector),
) -> Dict[str, Any]:
    """
    Ejecuta estrategia inteligente con predicción de régimen y selección automática.

    Steps:
    1. Check health & risk
    2. Predict regime
    3. Select strategy
    4. Simulate quick backtest check (shadow)
    5. Enqueue actual execution task in Celery
    """
    try:
        # Step 1: Check health & risk
        breaker_state = risk_manager.check_circuit_breaker()
        if breaker_state.value in ["danger", "stopped"]:
            return {
                "success": False,
                "message": f"Circuit breaker active: {breaker_state.value}",
                "data": {
                    "breaker_state": breaker_state.value,
                    "emergency_stop": risk_manager.emergency_stop,
                },
                "timestamp": datetime.now().isoformat(),
            }

        # Step 2: Predict regime (mock data for now)
        # TODO: Implementar predicción real con datos de mercado
        mock_features = {
            "rsi": 50.0,
            "macd": 0.0,
            "volatility": 0.02,
            "volume": 1000000.0,
        }

        # Mock recent data
        mock_data = pd.DataFrame(
            {
                "close": [100.0] * 60,
                "volume": [1000000.0] * 60,
                "high": [101.0] * 60,
                "low": [99.0] * 60,
                "rsi": [50.0] * 60,
                "macd": [0.0] * 60,
                "bb_upper": [102.0] * 60,
                "bb_lower": [98.0] * 60,
                "atr": [1.0] * 60,
                "volatility": [0.02] * 60,
                "returns": [0.001] * 60,
            }
        )

        regime_prediction = await ml_engine.predict_regime(
            request.symbol, mock_data, mock_features
        )

        # Step 3: Select strategy
        strategy_spec = strategy_selector.select_strategy(
            regime_prediction, request.symbol, request.account_state
        )

        # Step 4: Quick backtest check (shadow)
        if request.quick_backtest:
            backtest_service = get_backtesting_service()

            # Backtest rápido con datos recientes
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)  # Última semana

            try:
                backtest_result = await backtest_service.run_backtest(
                    strategy_spec,
                    request.symbol,
                    start_date,
                    end_date,
                    initial_capital=request.account_state.total_equity,
                )

                # Verificar si el backtest es aceptable
                if backtest_result.max_drawdown > 0.1:  # Más de 10% drawdown
                    return {
                        "success": False,
                        "message": "Backtest failed: excessive drawdown",
                        "data": {
                            "max_drawdown": backtest_result.max_drawdown,
                            "strategy": strategy_spec.strategy_name.value,
                        },
                        "timestamp": datetime.now().isoformat(),
                    }

                backtest_passed = True
                backtest_metrics = backtest_result.metrics_json

            except Exception as e:
                backtest_passed = False
                backtest_metrics = {"error": str(e)}
        else:
            backtest_passed = True
            backtest_metrics = {}

        # Step 5: Enqueue execution task (mock)
        if backtest_passed and not request.paper_mode:
            # TODO: Implementar enqueue real con Celery
            background_tasks.add_task(
                execute_strategy_task,
                request.symbol,
                strategy_spec,
                request.account_state,
            )
            execution_enqueued = True
        else:
            execution_enqueued = False

        return {
            "success": True,
            "message": "Intelligent strategy execution completed",
            "data": {
                "symbol": request.symbol,
                "regime_prediction": regime_prediction.dict(),
                "strategy_spec": strategy_spec.dict(),
                "breaker_state": breaker_state.value,
                "backtest_passed": backtest_passed,
                "backtest_metrics": backtest_metrics,
                "execution_enqueued": execution_enqueued,
                "paper_mode": request.paper_mode,
            },
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error executing intelligent strategy: {str(e)}"
        )


@router.get("/last_decision")
async def get_last_decision(
    symbol: str,
    ml_engine: HybridMLEngine = Depends(get_ml_engine),
    strategy_selector: StrategySelector = Depends(get_strategy_selector),
) -> Dict[str, Any]:
    """
    Obtiene la última decisión de estrategia para un símbolo.

    Returns:
        Última predicción de régimen + especificación de estrategia + reasoning
    """
    try:
        # Obtener última predicción
        if symbol in ml_engine.last_predictions:
            regime_prediction = ml_engine.last_predictions[symbol]
        else:
            # Mock prediction si no hay datos
            regime_prediction = RegimePrediction(
                long_regime=MarketRegime.RANGE,
                short_regime=MarketRegime.RANGE,
                long_conf=0.5,
                short_conf=0.5,
            )

        # Mock account state
        account_state = AccountState(
            total_equity=10000.0,
            available_balance=5000.0,
            total_exposure=0.5,
            daily_pnl=0.02,
            max_drawdown=0.05,
            risk_score=0.3,
        )

        # Obtener estrategia
        strategy_spec = strategy_selector.select_strategy(
            regime_prediction, symbol, account_state
        )

        return {
            "success": True,
            "data": {
                "symbol": symbol,
                "regime_prediction": regime_prediction.dict(),
                "strategy_spec": strategy_spec.dict(),
                "account_state": account_state.dict(),
                "features_used": {
                    "rsi": 50.0,
                    "macd": 0.0,
                    "volatility": 0.02,
                    "volume": 1000000.0,
                },
                "confidences": {
                    "long_regime": regime_prediction.long_conf,
                    "short_regime": regime_prediction.short_conf,
                    "strategy": strategy_spec.confidence,
                },
            },
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting last decision: {str(e)}"
        )


@router.post("/backtest/run")
async def run_backtest(
    request: BacktestRequest,
    backtest_service: BacktestingService = Depends(get_backtesting_service),
) -> Dict[str, Any]:
    """
    Ejecuta backtesting de una estrategia.

    Args:
        request: Parámetros del backtest

    Returns:
        Resultado del backtesting
    """
    try:
        # Configurar backtest
        config = BacktestConfig(
            initial_capital=request.initial_capital,
            commission=request.commission,
            slippage=request.slippage,
            walk_forward=request.walk_forward,
            persist_run_to_db=request.persist_run_to_db,
        )

        if request.walk_forward:
            results = await backtest_service.run_walk_forward_backtest(
                request.strategy_spec,
                request.symbol,
                request.start_date,
                request.end_date,
                config,
            )
        else:
            result = await backtest_service.run_backtest(
                request.strategy_spec,
                request.symbol,
                request.start_date,
                request.end_date,
                initial_capital=request.initial_capital,
                config=config,
            )
            results = [result]

        # Generar resumen
        summary = backtest_service.get_backtest_summary(results)

        return {
            "success": True,
            "data": {
                "symbol": request.symbol,
                "strategy": request.strategy_spec.strategy_name.value,
                "start_date": request.start_date.isoformat(),
                "end_date": request.end_date.isoformat(),
                "results_count": len(results),
                "summary": summary,
                "detailed_results": [result.dict() for result in results],
            },
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error running backtest: {str(e)}")


@router.get("/backtest/results")
async def get_backtest_results(
    symbol: Optional[str] = None,
    strategy: Optional[str] = None,
    limit: int = 10,
    backtest_service: BacktestingService = Depends(get_backtesting_service),
) -> Dict[str, Any]:
    """
    Obtiene resultados de backtesting.

    Args:
        symbol: Filtrar por símbolo
        strategy: Filtrar por estrategia
        limit: Número máximo de resultados

    Returns:
        Lista de resultados de backtesting
    """
    try:
        results = backtest_service.backtest_results

        # Filtrar resultados
        if symbol:
            results = [r for r in results if r.symbol == symbol]

        if strategy:
            results = [r for r in results if r.strategy_hash == strategy]

        # Limitar resultados
        results = results[-limit:] if limit > 0 else results

        return {
            "success": True,
            "data": {
                "results": [result.dict() for result in results],
                "total_count": len(results),
                "filters": {"symbol": symbol, "strategy": strategy, "limit": limit},
            },
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting backtest results: {str(e)}"
        )


@router.get("/ml/status")
async def get_ml_status(
    symbol: Optional[str] = None, ml_engine: HybridMLEngine = Depends(get_ml_engine)
) -> Dict[str, Any]:
    """
    Obtiene el estado de los modelos de ML.

    Args:
        symbol: Símbolo específico (opcional)

    Returns:
        Estado de los modelos de ML
    """
    try:
        if symbol:
            status = ml_engine.get_model_status(symbol)
        else:
            # Obtener estado de todos los símbolos
            status = {}
            for sym in ["BTCUSDT", "ETHUSDT", "ADAUSDT"]:  # Mock symbols
                status[sym] = ml_engine.get_model_status(sym)

        return {
            "success": True,
            "data": status,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting ML status: {str(e)}"
        )


@router.post("/ml/train")
async def train_ml_model(
    symbol: str,
    start_date: datetime,
    end_date: datetime,
    background_tasks: BackgroundTasks,
    ml_engine: HybridMLEngine = Depends(get_ml_engine),
    model_type: str = "LSTM",
) -> Dict[str, Any]:
    """
    Entrena modelo de ML para un símbolo.

    Args:
        symbol: Símbolo del trading pair
        start_date: Fecha de inicio de datos
        end_date: Fecha de fin de datos
        model_type: Tipo de modelo (LSTM/Transformer)

    Returns:
        Confirmación del entrenamiento
    """
    try:
        # Mock historical data
        import pandas as pd
        import numpy as np

        date_range = pd.date_range(start=start_date, end=end_date, freq="1H")
        n_periods = len(date_range)

        # Generar datos sintéticos
        np.random.seed(42)
        base_price = 100.0
        returns = np.random.normal(0.0001, 0.02, n_periods)
        prices = base_price * np.exp(np.cumsum(returns))

        df = pd.DataFrame(
            {
                "timestamp": date_range,
                "open": prices * (1 + np.random.normal(0, 0.001, n_periods)),
                "high": prices * (1 + np.abs(np.random.normal(0, 0.005, n_periods))),
                "low": prices * (1 - np.abs(np.random.normal(0, 0.005, n_periods))),
                "close": prices,
                "volume": np.random.lognormal(10, 1, n_periods),
                "rsi": np.random.uniform(20, 80, n_periods),
                "macd": np.random.normal(0, 0.1, n_periods),
                "bb_upper": prices * 1.02,
                "bb_lower": prices * 0.98,
                "atr": np.random.uniform(0.5, 2.0, n_periods),
                "volatility": np.random.uniform(0.01, 0.05, n_periods),
                "returns": returns,
            }
        )

        # Enqueue training task
        background_tasks.add_task(train_model_task, ml_engine, df, symbol, model_type)

        return {
            "success": True,
            "message": f"ML model training enqueued for {symbol}",
            "data": {
                "symbol": symbol,
                "model_type": model_type,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "data_points": len(df),
            },
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error training ML model: {str(e)}"
        )


# Background tasks
async def execute_strategy_task(
    symbol: str, strategy_spec: StrategySpec, account_state: AccountState
):
    """Background task para ejecutar estrategia."""
    # TODO: Implementar ejecución real de estrategia
    print(f"Executing strategy {strategy_spec.strategy_name.value} for {symbol}")


async def train_model_task(
    ml_engine: HybridMLEngine, df: pd.DataFrame, symbol: str, model_type: str
):
    """Background task para entrenar modelo."""
    try:
        from app.services.hybrid_ml_engine import DeepModelConfig

        config = DeepModelConfig(model_type=model_type)
        await ml_engine.train_deep_model(df, symbol, config=config)
        print(f"Model training completed for {symbol}")
    except Exception as e:
        print(f"Error training model for {symbol}: {e}")
