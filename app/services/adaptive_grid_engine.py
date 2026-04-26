"""
adaptive-grid-agent — Motor de grilla adaptativa para GridBot.

En lugar de usar rangos fijos (min_price, max_price hardcodeados en grid_config),
este módulo calcula rangos dinámicos centrados en el precio actual y ajusta
el número de niveles según la volatilidad del mercado.

Principio central (ATR-based grid):
  - Rango de grilla = N * ATR (Average True Range) del activo
  - Número de niveles = ajustado según régimen de mercado
  - Centro = precio actual de mercado

Integración con OptimizedGridManager:
  AdaptiveGridEngine.compute_adaptive_config() retorna un dict compatible
  con AssetConfig que el manager puede usar directamente.

Uso desde trading_tasks.py:
    from app.services.adaptive_grid_engine import adaptive_grid_engine
    new_config = adaptive_grid_engine.compute_adaptive_config("BTCUSDT", db)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import numpy as np
from sqlalchemy.orm import Session

from app.models.trade import Trade
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constantes de configuración
# ---------------------------------------------------------------------------

# Multiplicador ATR para el rango de la grilla (cuántos ATRs abarca el rango)
ATR_MULTIPLIER_DEFAULT = 3.0
ATR_MULTIPLIER_HIGH_VOL = 2.0  # En alta volatilidad, rango más estrecho
ATR_MULTIPLIER_LOW_VOL = 4.0  # En baja volatilidad, rango más amplio

# Límites de número de niveles de grilla
GRIDS_MIN = 3
GRIDS_MAX = 15
GRIDS_DEFAULT = 7

# Período en días para calcular ATR desde historial de trades
ATR_LOOKBACK_DAYS = 14

# Fallback si no hay suficientes datos
FALLBACK_RANGE_PCT = 0.04  # ±4% del precio actual


# ---------------------------------------------------------------------------
# Cálculo de volatilidad desde PnL histórico
# ---------------------------------------------------------------------------


def _estimate_atr_from_trades(
    db: Session,
    symbol: str,
    days: int = ATR_LOOKBACK_DAYS,
) -> Optional[float]:
    """
    Estima el ATR (Average True Range) desde el historial de trades cerrados.

    Como proxy del ATR usamos la desviación estándar de los precios de salida
    de los trades del símbolo en el período indicado. Esto es una aproximación
    válida cuando no se dispone de datos OHLCV locales.

    Retorna el ATR estimado en términos absolutos de precio, o None si no hay
    suficientes datos.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        db.query(Trade.exit_price)
        .filter(
            Trade.symbol == symbol.upper(),
            Trade.timestamp >= since,
            Trade.exit_price.isnot(None),
        )
        .all()
    )

    prices = [float(r.exit_price) for r in rows if r.exit_price]
    if len(prices) < 5:
        return None

    arr = np.array(prices)
    # Simulated true range: std de retornos * precio promedio ≈ ATR
    returns = np.diff(arr) / arr[:-1]
    daily_vol = float(np.std(returns))
    avg_price = float(np.mean(arr))
    return daily_vol * avg_price * np.sqrt(days)


def _detect_volatility_regime(atr: float, current_price: float) -> str:
    """
    Clasifica el régimen de volatilidad en función del ratio ATR/precio.

    Retorna: 'high', 'normal', 'low'
    """
    ratio = atr / current_price if current_price > 0 else 0
    if ratio > 0.06:
        return "high"
    if ratio < 0.02:
        return "low"
    return "normal"


# ---------------------------------------------------------------------------
# Motor principal
# ---------------------------------------------------------------------------


class AdaptiveGridEngine:
    """
    Calcula configuraciones de grilla adaptativas basadas en volatilidad real.

    Diseñado para usarse como singleton y ser llamado al inicio de cada
    ciclo de trading para revisar si la grilla necesita ajuste.
    """

    def compute_adaptive_config(
        self,
        symbol: str,
        current_price: float,
        db: Optional[Session] = None,
        atr_multiplier: float = ATR_MULTIPLIER_DEFAULT,
    ) -> Dict:
        """
        Calcula la configuración óptima de grilla para el símbolo y precio dados.

        Args:
            symbol: Par de trading (ej: "BTCUSDT")
            current_price: Precio actual del activo
            db: Sesión de SQLAlchemy (se crea una propia si es None)
            atr_multiplier: Factor de multiplicación sobre ATR para el rango

        Returns:
            Dict con keys: symbol, min_price, max_price, grids, atr, regime
            Compatible con AssetConfig de OptimizedGridManager.
        """
        own_session = db is None
        if own_session:
            db = SessionLocal()

        try:
            atr = _estimate_atr_from_trades(db, symbol)
        finally:
            if own_session:
                db.close()

        if atr is None or atr <= 0:
            # Fallback: usar ±FALLBACK_RANGE_PCT del precio actual
            half_range = current_price * FALLBACK_RANGE_PCT
            regime = "unknown"
            atr = half_range * 2
            logger.warning(
                "[AdaptiveGrid] No hay suficientes datos para %s. Usando fallback ±%.1f%%",
                symbol,
                FALLBACK_RANGE_PCT * 100,
            )
        else:
            regime = _detect_volatility_regime(atr, current_price)
            # Ajustar multiplicador según régimen
            if regime == "high":
                atr_multiplier = ATR_MULTIPLIER_HIGH_VOL
            elif regime == "low":
                atr_multiplier = ATR_MULTIPLIER_LOW_VOL
            half_range = atr * atr_multiplier / 2

        min_price = max(current_price - half_range, current_price * 0.80)
        max_price = current_price + half_range

        # Número de grillas: proporcional al rango, acotado
        range_pct = (max_price - min_price) / current_price
        grids = int(GRIDS_DEFAULT * (range_pct / 0.04))
        grids = max(GRIDS_MIN, min(GRIDS_MAX, grids))

        config = {
            "symbol": symbol,
            "min_price": round(min_price, 8),
            "max_price": round(max_price, 8),
            "grids": grids,
            "atr": round(atr, 8),
            "regime": regime,
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(
            "[AdaptiveGrid] %s | precio=%.2f | min=%.2f | max=%.2f | "
            "grids=%d | ATR=%.4f | régimen=%s",
            symbol,
            current_price,
            config["min_price"],
            config["max_price"],
            grids,
            atr,
            regime,
        )
        return config

    def should_readjust(
        self,
        symbol: str,
        current_price: float,
        current_min: float,
        current_max: float,
        threshold_pct: float = 0.30,
    ) -> bool:
        """
        Determina si la grilla actual necesita reajuste.

        Reglas de reajuste:
        1. El precio actual está fuera del rango activo.
        2. El precio está en el 30% extremo del rango (zona de riesgo de ruptura).

        Args:
            threshold_pct: Fracción del rango que activa reajuste en extremos

        Returns:
            True si se debe recomputar la grilla.
        """
        range_size = current_max - current_min
        if range_size <= 0:
            return True

        # Fuera del rango
        if current_price < current_min or current_price > current_max:
            logger.warning(
                "[AdaptiveGrid] %s fuera del rango activo (%.2f not in [%.2f, %.2f]) — reajuste requerido",
                symbol,
                current_price,
                current_min,
                current_max,
            )
            return True

        # En zona extrema del rango
        lower_band = current_min + range_size * threshold_pct
        upper_band = current_max - range_size * threshold_pct
        if current_price < lower_band or current_price > upper_band:
            logger.info(
                "[AdaptiveGrid] %s en zona extrema del rango — reajuste recomendado",
                symbol,
            )
            return True

        return False

    def compute_grid_levels(
        self, min_price: float, max_price: float, grids: int
    ) -> List[float]:
        """
        Calcula niveles de grilla con distribución logarítmica.

        La distribución log-uniforme coloca más niveles en precios bajos,
        donde hay mayor oportunidad de compra y mayor sensibilidad de PnL.
        """
        if grids < 2:
            raise ValueError("grids debe ser >= 2")

        log_min = np.log(min_price)
        log_max = np.log(max_price)
        log_levels = np.linspace(log_min, log_max, grids)
        levels = np.exp(log_levels).tolist()
        return [round(l, 8) for l in levels]


# Singleton del motor
adaptive_grid_engine = AdaptiveGridEngine()
