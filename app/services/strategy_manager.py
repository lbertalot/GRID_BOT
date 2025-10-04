"""
Strategy Manager

Adapta parámetros de la estrategia de grid en tiempo real según:
- Señales del motor de ML (régimen de mercado)
- Detección de cambio de régimen (ADWIN en ml_engine)
- Auto-reversión ante drawdown superior a un umbral en N ciclos

Compatibilidad:
- No bloquea el loop (las llamadas a ML usan el collector asíncrono)
- Mantiene modo paper trading (solo ajusta parámetros en memoria)
- No rompe funciones actuales; integración opcional desde el GridManager
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, Optional, Any, List

from app.services.ml_engine import MLEngine


logger = logging.getLogger(__name__)


@dataclass
class AdaptationPolicy:
    bullish_grid_increment: int = 2
    bearish_grid_decrement: int = 1
    max_grids: int = 20
    min_grids: int = 2
    bullish_qty_multiplier: float = 1.15
    bearish_qty_multiplier: float = 0.85
    min_qty_multiplier: float = 0.5
    max_qty_multiplier: float = 2.0
    # Auto-reversión
    drawdown_pct_threshold: float = 0.05  # 5%
    drawdown_window: int = 10             # últimos N trades


class StrategyManager:
    """Administra la adaptación de parámetros de grid por símbolo."""

    def __init__(self, policy: Optional[AdaptationPolicy] = None, ml_engine: Optional[MLEngine] = None):
        self.policy = policy or AdaptationPolicy()
        self.ml = ml_engine or MLEngine()
        # Guardar baseline para auto-reversión: {symbol: {grids, quantity, min_price, max_price}}
        self._baseline: Dict[str, Dict[str, float]] = {}

    def _snapshot_baseline_if_needed(self, manager: Any, symbol: str) -> None:
        try:
            asset = manager.config.assets.get(symbol)
            if asset and symbol not in self._baseline:
                self._baseline[symbol] = {
                    "grids": float(asset.grids),
                    "quantity": float(asset.quantity),
                    "min_price": float(asset.min_price),
                    "max_price": float(asset.max_price),
                }
        except Exception:
            pass

    def _compute_drawdown_flag(self, manager: Any) -> Dict[str, bool]:
        """Determina por símbolo si debe activarse auto-reversión por drawdown."""
        result: Dict[str, bool] = {}
        history: List[Any] = getattr(manager, "trading_history", []) or []
        if not history:
            return result
        # Agrupar por símbolo últimos N
        by_symbol: Dict[str, List[float]] = {}
        for tr in history[-self.policy.drawdown_window:]:
            symbol = getattr(tr, "symbol", None)
            profit = getattr(tr, "profit", 0.0) or 0.0
            if not symbol:
                continue
            by_symbol.setdefault(symbol, []).append(float(profit))

        for symbol, profits in by_symbol.items():
            total = sum(profits)
            # Umbral relativo al valor absoluto de ganancias previas en ventana
            gains = sum(p for p in profits if p > 0)
            base = max(1e-6, gains)  # evitar 0
            dd = -total if total < 0 else 0.0
            result[symbol] = (dd / base) >= self.policy.drawdown_pct_threshold
        return result

    async def adapt_manager(self, manager: Any, symbols: Optional[List[str]] = None) -> Dict[str, Dict[str, float]]:
        """
        Adapta parámetros (grids, quantity) por símbolo en base a señales del modelo.
        Retorna un dict con los cambios aplicados.
        """
        if not hasattr(manager, "config") or not hasattr(manager.config, "assets"):
            return {}
        target_symbols = symbols or [a.symbol for a in manager.config.assets.values() if getattr(a, "is_active", True)]

        # Evaluar drawdown local
        dd_flags = self._compute_drawdown_flag(manager)

        changes: Dict[str, Dict[str, float]] = {}
        for symbol in target_symbols:
            asset = manager.config.assets.get(symbol)
            if not asset:
                continue
            self._snapshot_baseline_if_needed(manager, symbol)

            # Auto-reversión si aplica
            if dd_flags.get(symbol):
                base = self._baseline.get(symbol)
                if base:
                    asset.grids = int(max(self.policy.min_grids, min(self.policy.max_grids, base["grids"])))
                    asset.quantity = float(max(0.0, min(base["quantity"], base["quantity"] * self.policy.max_qty_multiplier)))
                    asset.min_price = float(base["min_price"])  # mantener rango original
                    asset.max_price = float(base["max_price"])  # mantener rango original
                    changes[symbol] = {"grids": float(asset.grids), "quantity": float(asset.quantity)}
                    logger.info(f"Auto-reversión aplicada por drawdown en {symbol}")
                    continue

            # Predicción de régimen (0: bajista, 1: alcista)
            try:
                pred = await self.ml.predict_regime(symbol, interval="1m", limit=60)
            except Exception as e:
                logger.warning(f"Predicción ML fallida para {symbol}: {e}")
                continue

            # Ajustes en base al régimen
            if pred.label == 1 and pred.proba >= 0.6:  # alcista
                new_grids = int(min(self.policy.max_grids, max(self.policy.min_grids, asset.grids + self.policy.bullish_grid_increment)))
                qty = float(asset.quantity) * self.policy.bullish_qty_multiplier
                # limitar multiplicador total respecto a baseline si existe
                base = self._baseline.get(symbol)
                if base:
                    max_qty = base["quantity"] * self.policy.max_qty_multiplier
                    qty = min(qty, max_qty)
                asset.grids = new_grids
                asset.quantity = qty
                changes[symbol] = {"grids": float(asset.grids), "quantity": float(asset.quantity)}
            elif pred.label == 0 and pred.proba >= 0.6:  # bajista con alta confianza
                new_grids = int(max(self.policy.min_grids, min(self.policy.max_grids, asset.grids - self.policy.bearish_grid_decrement)))
                qty = float(asset.quantity) * self.policy.bearish_qty_multiplier
                base = self._baseline.get(symbol)
                if base:
                    min_qty = base["quantity"] * self.policy.min_qty_multiplier
                    qty = max(qty, min_qty)
                asset.grids = new_grids
                asset.quantity = qty
                changes[symbol] = {"grids": float(asset.grids), "quantity": float(asset.quantity)}
            else:
                # Sin cambios si la confianza es baja
                continue

        return changes


# Instancia global opcional (evitar efectos en exportación de OpenAPI/CI)
import os as _os
if _os.getenv("EXPORT_OPENAPI", "0") != "1":
    strategy_manager = StrategyManager()


