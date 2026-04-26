#!/usr/bin/env python3
"""
Script para Resetear Estado de Pruebas
GridBot V2.5
"""

import sys
import os
import logging
from datetime import datetime

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configurar logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def reset_circuit_breaker():
    """Resetea el circuit breaker"""
    try:
        from app.core.circuit_breaker import circuit_breaker

        # Cerrar circuit breaker
        circuit_breaker.close_circuit("Reset para pruebas")

        # Resetear métricas
        circuit_breaker.state["daily_loss"] = 0.0
        circuit_breaker.state["total_loss"] = 0.0
        circuit_breaker.state["consecutive_losses"] = 0
        circuit_breaker.state["hourly_loss"] = 0.0
        circuit_breaker.state["last_reset"] = datetime.now()

        circuit_breaker.save_state()

        print("✅ Circuit breaker reseteado")
        return True

    except Exception as e:
        print(f"❌ Error reseteando circuit breaker: {e}")
        return False


def reset_monitoring_system():
    """Resetea el sistema de monitoreo"""
    try:
        from app.core.monitoring import monitoring_system

        # Resetear métricas
        monitoring_system.metrics = {
            "total_trades": 0,
            "successful_trades": 0,
            "failed_trades": 0,
            "total_profit": 0.0,
            "total_loss": 0.0,
            "current_balance": 1000.0,  # Balance inicial
            "daily_pnl": 0.0,
            "hourly_pnl": 0.0,
            "last_update": datetime.now().isoformat(),
        }

        # Limpiar alertas
        monitoring_system.alerts = []

        monitoring_system.save_data()

        print("✅ Sistema de monitoreo reseteado")
        return True

    except Exception as e:
        print(f"❌ Error reseteando monitoreo: {e}")
        return False


def reset_paper_trading():
    """Resetea el paper trading"""
    try:
        from app.core.paper_trading import paper_trading_system

        # Resetear con balance inicial
        paper_trading_system.reset_paper_trading(1000.0)

        print("✅ Paper trading reseteado")
        return True

    except Exception as e:
        print(f"❌ Error reseteando paper trading: {e}")
        return False


def reset_test_files():
    """Elimina archivos de prueba"""
    test_files = ["testing_results.json", "paper_trading_state.json"]

    for file in test_files:
        if os.path.exists(file):
            try:
                os.remove(file)
                print(f"✅ Archivo eliminado: {file}")
            except Exception as e:
                print(f"❌ Error eliminando {file}: {e}")


def main():
    """Función principal"""
    print("🔄 RESETEANDO ESTADO DE PRUEBAS")
    print("=" * 40)
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    success = True

    # Resetear circuit breaker
    if not reset_circuit_breaker():
        success = False

    # Resetear monitoreo
    if not reset_monitoring_system():
        success = False

    # Resetear paper trading
    if not reset_paper_trading():
        success = False

    # Eliminar archivos de prueba
    reset_test_files()

    print("\n" + "=" * 40)
    if success:
        print("✅ Estado de pruebas reseteado exitosamente")
        print("🔄 Listo para ejecutar nuevas pruebas")
    else:
        print("❌ Algunos componentes no se pudieron resetear")

    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
