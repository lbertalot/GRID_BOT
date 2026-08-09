"""S-COV-85 Z4 — config_manager + hybrid_ml_engine + performance_analyzer.

Paper-only, heavy mocks. TensorFlow stubbed (ML_ENABLED=false / no live ML).
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import sys
import types
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import numpy as np
import pandas as pd
import pytest

pytestmark = pytest.mark.usefixtures("paper_env")


# ── TensorFlow stub (no real TF / no live ML) ────────────────────────────────


def _install_tf_stub():
    if "tensorflow" in sys.modules and getattr(
        sys.modules["tensorflow"], "__gridbot_stub__", False
    ):
        return

    tf = types.ModuleType("tensorflow")
    tf.__gridbot_stub__ = True
    tf.random = types.SimpleNamespace(set_seed=lambda *_a, **_k: None)

    keras = types.ModuleType("tensorflow.keras")
    layers = types.ModuleType("tensorflow.keras.layers")
    callbacks = types.ModuleType("tensorflow.keras.callbacks")
    models = types.ModuleType("tensorflow.keras.models")
    optimizers = types.ModuleType("tensorflow.keras.optimizers")

    class _Layer:
        def __init__(self, *a, **k):
            self.a, self.k = a, k

        def __call__(self, *a, **k):
            return MagicMock(name="tensor")

    for name in (
        "LSTM",
        "Dropout",
        "Dense",
        "Input",
        "MultiHeadAttention",
        "LayerNormalization",
        "GlobalAveragePooling1D",
    ):
        setattr(layers, name, _Layer)

    class _Sequential:
        def __init__(self, layers_list=None):
            self.layers_list = layers_list or []

        def compile(self, **k):
            return None

        def fit(self, *a, **k):
            return SimpleNamespace(history={"val_accuracy": [0.8, 0.9]})

        def predict(self, x):
            return np.array([[0.1, 0.7, 0.2]])

        def save(self, path):
            Path(path).write_bytes(b"fake")

    class _Model(_Sequential):
        def __init__(self, inputs=None, outputs=None):
            super().__init__()
            self.inputs, self.outputs = inputs, outputs

    class _CB:
        def __init__(self, *a, **k):
            pass

    keras.Sequential = _Sequential
    keras.Model = _Model
    keras.layers = layers
    keras.callbacks = callbacks
    keras.models = models
    keras.optimizers = optimizers
    callbacks.EarlyStopping = _CB
    callbacks.ReduceLROnPlateau = _CB
    models.load_model = MagicMock(return_value=_Sequential())
    optimizers.Adam = lambda **k: "adam"

    tf.keras = keras
    sys.modules["tensorflow"] = tf
    sys.modules["tensorflow.keras"] = keras
    sys.modules["tensorflow.keras.layers"] = layers
    sys.modules["tensorflow.keras.callbacks"] = callbacks
    sys.modules["tensorflow.keras.models"] = models
    sys.modules["tensorflow.keras.optimizers"] = optimizers


_install_tf_stub()
# Import único: reload duplica métricas Prometheus.
_HYBRID_MOD = importlib.import_module("app.services.hybrid_ml_engine")


def _sample_df(n: int = 120) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    return pd.DataFrame(
        {
            "close": close,
            "volume": rng.uniform(1000, 2000, n),
            "high": close + 1,
            "low": close - 1,
            "rsi": rng.uniform(30, 70, n),
            "macd": rng.normal(0, 0.1, n),
            "bb_upper": close + 2,
            "bb_lower": close - 2,
            "atr": rng.uniform(0.5, 1.5, n),
            "volatility": rng.uniform(0.01, 0.04, n),
            "returns": rng.normal(0, 0.01, n),
        }
    )


def _klines(n: int = 80):
    out = []
    price = 100.0
    for i in range(n):
        price *= 1.001 if i % 2 == 0 else 0.999
        out.append(
            [
                i * 60_000,
                str(price),
                str(price + 1),
                str(price - 1),
                str(price),
                str(1000 + i),
            ]
        )
    return out


# ── config_manager ───────────────────────────────────────────────────────────


@pytest.fixture
def cfg_mgr():
    import app.services.config_manager as mod

    fake = MagicMock()
    prices = [100 + i * 0.1 for i in range(24)]
    fake.get_ticker.return_value = {
        "lastPrice": "100.0",
        "volume": "2000000",
        "priceChangePercent": "1.5",
        "highPrice": "110",
        "lowPrice": "90",
    }
    fake.get_klines.return_value = [
        [0, "1", "2", "0.5", str(p), "1000"] for p in prices
    ]
    mod.binance_client = fake
    return mod.ConfigManager(), mod, fake


@pytest.mark.asyncio
async def test_config_manager_all_strategies(cfg_mgr):
    mgr, mod, fake = cfg_mgr
    from app.services.config_manager import OptimizationRequest, OptimizationStrategy

    with patch("app.services.config_manager.send_telegram_alert"):
        for strat in OptimizationStrategy:
            req = OptimizationRequest(
                symbol="BTC",
                strategy=strat,
                investment_amount=1000.0,
                risk_tolerance=0.5,
                max_grids=20,
            )
            if strat == OptimizationStrategy.MACHINE_LEARNING:
                # sync get_klines used in market; async path for historical
                async def _async_klines(**k):
                    return fake.get_klines.return_value

                fake.get_klines = MagicMock(side_effect=lambda **k: [
                    [0, "1", "2", "0.5", str(100 + i), "1000"] for i in range(30)
                ])
                # _get_historical_data awaits get_klines — make it awaitable
                async def _awaitable_klines(**kwargs):
                    return [[0, "1", "2", "0.5", str(100 + i), "1000"] for i in range(30)]

                fake.get_klines = _awaitable_klines
                # market data uses sync call — provide sync mock via patch
                with patch.object(
                    mgr,
                    "_get_market_data",
                    new_callable=AsyncMock,
                    return_value=mod.MarketData(
                        symbol="BTC",
                        current_price=100.0,
                        volatility=0.08,
                        volume_24h=2_000_000,
                        price_change_24h=1.0,
                        high_24h=110,
                        low_24h=90,
                        timestamp=datetime.now(),
                    ),
                ):
                    cfg = await mgr.optimize_parameters(req)
            else:
                # restore sync client for market
                sync = MagicMock()
                sync.get_ticker.return_value = {
                    "lastPrice": "100.0",
                    "volume": "500000",
                    "priceChangePercent": "-0.5",
                    "highPrice": "110",
                    "lowPrice": "90",
                }
                sync.get_klines.return_value = [
                    [0, "1", "2", "0.5", str(100 + i * 0.2), "1000"] for i in range(24)
                ]
                mod.binance_client = sync
                # volatility branches
                if strat == OptimizationStrategy.VOLATILITY_BASED:
                    # three vols via market data patch
                    for vol in (0.02, 0.10, 0.20):
                        with patch.object(
                            mgr,
                            "_get_market_data",
                            new_callable=AsyncMock,
                            return_value=mod.MarketData(
                                symbol="BTC",
                                current_price=100.0,
                                volatility=vol,
                                volume_24h=1_000_000,
                                price_change_24h=0.0,
                                high_24h=110,
                                low_24h=90,
                                timestamp=datetime.now(),
                            ),
                        ):
                            cfg = await mgr.optimize_parameters(
                                OptimizationRequest(
                                    symbol="BTC",
                                    strategy=strat,
                                    investment_amount=500.0,
                                )
                            )
                            assert cfg.grids >= 5
                    continue
                if strat == OptimizationStrategy.VOLUME_BASED:
                    for vol_amt in (100_000, 600_000, 2_000_000):
                        with patch.object(
                            mgr,
                            "_get_market_data",
                            new_callable=AsyncMock,
                            return_value=mod.MarketData(
                                symbol="BTC",
                                current_price=100.0,
                                volatility=0.1,
                                volume_24h=vol_amt,
                                price_change_24h=0.0,
                                high_24h=110,
                                low_24h=90,
                                timestamp=datetime.now(),
                            ),
                        ):
                            cfg = await mgr.optimize_parameters(
                                OptimizationRequest(
                                    symbol="BTC",
                                    strategy=strat,
                                    investment_amount=500.0,
                                )
                            )
                            assert cfg.quantity > 0
                    continue
                cfg = await mgr.optimize_parameters(req)
            assert cfg.symbol == "BTC"
            assert cfg.backtest_results is not None


@pytest.mark.asyncio
async def test_config_manager_helpers_and_errors(cfg_mgr):
    mgr, mod, fake = cfg_mgr
    from app.services.config_manager import (
        MarketData,
        OptimizationRequest,
        OptimizationStrategy,
        OptimizedConfig,
    )

    # cache hit
    md = MarketData(
        symbol="ETH",
        current_price=50.0,
        volatility=0.05,
        volume_24h=1e6,
        price_change_24h=0.1,
        high_24h=55,
        low_24h=45,
        timestamp=datetime.now(),
    )
    mgr.market_data_cache["ETH"] = md
    assert await mgr._get_market_data("ETH") is md

    # exception → defaults
    mod.binance_client = MagicMock()
    mod.binance_client.get_ticker.side_effect = RuntimeError("api")
    defaults = await mgr._get_market_data("SOL")
    assert defaults.current_price == 100.0

    # historical empty / ok
    async def _bad(**k):
        raise RuntimeError("x")

    mod.binance_client.get_klines = _bad
    assert await mgr._get_historical_data("X", 7) == []

    async def _ok(**k):
        return [[1, "1", "2", "0.5", "1.5", "10"]]

    mod.binance_client.get_klines = _ok
    hist = await mgr._get_historical_data("X", 7)
    assert hist[0]["close"] == 1.5

    feats = mgr._extract_features(
        [{"close": float(i)} for i in range(1, 25)], md
    )
    assert "trend" in feats
    assert mgr._extract_features([], md)["volatility"] == 0.1

    assert mgr._calculate_optimal_grids(0.1, 0.5) >= 5
    score = mgr._calculate_confidence_score(md, 15, 0.15)
    assert 0.1 <= score <= 1.0
    with patch.object(mgr, "_calculate_confidence_score", wraps=mgr._calculate_confidence_score):
        pass
    # force exception in confidence
    bad_md = MagicMock()
    bad_md.volatility = "x"
    bad_md.volume_24h = None
    assert mgr._calculate_confidence_score(bad_md, 15, 0.15) == 0.5

    cfg = OptimizedConfig(
        symbol="BTC",
        min_price=90,
        max_price=110,
        grids=10,
        quantity=0.01,
        confidence_score=0.8,
        optimization_strategy="grid_optimization",
        timestamp=datetime.now(),
    )
    with patch("numpy.random.uniform", return_value=1.0), patch(
        "numpy.random.normal", return_value=-0.2
    ):
        bt = await mgr._run_backtest(cfg, md)
    assert "roi" in bt
    assert mgr._calculate_simulated_drawdown(10.0, 30) >= 0
    with patch("numpy.random.uniform", side_effect=RuntimeError("x")):
        assert mgr._calculate_simulated_drawdown(1.0, 5) == 0.0
        bt_err = await mgr._run_backtest(cfg, md)
        assert "error" in bt_err or bt_err["total_trades"] == 0

    with patch("app.services.config_manager.send_telegram_alert") as tg:
        cfg.backtest_results = {"total_trades": 1, "win_rate": 0.5, "roi": 0.1}
        await mgr._send_optimization_notification(cfg)
        assert tg.called
    with patch(
        "app.services.config_manager.send_telegram_alert",
        side_effect=RuntimeError("tg"),
    ):
        await mgr._send_optimization_notification(cfg)

    mgr.optimization_history["BTC"] = [cfg]
    hist_one = await mgr.get_optimization_history("BTC")
    assert hist_one["symbol"] == "BTC"
    hist_all = await mgr.get_optimization_history()
    assert "all_optimizations" in hist_all

    with patch.object(
        mgr, "_get_market_data", new_callable=AsyncMock, return_value=md
    ):
        analysis = await mgr.get_market_analysis("ETH")
        assert analysis["trend"] in ("Alcista", "Bajista")
        md.volatility = 0.25
        md.price_change_24h = -1
        analysis2 = await mgr.get_market_analysis("ETH")
        assert analysis2["volatility"]["level"] == "Alta"

    with patch.object(
        mgr, "_get_market_data", new_callable=AsyncMock, side_effect=RuntimeError("x")
    ):
        assert await mgr.get_market_analysis("Z") == {}

    # optimize error path
    with patch.object(
        mgr, "_get_market_data", new_callable=AsyncMock, side_effect=RuntimeError("x")
    ):
        with pytest.raises(RuntimeError):
            await mgr.optimize_parameters(
                OptimizationRequest(symbol="BTC", investment_amount=100)
            )

    # ML fallback when no historical
    with patch.object(
        mgr,
        "_get_market_data",
        new_callable=AsyncMock,
        return_value=md,
    ), patch.object(
        mgr, "_get_historical_data", new_callable=AsyncMock, return_value=[]
    ), patch(
        "app.services.config_manager.send_telegram_alert"
    ):
        cfg_ml = await mgr.optimize_parameters(
            OptimizationRequest(
                symbol="ETH",
                strategy=OptimizationStrategy.MACHINE_LEARNING,
                investment_amount=200,
            )
        )
        assert cfg_ml.grids >= 5

    # ML trend branches via features
    for trend in (0.05, -0.05, 0.0):
        with patch.object(
            mgr,
            "_get_market_data",
            new_callable=AsyncMock,
            return_value=md,
        ), patch.object(
            mgr,
            "_get_historical_data",
            new_callable=AsyncMock,
            return_value=[{"close": float(i)} for i in range(1, 30)],
        ), patch.object(
            mgr,
            "_extract_features",
            return_value={"volatility": 0.1, "trend": trend, "momentum": 0},
        ), patch(
            "app.services.config_manager.send_telegram_alert"
        ):
            await mgr.optimize_parameters(
                OptimizationRequest(
                    symbol="ETH",
                    strategy=OptimizationStrategy.MACHINE_LEARNING,
                    investment_amount=200,
                )
            )

    # strategy helpers exception
    with patch.object(mgr, "_calculate_optimal_grids", side_effect=RuntimeError("x")):
        with pytest.raises(RuntimeError):
            await mgr._optimize_grid_strategy(
                OptimizationRequest(symbol="BTC", investment_amount=100), md
            )


@pytest.mark.asyncio
async def test_config_manager_history_exception(cfg_mgr):
    mgr, _, _ = cfg_mgr
    mgr.optimization_history = None  # type: ignore
    assert await mgr.get_optimization_history("X") == {}


# ── hybrid_ml_engine ─────────────────────────────────────────────────────────


@pytest.fixture
def hybrid(tmp_path):
    mod = _HYBRID_MOD
    eng = mod.HybridMLEngine(models_dir=str(tmp_path / "models"))
    return eng, mod


def test_hybrid_configs_and_river_models(hybrid):
    eng, mod = hybrid
    assert mod.ModelConfig().epochs == 100
    assert mod.DeepModelConfig().model_type == "LSTM"

    for mtype in ("HoeffdingTree", "AdaptiveRandomForest", "LogisticRegression"):
        eng.river_config.model_type = mtype
        assert eng._create_river_model() is not None
    eng.river_config.model_type = "Nope"
    with pytest.raises(ValueError):
        eng._create_river_model()

    eng.river_config.model_type = "HoeffdingTree"
    eng.initialize_river_model("BTCUSDT")
    assert "BTCUSDT" in eng.river_models
    # load path when already present skips create
    eng.initialize_river_model("BTCUSDT")

    path = eng._river_model_path("BTC/USDT:PERP")
    assert "BTC_USDT_PERP_river.pkl" in path

    eng.save_river_model("MISSING")  # no-op
    eng.save_river_model("BTCUSDT")
    assert Path(eng._river_model_path("BTCUSDT")).exists()

    eng2 = mod.HybridMLEngine(models_dir=eng.models_dir)
    assert eng2.load_river_model("BTCUSDT") is True
    # bad hash
    p = eng._river_model_path("BTCUSDT")
    Path(p + ".sha256").write_text("deadbeef")
    eng3 = mod.HybridMLEngine(models_dir=eng.models_dir)
    assert eng3.load_river_model("BTCUSDT") is False
    # missing
    assert eng3.load_river_model("NONE") is False
    # corrupt
    Path(p).write_text("not-joblib")
    Path(p + ".sha256").unlink(missing_ok=True)
    assert eng3.load_river_model("BTCUSDT") is False


@pytest.mark.asyncio
async def test_hybrid_deep_prepare_train_load(hybrid, tmp_path):
    eng, mod = hybrid
    from app.core.risk_manager import MarketRegime
    from sklearn.preprocessing import LabelEncoder, StandardScaler
    import joblib

    df = _sample_df(150)
    X, y = eng._prepare_deep_data(df, "BTCUSDT")
    assert len(X) > 0

    df2 = pd.DataFrame(
        {
            "close": np.linspace(1, 2, 80),
            "volume": np.ones(80),
            "high": np.linspace(1, 2, 80) + 0.1,
            "low": np.linspace(1, 2, 80) - 0.1,
            "returns": np.zeros(80),
            "volatility": np.full(80, 0.01),
        }
    )
    eng.deep_config.sequence_length = 10
    X2, _ = eng._prepare_deep_data(df2, "MINFEAT")
    assert len(X2) > 0
    eng.scalers.pop("MINFEAT", None)

    assert eng._create_lstm_model((10, 4), 3) is not None
    assert eng._create_transformer_model((10, 4), 3) is not None

    eng.deep_config.sequence_length = 10
    eng.deep_config.epochs = 1
    eng.deep_config.model_type = "LSTM"
    path = await eng.train_deep_model(_sample_df(150), "BTCUSDT")
    assert Path(path).exists()

    eng.scalers.pop("ETHUSDT", None)
    eng.label_encoders.pop("ETHUSDT", None)
    await eng.train_deep_model(
        _sample_df(150),
        "ETHUSDT",
        config=mod.DeepModelConfig(
            model_type="Transformer", epochs=1, sequence_length=10
        ),
    )

    eng.deep_config.model_type = "UNKNOWN"
    with pytest.raises(ValueError):
        await eng.train_deep_model(_sample_df(150), "X")

    eng.deep_config.model_type = "LSTM"
    eng.deep_config.sequence_length = 60
    with pytest.raises(ValueError):
        await eng.train_deep_model(_sample_df(70), "Y")

    out = tmp_path / "mdl"
    out.mkdir()
    (out / "model.h5").write_bytes(b"x")
    sc = StandardScaler()
    sc.fit([[1.0, 2.0]])
    sp = out / "scaler.pkl"
    joblib.dump(sc, sp)
    (out / "scaler.pkl.sha256").write_text(
        hashlib.sha256(sp.read_bytes()).hexdigest()
    )
    le = LabelEncoder()
    le.fit([MarketRegime.RANGE.value, MarketRegime.BULL_TREND.value])
    ep = out / "label_encoder.pkl"
    joblib.dump(le, ep)
    (out / "label_encoder.pkl.sha256").write_text(
        hashlib.sha256(ep.read_bytes()).hexdigest()
    )
    (out / "config.json").write_text(
        mod.DeepModelConfig(model_type="LSTM").model_dump_json()
    )
    assert eng.load_deep_model(str(out), "LOAD1") is True
    (out / "scaler.pkl.sha256").write_text("00")
    assert eng.load_deep_model(str(out), "LOAD2") is False
    # encoder hash mismatch
    (out / "scaler.pkl.sha256").write_text(
        hashlib.sha256(sp.read_bytes()).hexdigest()
    )
    (out / "label_encoder.pkl.sha256").write_text("00")
    assert eng.load_deep_model(str(out), "LOAD3") is False
    # missing model file
    assert eng.load_deep_model(str(tmp_path / "missing"), "LOAD4") is False

    deep_dir = Path(eng.models_dir) / "ZZUSDT_deep_LSTM_20200101"
    deep_dir.mkdir(parents=True, exist_ok=True)
    for name in (
        "model.h5",
        "scaler.pkl",
        "label_encoder.pkl",
        "config.json",
    ):
        src = out / name
        if name.endswith(".json"):
            (deep_dir / name).write_text(src.read_text())
        else:
            (deep_dir / name).write_bytes(src.read_bytes())
    (deep_dir / "scaler.pkl.sha256").write_text(
        hashlib.sha256((deep_dir / "scaler.pkl").read_bytes()).hexdigest()
    )
    (deep_dir / "label_encoder.pkl.sha256").write_text(
        hashlib.sha256((deep_dir / "label_encoder.pkl").read_bytes()).hexdigest()
    )
    assert eng.load_latest_deep_model("ZZUSDT") is True
    assert eng.load_latest_deep_model("ZZUSDT") is True
    assert eng.load_latest_deep_model("NOSUCH") is False


@pytest.mark.asyncio
async def test_hybrid_predict_paths(hybrid):
    eng, mod = hybrid
    from app.core.risk_manager import MarketRegime
    from sklearn.preprocessing import LabelEncoder, StandardScaler

    eng.river_config.model_type = "HoeffdingTree"
    eng.initialize_river_model("BTCUSDT")
    feats = {
        "close": 100.0,
        "volume": 1.0,
        "rsi": 50.0,
        "atr": 1.0,
        "volatility": 0.02,
        "returns": 0.01,
        "macd": 0.0,
    }
    eng.update_river_model("BTCUSDT", feats, MarketRegime.RANGE)
    # force n_samples % 100 == 0 log branch
    eng.river_metrics["BTCUSDT"].cm.n_samples = 100
    eng.update_river_model("BTCUSDT", feats, MarketRegime.RANGE)
    eng.update_river_model("NEW", feats, MarketRegime.BULL_TREND)

    short_r, short_c = eng.predict_short_regime("BTCUSDT", feats)
    assert isinstance(short_r, MarketRegime)

    # predict_one None / exception on disposable symbol
    eng.initialize_river_model("TMP1")
    eng.river_models["TMP1"].predict_one = lambda x: None
    r, c = eng.predict_short_regime("TMP1", feats)
    assert r == MarketRegime.RANGE
    eng.river_models["TMP1"].predict_one = MagicMock(side_effect=RuntimeError("x"))
    r2, _ = eng.predict_short_regime("TMP1", feats)
    assert r2 == MarketRegime.RANGE

    df = eng._klines_to_dataframe(_klines(50) + [["bad"]])
    assert not df.empty
    assert eng._klines_to_dataframe([]).empty
    assert "rsi" in df.columns
    assert eng._features_from_dataframe(pd.DataFrame())["rsi"] == 50.0
    assert eng._features_from_dataframe(df)["close"] > 0

    assert eng._infer_observed_regime(df.head(2)) == MarketRegime.RANGE
    df_hi = df.copy()
    df_hi.loc[df_hi.index[-1], "volatility"] = 0.05
    df_hi.loc[df_hi.index[0], "close"] = 200
    df_hi.loc[df_hi.index[-1], "close"] = 100
    assert eng._infer_observed_regime(df_hi) in (
        MarketRegime.HIGH_VOLATILITY_BEAR,
        MarketRegime.BEAR_TREND,
        MarketRegime.HIGH_VOL,
    )
    df_bull = df.copy()
    df_bull.loc[df_bull.index[0], "close"] = 100
    df_bull.loc[df_bull.index[-1], "close"] = 102
    df_bull["volatility"] = 0.01
    assert eng._infer_observed_regime(df_bull) == MarketRegime.BULL_TREND
    df_bear = df.copy()
    df_bear.loc[df_bear.index[0], "close"] = 100
    df_bear.loc[df_bear.index[-1], "close"] = 98
    df_bear["volatility"] = 0.01
    assert eng._infer_observed_regime(df_bear) == MarketRegime.BEAR_TREND
    df_hvol = df.copy()
    df_hvol["volatility"] = 0.05
    df_hvol.loc[df_hvol.index[0], "close"] = 100
    df_hvol.loc[df_hvol.index[-1], "close"] = 101
    assert eng._infer_observed_regime(df_hvol) == MarketRegime.HIGH_VOL
    df0 = df.copy()
    df0["close"] = 0.0
    assert eng._infer_observed_regime(df0) == MarketRegime.RANGE

    pred = await eng.predict_regime_from_klines(
        "BTCUSDT", _klines(60), train_online=True
    )
    assert pred.short_regime is not None

    # deep predict long — scaler alineado con features del DF
    eng.deep_config.sequence_length = 10
    sample = _sample_df(80)
    feature_cols = [
        c
        for c in [
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
        if c in sample.columns
    ]
    eng.scalers["BTCUSDT"] = StandardScaler().fit(sample[feature_cols].values)
    le = LabelEncoder()
    le.fit([r.value for r in MarketRegime])
    eng.label_encoders["BTCUSDT"] = le
    model = MagicMock()
    probs = np.zeros((1, len(le.classes_)))
    probs[0, list(le.classes_).index(MarketRegime.RANGE.value)] = 1.0
    model.predict.return_value = probs
    eng.deep_models["BTCUSDT"] = {
        "model": model,
        "path": eng.models_dir,
        "config": eng.deep_config,
        "last_trained": datetime.now(),
    }
    lr, lc = eng.predict_long_regime("BTCUSDT", sample)
    assert isinstance(lr, MarketRegime)

    with pytest.raises(ValueError):
        eng.predict_long_regime("NOMODEL", sample)

    with patch.object(
        eng, "_prepare_deep_data", return_value=(np.array([]), np.array([]))
    ):
        r, c = eng.predict_long_regime("BTCUSDT", sample)
        assert r == MarketRegime.RANGE

    with patch.object(eng, "_prepare_deep_data", side_effect=RuntimeError("x")):
        r, c = eng.predict_long_regime("BTCUSDT", sample)
        assert r == MarketRegime.RANGE

    combo = await eng.predict_regime("BTCUSDT", sample, feats)
    assert combo.long_conf is not None

    with patch.object(eng, "predict_long_regime", side_effect=RuntimeError("x")):
        fallback = await eng.predict_regime("BTCUSDT", sample, feats)
        assert fallback.long_regime == MarketRegime.RANGE

    # from_klines with deep model + long window
    eng.deep_config.sequence_length = 5
    pred2 = await eng.predict_regime_from_klines(
        "BTCUSDT", _klines(40), train_online=False
    )
    assert pred2.long_regime is not None

    st = eng.get_model_status("BTCUSDT")
    assert st["deep_model_loaded"] is True
    assert st["river_model_initialized"] is True
    assert st["last_prediction"] is not None
    st2 = eng.get_model_status("EMPTY")
    assert st2["deep_model_loaded"] is False

    # load_deep_model encoder hash mismatch + load when already in deep_models
    assert eng.load_latest_deep_model("BTCUSDT") is True  # already loaded


# ── performance_analyzer ─────────────────────────────────────────────────────


@pytest.fixture
def perf():
    import app.services.performance_analyzer as mod

    client = MagicMock()
    client.get_account.return_value = {
        "balances": [
            {"asset": "USDT", "free": "1000", "locked": "0"},
            {"asset": "BTC", "free": "0.01", "locked": "0"},
            {"asset": "BAD", "free": "1", "locked": "0"},
        ]
    }
    client.get_symbol_ticker.side_effect = lambda symbol=None, **k: (
        (_ for _ in ()).throw(RuntimeError("no"))
        if symbol == "BADUSDT"
        else {"price": "50000"}
    )
    client.get_historical_klines.return_value = [
        [0, "1", "2", "0.5", str(100 + i), str(1000 + i), 0, 0, 0, 0, 0, 0]
        for i in range(10)
    ]
    client.KLINE_INTERVAL_1DAY = "1d"
    mod.client = client
    return mod.PerformanceAnalyzer(), mod, client


@pytest.mark.asyncio
async def test_performance_analyzer_math_and_flows(perf):
    pa, mod, client = perf

    assert pa._calculate_total_return([100]) == 0.0
    assert pa._calculate_total_return([0, 10]) == 0.0
    assert pa._calculate_total_return([100, 110]) == pytest.approx(10.0)
    assert pa._calculate_volatility([100]) == 0.0
    assert pa._calculate_volatility([0, 0, 0]) == 0.0
    assert pa._calculate_volatility([100, 101, 102]) > 0
    assert pa._calculate_sharpe_ratio([100, 110], 0) == 0.0
    assert pa._calculate_sharpe_ratio([100, 110], 5.0) != 0
    assert pa._calculate_max_drawdown([100]) == 0.0
    assert pa._calculate_max_drawdown([100, 120, 90]) > 0

    empty = pa._calculate_trading_metrics([])
    assert empty[0] == 0.0
    win_only = pa._calculate_trading_metrics(
        [{"realized_pnl": 10}, {"realized_pnl": 5}]
    )
    assert win_only[0] == 100.0
    mixed = pa._calculate_trading_metrics(
        [{"realized_pnl": 10}, {"realized_pnl": -5}, {"realized_pnl": 0}]
    )
    assert mixed[1] == pytest.approx(2.0)

    em = pa._create_empty_metrics()
    assert em.total_trades == 0

    # portfolio history
    db = MagicMock()
    with patch.object(mod, "SessionLocal", return_value=db), patch.object(
        mod, "_snapshot_history", return_value=[100.0]
    ):
        assert await pa.get_portfolio_value_history(7) == []
    with patch.object(mod, "SessionLocal", return_value=db), patch.object(
        mod, "_snapshot_history", return_value=[100.0, 110.0, 105.0]
    ):
        vals = await pa.get_portfolio_value_history(7)
        assert len(vals) == 3
    with patch.object(mod, "SessionLocal", side_effect=RuntimeError("db")):
        assert await pa.get_portfolio_value_history(7) == []

    # trades
    row = SimpleNamespace(
        timestamp=datetime.now(timezone.utc),
        symbol="BTCUSDT",
        side="BUY",
        quantity=Decimal("0.01"),
        exit_price=Decimal("50000"),
        profit_loss=Decimal("10.5"),
    )
    q = MagicMock()
    q.filter.return_value.order_by.return_value.all.return_value = [row]
    db.query.return_value = q
    with patch.object(mod, "SessionLocal", return_value=db):
        trades = await pa.get_trade_history(30)
        assert trades[0]["realized_pnl"] == pytest.approx(10.5)
    with patch.object(mod, "SessionLocal", side_effect=RuntimeError("db")):
        assert await pa.get_trade_history(30) == []

    # current portfolio via snapshot
    latest = SimpleNamespace(
        captured_at=datetime.now(timezone.utc),
        total_value_usdt=Decimal("1234.56"),
    )
    with patch.object(mod, "SessionLocal", return_value=db), patch.object(
        mod, "get_latest_snapshot", return_value=latest
    ):
        assert await pa.get_current_portfolio_value() == pytest.approx(1234.56)

    # stale snapshot → binance
    latest.captured_at = datetime.now(timezone.utc) - timedelta(hours=1)
    with patch.object(mod, "SessionLocal", return_value=db), patch.object(
        mod, "get_latest_snapshot", return_value=latest
    ):
        val = await pa.get_current_portfolio_value()
        assert val > 0

    with patch.object(mod, "SessionLocal", side_effect=RuntimeError("db")):
        val2 = await pa.get_current_portfolio_value()
        assert val2 > 0

    mod.client.get_account.side_effect = RuntimeError("api")
    with patch.object(mod, "SessionLocal", side_effect=RuntimeError("db")):
        assert await pa.get_current_portfolio_value() == 0.0
    mod.client.get_account.side_effect = None
    mod.client.get_account.return_value = {
        "balances": [
            {"asset": "USDT", "free": "100", "locked": "0"},
            {"asset": "BTC", "free": "0.01", "locked": "0"},
            {"asset": "BAD", "free": "1", "locked": "0"},
        ]
    }

    # comprehensive
    with patch.object(
        pa, "get_portfolio_value_history", new_callable=AsyncMock, return_value=[]
    ):
        m = await pa.calculate_comprehensive_metrics(7)
        assert m.total_trades == 0
    with patch.object(
        pa,
        "get_portfolio_value_history",
        new_callable=AsyncMock,
        return_value=[100.0, 110.0, 105.0],
    ), patch.object(
        pa,
        "get_trade_history",
        new_callable=AsyncMock,
        return_value=[{"realized_pnl": 5}, {"realized_pnl": -2}],
    ), patch.object(
        pa, "get_current_portfolio_value", new_callable=AsyncMock, return_value=105.0
    ):
        m2 = await pa.calculate_comprehensive_metrics(30)
        assert m2.period_days == 30
        assert m2.winning_trades == 1
    with patch.object(
        pa,
        "get_portfolio_value_history",
        new_callable=AsyncMock,
        side_effect=RuntimeError("x"),
    ):
        m3 = await pa.calculate_comprehensive_metrics(30)
        assert m3.total_trades == 0

    asset = await pa.get_asset_performance("BTCUSDT", days=10)
    assert asset["symbol"] == "BTCUSDT"
    client.get_historical_klines.return_value = []
    assert "error" in await pa.get_asset_performance("BTCUSDT")
    client.get_historical_klines.side_effect = RuntimeError("x")
    assert "error" in await pa.get_asset_performance("BTCUSDT")
    client.get_historical_klines.side_effect = None
    client.get_historical_klines.return_value = [
        [0, "1", "2", "0.5", str(100 + i), str(1000), 0, 0, 0, 0, 0, 0]
        for i in range(5)
    ]

    alloc = await pa.get_portfolio_allocation()
    assert alloc["total_value"] > 0
    client.get_account.side_effect = RuntimeError("x")
    assert "error" in await pa.get_portfolio_allocation()
