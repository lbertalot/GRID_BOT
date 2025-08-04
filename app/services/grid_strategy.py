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
    Lógica optimizada para ser más sensible a los precios actuales.
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
    tolerance = range_size * 0.05  # Aumentado a 5% de tolerancia para mayor sensibilidad
    
    # Determinar la acción basada en la posición del precio respecto al nivel más cercano
    price_diff = abs(current_price - closest_level)
    
    # Si el precio está muy cerca del nivel (dentro de la tolerancia), generar señal
    if price_diff <= tolerance:
        # Determinar dirección basada en la posición del precio
        if current_price <= closest_level:
            # Precio en o por debajo del nivel -> SEÑAL DE COMPRA
            if last_action != 'BUY':
                return {"action": "BUY", "level": closest_level}
        else:
            # Precio por encima del nivel -> SEÑAL DE VENTA
            if last_action != 'SELL':
                return {"action": "SELL", "level": closest_level}
    
    # Verificar si el precio está en un extremo del rango (lógica adicional)
    if current_price <= min_level + tolerance and last_action != 'BUY':
        return {"action": "BUY", "level": min_level}
    elif current_price >= max_level - tolerance and last_action != 'SELL':
        return {"action": "SELL", "level": max_level}
    
    return {"action": None, "level": None} 