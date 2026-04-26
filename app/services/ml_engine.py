"""
Motor de aprendizaje continuo (online) usando River.

Objetivos:
- Clasificar régimen de mercado en tiempo real con entrenamiento incremental
- Extraer features a partir de klines: volatilidad, spread, volumen, RSI, ATR
- Guardar/cargar modelo periódicamente (joblib) y continuar entrenamiento
- Evitar bloqueos del loop: usar asyncio.to_thread para I/O pesado

Compatibilidad:
- Compatible con modo paper trading (solo lectura de datos)
- No rompe flujos actuales: módulo autocontenido
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from app.core.risk_manager import RegimePrediction as RiskRegimePrediction

try:
    from river import compose as rv_compose
    from river import preprocessing as rv_pre
    from river import linear_model as rv_linear
    from river import optim as rv_optim
    from river import metrics as rv_metrics
    from river.drift import ADWIN
except Exception:  # pragma: no cover - entorno sin river
    rv_compose = rv_pre = rv_linear = rv_optim = rv_metrics = ADWIN = None  # type: ignore

try:
    import joblib
except Exception:  # pragma: no cover
    joblib = None  # type: ignore

from app.services.market_data_collector import MarketDataCollector
from app.services.strategies.rsi_macd import rsi as rsi_np


logger = logging.getLogger(__name__)


@dataclass
class RegimePrediction:
    label: int
    proba: float


class MLEngine:
    """
    Motor de ML incremental para detección/adaptación de régimen.

    - Modelo: LogisticRegression online con estandarización (River)
    - Detector de cambio: ADWIN para disparar resets parciales
    """

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or os.getenv(
            "ML_MODEL_PATH", "data/ml/regime_model.joblib"
        )
        self.metric = None
        self.drift_detector = ADWIN() if ADWIN else None
        self.pipeline = None
        self._init_or_load_model()
        self.collector = MarketDataCollector()

    def _init_or_load_model(self) -> None:
        if joblib and Path(self.model_path).exists():
            try:
                self.pipeline = joblib.load(self.model_path)
                logger.info(f"Modelo ML cargado desde {self.model_path}")
                return
            except Exception as e:
                logger.warning(f"No se pudo cargar modelo, se inicializa nuevo: {e}")

        # Inicializar pipeline básica si River está disponible
        if rv_linear is None:
            self.pipeline = None
            logger.warning("River no disponible; MLEngine en modo no operativo")
            return

        optimizer = rv_optim.SGD(0.05)
        model = rv_linear.LogisticRegression(optimizer=optimizer)
        self.pipeline = rv_pre.StandardScaler() | model
        self.metric = rv_metrics.LogLoss()

    async def save_model(self) -> None:
        if not joblib or self.pipeline is None:
            return
        model_dir = Path(self.model_path).parent
        model_dir.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(joblib.dump, self.pipeline, self.model_path)

    async def compute_features_from_klines(
        self, klines: List[List[Any]]
    ) -> Dict[str, float]:
        """Extrae features a partir de klines: volatilidad, spread, volumen, RSI, ATR."""
        if not klines:
            return {
                "volatility": 0.0,
                "spread": 0.0,
                "volume": 0.0,
                "rsi": 50.0,
                "atr": 0.0,
            }

        closes = [float(k[4]) for k in klines]
        highs = [float(k[2]) for k in klines]
        lows = [float(k[3]) for k in klines]
        volumes = [float(k[5]) for k in klines]

        # Volatilidad: desviación estándar de cambios porcentuales
        returns = []
        for i in range(1, len(closes)):
            prev = closes[i - 1]
            cur = closes[i]
            if prev > 0:
                returns.append((cur - prev) / prev)
        volatility = (
            float(
                (
                    sum((x - (sum(returns) / len(returns))) ** 2 for x in returns)
                    / max(1, len(returns))
                )
                ** 0.5
            )
            if returns
            else 0.0
        )

        # Spread medio relativo
        spreads = []
        for h, l, c in zip(highs, lows, closes):
            if c > 0:
                spreads.append((h - l) / c)
        spread = float(sum(spreads) / len(spreads)) if spreads else 0.0

        # Volumen promedio
        volume = float(sum(volumes) / len(volumes)) if volumes else 0.0

        # RSI (reusar implementación existente basada en numpy)
        try:
            rsi_val = float(rsi_np(closes, period=min(14, max(2, len(closes) - 1))))
        except Exception:
            rsi_val = 50.0

        # ATR aproximado
        trs = []
        for i in range(1, len(klines)):
            h = highs[i]
            l = lows[i]
            pc = closes[i - 1]
            tr = max(h - l, abs(h - pc), abs(l - pc))
            trs.append(tr)
        atr = float(sum(trs) / len(trs)) if trs else 0.0

        return {
            "volatility": volatility,
            "spread": spread,
            "volume": volume,
            "rsi": rsi_val,
            "atr": atr,
        }

    def _heuristic_label(self, klines: List[List[Any]]) -> int:
        """Etiqueta heurística del régimen: 1 alcista si tendencia positiva reciente, 0 bajista."""
        if len(klines) < 3:
            return 0
        closes = [float(k[4]) for k in klines]
        return 1 if closes[-1] > closes[0] else 0

    async def train_on_symbol(
        self, symbol: str, interval: str = "1m", limit: int = 60
    ) -> None:
        """Entrena incrementalmente con klines recientes de un símbolo.
        Usa etiqueta heurística derivada de la tendencia reciente.
        """
        if self.pipeline is None:
            return
        kl = await self.collector.get_klines(symbol, interval, limit)
        x = await self.compute_features_from_klines(kl)
        y = self._heuristic_label(kl)

        # Detección de deriva: si cambia distribución (ADWIN), reiniciar métrica
        if self.drift_detector is not None:
            try:
                self.drift_detector.update(x["volatility"])  # señal simple
                if self.drift_detector.change_detected:
                    logger.info(
                        "Cambio de régimen detectado por ADWIN; reiniciando métrica"
                    )
                    self.metric = rv_metrics.LogLoss()
            except Exception:
                pass

        # Entrenamiento incremental
        try:
            self.pipeline = self.pipeline.learn_one(x, y)
            if self.metric is not None:
                self.metric = self.metric.update(
                    y, self.pipeline.predict_proba_one(x).get(True, 0.5)
                )
        except Exception as e:
            logger.warning(f"Error entrenando modelo online: {e}")

    async def predict_regime(
        self, symbol: str, interval: str = "1m", limit: int = 60
    ) -> RegimePrediction:
        """Predice régimen (0/1) y probabilidad para un símbolo.
        Si el modelo no está disponible, retorna valores por defecto.
        """
        kl = await self.collector.get_klines(symbol, interval, limit)
        x = await self.compute_features_from_klines(kl)
        if self.pipeline is None:
            return RegimePrediction(label=0, proba=0.5)
        try:
            proba_true = float(self.pipeline.predict_proba_one(x).get(True, 0.5))
            label = 1 if proba_true >= 0.5 else 0
            return RegimePrediction(label=label, proba=proba_true)
        except Exception as e:
            logger.warning(f"Predicción fallida: {e}")
            return RegimePrediction(label=0, proba=0.5)


def ml_prediction_to_regime_prediction(
    ml_pred: RegimePrediction,
) -> "RiskRegimePrediction":
    """Convierte la salida de MLEngine.predict_regime a RegimePrediction del risk_manager.
    label 0 -> RANGE, label 1 -> BULL_TREND; proba se usa como confianza.
    """
    from app.core.risk_manager import (
        MarketRegime,
        RegimePrediction as RiskRegimePrediction,
    )

    long_regime = MarketRegime.RANGE if ml_pred.label == 0 else MarketRegime.BULL_TREND
    short_regime = long_regime
    conf = max(0.0, min(1.0, float(ml_pred.proba)))
    return RiskRegimePrediction(
        long_regime=long_regime,
        short_regime=short_regime,
        long_conf=conf,
        short_conf=conf,
    )
