from fastapi import APIRouter

# from app.core.metrics import get_trading_metrics, get_binance_metrics, get_strategy_metrics
from binance import Client
import os
from dotenv import load_dotenv
from fastapi.responses import Response
from prometheus_client import generate_latest

router = APIRouter()


@router.get("/metrics")
async def prometheus_metrics():
    """Endpoint principal para métricas de Prometheus"""
    try:
        try:
            from app.core.obs_gauges import publish_obs_gauges

            publish_obs_gauges()
        except Exception:
            pass
        try:
            from app.core.pipeline_metrics_sidecar import hydrate_pipeline_counters

            hydrate_pipeline_counters()
        except Exception:
            pass
        try:
            from app.core.breaker_visibility import get_breaker_visibility_snapshot

            get_breaker_visibility_snapshot()
        except Exception:
            pass
        # Generar métricas de Prometheus directamente
        metrics_content = generate_latest()

        return Response(content=metrics_content, media_type="text/plain")

    except Exception as e:
        return {"error": f"Error generando métricas: {str(e)}"}


@router.get("/trading")
async def prometheus_trading_metrics():
    """Métricas de trading para Prometheus (sin autenticación)"""
    try:
        from prometheus_client import generate_latest

        # Generar métricas de Prometheus directamente
        metrics_content = generate_latest()

        return Response(content=metrics_content, media_type="text/plain")

    except Exception as e:
        return {"error": f"Error generando métricas: {str(e)}"}


@router.get("/binance")
async def prometheus_binance_metrics():
    """Métricas de Binance para Prometheus (sin autenticación)"""
    # return get_binance_metrics()
    return {"error": "Métricas no disponibles"}


@router.get("/strategies")
async def prometheus_strategy_metrics():
    """Métricas de estrategias para Prometheus (sin autenticación)"""
    # return get_strategy_metrics()
    return {"error": "Métricas no disponibles"}


@router.get("/pnl")
async def prometheus_pnl_metrics():
    """Métricas de P&L para Prometheus (sin autenticación)"""
    try:
        # Generar métricas de Prometheus directamente
        metrics_content = generate_latest()

        return Response(content=metrics_content, media_type="text/plain")

    except Exception as e:
        return {"error": f"Error generando métricas: {str(e)}"}


from fastapi import Depends
from app.core.auth import require_auth


@router.post("/update-pnl")
async def update_pnl_metrics(api_key: str = Depends(require_auth)):
    """Actualizar métricas de P&L en tiempo real (protegido)"""
    try:
        import asyncio

        # Cargar variables de entorno
        load_dotenv()
        api_key = os.getenv("BINANCE_API_KEY")
        api_secret = os.getenv("BINANCE_SECRET_KEY")

        if not api_key or not api_secret:
            return {"error": "Credenciales de Binance no configuradas"}

        # Conectar a Binance
        client = Client(api_key, api_secret)

        # ✅ FIX: Obtener información de la cuenta (non-blocking)
        account = await asyncio.to_thread(client.get_account)

        # Calcular valor total del portfolio
        total_value_usdt = 0.0
        asset_values = {}

        for balance in account["balances"]:
            asset = balance["asset"]
            free = float(balance["free"])
            locked = float(balance["locked"])
            total = free + locked

            if total > 0:
                if asset == "USDT":
                    value_usdt = total
                elif asset == "BUSD":
                    value_usdt = total  # BUSD ≈ USDT
                else:
                    # ✅ FIX: Obtener precio en USDT (non-blocking)
                    try:
                        ticker = await asyncio.to_thread(
                            client.get_symbol_ticker, symbol=f"{asset}USDT"
                        )
                        price_usdt = float(ticker["price"])
                        value_usdt = total * price_usdt
                    except:
                        value_usdt = 0.0

                asset_values[asset] = {"amount": total, "value_usdt": value_usdt}
                total_value_usdt += value_usdt

        # Calcular P&L aproximado (asumiendo que empezaste con $100)
        initial_investment = 100.0  # Ajusta según tu inversión inicial
        pnl_absolute = total_value_usdt - initial_investment
        pnl_percentage = (
            (pnl_absolute / initial_investment * 100) if initial_investment > 0 else 0.0
        )

        # Determinar estado de trading
        status = 2 if pnl_absolute > 0 else 0 if pnl_absolute < 0 else 1

        # Ordenar assets por valor
        sorted_assets = sorted(
            asset_values.items(), key=lambda x: x[1]["value_usdt"], reverse=True
        )
        top_assets = []

        for asset, data in sorted_assets[:5]:  # Top 5
            if data["value_usdt"] > 1.0:
                top_assets.append(
                    {
                        "asset": asset,
                        "amount": data["amount"],
                        "value_usdt": data["value_usdt"],
                    }
                )

        return {
            "success": True,
            "data": {
                "total_value_usdt": total_value_usdt,
                "pnl_absolute": pnl_absolute,
                "pnl_percentage": pnl_percentage,
                "trading_status": status,
                "status_text": "GANANDO"
                if status == 2
                else "PERDIENDO"
                if status == 0
                else "NEUTRAL",
                "top_assets": top_assets,
                "initial_investment": initial_investment,
            },
        }

    except Exception as e:
        return {"error": f"Error calculando P&L: {str(e)}"}
