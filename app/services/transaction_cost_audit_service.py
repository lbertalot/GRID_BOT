"""
Servicio delgado: auditoría after-cost para API y herramientas (paper / simulación).
"""

from __future__ import annotations

from typing import Optional

from app.core.metrics import gridbot_transaction_cost_audit_requests_total
from app.services.commission import CommissionRates, get_default_commission_rates
from app.schemas.transaction_cost_audit import (
    TransactionCostAuditRequest,
    TransactionCostAuditResponse,
)
from app.services.transaction_cost_model import compute_transaction_cost_audit


def run_transaction_cost_audit(
    request: TransactionCostAuditRequest,
) -> TransactionCostAuditResponse:
    """
    Calcula comisión + spread + slippage sobre el notional con Decimal internamente.
    """
    commission_rates: Optional[CommissionRates] = None
    if (
        request.commission_maker_fraction is not None
        or request.commission_taker_fraction is not None
    ):
        defaults = get_default_commission_rates()
        maker = (
            request.commission_maker_fraction
            if request.commission_maker_fraction is not None
            else defaults.maker
        )
        taker = (
            request.commission_taker_fraction
            if request.commission_taker_fraction is not None
            else defaults.taker
        )
        commission_rates = CommissionRates(maker=maker, taker=taker)

    audit = compute_transaction_cost_audit(
        request.notional_quote,
        request.order_type,
        request.side,
        request.spread_bps,
        request.slippage_bps,
        commission_rates=commission_rates,
    )
    return TransactionCostAuditResponse.model_validate(audit.to_serializable_dict())


def run_transaction_cost_audit_for_api(
    request: TransactionCostAuditRequest,
) -> TransactionCostAuditResponse:
    """
    Igual que `run_transaction_cost_audit` e incrementa el contador Prometheus por petición exitosa.
    """
    result = run_transaction_cost_audit(request)
    gridbot_transaction_cost_audit_requests_total.labels(
        order_type=request.order_type
    ).inc()
    return result
