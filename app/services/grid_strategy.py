from typing import List, Dict
import numpy as np


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


def decide_grid_action(
    current_price: float, grid_levels: List[float], last_action: str = None
) -> Dict:
    """
    Decide si comprar o vender según el precio actual y la última acción.

    Cerca de un nivel (tolerancia), **alterna** respecto a ``last_action`` para
    cerrar ciclos de grid (BUY→SELL→BUY). Sin eso, precio≈nivel + last=BUY
    dejaba ``action=None`` y solo acumulaba compras.
    """
    if not grid_levels:
        return {"action": None, "level": None}

    # Ordenar niveles de menor a mayor
    sorted_levels = sorted(grid_levels)
    min_level = sorted_levels[0]
    max_level = sorted_levels[-1]

    # Si el precio está fuera del rango, no operar
    if current_price < min_level or current_price > max_level:
        return {"action": None, "level": None}

    # Encontrar el nivel más cercano al precio actual
    closest_level = min(sorted_levels, key=lambda x: abs(x - current_price))

    # Calcular tolerancia dinámica basada en la volatilidad del rango
    range_size = max_level - min_level
    tolerance = (
        range_size * 0.10
    )  # Aumentado a 10% para facilitar generación de señales

    price_diff = abs(current_price - closest_level)
    last = (last_action or "").upper() or None

    # Cerca del nivel: alternar para completar round-trip
    if price_diff <= tolerance:
        if last == "BUY":
            return {"action": "SELL", "level": closest_level}
        if last == "SELL":
            return {"action": "BUY", "level": closest_level}
        # Sin historial: lado según posición relativa al nivel
        if current_price <= closest_level:
            return {"action": "BUY", "level": closest_level}
        return {"action": "SELL", "level": closest_level}

    # Extremos del rango
    if current_price <= min_level + tolerance and last != "BUY":
        return {"action": "BUY", "level": min_level}
    if current_price >= max_level - tolerance and last != "SELL":
        return {"action": "SELL", "level": max_level}

    return {"action": None, "level": None}
