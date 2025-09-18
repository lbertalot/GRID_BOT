from fastapi import APIRouter, HTTPException, Body, Depends
from pydantic import BaseModel
from binance import Client
import os
import json
from app.services.grid_strategy import calculate_grid_levels, decide_grid_action
from app.scheduler.grid_job import update_grid_config, get_grid_config
from app.services.binance_service import BinanceService
from app.services.order_validation import OrderValidator
from app.services.order_validation_dependency import validate_order_e2e  # E2E dependency
from sqlalchemy.orm import Session
from app.models.trade import Trade
from datetime import datetime
from app.db.session import SessionLocal
from sqlalchemy.orm import Session
from app.models.trade import Trade
from typing import List, Optional
from fastapi import Query
from app.services.telegram_alert import send_telegram_alert
from app.core.auth import require_auth
from app.schemas.validation import OrderRequest, GridParams
from app.core.precision import PrecisionNormalizer
from app.core.metrics import order_validation_rejects_total
from app.core.circuit_breakers import CircuitBreakers
from app.services.pnl_service import settle_pnl_on_sell, recompute_profit_metrics
from app.core.operation_tracker import OperationTracker, OperationStatus

router = APIRouter()
_operation_tracker = OperationTracker()

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
    timestamp: Optional[datetime] = None
) -> Trade:
    trade = Trade(
        symbol=symbol,
        side=side,
        quantity=quantity,
        entry_price=entry_price,
        exit_price=exit_price,
        profit_loss=profit_loss,
        timestamp=timestamp or datetime.utcnow()
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)
    return trade

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
            "message": "Servicio de Binance actualizado correctamente"
        }
    except Exception as e:
        # En caso de error, devolver información del servicio actual
        return {
            "status": "error",
            "error": str(e),
            "simulation_mode": binance_service.simulation_mode if hasattr(binance_service, 'simulation_mode') else True,
            "message": f"Error actualizando servicio de Binance: {str(e)}",
            "current_service_status": {
                "api_key_configured": bool(getattr(binance_service, 'api_key', None)),
                "api_secret_configured": bool(getattr(binance_service, 'api_secret', None))
            }
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
    db: Session = Depends(get_db)
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
    api_key: str = Depends(require_auth)
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
    api_key: str = Depends(require_auth)
):
    # Bloqueo por breakers (si está en modo crítico/protegido, rechazar)
    try:
        breakers = CircuitBreakers()
        summary = breakers.get_all_breakers_status()
        if summary.get('critical_mode') or summary.get('total_active', 0) > 0:
            order_validation_rejects_total.labels(reason="breaker_active", symbol=order.symbol.upper()).inc()
            raise HTTPException(status_code=503, detail="Trading bloqueado por circuit breaker activo")
    except HTTPException:
        raise
    except Exception:
        pass
    api_key_binance = os.getenv("BINANCE_API_KEY", "")
    api_secret = os.getenv("BINANCE_SECRET_KEY", "")
    client = Client(api_key_binance, api_secret)

    # Validación previa unificada (PRECIO/LOT/MIN_NOTIONAL + balance) usando dependencia E2E
    try:
        symbol = order.symbol.upper()
        current_price = None
        try:
            ticker = client.get_symbol_ticker(symbol=symbol)
            current_price = float(ticker["price"])
        except Exception:
            current_price = None

        price_for_validation = current_price if order.type == 'MARKET' else float(order.price) if order.price is not None else None
        validation = validate_order_e2e.__wrapped__(  # bypass Depends for direct call
            symbol=symbol,
            side=order.side,
            order_type=order.type,
            quantity=float(order.quantity),
            price=price_for_validation,
        )
        # Ajustar cantidad/precio recomendados
        rounded_qty = float(validation.get('recommended_quantity', order.quantity))
        order.quantity = rounded_qty
        if order.type == 'LIMIT' and validation.get('adjusted_price') is not None:
            order.price = float(validation['adjusted_price'])
    except HTTPException:
        raise
    except Exception as e:
        order_validation_rejects_total.labels(reason="validation_error", symbol=order.symbol.upper()).inc()
        raise HTTPException(status_code=400, detail=f"Error de validación previa: {e}")

    try:
        # Registrar INTENDED e idempotencia con newClientOrderId
        intended_price = float(order.price) if (order.type == 'LIMIT' and order.price) else float(current_price or 0.0)
        client_order_id = _operation_tracker.generate_client_order_id(
            asset=symbol,
            side=order.side,
            quantity=str(order.quantity),
            price=str(intended_price),
            metadata="{}",
        )
        await _operation_tracker.track_operation({
            'asset': symbol,
            'type': order.type,
            'side': order.side,
            'quantity': float(order.quantity),
            'price': intended_price,
            'metadata': {'route': 'order'}
        })

        if order.type == 'MARKET':
            if order.side == 'BUY':
                result = client.order_market_buy(symbol=order.symbol.upper(), quantity=order.quantity, newClientOrderId=client_order_id)
            elif order.side == 'SELL':
                result = client.order_market_sell(symbol=order.symbol.upper(), quantity=order.quantity, newClientOrderId=client_order_id)
            else:
                raise HTTPException(status_code=400, detail="Lado de orden inválido (debe ser BUY o SELL)")
        elif order.type == 'LIMIT':
            if not order.price:
                raise HTTPException(status_code=400, detail="Precio requerido para órdenes LIMIT")
            if order.side == 'BUY':
                result = client.order_limit_buy(symbol=order.symbol.upper(), quantity=order.quantity, price=str(order.price), timeInForce='GTC', newClientOrderId=client_order_id)
            elif order.side == 'SELL':
                result = client.order_limit_sell(symbol=order.symbol.upper(), quantity=order.quantity, price=str(order.price), timeInForce='GTC', newClientOrderId=client_order_id)
            else:
                raise HTTPException(status_code=400, detail="Lado de orden inválido (debe ser BUY o SELL)")
        else:
            raise HTTPException(status_code=400, detail="Tipo de orden inválido (debe ser MARKET o LIMIT)")

        # Marcar SUBMITTED/ACCEPTED (dependerá del flujo WS para estados subsecuentes)
        try:
            await _operation_tracker.update_operation_status(client_order_id, OperationStatus.SUBMITTED, {'exchange_status': result.get('status')})
            await _operation_tracker.update_operation_status(client_order_id, OperationStatus.ACCEPTED, {'exchange_status': result.get('status')})
        except Exception:
            pass
        # Registro en base de datos (y cálculo PnL si SELL)
        entry_price = float(result['fills'][0]['price']) if 'fills' in result and result['fills'] else 0.0
        symbol_u = order.symbol.upper()
        side_u = order.side.upper()
        qty_f = float(order.quantity)

        if side_u == 'BUY':
            log_trade(
                db=db,
                symbol=symbol_u,
                side=side_u,
                quantity=qty_f,
                entry_price=entry_price
            )
        else:
            # SELL: cerrar BUYs abiertos y registrar PnL realizado
            settle = settle_pnl_on_sell(db, symbol_u, qty_f, entry_price)
            # Recalcular métricas agregadas
            recompute_profit_metrics(db, strategy="grid")
        send_telegram_alert(f"✅ Orden ejecutada: {order.side} {order.quantity} {order.symbol} ({order.type})")
        return {"order": result}
    except Exception as e:
        send_telegram_alert(f"❌ Error ejecutando orden: {order.side} {order.quantity} {order.symbol} - {e}")
        raise HTTPException(status_code=400, detail=f"Error ejecutando orden: {e}")

@router.post("/run_grid")
def run_grid(
    params: GridParams = Body(...),
    api_key: str = Depends(require_auth)
):
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
        base_asset = params.symbol.replace("USDT", "").replace("BTC", "BTC").replace("BNB", "BNB")
        quote_asset = "USDT"
        
        # 2. Calcular niveles de la grilla
        grid_levels = calculate_grid_levels(params.min_price, params.max_price, params.grids)
        
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
                    error_msg = f"❌ Balance insuficiente para COMPRA\n" \
                               f"📊 Símbolo: {symbol}\n" \
                               f"💰 Cantidad: {quantity}\n" \
                               f"💵 Precio actual: ${current_price:.2f}\n" \
                               f"💸 Valor requerido: ${required_usdt:.2f}\n" \
                               f"💳 USDT disponible: ${available_usdt:.2f}\n" \
                               f"📉 Déficit: ${(required_usdt - available_usdt):.2f}"
                    send_telegram_alert(error_msg)
                    raise HTTPException(status_code=400, detail=f"Balance insuficiente: Necesitas ${required_usdt:.2f} USDT, tienes ${available_usdt:.2f}")
                
            elif action == "SELL":
                required_asset = quantity
                available_asset = balances.get(base_asset, 0)
                
                if available_asset < required_asset:
                    error_msg = f"❌ Balance insuficiente para VENTA\n" \
                               f"📊 Símbolo: {symbol}\n" \
                               f"💰 Cantidad requerida: {required_asset}\n" \
                               f"💳 {base_asset} disponible: {available_asset}\n" \
                               f"📉 Déficit: {(required_asset - available_asset):.6f} {base_asset}\n" \
                               f"💵 Valor estimado: ${estimated_value:.2f}"
                    send_telegram_alert(error_msg)
                    raise HTTPException(status_code=400, detail=f"Balance insuficiente: Necesitas {required_asset} {base_asset}, tienes {available_asset}")
            
            # 6. Ejecutar orden con validación mejorada
            try:
                result = order_validator.place_market_order_with_validation(symbol, action, quantity)
                
                # 7. Enviar alerta de éxito con detalles
                action_details = result['action_details']
                success_msg = f"✅ Grid Trading Exitoso\n" \
                             f"📊 Símbolo: {action_details['symbol']}\n" \
                             f"🔄 Acción: {action_details['side']}\n" \
                             f"💰 Cantidad original: {action_details['original_quantity']}\n" \
                             f"🔧 Cantidad ajustada: {action_details['adjusted_quantity']}\n" \
                             f"💵 Precio: ${action_details['current_price']:.2f}\n" \
                             f"💸 Valor: ${action_details['notional_value']:.2f}\n" \
                             f"📋 Orden ID: {result['order'].get('orderId', 'N/A')}"
                send_telegram_alert(success_msg)
                
                return {"decision": decision, "order_result": result['order'], "validation": result['validation']}
                
            except ValueError as ve:
                # Error de validación o precisión
                send_telegram_alert(str(ve))
                raise HTTPException(status_code=400, detail=str(ve))
                
        else:
            return {"decision": decision, "message": "No se ejecutó ninguna orden"}
            
    except Exception as e:
        # Manejo detallado de errores
        error_code = getattr(e, 'code', 'N/A')
        error_message = getattr(e, 'message', str(e))
        
        detailed_error = f"❌ Error en Grid Trading\n" \
                        f"📊 Símbolo: {params.symbol.upper()}\n" \
                        f"🔢 Código de error: {error_code}\n" \
                        f"📝 Mensaje: {error_message}\n" \
                        f"💰 Cantidad: {params.quantity}\n" \
                        f"📈 Precio min: ${params.min_price}\n" \
                        f"📉 Precio max: ${params.max_price}\n" \
                        f"🔗 Grids: {params.grids}"
        
        send_telegram_alert(detailed_error)
        raise HTTPException(status_code=400, detail=f"Error en grid trading: {e}")

@router.get("/grid_config")
def get_grid_config_endpoint():
    try:
        with open('grid_config_optimized.json', 'r') as f:
            config = json.load(f)
        return config
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading config: {e}")

@router.post("/grid_config")
def update_grid_config_endpoint(
    config: GridParams = Body(...),
    api_key: str = Depends(require_auth)
):
    update_grid_config(config.dict())
    return {"message": "Configuración actualizada", "config": config.dict()}
