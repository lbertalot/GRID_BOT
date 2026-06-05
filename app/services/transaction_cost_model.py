"""
Modelo central de costos de transacción (after-cost audit).

Alineado a Docs/PROTOCOL_PASSIVE_INCOME_BOT_V1_ARCHITECTURE.md §3.4 (comisión, spread, slippage).
Todas las cantidades monetarias en quote (p. ej. USDT) usan Decimal.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, Optional

import numpy as np

from app.services.commission import (
    CommissionRates,
    calculate_commission,
    get_default_commission_rates,
)

_BPS = Decimal("10000")
_QUOTE_QUANTIZE = Decimal("0.00000001")


def _bps_to_fraction(bps: Decimal) -> Decimal:
    if bps < 0:
        raise ValueError("bps no puede ser negativo")
    return bps / _BPS


@dataclass(frozen=True)
class TransactionCostAudit:
    """Desglose auditable de fricción en quote currency."""

    notional_quote: Decimal
    side: str
    order_type: str
    spread_bps: Decimal
    slippage_bps: Decimal
    commission_usdt: Decimal
    spread_cost_usdt: Decimal
    slippage_cost_usdt: Decimal
    total_friction_usdt: Decimal

    def to_serializable_dict(self) -> Dict[str, Any]:
        """Dict JSON-friendly (números como str para precisión decimal)."""
        return {
            "notional_quote": str(self.notional_quote),
            "side": self.side,
            "order_type": self.order_type,
            "spread_bps": str(self.spread_bps),
            "slippage_bps": str(self.slippage_bps),
            "commission_usdt": str(self.commission_usdt),
            "spread_cost_usdt": str(self.spread_cost_usdt),
            "slippage_cost_usdt": str(self.slippage_cost_usdt),
            "total_friction_usdt": str(self.total_friction_usdt),
        }


def compute_transaction_cost_audit(
    notional_quote: Decimal,
    order_type: str,
    side: str,
    spread_bps: Decimal,
    slippage_bps: Decimal,
    commission_rates: Optional[CommissionRates] = None,
) -> TransactionCostAudit:
    """
    Calcula comisión + coste modelado de spread + slippage sobre el notional (quote).

    El spread y el slippage se modelan como fracción adicional del notional (además de la comisión
    del exchange), coherente con auditorías after-cost del protocolo.
    """
    if notional_quote <= 0:
        raise ValueError("notional_quote debe ser positivo")
    side_u = side.upper()
    if side_u not in ("BUY", "SELL"):
        raise ValueError("side debe ser BUY o SELL")
    ot = order_type.upper()
    if ot not in ("MARKET", "LIMIT"):
        raise ValueError("order_type debe ser MARKET o LIMIT")

    rates = commission_rates or get_default_commission_rates()
    comm = calculate_commission(notional_quote, ot, rates)
    spread_frac = _bps_to_fraction(spread_bps)
    slip_frac = _bps_to_fraction(slippage_bps)
    spread_cost = (notional_quote * spread_frac).quantize(_QUOTE_QUANTIZE)
    slippage_cost = (notional_quote * slip_frac).quantize(_QUOTE_QUANTIZE)
    total_friction = (comm.commission_usdt + spread_cost + slippage_cost).quantize(
        _QUOTE_QUANTIZE
    )

    return TransactionCostAudit(
        notional_quote=notional_quote,
        side=side_u,
        order_type=ot,
        spread_bps=spread_bps,
        slippage_bps=slippage_bps,
        commission_usdt=comm.commission_usdt,
        spread_cost_usdt=spread_cost,
        slippage_cost_usdt=slippage_cost,
        total_friction_usdt=total_friction,
    )


def compute_execution_cost_sigma_proxies_from_ohlcv_arrays(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    open_: np.ndarray,
) -> tuple[float, float]:
    """
    Desviaciones empíricas (histórico de barras) para estrés §5.2.

    - Spread proxy: (high - low) / close en bps (rango intrabarra vs cierre).
    - Slippage proxy: |close - open| / open (fracción), desviación típica barra a barra.

    El estrés +2σ se aplica sobre la configuración base del backtest vía
    ``apply_two_sigma_execution_stress`` (no sustituye series reales de libro de órdenes).
    """
    h = np.asarray(high, dtype=np.float64)
    l = np.asarray(low, dtype=np.float64)
    c = np.asarray(close, dtype=np.float64)
    o = np.asarray(open_, dtype=np.float64)
    if h.shape != l.shape or h.shape != c.shape or h.shape != o.shape:
        raise ValueError("high, low, close, open deben tener la misma forma")

    close_safe = np.where(c == 0.0, np.nan, c)
    open_safe = np.where(o == 0.0, np.nan, o)
    spread_bps = (h - l) / close_safe * 10000.0
    slip_frac = np.abs(c - o) / open_safe
    spread_bps = spread_bps[np.isfinite(spread_bps)]
    slip_frac = slip_frac[np.isfinite(slip_frac)]

    sigma_spread_bps = float(np.std(spread_bps, ddof=1)) if spread_bps.size > 1 else 0.0
    sigma_slippage_fraction = (
        float(np.std(slip_frac, ddof=1)) if slip_frac.size > 1 else 0.0
    )
    return sigma_spread_bps, sigma_slippage_fraction


def apply_two_sigma_execution_stress(
    *,
    spread_bps: float,
    slippage_fraction: float,
    sigma_spread_bps: float,
    sigma_slippage_fraction: float,
) -> tuple[float, float]:
    """
    Protocolo §5.2: subir spread (bps) y slippage (fracción) en +2σ respecto a proxies históricos.
    """
    if sigma_spread_bps < 0 or sigma_slippage_fraction < 0:
        raise ValueError(
            "sigma_spread_bps y sigma_slippage_fraction no pueden ser negativos"
        )
    eff_sp = float(spread_bps) + 2.0 * float(sigma_spread_bps)
    eff_sl = float(slippage_fraction) + 2.0 * float(sigma_slippage_fraction)
    return max(0.0, eff_sp), max(0.0, eff_sl)


def vectorbt_fees_and_slippage_from_backtest_fractions(
    commission_fraction: float,
    slippage_fraction: float,
    spread_bps: float,
) -> tuple[float, float]:
    """
    Mapea comisión + slippage (fracción del notional) + spread en bps al par (fees, slippage) de vectorbt.

    Con ``spread_bps=0`` devuelve exactamente ``(commission_fraction, slippage_fraction)`` (compatibilidad).
    El spread se suma como fracción al parámetro ``slippage`` de vectorbt para mantener ``fees`` = solo comisión.
    """
    if spread_bps < 0:
        raise ValueError("spread_bps no puede ser negativo")
    extra_slippage = spread_bps / 10000.0
    return (float(commission_fraction), float(slippage_fraction) + extra_slippage)


def build_reference_transaction_cost_audit(
    reference_notional_quote: Decimal,
    commission_fraction: float,
    slippage_fraction: float,
    spread_bps: float,
    order_type: str = "MARKET",
) -> TransactionCostAudit:
    """
    Auditoría after-cost sobre un notional de referencia (p. ej. 1000 USDT) usando la misma convención
    que el backtest: comisión uniforme maker/taker y slippage en fracción → bps.
    """
    slip_bps = (Decimal(str(slippage_fraction)) * _BPS).quantize(_QUOTE_QUANTIZE)
    rates = CommissionRates(
        maker=Decimal(str(commission_fraction)),
        taker=Decimal(str(commission_fraction)),
    )
    return compute_transaction_cost_audit(
        reference_notional_quote,
        order_type,
        "BUY",
        Decimal(str(spread_bps)),
        slip_bps,
        commission_rates=rates,
    )
