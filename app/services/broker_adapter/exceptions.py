"""Errores de la capa BrokerAdapter (venues locales y multi-exchange)."""


class BrokerCapabilityError(RuntimeError):
    """
    El venue no expone aún la operación o está fuera del alcance de la fase
    actual (p. ej. BYMA/Rofex sin conectividad).
    """
