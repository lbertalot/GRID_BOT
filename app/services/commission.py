"""
Servicio de comisiones refactorizado a funciones puras
Siguiendo principios de programación funcional
"""

import logging
from decimal import Decimal
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from binance import Client

logger = logging.getLogger(__name__)


@dataclass
class CommissionRates:
    """Tasas de comisión para un símbolo"""

    maker: Decimal  # ✅ FIX: Decimal en lugar de float
    taker: Decimal  # ✅ FIX: Decimal en lugar de float
    symbol: Optional[str] = None


@dataclass
class CommissionResult:
    """Resultado del cálculo de comisión"""

    commission_usdt: Decimal  # ✅ FIX: Decimal en lugar de float
    commission_percentage: Decimal  # ✅ FIX: Decimal en lugar de float
    notional_value: Decimal  # ✅ FIX: Decimal en lugar de float
    order_type: str


def get_default_commission_rates() -> CommissionRates:
    """Obtiene tasas de comisión por defecto"""
    return CommissionRates(
        maker=Decimal("0.001"),  # 0.1% - ✅ FIX: Decimal
        taker=Decimal("0.001"),  # 0.1% - ✅ FIX: Decimal
    )


def calculate_commission(
    notional_value: Decimal,  # ✅ FIX: Decimal en lugar de float
    order_type: str = "MARKET",
    commission_rates: Optional[CommissionRates] = None,
) -> CommissionResult:
    """
    Calcula comisión para una operación (función pura)

    Args:
        notional_value: Valor notional de la operación
        order_type: Tipo de orden (MARKET/LIMIT)
        commission_rates: Tasas de comisión (opcional)

    Returns:
        CommissionResult con detalles de la comisión
    """
    if notional_value <= 0:
        raise ValueError("Valor notional debe ser positivo")

    rates = commission_rates or get_default_commission_rates()
    commission_rate = rates.taker if order_type == "MARKET" else rates.maker
    commission_usdt = notional_value * commission_rate

    return CommissionResult(
        commission_usdt=round(commission_usdt, 8),  # Decimal mantiene precisión
        commission_percentage=commission_rate * Decimal("100"),  # ✅ FIX: Decimal
        notional_value=notional_value,
        order_type=order_type,
    )


def calculate_profit_with_commissions(
    buy_price: Decimal,  # ✅ FIX: Decimal en lugar de float
    sell_price: Decimal,  # ✅ FIX: Decimal en lugar de float
    quantity: Decimal,  # ✅ FIX: Decimal en lugar de float
    buy_order_type: str = "MARKET",
    sell_order_type: str = "MARKET",
    commission_rates: Optional[CommissionRates] = None,
) -> Dict[str, Decimal]:  # ✅ FIX: Decimal en lugar de float
    """
    Calcula ganancia/pérdida considerando comisiones (función pura)
    """
    if any(price <= 0 for price in [buy_price, sell_price, quantity]):
        raise ValueError("Precios y cantidad deben ser positivos")

    # Calcular valores notionales
    buy_notional = quantity * buy_price
    sell_notional = quantity * sell_price

    # Calcular comisiones
    buy_commission = calculate_commission(
        buy_notional, buy_order_type, commission_rates
    )
    sell_commission = calculate_commission(
        sell_notional, sell_order_type, commission_rates
    )

    # Calcular ganancias
    gross_profit = sell_notional - buy_notional
    total_commission = buy_commission.commission_usdt + sell_commission.commission_usdt
    net_profit = gross_profit - total_commission

    return {
        "gross_profit": gross_profit,
        "buy_commission": buy_commission.commission_usdt,
        "sell_commission": sell_commission.commission_usdt,
        "total_commission": total_commission,
        "net_profit": net_profit,
        "profit_percentage": (net_profit / buy_notional * Decimal("100"))
        if buy_notional > 0
        else Decimal("0"),  # ✅ FIX: Decimal
    }


def validate_minimum_profit(
    buy_price: Decimal,  # ✅ FIX: Decimal en lugar de float
    sell_price: Decimal,  # ✅ FIX: Decimal en lugar de float
    quantity: Decimal,  # ✅ FIX: Decimal en lugar de float
    min_profit_percentage: Decimal = Decimal("0.5"),  # ✅ FIX: Decimal
    buy_order_type: str = "MARKET",
    sell_order_type: str = "MARKET",
    commission_rates: Optional[CommissionRates] = None,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Valida si una operación generará ganancia mínima (función pura)
    """
    profit_data = calculate_profit_with_commissions(
        buy_price,
        sell_price,
        quantity,
        buy_order_type,
        sell_order_type,
        commission_rates,
    )

    is_profitable = profit_data["profit_percentage"] >= min_profit_percentage

    return is_profitable, profit_data


# Función para actualizar tasas desde Binance (opcional)
async def update_commission_rates_from_binance(
    api_key: str, api_secret: str
) -> Optional[CommissionRates]:
    """
    Actualiza tasas de comisión desde Binance (función pura)
    """
    try:
        import asyncio

        client = Client(api_key, api_secret)

        # ✅ FIX: Obtener account info (non-blocking)
        account_info = await asyncio.to_thread(client.get_account)

        # ✅ FIX: Usar Decimal para precisión financiera
        maker_commission = Decimal(
            str(account_info.get("makerCommission", 15))
        ) / Decimal("10000")
        taker_commission = Decimal(
            str(account_info.get("takerCommission", 15))
        ) / Decimal("10000")

        return CommissionRates(maker=maker_commission, taker=taker_commission)
    except Exception as e:
        logger.warning(f"No se pudieron actualizar comisiones desde Binance: {e}")
        return None
