from typing import Protocol, Dict, Any

class Strategy(Protocol):
    def __call__(self, *, price_history: list[float], balances: dict[str, float], params: dict[str, Any]) -> dict:
        ...

# Ejemplo de respuesta estándar:
# {
#   'action': 'BUY' | 'SELL' | 'HOLD',
#   'quantity': float,
#   'reason': str,
#   'extra': dict (opcional)
# } 