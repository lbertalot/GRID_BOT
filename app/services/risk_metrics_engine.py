"""Motor de métricas de riesgo para GridBot v2.5.

Adaptado del playbook risk-metrics-calculation (antigravity-awesome-skills v10.2.0)
para el stack async/Decimal de GridBot.

Fuente de datos: tabla 'trades' en PostgreSQL (trades cerrados: exit_price IS NOT NULL
y profit_loss IS NOT NULL).

Factor de anualización: 365 días (crypto opera 24/7, a diferencia de los 252 días
bursátiles de los mercados tradicionales).

Tasa libre de riesgo: 0.0 por defecto. En crypto no existe una alternativa libre de
riesgo equivalente al treasury rate, por lo que el Sharpe se calcula sobre retorno bruto.

Uso típico (desde RiskManager):
    metricas = risk_metrics_engine.resumen_completo(
        db=db_session,
        portfolio_value=total_value_usdt,
        dias=90,
    )
    volatilidad = metricas["volatilidad"]
    max_dd      = metricas["max_drawdown"]
    sharpe      = metricas["sharpe_ratio"]
"""

from __future__ import annotations

import logging
from datetime import date as date_type
from datetime import datetime, timedelta
from typing import Dict, Optional

import numpy as np
import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.trade import Trade
from app.core.trace_decorator import traced

logger = logging.getLogger(__name__)

# ── Constantes globales ────────────────────────────────────────────────────────
_ANN_FACTOR: int = 365  # días/año para crypto (24/7)
_MIN_DIAS: int = 10  # mínimo de días con trades cerrados para cálculos válidos


# ── Helpers de acceso a DB ─────────────────────────────────────────────────────


def _fetch_daily_pnl_series(
    db: Session,
    dias: int = 90,
    symbol: Optional[str] = None,
) -> pd.Series:
    """Consulta la tabla 'trades' y retorna el PnL diario realizado como pd.Series.

    Solo considera trades cerrados (exit_price IS NOT NULL, profit_loss IS NOT NULL).
    Agrupa por DATE(timestamp) y suma profit_loss.

    Args:
        db:     Sesión SQLAlchemy activa. No se cierra aquí (responsabilidad del caller).
        dias:   Ventana temporal hacia atrás desde ahora (UTC).
        symbol: Si se provee, filtra por símbolo exacto (ej. 'BTCUSDT').

    Returns:
        pd.Series con índice DatetimeIndex y valores float (PnL diario en USDT).
        Retorna serie vacía si no hay datos o si ocurre un error de DB.
    """
    desde = datetime.utcnow() - timedelta(days=dias)

    query = db.query(
        func.date(Trade.timestamp).label("fecha"),
        func.sum(Trade.profit_loss).label("pnl_diario"),
    ).filter(
        Trade.profit_loss.isnot(None),
        Trade.exit_price.isnot(None),
        Trade.timestamp >= desde,
    )

    if symbol:
        query = query.filter(Trade.symbol == symbol.upper())

    try:
        rows = (
            query.group_by(func.date(Trade.timestamp))
            .order_by(func.date(Trade.timestamp).asc())
            .all()
        )
    except Exception as exc:
        logger.error("Error consultando PnL diario desde 'trades': %s", exc)
        return pd.Series(dtype=float, name="pnl_diario")

    if not rows:
        return pd.Series(dtype=float, name="pnl_diario")

    fechas = [r.fecha for r in rows]
    # profit_loss es Float en SQLAlchemy → puede llegar como float o Decimal dependiendo
    # del driver; normalizamos siempre a float nativo antes de pasarlo a numpy.
    valores = [float(r.pnl_diario) for r in rows]

    return pd.Series(valores, index=pd.to_datetime(fechas), name="pnl_diario")


# ── Motor de cálculo ───────────────────────────────────────────────────────────


class RiskMetricsEngine:
    """Motor de cálculo de métricas de riesgo usando datos reales de PostgreSQL.

    Adaptado del playbook risk-metrics-calculation (antigravity-awesome-skills v10.2.0)
    para el stack del GridBot:

    - Usa SQLAlchemy ORM síncrono (compatible con SessionLocal del proyecto).
    - Normaliza Decimal/Float a float nativo antes de cualquier operación numpy.
    - Factor de anualización 365 (crypto 24/7).
    - Retorna fallbacks seguros si no hay datos suficientes en lugar de lanzar excepciones,
      para no interrumpir el ciclo de monitoreo de riesgo.

    La clase es stateless: no almacena estado entre llamadas, lo que la hace segura
    para uso compartido como instancia global (risk_metrics_engine).
    """

    def __init__(
        self,
        rf_rate: float = 0.0,
        ann_factor: int = _ANN_FACTOR,
        min_dias: int = _MIN_DIAS,
    ) -> None:
        """
        Args:
            rf_rate:    Tasa libre de riesgo anual (0.0 para crypto).
            ann_factor: Factor de anualización (365 días para mercados 24/7).
            min_dias:   Días mínimos de datos para cálculos estadísticamente válidos.
        """
        self.rf_rate = rf_rate
        self.ann_factor = ann_factor
        self.min_dias = min_dias

    # ── Volatilidad ───────────────────────────────────────────────────────────

    def calcular_volatilidad(
        self, serie_pnl: pd.Series, portfolio_value: float
    ) -> float:
        """Volatilidad anualizada de retornos diarios: std(PnL/capital) * sqrt(365).

        Args:
            serie_pnl:       PnL diario en USDT.
            portfolio_value: Valor del portafolio en USDT (para normalizar PnL a retornos).

        Returns:
            Volatilidad anualizada como fracción (0.05 = 5%). Fallback: 0.05.
        """
        if len(serie_pnl) < self.min_dias or portfolio_value <= 0:
            return 0.05

        returns = serie_pnl / portfolio_value
        vol = float(returns.std()) * np.sqrt(self.ann_factor)

        if not np.isfinite(vol) or vol < 0:
            return 0.05
        return vol

    # ── Sharpe Ratio ──────────────────────────────────────────────────────────

    def calcular_sharpe(self, serie_pnl: pd.Series, portfolio_value: float) -> float:
        """Sharpe Ratio anualizado: (retorno_excedente_anual) / volatilidad_anual.

        Para crypto rf_rate=0.0 porque no existe alternativa libre de riesgo equivalente.
        Fórmula: (mean_diario - rf/365) / std_diario * sqrt(365).

        Args:
            serie_pnl:       PnL diario en USDT.
            portfolio_value: Valor del portafolio en USDT.

        Returns:
            Sharpe Ratio (puede ser negativo). Fallback: 0.0.
        """
        if len(serie_pnl) < self.min_dias or portfolio_value <= 0:
            return 0.0

        returns = serie_pnl / portfolio_value
        vol_diaria = float(returns.std())

        if vol_diaria == 0 or not np.isfinite(vol_diaria):
            return 0.0

        exceso_diario = float(returns.mean()) - (self.rf_rate / self.ann_factor)
        sharpe = (exceso_diario / vol_diaria) * np.sqrt(self.ann_factor)

        return float(sharpe) if np.isfinite(sharpe) else 0.0

    # ── Máximo Drawdown ───────────────────────────────────────────────────────

    def calcular_max_drawdown(self, serie_pnl: pd.Series) -> float:
        """Máximo Drawdown sobre la curva de equity acumulada (PnL acumulado).

        DD_t = (equity_max_historico_t - equity_t) / |equity_max_historico_t|
        Max DD = max(DD_t) sobre todo el período.

        Se usa PnL acumulado como proxy de equity (no requiere snapshots de balance).

        Args:
            serie_pnl: PnL diario en USDT.

        Returns:
            Max Drawdown como fracción positiva (0.10 = 10%). Fallback: 0.05.
        """
        if len(serie_pnl) < 2:
            return 0.05

        equity = serie_pnl.cumsum()
        running_max = equity.cummax()

        # Evitar división por cero cuando el running_max pasa por 0
        denom = running_max.abs().replace(0, np.nan)
        drawdowns = (equity - running_max) / denom
        drawdowns = drawdowns.fillna(0.0)

        max_dd = abs(float(drawdowns.min()))

        if not np.isfinite(max_dd) or max_dd <= 0:
            return 0.05
        return max_dd

    # ── VaR y CVaR ───────────────────────────────────────────────────────────

    def calcular_var_historico(
        self, serie_pnl: pd.Series, confianza: float = 0.95
    ) -> float:
        """VaR Histórico: pérdida máxima en un día con P(confianza) de probabilidad.

        Ejemplo: var_95=5.0 → "Con 95% de confianza no perderemos más de 5 USDT en un día".

        Usa el percentil empírico de la distribución de PnL diarios (no asume normalidad,
        lo que es importante porque los retornos de un grid bot tienen sesgo positivo
        y colas asimétricas).

        Args:
            serie_pnl: PnL diario en USDT.
            confianza: Nivel de confianza (0.95 = 95%).

        Returns:
            VaR en USDT (valor positivo = pérdida esperada). 0.0 si datos insuficientes.
        """
        if len(serie_pnl) < self.min_dias:
            return 0.0

        var_usdt = -np.percentile(serie_pnl.values, (1 - confianza) * 100)
        return float(var_usdt) if np.isfinite(var_usdt) else 0.0

    def calcular_cvar(self, serie_pnl: pd.Series, confianza: float = 0.95) -> float:
        """CVaR / Expected Shortfall: pérdida *esperada* dado que se superó el VaR.

        Captura el riesgo de cola mejor que el VaR solo. Siempre >= VaR.

        Args:
            serie_pnl: PnL diario en USDT.
            confianza: Nivel de confianza (0.95 = 95%).

        Returns:
            CVaR en USDT (valor positivo). 0.0 si datos insuficientes.
        """
        if len(serie_pnl) < self.min_dias:
            return 0.0

        var = self.calcular_var_historico(serie_pnl, confianza)
        tail = serie_pnl[serie_pnl <= -var]

        if len(tail) == 0:
            return var

        cvar = -float(tail.mean())
        return cvar if np.isfinite(cvar) else var

    # ── PnL de hoy ───────────────────────────────────────────────────────────

    def calcular_pnl_hoy(self, serie_pnl: pd.Series) -> float:
        """Extrae el PnL realizado HOY de la serie ya cargada (sin query adicional).

        Busca la entrada de hoy en el índice de la serie. Si no existe (sin trades
        cerrados hoy), retorna 0.0.

        Args:
            serie_pnl: PnL diario en USDT con índice DatetimeIndex.

        Returns:
            PnL de hoy en USDT. Negativo = pérdida. 0.0 si no hay trades hoy.
        """
        if serie_pnl.empty:
            return 0.0

        hoy = pd.Timestamp(date_type.today())
        try:
            return float(serie_pnl.get(hoy, 0.0))
        except Exception:
            return 0.0

    # ── Resumen completo (punto de entrada principal) ─────────────────────────

    @traced("risk_metrics.resumen_completo")
    def resumen_completo(
        self,
        db: Session,
        portfolio_value: float,
        dias: int = 90,
        symbol: Optional[str] = None,
    ) -> Dict:
        """Consulta la tabla 'trades' y calcula todas las métricas de riesgo.

        Diseñado para llamarse UNA SOLA VEZ por ciclo de monitoreo y cachear el resultado
        en el caller (evita múltiples queries a la DB por ciclo).

        Args:
            db:              Sesión SQLAlchemy activa. No se cierra aquí.
            portfolio_value: Valor actual del portafolio en USDT (para normalizar retornos).
            dias:            Ventana temporal de historial (default: 90 días).
            symbol:          Filtrar por símbolo (None = todos los pares activos).

        Returns:
            Dict con las siguientes claves:
                volatilidad         float  Volatilidad anualizada (fracción, 0.05=5%)
                sharpe_ratio        float  Sharpe Ratio anualizado
                max_drawdown        float  Máximo Drawdown (fracción positiva)
                var_95_usdt         float  VaR histórico 95% en USDT
                cvar_95_usdt        float  CVaR / Expected Shortfall 95% en USDT
                pnl_hoy_usdt        float  PnL realizado hoy en USDT (negativo=pérdida)
                dias_analizados     int    Días con trades cerrados encontrados
                datos_insuficientes bool   True si hay menos de min_dias días
                pnl_total_usdt      float  PnL acumulado total del período
                pnl_promedio_diario float  PnL promedio por día
        """
        serie = _fetch_daily_pnl_series(db, dias=dias, symbol=symbol)
        n = len(serie)
        insuficiente = n < self.min_dias

        if insuficiente:
            logger.warning(
                "Datos insuficientes para métricas de riesgo: %d días con trades "
                "cerrados (mínimo %d). Se usarán valores de fallback seguros.",
                n,
                self.min_dias,
            )

        return {
            "volatilidad": self.calcular_volatilidad(serie, portfolio_value),
            "sharpe_ratio": self.calcular_sharpe(serie, portfolio_value),
            "max_drawdown": self.calcular_max_drawdown(serie),
            "var_95_usdt": self.calcular_var_historico(serie, 0.95),
            "cvar_95_usdt": self.calcular_cvar(serie, 0.95),
            "pnl_hoy_usdt": self.calcular_pnl_hoy(serie),
            "dias_analizados": n,
            "datos_insuficientes": insuficiente,
            "pnl_total_usdt": float(serie.sum()) if n > 0 else 0.0,
            "pnl_promedio_diario": float(serie.mean()) if n > 0 else 0.0,
        }


# ── Instancia global reutilizable ──────────────────────────────────────────────
# rf_rate=0.0 para crypto; ann_factor=365 (mercado 24/7).
risk_metrics_engine = RiskMetricsEngine(rf_rate=0.0, ann_factor=365, min_dias=10)
