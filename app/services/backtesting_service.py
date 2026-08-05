"""
BacktestingService para V2.5 "Low-Risk, Predictive & Adaptive Grid".
Usa vectorbt para simulación de estrategias con walk-forward analysis.
"""

import logging
import os
import json
from decimal import Decimal
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, timezone

# Configurar numba antes de importar vectorbt
os.environ["NUMBA_DISABLE_CACHE"] = "1"
os.environ["NUMBA_CACHE_DIR"] = "/dev/null"

try:
    import vectorbt as vbt

    print("✅ VectorBT importado correctamente")
except Exception as e:
    print(f"❌ Error importando VectorBT: {e}")

    # Crear un mock de vectorbt para evitar errores
    class MockVectorBT:
        class Portfolio:
            pass

        class PortfolioStats:
            pass

    vbt = MockVectorBT()

from pydantic import BaseModel, Field, field_validator
from prometheus_client import Counter, Histogram, Gauge

from app.services.strategy_selector import StrategySpec, StrategyType
from app.services.transaction_cost_model import (
    apply_two_sigma_execution_stress,
    build_reference_transaction_cost_audit,
    compute_execution_cost_sigma_proxies_from_ohlcv_arrays,
    vectorbt_fees_and_slippage_from_backtest_fractions,
)

# Métricas Prometheus
BACKTEST_RUNS_TOTAL = Counter(
    "backtest_runs_total", "Total backtest runs", ["symbol", "strategy"]
)

BACKTEST_DURATION = Histogram(
    "backtest_duration_seconds", "Backtest execution duration", ["symbol", "strategy"]
)

BACKTEST_METRICS = Gauge(
    "backtest_metrics", "Backtest performance metrics", ["symbol", "strategy", "metric"]
)


class BacktestConfig(BaseModel):
    """Configuración para backtesting"""

    initial_capital: float = Field(default=10000.0, description="Capital inicial")
    commission: float = Field(default=0.001, description="Comisión maker/taker")
    slippage: float = Field(default=0.0005, description="Slippage model")
    spread_bps: float = Field(
        default=0.0,
        ge=0.0,
        description="Spread modelado (bps); se suma al slippage de vectorbt",
    )
    backtest_order_type: str = Field(
        default="MARKET",
        description="MARKET o LIMIT para auditoría de comisión en metrics_json",
    )
    cost_model_reference_notional_usdt: float = Field(
        default=1000.0,
        gt=0.0,
        description="Notional quote (USDT) de referencia para transaction_cost_audit",
    )
    walk_forward: bool = Field(default=True, description="Usar walk-forward analysis")
    window_size: int = Field(default=252, description="Tamaño de ventana (días)")
    step_size: int = Field(default=63, description="Paso de ventana (días)")
    min_samples: int = Field(
        default=100, description="Mínimo de muestras para entrenar"
    )
    cost_stress_two_sigma: bool = Field(
        default=False,
        description=(
            "Si True, spread_bps y slippage efectivos = baseline + 2σ de proxies OHLCV "
            "(§5.2 protocolo Passive Income)."
        ),
    )
    persist_run_to_db: bool = Field(
        default=False,
        description=(
            "Si True, al completar run_backtest persiste en backtest_runs/backtest_metrics "
            "(requiere migración Alembic aplicada)."
        ),
    )

    @field_validator("backtest_order_type", mode="before")
    @classmethod
    def _normalize_order_type(cls, value: str) -> str:
        u = str(value).upper()
        if u not in ("MARKET", "LIMIT"):
            raise ValueError("backtest_order_type debe ser MARKET o LIMIT")
        return u


def resolve_backtest_simulation_config(
    config: BacktestConfig,
    df: pd.DataFrame,
) -> tuple[BacktestConfig, dict[str, Any]]:
    """
    Configuración usada en vectorbt y en transaction_cost_audit.

    Con ``cost_stress_two_sigma`` aplica +2σ sobre spread y slippage respecto a
    desviaciones empíricas de las barras del propio ``df``.
    """
    if not config.cost_stress_two_sigma:
        return config, {}

    sigma_sp, sigma_sl = compute_execution_cost_sigma_proxies_from_ohlcv_arrays(
        df["high"].to_numpy(dtype=float, copy=False),
        df["low"].to_numpy(dtype=float, copy=False),
        df["close"].to_numpy(dtype=float, copy=False),
        df["open"].to_numpy(dtype=float, copy=False),
    )
    eff_spread_bps, eff_slippage = apply_two_sigma_execution_stress(
        spread_bps=config.spread_bps,
        slippage_fraction=config.slippage,
        sigma_spread_bps=sigma_sp,
        sigma_slippage_fraction=sigma_sl,
    )
    stressed = config.model_copy(
        update={"spread_bps": eff_spread_bps, "slippage": eff_slippage}
    )
    meta: dict[str, Any] = {
        "cost_stress_two_sigma": True,
        "cost_stress_sigma_spread_bps": sigma_sp,
        "cost_stress_sigma_slippage_fraction": sigma_sl,
        "backtest_spread_bps_baseline": float(config.spread_bps),
        "backtest_slippage_baseline": float(config.slippage),
        "backtest_spread_bps_effective": float(eff_spread_bps),
        "backtest_slippage_effective": float(eff_slippage),
    }
    return stressed, meta


class BacktestResult(BaseModel):
    """Resultado de backtesting"""

    symbol: str
    strategy_hash: str
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_capital: float
    total_return: float
    max_drawdown: float
    sharpe_ratio: float
    sortino_ratio: float
    win_rate: float
    profit_factor: float
    total_trades: int
    avg_trade_duration: float
    metrics_json: Dict[str, Any]
    backtest_ts: datetime = Field(default_factory=datetime.now)


class BacktestingService:
    """
    Servicio de backtesting usando vectorbt con walk-forward analysis.
    """

    def __init__(self, results_dir: str = "backtest_results"):
        self.results_dir = results_dir
        os.makedirs(results_dir, exist_ok=True)

        # Configuración por defecto
        self.default_config = BacktestConfig()

        # Cache de datos históricos
        self.historical_data: Dict[str, pd.DataFrame] = {}

        # Resultados de backtesting
        self.backtest_results: List[BacktestResult] = []

        self.logger = logging.getLogger(__name__)

    def _vectorbt_fees_slippage(self, config: BacktestConfig) -> tuple[float, float]:
        return vectorbt_fees_and_slippage_from_backtest_fractions(
            config.commission,
            config.slippage,
            config.spread_bps,
        )

    def _persist_backtest_run_to_db(
        self,
        *,
        baseline_config: BacktestConfig,
        sim_config: BacktestConfig,
        result: BacktestResult,
        cost_stress_meta: dict[str, Any],
        started_at: datetime,
    ) -> None:
        from app.core.metrics import gridbot_backtest_run_persist_total

        try:
            from app.db.session import SessionLocal
            from app.services.backtest_persistence import persist_completed_backtest_run

            db = SessionLocal()
            try:
                persist_completed_backtest_run(
                    db,
                    name=None,
                    baseline_config=baseline_config,
                    sim_config=sim_config,
                    result=result,
                    cost_stress_meta=cost_stress_meta,
                    started_at=started_at,
                    finished_at=datetime.now(timezone.utc),
                )
                db.commit()
                gridbot_backtest_run_persist_total.labels(outcome="success").inc()
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()
        except Exception as exc:
            gridbot_backtest_run_persist_total.labels(outcome="failure").inc()
            self.logger.warning("persist_run_to_db failed: %s", exc)

    async def download_ohlcv_data(
        self, symbol: str, start_date: datetime, end_date: datetime
    ) -> pd.DataFrame:
        """
        Descarga datos OHLCV usando CCXT/Binance.

        Args:
            symbol: Símbolo del trading pair
            start_date: Fecha de inicio
            end_date: Fecha de fin

        Returns:
            DataFrame con datos OHLCV
        """
        try:
            # TODO: Implementar descarga real usando CCXT
            # Por ahora, generar datos sintéticos para testing

            date_range = pd.date_range(start=start_date, end=end_date, freq="1H")
            n_periods = len(date_range)

            # Generar datos sintéticos con tendencia y volatilidad
            np.random.seed(42)  # Para reproducibilidad

            # Precio base
            base_price = 100.0

            # Retornos con tendencia
            returns = np.random.normal(
                0.0001, 0.02, n_periods
            )  # 0.01% tendencia, 2% volatilidad

            # Agregar tendencias
            trend = np.linspace(0, 0.1, n_periods)  # Tendencia alcista
            returns += trend / n_periods

            # Calcular precios
            prices = base_price * np.exp(np.cumsum(returns))

            # Crear DataFrame OHLCV
            df = pd.DataFrame(
                {
                    "timestamp": date_range,
                    "open": prices * (1 + np.random.normal(0, 0.001, n_periods)),
                    "high": prices
                    * (1 + np.abs(np.random.normal(0, 0.005, n_periods))),
                    "low": prices * (1 - np.abs(np.random.normal(0, 0.005, n_periods))),
                    "close": prices,
                    "volume": np.random.lognormal(10, 1, n_periods),
                }
            )

            # Asegurar que high >= low
            df["high"] = np.maximum(df["high"], df["low"])
            df["high"] = np.maximum(df["high"], df["close"])
            df["low"] = np.minimum(df["low"], df["close"])

            # Agregar características técnicas
            df = self._add_technical_features(df)

            self.historical_data[symbol] = df
            self.logger.info(f"Downloaded {len(df)} OHLCV records for {symbol}")

            return df

        except Exception as e:
            self.logger.error(f"Error downloading OHLCV data for {symbol}: {e}")
            raise

    def _add_technical_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Agrega características técnicas al DataFrame."""
        # RSI
        df["rsi"] = vbt.RSI.run(df["close"]).rsi

        # MACD
        macd = vbt.MACD.run(df["close"])
        df["macd"] = macd.macd
        df["macd_signal"] = macd.signal

        # Bollinger Bands
        bb = vbt.BBANDS.run(df["close"])
        df["bb_upper"] = bb.upper
        df["bb_lower"] = bb.lower
        df["bb_middle"] = bb.middle

        # ATR
        df["atr"] = vbt.ATR.run(df["high"], df["low"], df["close"]).atr

        # Volatilidad
        df["volatility"] = df["close"].pct_change().rolling(20).std()

        # Retornos
        df["returns"] = df["close"].pct_change()

        return df

    def _simulate_grid_trading(
        self, df: pd.DataFrame, strategy_spec: StrategySpec, config: BacktestConfig
    ) -> vbt.Portfolio:
        """
        Simula estrategia de grid trading.

        Args:
            df: DataFrame con datos OHLCV
            strategy_spec: Especificación de estrategia
            config: Configuración de backtesting

        Returns:
            Portfolio de vectorbt
        """
        params = strategy_spec.params

        # Parámetros del grid
        grid_spacing = params.grid_spacing_bps / 10000  # Convertir bps a decimal
        grid_levels = params.grid_levels or 10
        order_size = params.order_size_usdt or 100.0

        # Calcular niveles del grid
        base_price = df["close"].iloc[0]
        grid_prices = []

        for i in range(-grid_levels // 2, grid_levels // 2 + 1):
            price = base_price * (1 + i * grid_spacing)
            grid_prices.append(price)

        grid_prices = sorted(grid_prices)

        # Crear señales de compra/venta
        buy_signals = pd.DataFrame(index=df.index, columns=grid_prices)
        sell_signals = pd.DataFrame(index=df.index, columns=grid_prices)

        for i, price in enumerate(grid_prices):
            # Señales de compra cuando el precio toca el nivel
            buy_signals[price] = (df["low"] <= price) & (df["low"].shift(1) > price)

            # Señales de venta cuando el precio sube
            sell_signals[price] = (df["high"] >= price * (1 + grid_spacing)) & (
                df["high"].shift(1) < price * (1 + grid_spacing)
            )

        vt_fees, vt_slippage = self._vectorbt_fees_slippage(config)

        # Crear portfolio
        portfolio = vbt.Portfolio.from_signals(
            close=df["close"],
            entries=buy_signals,
            exits=sell_signals,
            size=order_size / df["close"],  # Tamaño en unidades
            fees=vt_fees,
            slippage=vt_slippage,
            init_cash=config.initial_capital,
            freq="1H",
        )

        return portfolio

    def _simulate_dca_strategy(
        self, df: pd.DataFrame, strategy_spec: StrategySpec, config: BacktestConfig
    ) -> vbt.Portfolio:
        """
        Simula estrategia DCA (Dollar Cost Averaging).

        Args:
            df: DataFrame con datos OHLCV
            strategy_spec: Especificación de estrategia
            config: Configuración de backtesting

        Returns:
            Portfolio de vectorbt
        """
        params = strategy_spec.params

        # Parámetros DCA
        tranche_size = params.tranche_size or 100.0
        interval = params.interval or 3600  # 1 hora en segundos
        take_profit = params.take_profit or 0.05

        # Crear señales de entrada cada intervalo
        entry_signals = pd.Series(False, index=df.index)
        entry_signals.iloc[::interval] = True  # Cada intervalo

        # Crear señales de salida basadas en take profit
        exit_signals = pd.Series(False, index=df.index)

        # Calcular take profit levels
        entry_prices = df["close"].where(entry_signals)
        take_profit_prices = entry_prices * (1 + take_profit)

        # Señales de salida cuando se alcanza take profit
        for i in range(1, len(df)):
            if entry_signals.iloc[i - 1]:
                entry_price = df["close"].iloc[i - 1]
                tp_price = entry_price * (1 + take_profit)

                # Buscar cuando se alcanza take profit
                for j in range(i, len(df)):
                    if df["high"].iloc[j] >= tp_price:
                        exit_signals.iloc[j] = True
                        break

        vt_fees, vt_slippage = self._vectorbt_fees_slippage(config)

        # Crear portfolio
        portfolio = vbt.Portfolio.from_signals(
            close=df["close"],
            entries=entry_signals,
            exits=exit_signals,
            size=tranche_size / df["close"],
            fees=vt_fees,
            slippage=vt_slippage,
            init_cash=config.initial_capital,
            freq="1H",
        )

        return portfolio

    def _simulate_scalping_strategy(
        self, df: pd.DataFrame, strategy_spec: StrategySpec, config: BacktestConfig
    ) -> vbt.Portfolio:
        """
        Simula estrategia de scalping.

        Args:
            df: DataFrame con datos OHLCV
            strategy_spec: Especificación de estrategia
            config: Configuración de backtesting

        Returns:
            Portfolio de vectorbt
        """
        params = strategy_spec.params

        # Parámetros de scalping
        order_size = params.order_size_usdt or 50.0
        take_profit = params.take_profit or 0.02
        stop_loss = params.stop_loss or 0.01

        # Señales basadas en RSI y MACD
        rsi = df["rsi"]
        macd = df["macd"]
        macd_signal = df["macd_signal"]

        # Entradas: RSI oversold + MACD crossover
        entry_signals = (
            (rsi < 30) & (macd > macd_signal) & (macd.shift(1) <= macd_signal.shift(1))
        )

        # Salidas: take profit o stop loss
        exit_signals = pd.Series(False, index=df.index)

        for i in range(len(df)):
            if entry_signals.iloc[i]:
                entry_price = df["close"].iloc[i]
                tp_price = entry_price * (1 + take_profit)
                sl_price = entry_price * (1 - stop_loss)

                # Buscar salida
                for j in range(i + 1, len(df)):
                    if df["high"].iloc[j] >= tp_price or df["low"].iloc[j] <= sl_price:
                        exit_signals.iloc[j] = True
                        break

        vt_fees, vt_slippage = self._vectorbt_fees_slippage(config)

        # Crear portfolio
        portfolio = vbt.Portfolio.from_signals(
            close=df["close"],
            entries=entry_signals,
            exits=exit_signals,
            size=order_size / df["close"],
            fees=vt_fees,
            slippage=vt_slippage,
            init_cash=config.initial_capital,
            freq="1H",
        )

        return portfolio

    async def run_backtest(
        self,
        strategy_spec: StrategySpec,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        initial_capital: Optional[float] = None,
        config: Optional[BacktestConfig] = None,
    ) -> BacktestResult:
        """
        Ejecuta backtesting de una estrategia.

        Args:
            strategy_spec: Especificación de estrategia
            symbol: Símbolo del trading pair
            start_date: Fecha de inicio
            end_date: Fecha de fin
            initial_capital: Capital inicial
            config: Configuración de backtesting

        Returns:
            Resultado del backtesting
        """
        if config is None:
            config = self.default_config

        if initial_capital is not None:
            config.initial_capital = initial_capital

        start_time = datetime.now(timezone.utc)

        try:
            self.logger.info(
                f"Running backtest for {symbol} with {strategy_spec.strategy_name.value}"
            )

            # Descargar datos
            df = await self.download_ohlcv_data(symbol, start_date, end_date)

            if len(df) < config.min_samples:
                raise ValueError(
                    f"Insufficient data: {len(df)} samples < {config.min_samples}"
                )

            sim_config, cost_stress_meta = resolve_backtest_simulation_config(
                config, df
            )

            # Seleccionar estrategia de simulación
            if strategy_spec.strategy_name == StrategyType.GRID_TRADING:
                portfolio = self._simulate_grid_trading(df, strategy_spec, sim_config)
            elif strategy_spec.strategy_name == StrategyType.DCA:
                portfolio = self._simulate_dca_strategy(df, strategy_spec, sim_config)
            elif strategy_spec.strategy_name == StrategyType.SCALPING:
                portfolio = self._simulate_scalping_strategy(
                    df, strategy_spec, sim_config
                )
            else:
                # HOLD strategy - no trading
                portfolio = vbt.Portfolio.from_holding(
                    close=df["close"], init_cash=sim_config.initial_capital, freq="1H"
                )

            # Calcular métricas
            total_return = portfolio.total_return()
            max_drawdown = portfolio.max_drawdown()
            sharpe_ratio = portfolio.sharpe_ratio()
            sortino_ratio = portfolio.sortino_ratio()
            win_rate = portfolio.win_rate()
            profit_factor = portfolio.profit_factor()
            total_trades = portfolio.count()

            # Calcular duración promedio de trades
            trade_durations = portfolio.trades.duration
            avg_trade_duration = (
                trade_durations.mean().total_seconds() / 3600
            )  # En horas

            # Capital final
            final_capital = portfolio.value.iloc[-1]

            vt_fees, vt_slippage = self._vectorbt_fees_slippage(sim_config)
            ref_n = Decimal(str(sim_config.cost_model_reference_notional_usdt))
            cost_audit = build_reference_transaction_cost_audit(
                ref_n,
                sim_config.commission,
                sim_config.slippage,
                sim_config.spread_bps,
                sim_config.backtest_order_type,
            )

            metrics_body: dict[str, Any] = {
                "total_return": float(total_return),
                "max_drawdown": float(max_drawdown),
                "sharpe_ratio": float(sharpe_ratio),
                "sortino_ratio": float(sortino_ratio),
                "win_rate": float(win_rate),
                "profit_factor": float(profit_factor),
                "total_trades": int(total_trades),
                "avg_trade_duration": float(avg_trade_duration),
                "final_capital": float(final_capital),
                "backtest_spread_bps": float(sim_config.spread_bps),
                "backtest_slippage": float(sim_config.slippage),
                "backtest_order_type": sim_config.backtest_order_type,
                "vectorbt_fees": vt_fees,
                "vectorbt_slippage": vt_slippage,
                "cost_model_reference_notional_quote": str(ref_n),
                "transaction_cost_audit": cost_audit.to_serializable_dict(),
            }
            metrics_body.update(cost_stress_meta)
            result = BacktestResult(
                symbol=symbol,
                strategy_hash=strategy_spec.strategy_name.value,
                start_date=start_date,
                end_date=end_date,
                initial_capital=sim_config.initial_capital,
                final_capital=final_capital,
                total_return=total_return,
                max_drawdown=max_drawdown,
                sharpe_ratio=sharpe_ratio,
                sortino_ratio=sortino_ratio,
                win_rate=win_rate,
                profit_factor=profit_factor,
                total_trades=total_trades,
                avg_trade_duration=avg_trade_duration,
                metrics_json=metrics_body,
            )

            if config.persist_run_to_db:
                self._persist_backtest_run_to_db(
                    baseline_config=config,
                    sim_config=sim_config,
                    result=result,
                    cost_stress_meta=cost_stress_meta,
                    started_at=start_time,
                )

            # Guardar resultado
            self.backtest_results.append(result)

            # Actualizar métricas Prometheus
            BACKTEST_RUNS_TOTAL.labels(
                symbol=symbol, strategy=strategy_spec.strategy_name.value
            ).inc()

            duration = (datetime.now() - start_time).total_seconds()
            BACKTEST_DURATION.labels(
                symbol=symbol, strategy=strategy_spec.strategy_name.value
            ).observe(duration)

            # Métricas individuales
            BACKTEST_METRICS.labels(
                symbol=symbol,
                strategy=strategy_spec.strategy_name.value,
                metric="total_return",
            ).set(total_return)
            BACKTEST_METRICS.labels(
                symbol=symbol,
                strategy=strategy_spec.strategy_name.value,
                metric="sharpe_ratio",
            ).set(sharpe_ratio)
            BACKTEST_METRICS.labels(
                symbol=symbol,
                strategy=strategy_spec.strategy_name.value,
                metric="max_drawdown",
            ).set(max_drawdown)

            self.logger.info(
                f"Backtest completed for {symbol}: "
                f"Return={total_return:.2%}, Sharpe={sharpe_ratio:.2f}, "
                f"MaxDD={max_drawdown:.2%}, Trades={total_trades}"
            )

            return result

        except Exception as e:
            self.logger.error(f"Error running backtest for {symbol}: {e}")
            raise

    async def run_walk_forward_backtest(
        self,
        strategy_spec: StrategySpec,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        config: Optional[BacktestConfig] = None,
    ) -> List[BacktestResult]:
        """
        Ejecuta backtesting walk-forward.

        Args:
            strategy_spec: Especificación de estrategia
            symbol: Símbolo del trading pair
            start_date: Fecha de inicio
            end_date: Fecha de fin
            config: Configuración de backtesting

        Returns:
            Lista de resultados de backtesting
        """
        if config is None:
            config = self.default_config

        if not config.walk_forward:
            # Ejecutar backtest simple
            result = await self.run_backtest(
                strategy_spec, symbol, start_date, end_date, config=config
            )
            return [result]

        results = []
        current_start = start_date

        while current_start + timedelta(days=config.window_size) <= end_date:
            current_end = current_start + timedelta(days=config.window_size)

            try:
                result = await self.run_backtest(
                    strategy_spec, symbol, current_start, current_end, config=config
                )
                results.append(result)

                self.logger.info(
                    f"Walk-forward window {current_start.date()} - {current_end.date()}: "
                    f"Return={result.total_return:.2%}, Sharpe={result.sharpe_ratio:.2f}"
                )

            except Exception as e:
                self.logger.error(
                    f"Error in walk-forward window {current_start.date()} - {current_end.date()}: {e}"
                )

            # Mover ventana
            current_start += timedelta(days=config.step_size)

        return results

    def save_backtest_results(
        self, results: List[BacktestResult], filename: Optional[str] = None
    ) -> str:
        """
        Guarda resultados de backtesting en archivo.

        Args:
            results: Lista de resultados
            filename: Nombre del archivo (opcional)

        Returns:
            Ruta del archivo guardado
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"backtest_results_{timestamp}.json"

        filepath = os.path.join(self.results_dir, filename)

        # Convertir a JSON
        results_data = [result.dict() for result in results]

        with open(filepath, "w") as f:
            json.dump(results_data, f, indent=2, default=str)

        self.logger.info(f"Backtest results saved to {filepath}")
        return filepath

    def load_backtest_results(self, filepath: str) -> List[BacktestResult]:
        """
        Carga resultados de backtesting desde archivo.

        Args:
            filepath: Ruta del archivo

        Returns:
            Lista de resultados
        """
        with open(filepath, "r") as f:
            data = json.load(f)

        results = [BacktestResult(**item) for item in data]
        self.logger.info(f"Loaded {len(results)} backtest results from {filepath}")

        return results

    def get_backtest_summary(self, results: List[BacktestResult]) -> Dict[str, Any]:
        """
        Genera resumen de resultados de backtesting.

        Args:
            results: Lista de resultados

        Returns:
            Resumen de métricas
        """
        if not results:
            return {}

        # Calcular estadísticas agregadas
        total_returns = [r.total_return for r in results]
        sharpe_ratios = [r.sharpe_ratio for r in results]
        max_drawdowns = [r.max_drawdown for r in results]
        win_rates = [r.win_rate for r in results]

        summary = {
            "total_backtests": len(results),
            "avg_total_return": np.mean(total_returns),
            "std_total_return": np.std(total_returns),
            "avg_sharpe_ratio": np.mean(sharpe_ratios),
            "avg_max_drawdown": np.mean(max_drawdowns),
            "avg_win_rate": np.mean(win_rates),
            "best_return": max(total_returns),
            "worst_return": min(total_returns),
            "best_sharpe": max(sharpe_ratios),
            "worst_drawdown": min(max_drawdowns),
        }

        return summary
