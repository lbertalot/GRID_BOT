"""Backfill idempotente del export JSON al ledger PostgreSQL paper."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from sqlalchemy.orm import Session

from app.models.paper_ledger import (
    PaperLedgerAccount,
    PaperLedgerCycle,
    PaperLedgerEquitySample,
    PaperLedgerFill,
    PaperLedgerFillCycle,
    PaperLedgerIntent,
)


class PaperLedgerBackfillError(ValueError):
    """El export no puede asentarse íntegramente y se rechaza."""


def _decimal(value: Any, field: str) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise PaperLedgerBackfillError(f"{field} debe serializarse como Decimal/string")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise PaperLedgerBackfillError(f"{field} inválido") from exc
    if not result.is_finite() or abs(result.as_tuple().exponent) > 12:
        raise PaperLedgerBackfillError(f"{field} inválido")
    return result


def _timestamp(value: Any, field: str) -> datetime:
    try:
        result = datetime.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise PaperLedgerBackfillError(f"{field} inválido") from exc
    if result.tzinfo is None:
        raise PaperLedgerBackfillError(f"{field} debe incluir zona horaria")
    return result.astimezone(timezone.utc)


def _sample_id(sample: Mapping[str, Any]) -> str:
    raw = "|".join(str(sample.get(key, "")) for key in ("at", "equity", "cash", "inventory_value"))
    return hashlib.sha256(raw.encode()).hexdigest()


def _same_value(left: Any, right: Any) -> bool:
    if isinstance(left, datetime) and isinstance(right, datetime):
        return left.astimezone(timezone.utc) == right.astimezone(timezone.utc)
    return left == right


def validate_payload(payload: Mapping[str, Any]) -> None:
    if payload.get("schema_version") != 1 or payload.get("quote_asset") != "USDT":
        raise PaperLedgerBackfillError("schema/version de ledger no soportado")
    cycles = payload.get("cycles")
    fills = payload.get("fills")
    if not isinstance(cycles, list) or not isinstance(fills, list):
        raise PaperLedgerBackfillError("cycles/fills inválidos")
    cycle_ids = {str(c.get("cycle_id")) for c in cycles if isinstance(c, Mapping)}
    if len(cycle_ids) != len(cycles) or "" in cycle_ids:
        raise PaperLedgerBackfillError("cycle_id duplicado o inválido")
    fill_ids = {str(f.get("fill_id")) for f in fills if isinstance(f, Mapping)}
    if len(fill_ids) != len(fills) or "" in fill_ids:
        raise PaperLedgerBackfillError("fill_id duplicado o inválido")
    for cycle in cycles:
        if not isinstance(cycle, Mapping):
            raise PaperLedgerBackfillError("cycle inválido")
        quantity = _decimal(cycle.get("buy_quantity"), "buy_quantity")
        open_quantity = _decimal(cycle.get("open_quantity"), "open_quantity")
        if quantity <= 0 or open_quantity < 0 or open_quantity > quantity:
            raise PaperLedgerBackfillError("cantidad de ciclo inválida")
        _timestamp(cycle.get("opened_at"), "opened_at")
        if open_quantity == 0 and cycle.get("closed_at") is None:
            raise PaperLedgerBackfillError("ciclo cerrado sin closed_at")
        if open_quantity > 0 and cycle.get("closed_at") is not None:
            raise PaperLedgerBackfillError("ciclo abierto con closed_at")
    for fill in fills:
        if not isinstance(fill, Mapping):
            raise PaperLedgerBackfillError("fill inválido")
        ids = tuple(fill.get("cycle_ids") or (fill.get("cycle_id"),))
        if not ids or any(str(cycle_id) not in cycle_ids for cycle_id in ids):
            raise PaperLedgerBackfillError("fill referencia un ciclo inexistente")
        if len(ids) != 1:
            raise PaperLedgerBackfillError("fill multi-ciclo no reconstruible de forma segura")
        if str(fill.get("side")).upper() not in {"BUY", "SELL"}:
            raise PaperLedgerBackfillError("lado de fill inválido")
        if _decimal(fill.get("quantity"), "fill.quantity") <= 0 or _decimal(fill.get("price"), "fill.price") <= 0:
            raise PaperLedgerBackfillError("importe de fill inválido")
        _timestamp(fill.get("executed_at"), "fill.executed_at")


def backfill_payload(
    db: Session, *, ledger: Mapping[str, Any], series: Mapping[str, Any], window_id: str, source_sha256: str
) -> dict[str, int]:
    """Inserta el snapshot completo; duplicados idénticos son un no-op.

    El llamador debe ejecutar commit o rollback para conservar una única transacción.
    """
    validate_payload(ledger)
    if not window_id or len(source_sha256) != 64:
        raise PaperLedgerBackfillError("window_id/source_sha256 inválido")
    account = db.get(PaperLedgerAccount, window_id)
    canonical = json.dumps(ledger["cost_model"], sort_keys=True, separators=(",", ":"))
    account_values = {
        "schema_version": 1, "quote_asset": "USDT", "initial_cash": _decimal(ledger["initial_cash"], "initial_cash"),
        "cash": _decimal(ledger["cash"], "cash"), "deployed_capital": _decimal(ledger["deployed_capital"], "deployed_capital"),
        "realized_gross_pnl_usdt": _decimal(ledger["realized_gross_pnl_usdt"], "realized_gross_pnl_usdt"),
        "realized_net_pnl_usdt": _decimal(ledger["realized_net_pnl_usdt"], "realized_net_pnl_usdt"),
        "fees_total_usdt": _decimal(ledger["fees_total_usdt"], "fees_total_usdt"),
        "slippage_total_usdt": _decimal(ledger["slippage_total_usdt"], "slippage_total_usdt"),
        "cost_model_json": canonical, "created_at": _timestamp(ledger["created_at"], "created_at"),
        "updated_at": _timestamp(ledger["updated_at"], "updated_at"),
    }
    if account is None:
        db.add(PaperLedgerAccount(window_id=window_id, **account_values))
    elif any(
        not _same_value(getattr(account, key), value)
        for key, value in account_values.items()
    ):
        raise PaperLedgerBackfillError("cuenta preexistente difiere del export")
    inserted = {"cycles": 0, "intents": 0, "fills": 0, "samples": 0}
    for item in ledger["cycles"]:
        cycle_id = str(item["cycle_id"])
        if db.get(PaperLedgerCycle, cycle_id) is not None:
            continue
        db.add(PaperLedgerCycle(
            cycle_id=cycle_id, symbol=str(item["symbol"]).upper(), grid_level=Decimal(str(item.get("grid_level"))) if item.get("grid_level") is not None else None,
            buy_price=_decimal(item["buy_price"], "buy_price"), buy_quantity=_decimal(item["buy_quantity"], "buy_quantity"),
            open_quantity=_decimal(item["open_quantity"], "open_quantity"),
            cost_basis_open_usdt=_decimal(item["buy_price"], "buy_price") * _decimal(item["open_quantity"], "open_quantity") + _decimal(item["buy_fee_remaining"], "buy_fee_remaining") + _decimal(item["buy_slippage_remaining"], "buy_slippage_remaining"),
            opened_at=_timestamp(item["opened_at"], "opened_at"), closed_at=_timestamp(item["closed_at"], "closed_at") if item.get("closed_at") else None,
            **{key: _decimal(item.get(key, "0"), key) for key in ("buy_fee_usdt", "buy_slippage_usdt", "buy_fee_remaining", "buy_slippage_remaining", "closed_quantity", "sell_notional_usdt", "gross_pnl_usdt", "net_pnl_usdt", "fees_usdt", "slippage_usdt")},
        ))
        inserted["cycles"] += 1
    db.flush()
    for item in ledger["fills"]:
        fill_id = str(item["fill_id"])
        if db.get(PaperLedgerFill, fill_id) is not None:
            continue
        intent_id = f"json-{fill_id}"
        db.add(PaperLedgerIntent(intent_id=intent_id, client_order_id=intent_id, symbol=str(item["symbol"]).upper(), side=str(item["side"]).upper(), state="FILLED", created_at=_timestamp(item["executed_at"], "executed_at")))
        db.flush()
        db.add(PaperLedgerFill(fill_id=fill_id, intent_id=intent_id, cycle_id=str(item["cycle_id"]), side=str(item["side"]).upper(), quantity=_decimal(item["quantity"], "quantity"), price=_decimal(item["price"], "price"), executed_at=_timestamp(item["executed_at"], "executed_at"), symbol=str(item["symbol"]).upper(), order_type=str(item["order_type"]).upper(), notional_usdt=_decimal(item["notional_usdt"], "notional_usdt"), commission_usdt=_decimal(item["commission_usdt"], "commission_usdt"), slippage_usdt=_decimal(item["slippage_usdt"], "slippage_usdt"), grid_level=Decimal(str(item["grid_level"])) if item.get("grid_level") is not None else None))
        for cycle_id in tuple(item.get("cycle_ids") or (item["cycle_id"],)):
            db.add(PaperLedgerFillCycle(fill_id=fill_id, cycle_id=str(cycle_id), quantity=_decimal(item["quantity"], "quantity")))
        inserted["intents"] += 1
        inserted["fills"] += 1
    for item in series.get("samples", []):
        if not isinstance(item, Mapping):
            raise PaperLedgerBackfillError("sample inválido")
        sample_id = _sample_id(item)
        if db.get(PaperLedgerEquitySample, sample_id) is None:
            db.add(PaperLedgerEquitySample(sample_id=sample_id, at=_timestamp(item["at"], "sample.at"), equity=_decimal(item["equity"], "sample.equity"), cash=_decimal(item["cash"], "sample.cash"), inventory_value=_decimal(item["inventory_value"], "sample.inventory_value"), deployed_capital=_decimal(item["deployed_capital"], "sample.deployed_capital"), config_hash=item.get("config_hash"), daily_close_at=_timestamp(item["daily_close_at"], "daily_close_at") if item.get("daily_close_at") else None))
            inserted["samples"] += 1
    return inserted
