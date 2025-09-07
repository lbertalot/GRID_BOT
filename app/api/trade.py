from fastapi import APIRouter, HTTPException, Body, Depends
from pydantic import BaseModel
from binance import Client
import os
import json
from app.services.grid_strategy import calculate_grid_levels, decide_grid_action
from app.scheduler.grid_job import update_grid_config, get_grid_config
from app.services.binance_service import BinanceService
from app.services.order_validation import OrderValidator
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

router = APIRouter()

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

@router.post("/order")
def place_order(
    order: OrderRequest = Body(...), 
    db: Session = Depends(get_db),
    api_key: str = Depends(require_auth)
):
    api_key_binance = os.getenv("BINANCE_API_KEY", "")
    api_secret = os.getenv("BINANCE_API_SECRET", "")
    client = Client(api_key_binance, api_secret)

    # Validación previa (precisión, notional, fondos)
    try:
        normalizer = PrecisionNormalizer(client)
        symbol = order.symbol.upper()
        # Precio actual para MARKET; si LIMIT usar order.price
        ticker = client.get_symbol_ticker(symbol=symbol)
        current_price = float(ticker["price"])
        price_for_validation = current_price if order.type == 'MARKET' else float(order.price)
        rounded_price = normalizer.round_price(symbol, price_for_validation)
        rounded_qty = normalizer.round_quantity(symbol, float(order.quantity))
        if not normalizer.validate_notional(symbol, rounded_price, rounded_qty):
            order_validation_rejects_total.labels(reason="min_notional", symbol=symbol).inc()
            raise HTTPException(status_code=400, detail=f"Valor notional insuficiente: {rounded_price*rounded_qty:.6f} < minNotional")
        # Balance suficiente (BUY: USDT; SELL: base)
        account = client.get_account()
        balances = {b['asset']: float(b['free']) for b in account.get('balances', [])}
        if order.side.upper() == 'BUY':
            need_usdt = rounded_price * rounded_qty
            have_usdt = balances.get('USDT', 0.0)
            if have_usdt + 1e-9 < need_usdt:
                order_validation_rejects_total.labels(reason="insufficient_usdt", symbol=symbol).inc()
                raise HTTPException(status_code=400, detail=f"USDT insuficiente: requiere {need_usdt:.6f}, disponible {have_usdt:.6f}")
        else:
            base_asset = symbol.replace('USDT', '')
            have_base = balances.get(base_asset, 0.0)
            if have_base + 1e-12 < rounded_qty:
                order_validation_rejects_total.labels(reason="insufficient_asset", symbol=symbol).inc()
                raise HTTPException(status_code=400, detail=f"{base_asset} insuficiente: requiere {rounded_qty:.8f}, disponible {have_base:.8f}")
        # Sobrescribir cantidad/precio redondeados si aplica
        order.quantity = rounded_qty
        if order.type == 'LIMIT':
            order.price = rounded_price
    except HTTPException:
        raise
    except Exception as e:
        order_validation_rejects_total.labels(reason="validation_error", symbol=order.symbol.upper()).inc()
        raise HTTPException(status_code=400, detail=f"Error de validación previa: {e}")

    try:
        if order.type == 'MARKET':
            if order.side == 'BUY':
                result = client.order_market_buy(symbol=order.symbol.upper(), quantity=order.quantity)
            elif order.side == 'SELL':
                result = client.order_market_sell(symbol=order.symbol.upper(), quantity=order.quantity)
            else:
                raise HTTPException(status_code=400, detail="Lado de orden inválido (debe ser BUY o SELL)")
        elif order.type == 'LIMIT':
            if not order.price:
                raise HTTPException(status_code=400, detail="Precio requerido para órdenes LIMIT")
            if order.side == 'BUY':
                result = client.order_limit_buy(symbol=order.symbol.upper(), quantity=order.quantity, price=str(order.price), timeInForce='GTC')
            elif order.side == 'SELL':
                result = client.order_limit_sell(symbol=order.symbol.upper(), quantity=order.quantity, price=str(order.price), timeInForce='GTC')
            else:
                raise HTTPException(status_code=400, detail="Lado de orden inválido (debe ser BUY o SELL)")
        else:
            raise HTTPException(status_code=400, detail="Tipo de orden inválido (debe ser MARKET o LIMIT)")
        # Registro en base de datos
        entry_price = float(result['fills'][0]['price']) if 'fills' in result and result['fills'] else 0.0
        log_trade(
            db=db,
            symbol=order.symbol.upper(),
            side=order.side,
            quantity=order.quantity,
            entry_price=entry_price
        )
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
    api_secret = os.getenv("BINANCE_API_SECRET", "")
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
