#!/usr/bin/env python3
"""
Script de Reactivación Gradual
GridBot V2.5 - Fase 6
"""

import sys
import os
import json
import logging
from datetime import datetime

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configurar logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def start_gradual_reactivation():
    """Inicia la reactivación gradual del sistema"""
    print("🚀 INICIANDO REACTIVACIÓN GRADUAL DEL SISTEMA")
    print("=" * 60)
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("📋 Fase 6: Reactivación Segura")

    try:
        # 1. Verificar estado del sistema
        print("\n🔍 1. VERIFICANDO ESTADO DEL SISTEMA...")

        from app.core.safety_validator import get_system_safety_status

        safety_status = get_system_safety_status()

        if not safety_status["system_safe"]:
            print("❌ Sistema no está en estado seguro para reactivación")
            print("🔧 Corregir problemas antes de continuar")
            return False

        print("✅ Sistema en estado seguro")

        # 2. Iniciar monitoreo continuo
        print("\n📊 2. INICIANDO MONITOREO CONTINUO...")

        from app.core.continuous_monitoring import start_continuous_monitoring

        if start_continuous_monitoring():
            print("✅ Monitoreo continuo iniciado")
        else:
            print("❌ Error iniciando monitoreo continuo")
            return False

        # 3. Activar paper trading con 1 asset
        print("\n📄 3. ACTIVANDO PAPER TRADING CON 1 ASSET...")

        from app.core.paper_trading import paper_trading_system
        from app.core.unified_config import get_config

        config = get_config()

        # Activar BTCUSDT para paper trading
        btc_config = config.get_asset_config("BTCUSDT")
        if btc_config:
            btc_config["is_active"] = True
            btc_config["grids"] = 5  # Configuración conservadora
            btc_config["quantity"] = 0.001
            btc_config["investment_amount"] = 100.0

            config.update_asset_config("BTCUSDT", btc_config)
            print("✅ BTCUSDT activado para paper trading")
            print(f"   Grids: {btc_config['grids']}")
            print(f"   Cantidad: {btc_config['quantity']}")
            print(f"   Inversión: ${btc_config['investment_amount']}")
        else:
            print("❌ No se pudo activar BTCUSDT")
            return False

        # 4. Ejecutar trades de prueba
        print("\n🧪 4. EJECUTANDO TRADES DE PRUEBA...")

        # Simular algunos trades para validar el sistema
        test_trades = [
            {"symbol": "BTCUSDT", "side": "BUY", "quantity": 0.001, "price": 108000},
            {"symbol": "BTCUSDT", "side": "BUY", "quantity": 0.001, "price": 107500},
            {"symbol": "BTCUSDT", "side": "SELL", "quantity": 0.001, "price": 108500},
        ]

        for i, trade in enumerate(test_trades, 1):
            print(
                f"   Trade {i}: {trade['side']} {trade['quantity']} {trade['symbol']} @ ${trade['price']}"
            )

            if trade["side"] == "BUY":
                result = paper_trading_system.place_buy_order(
                    trade["symbol"], trade["quantity"], trade["price"]
                )
            else:
                result = paper_trading_system.place_sell_order(
                    trade["symbol"], trade["quantity"], trade["price"]
                )

            if result["success"]:
                print(f"      ✅ Ejecutado: {result['order_id']}")
            else:
                print(f"      ❌ Error: {result['error']}")

        # 5. Verificar estado después de trades
        print("\n📊 5. VERIFICANDO ESTADO DESPUÉS DE TRADES...")

        portfolio = paper_trading_system.get_portfolio_summary()

        print(f"   Balance actual: ${portfolio['current_balance']:.2f}")
        print(f"   Total trades: {portfolio['total_trades']}")
        print(f"   Posiciones abiertas: {portfolio['open_positions']}")
        print(
            f"   PnL total: ${portfolio['total_pnl']:.2f} ({portfolio['total_pnl_pct']:.2f}%)"
        )

        # 6. Crear plan de monitoreo
        print("\n📋 6. CREANDO PLAN DE MONITOREO...")

        monitoring_plan = {
            "timestamp": datetime.now().isoformat(),
            "phase": "6_gradual_reactivation_started",
            "status": "active",
            "current_step": "Paper Trading con BTCUSDT",
            "next_steps": [
                {
                    "step": 1,
                    "action": "Monitoreo 24/7",
                    "description": "Monitorear sistema durante 24 horas",
                    "duration": "24 horas",
                    "criteria": "Sin pérdidas significativas, circuit breakers estables",
                },
                {
                    "step": 2,
                    "action": "Validación de Estabilidad",
                    "description": "Verificar estabilidad del sistema",
                    "duration": "48 horas",
                    "criteria": "Rendimiento consistente, sin alertas críticas",
                },
                {
                    "step": 3,
                    "action": "Activación de Más Assets",
                    "description": "Activar ETHUSDT y BNBUSDT",
                    "duration": "72 horas",
                    "criteria": "Paper trading estable con múltiples assets",
                },
                {
                    "step": 4,
                    "action": "Evaluación de Trading Real",
                    "description": "Considerar activar trading real",
                    "duration": "96 horas",
                    "criteria": "Sistema completamente estable y probado",
                },
            ],
            "safety_measures": [
                "Circuit breakers activos y monitoreados",
                "Límites de pérdida configurados",
                "Monitoreo continuo cada 30 segundos",
                "Alertas automáticas habilitadas",
                "Parada de emergencia operativa",
                "Paper trading solo (sin riesgo real)",
            ],
            "monitoring_interval": "30 segundos",
            "alert_thresholds": {
                "max_paper_trading_loss": -5.0,  # 5%
                "max_circuit_breaker_activations": 2,
                "max_system_errors": 0,
            },
        }

        # Guardar plan
        plan_file = f"monitoring_plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(plan_file, "w") as f:
            json.dump(monitoring_plan, f, indent=2)

        print(f"✅ Plan de monitoreo guardado en: {plan_file}")

        # 7. Resumen final
        print("\n" + "=" * 60)
        print("🎯 REACTIVACIÓN GRADUAL INICIADA")
        print("=" * 60)

        print("✅ Sistema verificado y seguro")
        print("✅ Monitoreo continuo activo")
        print("✅ Paper trading activado con BTCUSDT")
        print("✅ Trades de prueba ejecutados")
        print("✅ Plan de monitoreo creado")

        print("\n📊 ESTADO ACTUAL:")
        print("   Asset activo: BTCUSDT")
        print("   Modo: Paper Trading")
        print("   Monitoreo: Continuo (30s)")
        print("   Circuit breakers: Operativos")
        print("   Alertas: Habilitadas")

        print("\n⏰ PRÓXIMOS PASOS:")
        print("   1. Monitorear 24 horas")
        print("   2. Validar estabilidad")
        print("   3. Activar más assets")
        print("   4. Evaluar trading real")

        print("\n🛡️ MEDIDAS DE SEGURIDAD:")
        print("   • Solo paper trading (sin riesgo real)")
        print("   • Circuit breakers activos")
        print("   • Monitoreo continuo")
        print("   • Alertas automáticas")
        print("   • Parada de emergencia")

        return True

    except Exception as e:
        print(f"❌ Error en reactivación gradual: {e}")
        logger.error(f"Error en reactivación: {e}")
        return False


def main():
    """Función principal"""
    success = start_gradual_reactivation()

    if success:
        print("\n🎉 REACTIVACIÓN GRADUAL INICIADA EXITOSAMENTE")
        print("📊 El sistema está ahora en modo paper trading")
        print("🔄 Monitoreo continuo activo")
        print("⏰ Revisar estado en 24 horas")

        # Mostrar comandos útiles
        print("\n💡 COMANDOS ÚTILES:")
        print(
            '   • Ver estado: python -c "from app.core.continuous_monitoring import get_monitoring_summary; print(get_monitoring_summary())"'
        )
        print(
            '   • Ver portafolio: python -c "from app.core.paper_trading import get_paper_portfolio_summary; print(get_paper_portfolio_summary())"'
        )
        print(
            '   • Detener monitoreo: python -c "from app.core.continuous_monitoring import stop_continuous_monitoring; stop_continuous_monitoring()"'
        )

    else:
        print("\n❌ REACTIVACIÓN GRADUAL FALLÓ")
        print("🔧 Revisar errores antes de continuar")

    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
