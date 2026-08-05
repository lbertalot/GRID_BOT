"""
HybridMLEngine para V2.5 "Low-Risk, Predictive & Adaptive Grid".
Combina modelos deep learning (LSTM/Transformer) con River para predicción de régimen.
"""

import hashlib
import asyncio
import json
import logging
import os
import joblib
import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple, Any, List
from datetime import datetime

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
from sklearn.preprocessing import StandardScaler, LabelEncoder

# River para ML online (HoeffdingTree vive en river.tree desde ~0.21)
from river import metrics
from river import linear_model
from river import ensemble
from river import tree as river_tree

from pydantic import BaseModel, Field
from prometheus_client import Counter, Histogram, Gauge

from app.core.risk_manager import MarketRegime, RegimePrediction

# Métricas Prometheus
REGIME_PREDICTIONS_TOTAL = Counter(
    "regime_predictions_total",
    "Total regime predictions made",
    ["symbol", "long", "short"],
)

REGIME_CONFIDENCE = Histogram(
    "regime_confidence", "Regime prediction confidence", ["symbol", "horizon"]
)

MODEL_TRAINING_DURATION = Histogram(
    "model_training_duration_seconds",
    "Model training duration in seconds",
    ["model_type", "symbol"],
)

MODEL_ACCURACY = Gauge(
    "model_accuracy", "Model accuracy score", ["model_type", "symbol"]
)


class ModelConfig(BaseModel):
    """Configuración para modelos de ML"""

    sequence_length: int = Field(
        default=60, description="Longitud de secuencia para LSTM"
    )
    hidden_units: int = Field(default=128, description="Unidades ocultas")
    dropout_rate: float = Field(default=0.2, description="Tasa de dropout")
    learning_rate: float = Field(default=0.001, description="Learning rate")
    batch_size: int = Field(default=32, description="Batch size")
    epochs: int = Field(default=100, description="Número de épocas")
    validation_split: float = Field(default=0.2, description="Split de validación")


class DeepModelConfig(ModelConfig):
    """Configuración específica para modelos deep learning"""

    model_type: str = Field(
        default="LSTM", description="Tipo de modelo (LSTM/Transformer)"
    )
    num_layers: int = Field(default=2, description="Número de capas")
    attention_heads: int = Field(
        default=8, description="Cabezas de atención (Transformer)"
    )


class RiverModelConfig(BaseModel):
    """Configuración para modelos River"""

    model_type: str = Field(default="HoeffdingTree", description="Tipo de modelo River")
    grace_period: int = Field(
        default=100, description="Grace period para drift detection"
    )
    split_confidence: float = Field(
        default=0.1,
        description="Umbral de split (river≥0.21: parámetro `tau` del HoeffdingTree)",
    )
    leaf_prediction: str = Field(default="mc", description="Predicción de hoja")


class HybridMLEngine:
    """
    Motor de ML híbrido que combina modelos deep learning con River.
    """

    def __init__(self, models_dir: str = "models"):
        self.models_dir = models_dir
        os.makedirs(models_dir, exist_ok=True)

        # Modelos deep learning
        self.deep_models: Dict[str, Any] = {}
        self.scalers: Dict[str, StandardScaler] = {}
        self.label_encoders: Dict[str, LabelEncoder] = {}

        # Modelos River
        self.river_models: Dict[str, Any] = {}
        self.river_metrics: Dict[str, metrics.Accuracy] = {}

        # Configuraciones
        self.deep_config = DeepModelConfig()
        self.river_config = RiverModelConfig()

        # Estado
        self.is_training = False
        self.last_predictions: Dict[str, RegimePrediction] = {}

        self.logger = logging.getLogger(__name__)

        # Inicializar TensorFlow
        tf.random.set_seed(42)

    def _create_lstm_model(
        self, input_shape: Tuple[int, int], num_classes: int
    ) -> keras.Model:
        """Crea modelo LSTM."""
        model = keras.Sequential(
            [
                layers.LSTM(
                    self.deep_config.hidden_units,
                    return_sequences=True,
                    input_shape=input_shape,
                ),
                layers.Dropout(self.deep_config.dropout_rate),
                layers.LSTM(self.deep_config.hidden_units // 2, return_sequences=False),
                layers.Dropout(self.deep_config.dropout_rate),
                layers.Dense(self.deep_config.hidden_units // 4, activation="relu"),
                layers.Dropout(self.deep_config.dropout_rate),
                layers.Dense(num_classes, activation="softmax"),
            ]
        )

        model.compile(
            optimizer=keras.optimizers.Adam(
                learning_rate=self.deep_config.learning_rate
            ),
            loss="sparse_categorical_crossentropy",
            metrics=["accuracy"],
        )

        return model

    def _create_transformer_model(
        self, input_shape: Tuple[int, int], num_classes: int
    ) -> keras.Model:
        """Crea modelo Transformer."""
        inputs = layers.Input(shape=input_shape)

        # Multi-head attention
        attention_output = layers.MultiHeadAttention(
            num_heads=self.deep_config.attention_heads,
            key_dim=self.deep_config.hidden_units // self.deep_config.attention_heads,
        )(inputs, inputs)

        # Add & Norm
        attention_output = layers.LayerNormalization(epsilon=1e-6)(
            attention_output + inputs
        )

        # Feed forward
        ffn_output = layers.Dense(self.deep_config.hidden_units * 4, activation="relu")(
            attention_output
        )
        ffn_output = layers.Dense(self.deep_config.hidden_units)(ffn_output)
        ffn_output = layers.LayerNormalization(epsilon=1e-6)(
            ffn_output + attention_output
        )

        # Global average pooling
        pooled_output = layers.GlobalAveragePooling1D()(ffn_output)

        # Classification head
        dense_output = layers.Dense(
            self.deep_config.hidden_units // 2, activation="relu"
        )(pooled_output)
        dense_output = layers.Dropout(self.deep_config.dropout_rate)(dense_output)
        outputs = layers.Dense(num_classes, activation="softmax")(dense_output)

        model = keras.Model(inputs=inputs, outputs=outputs)
        model.compile(
            optimizer=keras.optimizers.Adam(
                learning_rate=self.deep_config.learning_rate
            ),
            loss="sparse_categorical_crossentropy",
            metrics=["accuracy"],
        )

        return model

    def _prepare_deep_data(
        self, df: pd.DataFrame, symbol: str
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Prepara datos para modelos deep learning."""
        # Características técnicas
        features = [
            "close",
            "volume",
            "high",
            "low",
            "rsi",
            "macd",
            "bb_upper",
            "bb_lower",
            "atr",
            "volatility",
            "returns",
        ]

        # Filtrar características disponibles
        available_features = [f for f in features if f in df.columns]

        if len(available_features) < 5:
            # Características mínimas
            available_features = ["close", "volume", "high", "low"]

        # Preparar datos
        data = df[available_features].values

        # Normalizar
        if symbol not in self.scalers:
            self.scalers[symbol] = StandardScaler()
            data_scaled = self.scalers[symbol].fit_transform(data)
        else:
            data_scaled = self.scalers[symbol].transform(data)

        # Crear secuencias
        X, y = [], []
        for i in range(self.deep_config.sequence_length, len(data_scaled)):
            X.append(data_scaled[i - self.deep_config.sequence_length : i])

            # Determinar régimen basado en retornos futuros (3-7 días)
            future_window = min(7, len(data_scaled) - i)
            if future_window >= 3:
                future_returns = df["returns"].iloc[i : i + future_window].sum()
                if future_returns > 0.05:  # 5% de ganancia
                    regime = MarketRegime.BULL_TREND
                elif future_returns < -0.05:  # 5% de pérdida
                    regime = MarketRegime.BEAR_TREND
                elif (
                    df["volatility"].iloc[i]
                    > df["volatility"].rolling(20).mean().iloc[i] * 1.5
                ):
                    regime = MarketRegime.HIGH_VOL
                else:
                    regime = MarketRegime.RANGE
            else:
                regime = MarketRegime.RANGE

            y.append(regime.value)

        return np.array(X), np.array(y)

    async def train_deep_model(
        self,
        history_df: pd.DataFrame,
        symbol: str,
        output_path: Optional[str] = None,
        config: Optional[DeepModelConfig] = None,
    ) -> str:
        """
        Entrena modelo deep learning para predicción de régimen.

        Args:
            history_df: DataFrame con datos históricos
            symbol: Símbolo del trading pair
            output_path: Ruta de salida para el modelo
            config: Configuración del modelo

        Returns:
            Ruta del modelo guardado
        """
        if config:
            self.deep_config = config

        self.is_training = True
        start_time = datetime.now()

        try:
            self.logger.info(f"Training deep model for {symbol}")

            # Preparar datos
            X, y = self._prepare_deep_data(history_df, symbol)

            if len(X) < 100:
                raise ValueError(f"Insufficient data for {symbol}: {len(X)} samples")

            # Codificar etiquetas
            if symbol not in self.label_encoders:
                self.label_encoders[symbol] = LabelEncoder()
                y_encoded = self.label_encoders[symbol].fit_transform(y)
            else:
                y_encoded = self.label_encoders[symbol].transform(y)

            # Crear modelo
            input_shape = (X.shape[1], X.shape[2])
            num_classes = len(np.unique(y_encoded))

            if self.deep_config.model_type == "LSTM":
                model = self._create_lstm_model(input_shape, num_classes)
            elif self.deep_config.model_type == "Transformer":
                model = self._create_transformer_model(input_shape, num_classes)
            else:
                raise ValueError(f"Unknown model type: {self.deep_config.model_type}")

            # Callbacks
            callbacks = [
                keras.callbacks.EarlyStopping(
                    monitor="val_loss", patience=10, restore_best_weights=True
                ),
                keras.callbacks.ReduceLROnPlateau(
                    monitor="val_loss", factor=0.5, patience=5
                ),
            ]

            # Entrenar
            history = model.fit(
                X,
                y_encoded,
                batch_size=self.deep_config.batch_size,
                epochs=self.deep_config.epochs,
                validation_split=self.deep_config.validation_split,
                callbacks=callbacks,
                verbose=1,
            )

            # Evaluar
            val_accuracy = max(history.history["val_accuracy"])
            MODEL_ACCURACY.labels(model_type="deep", symbol=symbol).set(val_accuracy)

            # Guardar modelo
            if output_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = os.path.join(
                    self.models_dir,
                    f"{symbol}_deep_{self.deep_config.model_type}_{timestamp}",
                )

            os.makedirs(output_path, exist_ok=True)

            # Guardar modelo y componentes
            model.save(os.path.join(output_path, "model.h5"))

            scaler_path = os.path.join(output_path, "scaler.pkl")
            joblib.dump(self.scalers[symbol], scaler_path)
            with open(scaler_path + ".sha256", "w") as hf:
                hf.write(hashlib.sha256(open(scaler_path, "rb").read()).hexdigest())

            encoder_path = os.path.join(output_path, "label_encoder.pkl")
            joblib.dump(self.label_encoders[symbol], encoder_path)
            with open(encoder_path + ".sha256", "w") as hf:
                hf.write(hashlib.sha256(open(encoder_path, "rb").read()).hexdigest())

            # Guardar configuración
            with open(os.path.join(output_path, "config.json"), "w") as f:
                f.write(self.deep_config.json())

            # Guardar en diccionario
            self.deep_models[symbol] = {
                "model": model,
                "path": output_path,
                "config": self.deep_config,
                "last_trained": datetime.now(),
            }

            # Métricas
            training_duration = (datetime.now() - start_time).total_seconds()
            MODEL_TRAINING_DURATION.labels(model_type="deep", symbol=symbol).observe(
                training_duration
            )

            self.logger.info(
                f"Deep model trained for {symbol} in {training_duration:.2f}s. "
                f"Accuracy: {val_accuracy:.3f}"
            )

            return output_path

        except Exception as e:
            self.logger.error(f"Error training deep model for {symbol}: {e}")
            raise
        finally:
            self.is_training = False

    def load_deep_model(self, path: str, symbol: str) -> bool:
        """
        Carga modelo deep learning desde disco.

        Args:
            path: Ruta del modelo
            symbol: Símbolo del trading pair

        Returns:
            True si se cargó exitosamente
        """
        try:
            # Cargar modelo
            model = keras.models.load_model(os.path.join(path, "model.h5"))

            # Cargar scaler (joblib con verificación SHA256)
            scaler_path = os.path.join(path, "scaler.pkl")
            scaler_hash_path = scaler_path + ".sha256"
            if os.path.exists(scaler_hash_path):
                expected_hash = open(scaler_hash_path).read().strip()
                actual_hash = hashlib.sha256(open(scaler_path, "rb").read()).hexdigest()
                if actual_hash != expected_hash:
                    raise ValueError(f"SHA256 mismatch for {scaler_path}")
            scaler = joblib.load(scaler_path)

            # Cargar label encoder (joblib con verificación SHA256)
            encoder_path = os.path.join(path, "label_encoder.pkl")
            encoder_hash_path = encoder_path + ".sha256"
            if os.path.exists(encoder_hash_path):
                expected_hash = open(encoder_hash_path).read().strip()
                actual_hash = hashlib.sha256(
                    open(encoder_path, "rb").read()
                ).hexdigest()
                if actual_hash != expected_hash:
                    raise ValueError(f"SHA256 mismatch for {encoder_path}")
            label_encoder = joblib.load(encoder_path)

            # Cargar configuración
            with open(os.path.join(path, "config.json"), "r") as f:
                config_data = json.load(f)
                config = DeepModelConfig(**config_data)

            # Guardar en diccionario
            self.deep_models[symbol] = {
                "model": model,
                "path": path,
                "config": config,
                "last_trained": datetime.fromtimestamp(os.path.getmtime(path)),
            }

            self.scalers[symbol] = scaler
            self.label_encoders[symbol] = label_encoder

            self.logger.info(f"Deep model loaded for {symbol} from {path}")
            return True

        except Exception as e:
            self.logger.error(f"Error loading deep model for {symbol}: {e}")
            return False

    def _create_river_model(self) -> Any:
        """Crea modelo River para predicción online."""
        if self.river_config.model_type == "HoeffdingTree":
            return river_tree.HoeffdingTreeClassifier(
                grace_period=self.river_config.grace_period,
                tau=float(self.river_config.split_confidence),
                leaf_prediction=self.river_config.leaf_prediction,
            )
        elif self.river_config.model_type == "AdaptiveRandomForest":
            return ensemble.AdaptiveRandomForestClassifier(n_models=10, seed=42)
        elif self.river_config.model_type == "LogisticRegression":
            return linear_model.LogisticRegression()
        else:
            raise ValueError(
                f"Unknown River model type: {self.river_config.model_type}"
            )

    def initialize_river_model(self, symbol: str) -> None:
        """
        Inicializa modelo River para un símbolo.

        Args:
            symbol: Símbolo del trading pair
        """
        if symbol not in self.river_models and self.load_river_model(symbol):
            return

        if symbol not in self.river_models:
            self.river_models[symbol] = self._create_river_model()
            self.river_metrics[symbol] = metrics.Accuracy()

            self.logger.info(f"River model initialized for {symbol}")

    def _river_model_path(self, symbol: str) -> str:
        """Ruta de persistencia para el componente River online."""
        safe_symbol = symbol.replace("/", "_").replace(":", "_")
        return os.path.join(self.models_dir, f"{safe_symbol}_river.pkl")

    def load_river_model(self, symbol: str) -> bool:
        """Carga el modelo River online de un símbolo si existe."""
        path = self._river_model_path(symbol)
        if not os.path.exists(path):
            return False

        try:
            hash_path = path + ".sha256"
            if os.path.exists(hash_path):
                expected_hash = open(hash_path).read().strip()
                actual_hash = hashlib.sha256(open(path, "rb").read()).hexdigest()
                if actual_hash != expected_hash:
                    self.logger.error(
                        f"SHA256 mismatch for River model {path} — refusing to load"
                    )
                    return False
            payload = joblib.load(path)

            self.river_models[symbol] = payload["model"]
            self.river_metrics[symbol] = payload.get("metric", metrics.Accuracy())
            self.logger.info(f"River model loaded for {symbol} from {path}")
            return True
        except Exception as e:
            self.logger.warning(f"Error loading River model for {symbol}: {e}")
            return False

    def save_river_model(self, symbol: str) -> None:
        """Persiste el modelo River online para sobrevivir reinicios Docker."""
        if symbol not in self.river_models:
            return

        os.makedirs(self.models_dir, exist_ok=True)
        path = self._river_model_path(symbol)
        payload = {
            "model": self.river_models[symbol],
            "metric": self.river_metrics.get(symbol, metrics.Accuracy()),
            "saved_at": datetime.now().isoformat(),
        }
        joblib.dump(payload, path)
        with open(path + ".sha256", "w") as hf:
            hf.write(hashlib.sha256(open(path, "rb").read()).hexdigest())

    def update_river_model(
        self, symbol: str, features: Dict[str, float], regime: MarketRegime
    ) -> None:
        """
        Actualiza modelo River con nuevos datos.

        Args:
            symbol: Símbolo del trading pair
            features: Características del mercado
            regime: Régimen real observado
        """
        if symbol not in self.river_models:
            self.initialize_river_model(symbol)

        # Convertir características a formato River
        x = features
        y = regime.value

        # Actualizar modelo
        y_pred = self.river_models[symbol].predict_one(x)
        self.river_models[symbol].learn_one(x, y)

        # Actualizar métricas
        self.river_metrics[symbol].update(y, y_pred)

        # Log cada 100 actualizaciones
        if self.river_metrics[symbol].n_samples % 100 == 0:
            accuracy = self.river_metrics[symbol].get()
            self.logger.debug(f"River model accuracy for {symbol}: {accuracy:.3f}")

    def predict_long_regime(
        self, symbol: str, recent_window: pd.DataFrame
    ) -> Tuple[MarketRegime, float]:
        """
        Predice régimen a largo plazo usando modelo deep learning.

        Args:
            symbol: Símbolo del trading pair
            recent_window: Ventana reciente de datos

        Returns:
            Tupla (régimen, confianza)
        """
        if symbol not in self.deep_models:
            raise ValueError(f"No deep model available for {symbol}")

        try:
            # Preparar datos
            X, _ = self._prepare_deep_data(recent_window, symbol)

            if len(X) == 0:
                return MarketRegime.RANGE, 0.5

            # Obtener última secuencia
            X_last = X[-1:]

            # Predicción
            model = self.deep_models[symbol]["model"]
            predictions = model.predict(X_last)

            # Obtener clase y confianza
            predicted_class = np.argmax(predictions[0])
            confidence = float(predictions[0][predicted_class])

            # Decodificar régimen
            regime_name = self.label_encoders[symbol].inverse_transform(
                [predicted_class]
            )[0]
            regime = MarketRegime(regime_name)

            # Métricas
            REGIME_PREDICTIONS_TOTAL.labels(
                symbol=symbol, long=regime.value, short=""
            ).inc()
            REGIME_CONFIDENCE.labels(symbol=symbol, horizon="long").observe(confidence)

            return regime, confidence

        except Exception as e:
            self.logger.error(f"Error predicting long regime for {symbol}: {e}")
            return MarketRegime.RANGE, 0.5

    def predict_short_regime(
        self, symbol: str, features: Dict[str, float]
    ) -> Tuple[MarketRegime, float]:
        """
        Predice régimen a corto plazo usando modelo River.

        Args:
            symbol: Símbolo del trading pair
            features: Características actuales del mercado

        Returns:
            Tupla (régimen, confianza)
        """
        if symbol not in self.river_models:
            self.initialize_river_model(symbol)

        try:
            # Predicción
            y_pred = self.river_models[symbol].predict_one(features)
            if y_pred is None:
                return MarketRegime.RANGE, 0.5

            # Obtener confianza (simplificado)
            confidence = 0.7  # River no proporciona confianza directamente

            regime = MarketRegime(y_pred)

            # Métricas
            REGIME_PREDICTIONS_TOTAL.labels(
                symbol=symbol, long="", short=regime.value
            ).inc()
            REGIME_CONFIDENCE.labels(symbol=symbol, horizon="short").observe(confidence)

            return regime, confidence

        except Exception as e:
            self.logger.error(f"Error predicting short regime for {symbol}: {e}")
            return MarketRegime.RANGE, 0.5

    def _klines_to_dataframe(self, klines: List[List[Any]]) -> pd.DataFrame:
        """Convierte klines de Binance a DataFrame con features técnicas básicas."""
        rows = []
        for kline in klines:
            try:
                rows.append(
                    {
                        "open": float(kline[1]),
                        "high": float(kline[2]),
                        "low": float(kline[3]),
                        "close": float(kline[4]),
                        "volume": float(kline[5]),
                    }
                )
            except (IndexError, TypeError, ValueError):
                continue

        df = pd.DataFrame(rows)
        if df.empty:
            return df

        df["returns"] = df["close"].pct_change().fillna(0.0)
        df["volatility"] = df["returns"].rolling(20, min_periods=2).std().fillna(0.0)

        delta = df["close"].diff().fillna(0.0)
        gain = delta.clip(lower=0).rolling(14, min_periods=1).mean()
        loss = (-delta.clip(upper=0)).rolling(14, min_periods=1).mean()
        rs = gain / loss.replace(0, np.nan)
        df["rsi"] = (100 - (100 / (1 + rs))).fillna(50.0)

        ema_fast = df["close"].ewm(span=12, adjust=False).mean()
        ema_slow = df["close"].ewm(span=26, adjust=False).mean()
        df["macd"] = ema_fast - ema_slow

        rolling_mean = df["close"].rolling(20, min_periods=1).mean()
        rolling_std = df["close"].rolling(20, min_periods=1).std().fillna(0.0)
        df["bb_upper"] = rolling_mean + (rolling_std * 2)
        df["bb_lower"] = rolling_mean - (rolling_std * 2)

        previous_close = df["close"].shift(1).fillna(df["close"])
        true_range = pd.concat(
            [
                df["high"] - df["low"],
                (df["high"] - previous_close).abs(),
                (df["low"] - previous_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        df["atr"] = true_range.rolling(14, min_periods=1).mean().fillna(0.0)

        return df

    def _features_from_dataframe(self, df: pd.DataFrame) -> Dict[str, float]:
        """Extrae el último snapshot de features para River."""
        if df.empty:
            return {
                "close": 0.0,
                "volume": 0.0,
                "rsi": 50.0,
                "atr": 0.0,
                "volatility": 0.0,
                "returns": 0.0,
                "macd": 0.0,
            }

        last = df.iloc[-1]
        return {
            "close": float(last.get("close", 0.0)),
            "volume": float(last.get("volume", 0.0)),
            "rsi": float(last.get("rsi", 50.0)),
            "atr": float(last.get("atr", 0.0)),
            "volatility": float(last.get("volatility", 0.0)),
            "returns": float(last.get("returns", 0.0)),
            "macd": float(last.get("macd", 0.0)),
        }

    def _infer_observed_regime(self, df: pd.DataFrame) -> MarketRegime:
        """Etiqueta online conservadora para entrenar River con klines recientes."""
        if len(df) < 3:
            return MarketRegime.RANGE

        first_close = float(df["close"].iloc[0])
        last_close = float(df["close"].iloc[-1])
        if first_close <= 0:
            return MarketRegime.RANGE

        window_return = (last_close - first_close) / first_close
        volatility = float(df["volatility"].iloc[-1])

        if volatility >= 0.03 and window_return < 0:
            return MarketRegime.HIGH_VOLATILITY_BEAR
        if volatility >= 0.03:
            return MarketRegime.HIGH_VOL
        if window_return >= 0.01:
            return MarketRegime.BULL_TREND
        if window_return <= -0.01:
            return MarketRegime.BEAR_TREND
        return MarketRegime.RANGE

    def load_latest_deep_model(self, symbol: str) -> bool:
        """Intenta cargar el modelo deep más reciente del directorio de modelos."""
        if symbol in self.deep_models or not os.path.isdir(self.models_dir):
            return symbol in self.deep_models

        candidates = [
            os.path.join(self.models_dir, entry)
            for entry in os.listdir(self.models_dir)
            if entry.startswith(f"{symbol}_deep_")
            and os.path.isdir(os.path.join(self.models_dir, entry))
        ]
        if not candidates:
            return False

        latest = max(candidates, key=os.path.getmtime)
        return self.load_deep_model(latest, symbol)

    async def predict_regime_from_klines(
        self,
        symbol: str,
        klines: List[List[Any]],
        train_online: bool = True,
    ) -> RegimePrediction:
        """
        Predice régimen desde klines y actualiza el componente online River.

        TensorFlow/Keras es requisito de importación del motor híbrido. Si aún no
        existe un modelo deep entrenado para el símbolo, el horizonte largo usa la
        señal online como puente explícito y observable, no un fallback de error.
        """
        df = self._klines_to_dataframe(klines)
        features = self._features_from_dataframe(df)

        if train_online and not df.empty:
            observed_regime = self._infer_observed_regime(df)
            self.update_river_model(symbol, features, observed_regime)
            await asyncio.to_thread(self.save_river_model, symbol)

        await asyncio.to_thread(self.load_latest_deep_model, symbol)

        short_regime, short_conf = self.predict_short_regime(symbol, features)
        if symbol in self.deep_models and len(df) > self.deep_config.sequence_length:
            long_regime, long_conf = self.predict_long_regime(symbol, df)
        else:
            long_regime, long_conf = short_regime, max(0.5, short_conf * 0.9)

        prediction = RegimePrediction(
            long_regime=long_regime,
            short_regime=short_regime,
            long_conf=long_conf,
            short_conf=short_conf,
        )
        self.last_predictions[symbol] = prediction

        self.logger.info(
            f"Hybrid regime prediction for {symbol}: "
            f"Long={long_regime.value}({long_conf:.2f}), "
            f"Short={short_regime.value}({short_conf:.2f})"
        )

        return prediction

    async def predict_regime(
        self, symbol: str, recent_data: pd.DataFrame, current_features: Dict[str, float]
    ) -> RegimePrediction:
        """
        Predice régimen combinando modelos deep learning y River.

        Args:
            symbol: Símbolo del trading pair
            recent_data: Datos recientes para modelo deep
            current_features: Características actuales para River

        Returns:
            Predicción de régimen
        """
        try:
            # Predicción a largo plazo (deep learning)
            long_regime, long_conf = self.predict_long_regime(symbol, recent_data)

            # Predicción a corto plazo (River)
            short_regime, short_conf = self.predict_short_regime(
                symbol, current_features
            )

            # Crear predicción combinada
            prediction = RegimePrediction(
                long_regime=long_regime,
                short_regime=short_regime,
                long_conf=long_conf,
                short_conf=short_conf,
            )

            # Guardar última predicción
            self.last_predictions[symbol] = prediction

            self.logger.info(
                f"Regime prediction for {symbol}: "
                f"Long={long_regime.value}({long_conf:.2f}), "
                f"Short={short_regime.value}({short_conf:.2f})"
            )

            return prediction

        except Exception as e:
            self.logger.error(f"Error predicting regime for {symbol}: {e}")
            # Retornar predicción por defecto
            return RegimePrediction(
                long_regime=MarketRegime.RANGE,
                short_regime=MarketRegime.RANGE,
                long_conf=0.5,
                short_conf=0.5,
            )

    def get_model_status(self, symbol: str) -> Dict[str, Any]:
        """
        Obtiene el estado de los modelos para un símbolo.

        Returns:
            Dict con estado de los modelos
        """
        status = {
            "symbol": symbol,
            "deep_model_loaded": symbol in self.deep_models,
            "river_model_initialized": symbol in self.river_models,
            "last_prediction": None,
            "deep_model_info": None,
            "river_model_info": None,
        }

        if symbol in self.last_predictions:
            status["last_prediction"] = self.last_predictions[symbol].dict()

        if symbol in self.deep_models:
            model_info = self.deep_models[symbol]
            status["deep_model_info"] = {
                "path": model_info["path"],
                "model_type": model_info["config"].model_type,
                "last_trained": model_info["last_trained"].isoformat(),
            }

        if symbol in self.river_models:
            metric = self.river_metrics[symbol]
            status["river_model_info"] = {
                "model_type": self.river_config.model_type,
                "accuracy": metric.get(),
                "samples_processed": metric.n_samples,
            }

        return status
