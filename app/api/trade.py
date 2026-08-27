from fastapi import APIRouter, HTTPException, Body, Depends
from binance import Client
import asyncio
import logging
import os
import json
from app.services.grid_strategy import calculate_grid_levels, decide_grid_action
from app.scheduler.grid_job import update_grid_config
from app.services.binance_service import BinanceService
from app.services.order_validation import OrderValidator
from sqlalchemy.orm import Session
from app.models.trade import Trade
from datetime import datetime
from app.db.session import SessionLocal
from typing import Optional
from fastapi import Query
from app.services.telegram_alert import send_telegram_alert
from app.core.auth import require_auth
from app.schemas.validation import OrderRequest, GridParams
from app.core.metrics import (
    order_validation_rejects_total,
    gridbot_spot_market_submit_path_total,
)
from app.core.circuit_breakers import get_shared_breakers
from app.core.system_integrity_state import (
    SystemIntegrityOrderBlocked,
    assert_system_integrity_execution_allowed,
    system_integrity_record_from_breaker_summary,
)
from fastapi import Request
from app.services.pnl_service import settle_pnl_on_sell, recompute_profit_metrics
from app.core.operation_tracker import OperationTracker, OperationStatus
from app.models.alerts import Alert
from app.services.balance_service import BalanceService
from decimal import Decimal
from app.services.broker_adapter import use_broker_adapter_for_trade_execution_from_env
from app.services.broker_market_execution import place_spot_market_via_adapter

router = APIRouter()
_operation_tracker = OperationTracker()
logger = logging.getLogger(__name__)

# Instancia global del servicio de Binance
binance_service = BinanceService()


def log_trade(
    db: Session,
    symbol: str,
    side: str,
    quantity: float,
    entry_price: float,
    exit_price: Optional[float] = None,
    profit_loss: Optional[float] = None,
    timestamp: Optional[datetime] = None,
) -> Trade:
    trade = Trade(
        symbol=symbol,
        side=side,
        quantity=quantity,
        entry_price=entry_price,
        exit_price=exit_price,
        profit_loss=profit_loss,
        timestamp=timestamp or datetime.utcnow(),
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)
    return trade


@router.post("/controlled-write-test")
def controlled_write_test(
    api_key: str = Depends(require_auth),
):
    """
    Prueba controlada de escritura (solo en development + PAPER_TRADING).
    Inserta 1 registro en trades, balances y alerts para validar persistencia E2E.
    """
    if os.getenv("ENVIRONMENT", "").lower() != "development":
        raise HTTPException(
            status_code=403, detail="Endpoint habilitado solo en development"
        )
    if os.getenv("PAPER_TRADING", "false").lower() not in {"1", "true", "yes"}:
        raise HTTPException(
            status_code=403, detail="Endpoint requiere PAPER_TRADING=true"
        )

    marker = f"AUDIT_CTRL_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    db = SessionLocal()
    try:
        trade = log_trade(
            db=db,
            symbol=marker,
            side="BUY",
            quantity=0.001,
            entry_price=1.0,
            timestamp=datetime.utcnow(),
        )
        balance = BalanceService.update_balance(db, "AUDITCTRL", Decimal("1.00000000"))
        alert = Alert(
            type="AUDIT_WRITE_TEST",
            message=f"controlled endpoint marker={marker}",
            level="INFO",
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        return {
            "status": "ok",
            "marker": marker,
            "trade_id": trade.id,
            "balance_id": getattr(balance, "id", None),
            "alert_id": alert.id,
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Controlled write failed: {e}")
    finally:
        db.close()


@router.get("/binance_status")
def get_binance_status():
    """Endpoint para verificar el estado del servicio de Binance"""
    global binance_service

    try:
        # Crear una nueva instancia del servicio
        new_service = BinanceService()

        # Obtener precio real
        price = new_service.get_current_price("BTCUSDT")

        # Obtener información de cuenta
        account_info = new_service.get_account_info()

        # Actualizar la instancia global
        binance_service = new_service

        return {
            "status": "success",
            "simulation_mode": new_service.simulation_mode,
            "btc_price": price,
            "account_type": account_info.get("accountType", "N/A"),
            "balances_count": len(account_info.get("balances", [])),
            "api_key_configured": bool(new_service.api_key),
            "api_secret_configured": bool(new_service.api_secret),
            "message": "Servicio de Binance actualizado correctamente",
        }
    except Exception as e:
        # En caso de error, devolver información del servicio actual
        return {
            "status": "error",
            "error": str(e),
            "simulation_mode": binance_service.simulation_mode
            if hasattr(binance_service, "simulation_mode")
            else True,
            "message": f"Error actualizando servicio de Binance: {str(e)}",
            "current_service_status": {
                "api_key_configured": bool(getattr(binance_service, "api_key", None)),
                "api_secret_configured": bool(
                    getattr(binance_service, "api_secret", None)
                ),
            },
        }


@router.get("/price/{symbol}")
def get_price(symbol: str):
    try:
        price = binance_service.get_current_price(symbol.upper())
        return {"symbol": symbol.upper(), "price": price}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error consultando Binance: {e}")


@router.get("/balances")
def get_balances():
    try:
        account_info = binance_service.get_account_info()
        balances = {
            b["asset"]: float(b["free"])
            for b in account_info["balances"]
            if float(b["free"]) > 0
        }
        return balances
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error consultando balances: {e}")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/trades")
def get_trades(
    symbol: Optional[str] = Query(None, description="Filtrar por símbolo"),
    side: Optional[str] = Query(None, description="Filtrar por lado (BUY/SELL)"),
    limit: int = Query(10, ge=1, le=100, description="Número de resultados"),
    offset: int = Query(0, ge=0, description="Número de resultados a saltar"),
    db: Session = Depends(get_db),
    api_key: str = Depends(require_auth),
):
    query = db.query(Trade)
    if symbol:
        query = query.filter(Trade.symbol == symbol.upper())
    if side:
        query = query.filter(Trade.side == side.upper())
    trades = query.offset(offset).limit(limit).all()
    return trades


# Alias protegido explícito para tests: /api/trades requiere auth
@router.get("/api/trades")
def get_trades_api_protected(
    symbol: Optional[str] = Query(None),
    side: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    api_key: str = Depends(require_auth),
):
    query = db.query(Trade)
    if symbol:
        query = query.filter(Trade.symbol == symbol.upper())
    if side:
        query = query.filter(Trade.side == side.upper())
    trades = query.offset(offset).limit(limit).all()
    return trades


@router.post("/order")
async def place_order(
    order: OrderRequest = Body(...),
    db: Session = Depends(get_db),
    api_key: str = Depends(require_auth),
    request: Request = None,
):
    # Bloqueo por breakers (si está en modo crítico/protegido, rechazar)
    try:
        if request is not None:
            breakers = getattr(request.app.state, "breakers", None) or get_shared_breakers()
        else:
            breakers = get_shared_breakers()
        summary = breakers.get_all_breakers_status()

        # REDUCE_ONLY permite solamente una reserva/liquidación en el ledger PAPER.
        # Esta ruta genérica llega a Binance y por eso jamás propaga un SELL real.
        assert_system_integrity_execution_allowed(
            record=system_integrity_record_from_breaker_summary(summary),
            side=order.side,
            reduce_only=False,
            paper_only=False,
        )
        if summary.get("critical_mode") or summary.get("total_active", 0) > 0:
            order_validation_rejects_total.labels(
                reason="breaker_active", symbol=order.symbol.upper()
            ).inc()
            raise HTTPException(
                status_code=503, detail="Trading bloqueado por circuit breaker activo"
            )
    except SystemIntegrityOrderBlocked as exc:
        logger.warning("Orden bloqueada por system_integrity: %s", exc)
        raise HTTPException(
            status_code=503, detail=f"Trading bloqueado por system_integrity: {exc}"
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        # Una autorización no verificable nunca equivale a breaker cerrado.
        logger.error("No se pudo verificar circuit breakers: %s", exc)
        raise HTTPException(
            status_code=503, detail="Estado de protección no verificable"
        ) from exc
    api_key_binance = os.getenv("BINANCE_API_KEY", "")
    api_secret = os.getenv("BINANCE_SECRET_KEY", "")

    # ✅ Bug #3 Fix: Inicializar client en thread separado
    # Usar testnet si está habilitado por entorno
    use_testnet = os.getenv("BINANCE_TESTNET", "false").lower() in {"1", "true", "yes"}
    # Evita pasar flags por posición (rompe host, p.ej. api.binance.false).
    # Forzamos argumentos con nombre para respetar testnet sin alterar tld.
    client = await asyncio.to_thread(
        Client,
        api_key=api_key_binance,
        api_secret=api_secret,
        testnet=use_testnet,
    )

    # Validación previa unificada (PRECIO/LOT/MIN_NOTIONAL + balance) usando dependencia E2E
    try:
        symbol = order.symbol.upper()
        current_price: Optional[Decimal] = None
        try:
            # ✅ Bug #3 Fix: Obtener ticker en thread separado
            ticker = await asyncio.to_thread(client.get_symbol_ticker, symbol=symbol)
            current_price = Decimal(str(ticker["price"]))
        except Exception:
            current_price = None

        price_for_validation = (
            float(current_price)
            if current_price is not None and order.type == "MARKET"
            else float(Decimal(str(order.price)))
            if order.price is not None
            else None
        )
        # Validación directa en ruta (sin depender de __wrapped__).
        order_validator = OrderValidator(client)
        validation = order_validator.validate_order_parameters(
            symbol=symbol,
            quantity=float(Decimal(str(order.quantity))),
            side=order.side,
            order_type=order.type,
            price=price_for_validation,
        )
        if not validation.get("is_valid"):
            reason = "|".join(validation.get("errors", [])[:1]) or "invalid_order"
            order_validation_rejects_total.labels(reason=reason, symbol=symbol).inc()
            raise HTTPException(
                status_code=400,
                detail={
                    "status": "rejected",
                    "reason": reason,
                    "validation": validation,
                },
            )
        # Ajustar cantidad/precio recomendados — usar Decimal para precisión
        rounded_qty = Decimal(
            str(validation.get("recommended_quantity", order.quantity))
        )
        order.quantity = float(
            rounded_qty
        )  # OrderRequest espera float; Decimal ya redondeó
        if order.type == "LIMIT" and validation.get("adjusted_price") is not None:
            order.price = float(Decimal(str(validation["adjusted_price"])))
    except HTTPException:
        raise
    except Exception as e:
        order_validation_rejects_total.labels(
            reason="validation_error", symbol=order.symbol.upper()
        ).inc()
        raise HTTPException(status_code=400, detail=f"Error de validación previa: {e}")

    try:
        # Registrar INTENDED e idempotencia con newClientOrderId
        # Usar Decimal para precisión en precios financieros
        intended_price_d = (
            Decimal(str(order.price))
            if (order.type == "LIMIT" and order.price)
            else (current_price or Decimal("0"))
        )
        intended_price = float(intended_price_d)  # track_operation acepta float
        client_order_id = _operation_tracker.generate_client_order_id(
            asset=symbol,
            side=order.side,
            quantity=str(order.quantity),
            price=str(intended_price),
            metadata="{}",
        )
        await _operation_tracker.track_operation(
            {
                "asset": symbol,
                "type": order.type,
                "side": order.side,
                "quantity": float(order.quantity),
                "price": intended_price,
                "metadata": {"route": "order"},
            }
        )

        if order.type == "MARKET":
            if order.side not in ("BUY", "SELL"):
                raise HTTPException(
                    status_code=400,
                    detail="Lado de orden inválido (debe ser BUY o SELL)",
                )
            market_path: str | None = None
            if use_broker_adapter_for_trade_execution_from_env():
                try:
                    result = await place_spot_market_via_adapter(
                        symbol=order.symbol.upper(),
                        side=order.side,
                        quantity_base=float(order.quantity),
                        client_order_id=client_order_id,
                        recv_window_ms=10_000,
                        binance_wrapper=None,
                    )
                    market_path = "broker_adapter"
                except Exception as adapter_err:
                    from app.core.order_execution_guard import RealOrderBlocked

                    if isinstance(adapter_err, RealOrderBlocked):
                        raise HTTPException(
                            status_code=403,
                            detail=f"Orden real bloqueada: {adapter_err.reason}",
                        ) from adapter_err
                    if "-1021" not in str(adapter_err):
                        raise
                    market_path = None
            if market_path is None:
                from app.core.order_execution_guard import (
                    RealOrderBlocked,
                    assert_real_order_allowed,
                )

                try:
                    assert_real_order_allowed(
                        context="trade.place_order.binance_client"
                    )
                except RealOrderBlocked as blocked:
                    raise HTTPException(
                        status_code=403,
                        detail=f"Orden real bloqueada: {blocked.reason}",
                    ) from blocked
                if order.side == "BUY":
                    result = await asyncio.to_thread(
                        client.order_market_buy,
                        symbol=order.symbol.upper(),
                        quantity=order.quantity,
                        newClientOrderId=client_order_id,
                    )
                else:
                    result = await asyncio.to_thread(
                        client.order_market_sell,
                        symbol=order.symbol.upper(),
                        quantity=order.quantity,
                        newClientOrderId=client_order_id,
                    )
                market_path = "binance_client"
            gridbot_spot_market_submit_path_total.labels(
                source="http_trade", path=market_path
            ).inc()
        elif order.type == "LIMIT":
            if not order.price:
                raise HTTPException(
                    status_code=400, detail="Precio requerido para órdenes LIMIT"
                )
            from app.core.order_execution_guard import (
                RealOrderBlocked,
                assert_real_order_allowed,
            )

            try:
                assert_real_order_allowed(context="trade.place_order.limit")
            except RealOrderBlocked as blocked:
                raise HTTPException(
                    status_code=403,
                    detail=f"Orden real bloqueada: {blocked.reason}",
                ) from blocked
            if order.side == "BUY":
                result = await asyncio.to_thread(
                    client.order_limit_buy,
                    symbol=order.symbol.upper(),
                    quantity=order.quantity,
                    price=str(order.price),
                    timeInForce="GTC",
                    newClientOrderId=client_order_id,
                )
            elif order.side == "SELL":
                result = await asyncio.to_thread(
                    client.order_limit_sell,
                    symbol=order.symbol.upper(),
                    quantity=order.quantity,
                    price=str(order.price),
                    timeInForce="GTC",
                    newClientOrderId=client_order_id,
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Lado de orden inválido (debe ser BUY o SELL)",
                )
        else:
            raise HTTPException(
                status_code=400,
                detail="Tipo de orden inválido (debe ser MARKET o LIMIT)",
            )

        # Marcar SUBMITTED/ACCEPTED (dependerá del flujo WS para estados subsecuentes)
        try:
            await _operation_tracker.update_operation_status(
                client_order_id,
                OperationStatus.SUBMITTED,
                {"exchange_status": result.get("status")},
            )
            await _operation_tracker.update_operation_status(
                client_order_id,
                OperationStatus.ACCEPTED,
                {"exchange_status": result.get("status")},
            )
        except Exception:
            pass
        # Registro en base de datos (y cálculo PnL si SELL)
        # Usar Decimal para el precio de fill — es un dato financiero crítico
        entry_price = (
            float(Decimal(str(result["fills"][0]["price"])))
            if "fills" in result and result["fills"]
            else 0.0
        )
        symbol_u = order.symbol.upper()
        side_u = order.side.upper()
        qty_f = float(Decimal(str(order.quantity)))

        if side_u == "BUY":
            log_trade(
                db=db,
                symbol=symbol_u,
                side=side_u,
                quantity=qty_f,
                entry_price=entry_price,
            )
        else:
            # SELL: cerrar BUYs abiertos y registrar PnL realizado
            settle = settle_pnl_on_sell(db, symbol_u, qty_f, entry_price)
            # Recalcular métricas agregadas
            recompute_profit_metrics(db, strategy="grid")
        send_telegram_alert(
            f"✅ Orden ejecutada: {order.side} {order.quantity} {order.symbol} ({order.type})"
        )
        return {"order": result}
    except Exception as e:
        send_telegram_alert(
            f"❌ Error ejecutando orden: {order.side} {order.quantity} {order.symbol} - {e}"
        )
        raise HTTPException(status_code=400, detail=f"Error ejecutando orden: {e}")


@router.post("/run_grid")
def run_grid(params: GridParams = Body(...), api_key: str = Depends(require_auth)):
    api_key_binance = os.getenv("BINANCE_API_KEY", "")
    api_secret = os.getenv("BINANCE_SECRET_KEY", "")
    client = Client(api_key_binance, api_secret)

    # Crear validador de órdenes
    order_validator = OrderValidator(client)

    try:
        # 1. Verificar balance antes de ejecutar
        account_info = client.get_account()
        balances = {b["asset"]: float(b["free"]) for b in account_info["balances"]}

        # Extraer el asset base del símbolo (ej: BTCUSDT -> BTC)
        base_asset = (
            params.symbol.replace("USDT", "")
            .replace("BTC", "BTC")
            .replace("BNB", "BNB")
        )
        quote_asset = "USDT"

        # 2. Calcular niveles de la grilla
        grid_levels = calculate_grid_levels(
            params.min_price, params.max_price, params.grids
        )

        # 3. Obtener precio actual
        ticker = client.get_symbol_ticker(symbol=params.symbol.upper())
        current_price = float(ticker["price"])

        # 4. Decidir acción
        last_action = params.last_action or "NONE"
        decision = decide_grid_action(current_price, grid_levels, last_action)

        if decision["action"]:
            # 5. Verificar balance específico para la acción
            action = decision["action"]
            quantity = params.quantity
            symbol = params.symbol.upper()

            # Calcular valor estimado de la operación
            estimated_value = quantity * current_price

            # Verificar balance según la acción
            if action == "BUY":
                required_usdt = estimated_value
                available_usdt = balances.get(quote_asset, 0)

                if available_usdt < required_usdt:
                    error_msg = (
                        f"❌ Balance insuficiente para COMPRA\n"
                        f"📊 Símbolo: {symbol}\n"
                        f"💰 Cantidad: {quantity}\n"
                        f"💵 Precio actual: ${current_price:.2f}\n"
                        f"💸 Valor requerido: ${required_usdt:.2f}\n"
                        f"💳 USDT disponible: ${available_usdt:.2f}\n"
                        f"📉 Déficit: ${(required_usdt - available_usdt):.2f}"
                    )
                    send_telegram_alert(error_msg)
                    raise HTTPException(
                        status_code=400,
                        detail=f"Balance insuficiente: Necesitas ${required_usdt:.2f} USDT, tienes ${available_usdt:.2f}",
                    )

            elif action == "SELL":
                required_asset = quantity
                available_asset = balances.get(base_asset, 0)

                if available_asset < required_asset:
                    error_msg = (
                        f"❌ Balance insuficiente para VENTA\n"
                        f"📊 Símbolo: {symbol}\n"
                        f"💰 Cantidad requerida: {required_asset}\n"
                        f"💳 {base_asset} disponible: {available_asset}\n"
                        f"📉 Déficit: {(required_asset - available_asset):.6f} {base_asset}\n"
                        f"💵 Valor estimado: ${estimated_value:.2f}"
                    )
                    send_telegram_alert(error_msg)
                    raise HTTPException(
                        status_code=400,
                        detail=f"Balance insuficiente: Necesitas {required_asset} {base_asset}, tienes {available_asset}",
                    )

            # 6. Ejecutar orden con validación mejorada
            try:
                result = order_validator.place_market_order_with_validation(
                    symbol, action, quantity
                )

                # 7. Enviar alerta de éxito con detalles
                action_details = result["action_details"]
                success_msg = (
                    f"✅ Grid Trading Exitoso\n"
                    f"📊 Símbolo: {action_details['symbol']}\n"
                    f"🔄 Acción: {action_details['side']}\n"
                    f"💰 Cantidad original: {action_details['original_quantity']}\n"
                    f"🔧 Cantidad ajustada: {action_details['adjusted_quantity']}\n"
                    f"💵 Precio: ${action_details['current_price']:.2f}\n"
                    f"💸 Valor: ${action_details['notional_value']:.2f}\n"
                    f"📋 Orden ID: {result['order'].get('orderId', 'N/A')}"
                )
                send_telegram_alert(success_msg)

                return {
                    "decision": decision,
                    "order_result": result["order"],
                    "validation": result["validation"],
                }

            except ValueError as ve:
                # Error de validación o precisión
                send_telegram_alert(str(ve))
                raise HTTPException(status_code=400, detail=str(ve))

        else:
            return {"decision": decision, "message": "No se ejecutó ninguna orden"}

    except Exception as e:
        # Manejo detallado de errores
        error_code = getattr(e, "code", "N/A")
        error_message = getattr(e, "message", str(e))

        detailed_error = (
            f"❌ Error en Grid Trading\n"
            f"📊 Símbolo: {params.symbol.upper()}\n"
            f"🔢 Código de error: {error_code}\n"
            f"📝 Mensaje: {error_message}\n"
            f"💰 Cantidad: {params.quantity}\n"
            f"📈 Precio min: ${params.min_price}\n"
            f"📉 Precio max: ${params.max_price}\n"
            f"🔗 Grids: {params.grids}"
        )

        send_telegram_alert(detailed_error)
        raise HTTPException(status_code=400, detail=f"Error en grid trading: {e}")


@router.get("/grid_config")
def get_grid_config_endpoint(api_key: str = Depends(require_auth)):
    try:
        with open("grid_config_optimized.json", "r") as f:
            config = json.load(f)
        return config
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading config: {e}")


@router.post("/grid_config")
def update_grid_config_endpoint(
    config: GridParams = Body(...), api_key: str = Depends(require_auth)
):
    update_grid_config(config.dict())
    return {"message": "Configuración actualizada", "config": config.dict()}
