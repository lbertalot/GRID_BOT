from typing import List, Dict, Optional
import numpy as np


# Fracción del spacing medio usada como tolerancia de “cerca del nivel”.
# Desk MM 2026-08-26: NO usar range_size×0.10 (≈1 spacing entero en banda ±5%).
DEFAULT_TOL_FRAC_OF_SPACING = 0.25


def calculate_grid_levels(
    min_price: float, max_price: float, grids: int
) -> List[float]:
    """
    Calcula niveles de grilla con distribución logarítmica.

    adaptive-grid-agent: reemplaza la distribución lineal original.
    La distribución log-uniforme pone más niveles en precios bajos,
    donde el PnL por movimiento porcentual es mayor, mejorando la
    captura de oscilaciones en rangos de alta volatilidad.
    """
    if grids < 2:
        raise ValueError("El número de grillas debe ser al menos 2")
    log_min = np.log(min_price)
    log_max = np.log(max_price)
    log_levels = np.linspace(log_min, log_max, grids)
    return [round(float(np.exp(l)), 8) for l in log_levels]


def _median_spacing(sorted_levels: List[float]) -> float:
    if len(sorted_levels) < 2:
        return 0.0
    gaps = [
        sorted_levels[i + 1] - sorted_levels[i] for i in range(len(sorted_levels) - 1)
    ]
    gaps_sorted = sorted(gaps)
    mid = len(gaps_sorted) // 2
    if len(gaps_sorted) % 2:
        return float(gaps_sorted[mid])
    return float((gaps_sorted[mid - 1] + gaps_sorted[mid]) / 2.0)


def _nearest_level_index(sorted_levels: List[float], price: float) -> int:
    return min(
        range(len(sorted_levels)),
        key=lambda i: abs(sorted_levels[i] - price),
    )


def decide_grid_action(
    current_price: float,
    grid_levels: List[float],
    last_action: str = None,
    last_level: Optional[float] = None,
    *,
    tol_frac_of_spacing: float = DEFAULT_TOL_FRAC_OF_SPACING,
) -> Dict:
    """
    Decide si comprar o vender según el precio actual y la última acción.

    Reglas L0 / MM (2026-08-26):
    - Tolerancia = ``tol_frac_of_spacing`` × spacing mediano (default 0.25),
      **no** ``range_size × 0.10`` (eso ≈ 1 spacing en banda ±5% y permitía
      round-trips intra-nivel que no capturan 100 bps brutos).
    - Tras BUY: SELL solo si el nivel objetivo tiene índice ≥ índice del
      ``last_level`` (o del nivel de compra) + 1 (Δnivel ≥ 1).
    - Tras SELL: BUY solo con Δnivel ≤ −1 respecto de ``last_level``.
    - Sin ``last_level`` y last=BUY/SELL: no alternar en el mismo nivel;
      esperar cruce al vecino (mismo criterio de índice usando el closest
      actual como ancla débil solo para el lado de apertura sin historial).
    """
    if not grid_levels:
        return {"action": None, "level": None}

    sorted_levels = sorted(grid_levels)
    min_level = sorted_levels[0]
    max_level = sorted_levels[-1]

    if current_price < min_level or current_price > max_level:
        return {"action": None, "level": None}

    spacing = _median_spacing(sorted_levels)
    if spacing <= 0:
        return {"action": None, "level": None}
    tol_frac = max(0.0, float(tol_frac_of_spacing))
    tolerance = spacing * tol_frac

    closest_idx = _nearest_level_index(sorted_levels, current_price)
    closest_level = sorted_levels[closest_idx]
    price_diff = abs(current_price - closest_level)
    last = (last_action or "").upper() or None

    last_idx: Optional[int] = None
    if last_level is not None:
        try:
            last_idx = _nearest_level_index(sorted_levels, float(last_level))
        except (TypeError, ValueError):
            last_idx = None

    def _near(idx: int) -> bool:
        return abs(current_price - sorted_levels[idx]) <= tolerance

    # Round-trip con memoria de nivel: exigir Δnivel ≥ 1
    if price_diff <= tolerance and last in ("BUY", "SELL"):
        if last_idx is not None:
            if last == "BUY" and closest_idx >= last_idx + 1 and _near(closest_idx):
                return {"action": "SELL", "level": closest_level}
            if last == "SELL" and closest_idx <= last_idx - 1 and _near(closest_idx):
                return {"action": "BUY", "level": closest_level}
            return {"action": None, "level": None}
        # Sin last_level: no alternar en el mismo closest; exigir vecino
        if last == "BUY" and closest_idx + 1 < len(sorted_levels):
            up = closest_idx + 1
            if current_price >= sorted_levels[up] - tolerance:
                return {"action": "SELL", "level": sorted_levels[up]}
        if last == "SELL" and closest_idx - 1 >= 0:
            down = closest_idx - 1
            if current_price <= sorted_levels[down] + tolerance:
                return {"action": "BUY", "level": sorted_levels[down]}
        return {"action": None, "level": None}

    # Sin historial: lado según posición relativa al nivel (apertura)
    if price_diff <= tolerance and last is None:
        if current_price <= closest_level:
            return {"action": "BUY", "level": closest_level}
        return {"action": "SELL", "level": closest_level}

    # Extremos del rango (con anti-repetición)
    if current_price <= min_level + tolerance and last != "BUY":
        if last == "SELL" and last_idx is not None and last_idx <= 0:
            return {"action": None, "level": None}
        return {"action": "BUY", "level": min_level}
    if current_price >= max_level - tolerance and last != "SELL":
        if last == "BUY" and last_idx is not None and last_idx >= len(sorted_levels) - 1:
            return {"action": None, "level": None}
        return {"action": "SELL", "level": max_level}

    return {"action": None, "level": None}
