from typing import List, Dict

def calculate_grid_levels(min_price: float, max_price: float, grids: int) -> List[float]:
    """Ejecuta calculate_grid_levels."""
    if grids < 2:
        raise ValueError("El número de grillas debe ser al menos 2")
    step = (max_price - min_price) / (grids - 1)
    return [round(min_price + i * step, 8) for i in range(grids)]

def decide_grid_action(current_price: float, grid_levels: List[float], last_action: str = None) -> Dict:
    """
    Decide si comprar o vender según el precio actual y la última acción.
    Retorna un dict con la acción ('BUY'/'SELL'/None) y el nivel objetivo.
    """
    for i, level in enumerate(grid_levels):
        if current_price <= level and (last_action != 'BUY'):
            return {"action": "BUY", "level": level}
        if current_price >= level and (last_action != 'SELL'):
            return {"action": "SELL", "level": level}
    return {"action": None, "level": None} 