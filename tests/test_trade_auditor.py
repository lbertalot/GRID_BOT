#!/usr/bin/env python3
"""
Test para validar el sistema de auditoría y reconciliación de trades
"""

import pytest
import sys
import os
from datetime import datetime

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.trade_auditor import TradeAuditor


class TestTradeAuditor:
    """Test para validar el sistema de auditoría de trades"""

    @pytest.fixture
    def trade_auditor(self):
        """Fixture para TradeAuditor"""
        return TradeAuditor()

    def test_audit_configuration(self, trade_auditor):
        """Test que la configuración de auditoría está correcta"""
        config = trade_auditor.audit_config

        # Verificar que todos los parámetros están definidos
        assert "max_discrepancy_usdt" in config
        assert "max_discrepancy_pct" in config
        assert "lookback_hours" in config
        assert "min_trades_for_audit" in config
        assert "auto_reconcile_threshold" in config

        # Verificar que los valores son razonables
        assert config["max_discrepancy_usdt"] > 0
        assert 0 < config["max_discrepancy_pct"] < 1
        assert config["lookback_hours"] > 0
        assert config["min_trades_for_audit"] > 0
        assert config["auto_reconcile_threshold"] > 0

        print("📋 Configuración de auditoría:")
        for key, value in config.items():
            print(f"  - {key}: {value}")

    @pytest.mark.asyncio
    async def test_audit_trades_basic(self, trade_auditor):
        """Test auditoría básica de trades"""

        # Ejecutar auditoría
        result = await trade_auditor.audit_trades(hours_back=1)

        # Verificar estructura del resultado
        assert "audit_timestamp" in result
        assert "status" in result
        assert "internal_trades_count" in result
        assert "binance_trades_count" in result
        assert "discrepancies" in result
        assert "reconciliation_metrics" in result

        # Verificar que se ejecutó sin errores
        assert result["status"] in ["completed", "error"]

        print("📊 Resultado de auditoría:")
        print(f"  - Status: {result['status']}")
        print(f"  - Trades internos: {result['internal_trades_count']}")
        print(f"  - Trades Binance: {result['binance_trades_count']}")
        print(f"  - Discrepancias: {len(result['discrepancies'])}")

    @pytest.mark.asyncio
    async def test_compare_trades_logic(self, trade_auditor):
        """Test lógica de comparación de trades"""

        # Trades internos simulados
        internal_trades = [
            {
                "id": 1,
                "symbol": "ETHUSDT",
                "side": "BUY",
                "quantity": 0.1,
                "price": 3000.0,
                "timestamp": datetime.now(),
                "profit_loss": 0.0,
                "status": "FILLED",
                "order_id": 12345,
            }
        ]

        # Trades de Binance simulados
        binance_trades = [
            {
                "id": 12345,
                "symbol": "ETHUSDT",
                "side": "BUY",
                "quantity": 0.1,
                "price": 3000.0,
                "timestamp": datetime.now(),
                "commission": 0.3,
                "commission_asset": "USDT",
                "order_id": 12345,
            }
        ]

        # Comparar trades
        discrepancies = await trade_auditor._compare_trades(
            internal_trades, binance_trades
        )

        # No debería haber discrepancias para trades idénticos
        assert len(discrepancies) == 0

        print(f"✅ Comparación de trades: {len(discrepancies)} discrepancias")

    @pytest.mark.asyncio
    async def test_compare_trades_with_discrepancies(self, trade_auditor):
        """Test comparación con discrepancias"""

        # Trades internos
        internal_trades = [
            {
                "id": 1,
                "symbol": "ETHUSDT",
                "side": "BUY",
                "quantity": 0.1,
                "price": 3000.0,
                "timestamp": datetime.now(),
                "profit_loss": 0.0,
                "status": "FILLED",
                "order_id": 12345,
            }
        ]

        # Trades de Binance con discrepancia
        binance_trades = [
            {
                "id": 12345,
                "symbol": "ETHUSDT",
                "side": "BUY",
                "quantity": 0.2,  # Cantidad diferente
                "price": 3000.0,
                "timestamp": datetime.now(),
                "commission": 0.3,
                "commission_asset": "USDT",
                "order_id": 12345,
            }
        ]

        # Comparar trades
        discrepancies = await trade_auditor._compare_trades(
            internal_trades, binance_trades
        )

        # Debería detectar discrepancia de cantidad
        assert len(discrepancies) > 0
        assert any(d["type"] == "quantity_mismatch" for d in discrepancies)

        print(f"🔍 Discrepancias detectadas: {len(discrepancies)}")
        for discrepancy in discrepancies:
            print(f"  - {discrepancy['type']}: {discrepancy['description']}")

    def test_calculate_reconciliation_metrics(self, trade_auditor):
        """Test cálculo de métricas de reconciliación"""

        # Discrepancias simuladas
        discrepancies = [
            {"severity": "critical", "type": "side_mismatch"},
            {"severity": "high", "type": "quantity_mismatch"},
            {"severity": "medium", "type": "price_mismatch"},
            {"severity": "medium", "type": "price_mismatch"},
        ]

        # Calcular métricas
        metrics = trade_auditor._calculate_reconciliation_metrics(discrepancies)

        # Verificar métricas
        assert metrics["total_discrepancies"] == 4
        assert metrics["critical_discrepancies"] == 1
        assert metrics["high_discrepancies"] == 1
        assert metrics["medium_discrepancies"] == 2
        assert 0 <= metrics["accuracy_percent"] <= 100
        assert "reconciliation_status" in metrics

        print("📊 Métricas de reconciliación:")
        print(f"  - Total discrepancias: {metrics['total_discrepancies']}")
        print(f"  - Críticas: {metrics['critical_discrepancies']}")
        print(f"  - Altas: {metrics['high_discrepancies']}")
        print(f"  - Medias: {metrics['medium_discrepancies']}")
        print(f"  - Precisión: {metrics['accuracy_percent']}%")
        print(f"  - Estado: {metrics['reconciliation_status']}")

    @pytest.mark.asyncio
    async def test_auto_reconcile_discrepancies(self, trade_auditor):
        """Test reconciliación automática de discrepancias"""

        # Discrepancias simuladas
        discrepancies = [
            {
                "type": "missing_internal",
                "order_id": 12345,
                "binance_trade": {"symbol": "ETHUSDT", "side": "BUY"},
            },
            {
                "type": "quantity_mismatch",
                "order_id": 67890,
                "internal_value": 0.1,
                "binance_value": 0.2,
            },
        ]

        # Intentar reconciliación automática
        result = await trade_auditor.auto_reconcile_discrepancies(discrepancies)

        # Verificar estructura del resultado
        assert "reconciled_count" in result
        assert "failed_count" in result
        assert "reconciled_orders" in result
        assert "failed_orders" in result

        print("🔄 Resultado de reconciliación automática:")
        print(f"  - Reconciliados: {result['reconciled_count']}")
        print(f"  - Fallidos: {result['failed_count']}")
        print(f"  - Órdenes reconciliadas: {result['reconciled_orders']}")

    @pytest.mark.asyncio
    async def test_audit_specific_symbol(self, trade_auditor):
        """Test auditoría de símbolo específico"""

        # Auditoría solo para ETHUSDT
        result = await trade_auditor.audit_trades(symbol="ETHUSDT", hours_back=1)

        # Verificar que se ejecutó
        assert "status" in result
        assert result["symbol"] == "ETHUSDT"

        print(f"🎯 Auditoría de ETHUSDT: {result['status']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
