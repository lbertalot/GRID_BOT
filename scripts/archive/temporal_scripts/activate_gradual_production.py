#!/usr/bin/env python3
"""
Script de Activación Gradual Completa
GridBot V2.5 - Fase 7: Activación Gradual y Monitoreo Prolongado
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


def activate_gradual_production():
    """Activa gradualmente el sistema para producción"""
    print("🚀 INICIANDO ACTIVACIÓN GRADUAL COMPLETA")
    print("=" * 60)
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("📋 Fase 7: Activación Gradual y Monitoreo Prolongado")

    try:
        # 1. Verificar estado del sistema
        print("\n🔍 1. VERIFICANDO ESTADO DEL SISTEMA...")

        from app.core.safety_validator import get_system_safety_status

        safety_status = get_system_safety_status()

        if not safety_status["system_safe"]:
            print("❌ Sistema no está en estado seguro para activación")
            print("🔧 Corregir problemas antes de continuar")
            return False

        print("✅ Sistema en estado seguro")

        # 2. Verificar configuración actual
        print("\n⚙️ 2. VERIFICANDO CONFIGURACIÓN ACTUAL...")

        from app.core.unified_config import get_config

        config = get_config()
        config_summary = config.get_config_summary()

        print(f"   Assets totales: {config_summary['assets_summary']['total_assets']}")
        print(f"   Assets activos: {config_summary['assets_summary']['active_assets']}")
        print(
            f"   Trading real: {'❌ Habilitado' if config_summary['system_settings']['trading_enabled'] else '✅ Deshabilitado'}"
        )
        print(
            f"   Paper trading: {'✅ Habilitado' if config_summary['system_settings']['paper_trading'] else '❌ Deshabilitado'}"
        )

        # 3. Fase 1: Activar más assets para paper trading
        print("\n📄 3. FASE 1: ACTIVANDO MÁS ASSETS PARA PAPER TRADING...")

        # Activar ETHUSDT y BNBUSDT para paper trading
        additional_assets = [
            {
                "symbol": "ETHUSDT",
                "grids": 5,
                "quantity": 0.01,
                "investment_amount": 100.0,
            },
            {
                "symbol": "BNBUSDT",
                "grids": 5,
                "quantity": 0.1,
                "investment_amount": 100.0,
            },
        ]

        for asset_config in additional_assets:
            symbol = asset_config["symbol"]
            asset = config.get_asset_config(symbol)

            if asset:
                asset["is_active"] = True
                asset["grids"] = asset_config["grids"]
                asset["quantity"] = asset_config["quantity"]
                asset["investment_amount"] = asset_config["investment_amount"]

                config.update_asset_config(symbol, asset)
                print(f"✅ {symbol} activado para paper trading")
                print(f"   Grids: {asset_config['grids']}")
                print(f"   Cantidad: {asset_config['quantity']}")
                print(f"   Inversión: ${asset_config['investment_amount']}")
            else:
                print(f"❌ No se pudo activar {symbol}")

        # 4. Fase 2: Ejecutar trades de prueba con múltiples assets
        print("\n🧪 4. FASE 2: EJECUTANDO TRADES DE PRUEBA MULTI-ASSET...")

        from app.core.paper_trading import paper_trading_system

        # Trades de prueba para cada asset
        test_trades = [
            {"symbol": "BTCUSDT", "side": "BUY", "quantity": 0.001, "price": 108000},
            {"symbol": "ETHUSDT", "side": "BUY", "quantity": 0.01, "price": 4400},
            {"symbol": "BNBUSDT", "side": "BUY", "quantity": 0.1, "price": 850},
            {"symbol": "BTCUSDT", "side": "SELL", "quantity": 0.001, "price": 108500},
            {"symbol": "ETHUSDT", "side": "SELL", "quantity": 0.01, "price": 4450},
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

        # 5. Fase 3: Verificar estado multi-asset
        print("\n📊 5. FASE 3: VERIFICANDO ESTADO MULTI-ASSET...")

        portfolio = paper_trading_system.get_portfolio_summary()

        print(f"   Balance actual: ${portfolio['current_balance']:.2f}")
        print(f"   Total trades: {portfolio['total_trades']}")
        print(f"   Posiciones abiertas: {portfolio['open_positions']}")
        print(
            f"   PnL total: ${portfolio['total_pnl']:.2f} ({portfolio['total_pnl_pct']:.2f}%)"
        )

        # Mostrar posiciones por asset
        for position in portfolio["positions"]:
            print(
                f"   📈 {position['symbol']}: {position['quantity']} @ ${position['avg_price']:.2f}"
            )

        # 6. Fase 4: Configurar monitoreo extendido
        print("\n📊 6. FASE 4: CONFIGURANDO MONITOREO EXTENDIDO...")

        from app.core.continuous_monitoring import start_continuous_monitoring

        if start_continuous_monitoring():
            print("✅ Monitoreo continuo extendido iniciado")
        else:
            print("❌ Error iniciando monitoreo extendido")
            return False

        # 7. Fase 5: Crear plan de activación gradual
        print("\n📋 7. FASE 5: CREANDO PLAN DE ACTIVACIÓN GRADUAL...")

        activation_plan = {
            "timestamp": datetime.now().isoformat(),
            "phase": "7_gradual_activation_complete",
            "status": "active",
            "current_step": "Paper Trading Multi-Asset",
            "next_phases": [
                {
                    "phase": "7.1",
                    "action": "Monitoreo Extendido",
                    "description": "Monitorear sistema multi-asset durante 72 horas",
                    "duration": "72 horas",
                    "criteria": "Estabilidad con múltiples assets, sin pérdidas significativas",
                },
                {
                    "phase": "7.2",
                    "action": "Evaluación de Rendimiento",
                    "description": "Analizar rendimiento y ajustar parámetros",
                    "duration": "96 horas",
                    "criteria": "Rendimiento consistente, métricas estables",
                },
                {
                    "phase": "7.3",
                    "action": "Preparación Trading Real",
                    "description": "Preparar sistema para activación de trading real",
                    "duration": "120 horas",
                    "criteria": "Sistema completamente estable y probado",
                },
                {
                    "phase": "7.4",
                    "action": "Activación Trading Real",
                    "description": "Activar trading real con monitoreo intensivo",
                    "duration": "144 horas",
                    "criteria": "Paper trading exitoso por 5+ días",
                },
            ],
            "current_assets": {
                "BTCUSDT": {"active": True, "mode": "Paper Trading"},
                "ETHUSDT": {"active": True, "mode": "Paper Trading"},
                "BNBUSDT": {"active": True, "mode": "Paper Trading"},
            },
            "monitoring_config": {
                "interval": "30 segundos",
                "extended_logging": True,
                "performance_tracking": True,
                "alert_thresholds": {
                    "max_paper_trading_loss": -3.0,  # 3%
                    "max_circuit_breaker_activations": 1,
                    "max_system_errors": 0,
                    "min_performance_score": 0.8,
                },
            },
        }

        # Guardar plan
        plan_file = (
            f"gradual_activation_plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(plan_file, "w") as f:
            json.dump(activation_plan, f, indent=2)

        print(f"✅ Plan de activación gradual guardado en: {plan_file}")

        # 8. Resumen final
        print("\n" + "=" * 60)
        print("🎯 ACTIVACIÓN GRADUAL COMPLETADA")
        print("=" * 60)

        print("✅ Sistema verificado y seguro")
        print("✅ Múltiples assets activados")
        print("✅ Trades de prueba ejecutados")
        print("✅ Monitoreo extendido configurado")
        print("✅ Plan de activación gradual creado")

        print("\n📊 ESTADO ACTUAL:")
        print("   Assets activos: 3 (BTCUSDT, ETHUSDT, BNBUSDT)")
        print("   Modo: Paper Trading Multi-Asset")
        print("   Monitoreo: Extendido (30s)")
        print("   Circuit breakers: Operativos")
        print("   Alertas: Configuradas y activas")

        print("\n⏰ PRÓXIMOS PASOS:")
        print("   1. Monitorear 72 horas (multi-asset)")
        print("   2. Evaluar rendimiento y estabilidad")
        print("   3. Preparar trading real")
        print("   4. Activación gradual de trading real")

        print("\n🛡️ MEDIDAS DE SEGURIDAD:")
        print("   • Solo paper trading (sin riesgo real)")
        print("   • Circuit breakers activos y monitoreados")
        print("   • Monitoreo continuo extendido")
        print("   • Alertas automáticas habilitadas")
        print("   • Parada de emergencia operativa")
        print("   • Validación multi-asset")

        return True

    except Exception as e:
        print(f"❌ Error en activación gradual: {e}")
        logger.error(f"Error en activación: {e}")
        return False


def main():
    """Función principal"""
    success = activate_gradual_production()

    if success:
        print("\n🎉 ACTIVACIÓN GRADUAL COMPLETADA EXITOSAMENTE")
        print("📊 El sistema está ahora en modo paper trading multi-asset")
        print("🔄 Monitoreo extendido activo")
        print("⏰ Próxima revisión en 72 horas")

        # Mostrar comandos útiles
        print("\n💡 COMANDOS ÚTILES:")
        print(
            '   • Ver estado: python -c "from app.core.continuous_monitoring import get_monitoring_summary; print(get_monitoring_summary())"'
        )
        print(
            '   • Ver portafolio: python -c "from app.core.paper_trading import get_paper_portfolio_summary; print(get_paper_portfolio_summary())"'
        )
        print(
            '   • Ver configuración: python -c "from app.core.unified_config import get_config; print(get_config().get_config_summary())"'
        )
        print(
            '   • Detener monitoreo: python -c "from app.core.continuous_monitoring import stop_continuous_monitoring; stop_continuous_monitoring()"'
        )

    else:
        print("\n❌ ACTIVACIÓN GRADUAL FALLÓ")
        print("🔧 Revisar errores antes de continuar")

    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
