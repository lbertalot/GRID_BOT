"""
Trade Auditor - Sistema de auditoría y reconciliación de trades
GridBot v2.5 - Detección de discrepancias entre sistema interno y Binance
"""

import logging
from typing import Any, Dict, List, Optional, Union

from datetime import datetime, timedelta

from sqlalchemy import desc
from sqlalchemy.exc import IntegrityError

from app.db.session import SessionLocal
from app.models.trade import Trade
from app.services.binance_service import BinanceService
from app.core.metrics import (
    reconciliation_discrepancies_total,
    reconciliation_accuracy_percent,
)

logger = logging.getLogger(__name__)


class TradeAuditor:
    """
    Sistema de auditoría y reconciliación de trades para detectar discrepancias
    entre el sistema interno y Binance (fuente de verdad)
    """

    def __init__(self):
        self.binance_service = BinanceService()
        self.logger = logger

        # Configuración de auditoría
        self.audit_config = {
            "max_discrepancy_usdt": 1.0,  # Máximo 1 USDT de discrepancia
            "max_discrepancy_pct": 0.01,  # Máximo 1% de discrepancia
            "lookback_hours": 24,  # Revisar últimos 24 horas
            "min_trades_for_audit": 5,  # Mínimo 5 trades para auditoría
            "auto_reconcile_threshold": 0.1,  # Auto-reconciliar si discrepancia < 0.1 USDT
        }

        self.logger.info("🔍 Trade Auditor inicializado")

    @staticmethod
    def _normalize_order_id_key(order_id: Union[int, str, None]) -> str:
        if order_id is None:
            return ""
        return str(order_id)

    async def audit_trades(
        self, symbol: str = None, hours_back: int = 24
    ) -> Dict[str, Any]:
        """
        Auditar trades entre sistema interno y Binance

        Args:
            symbol: Símbolo específico a auditar (opcional)
            hours_back: Horas hacia atrás para auditar

        Returns:
            Resultado de la auditoría
        """
        try:
            self.logger.info(
                f"🔍 Iniciando auditoría de trades (últimas {hours_back}h)"
            )

            # Obtener trades del sistema interno
            internal_trades = await self._get_internal_trades(symbol, hours_back)

            # Obtener trades de Binance
            binance_trades = await self._get_binance_trades(symbol, hours_back)

            # Comparar y detectar discrepancias
            discrepancies = await self._compare_trades(internal_trades, binance_trades)

            # Calcular métricas de reconciliación
            reconciliation_metrics = self._calculate_reconciliation_metrics(
                discrepancies
            )

            # Actualizar métricas de Prometheus
            self._update_prometheus_metrics(discrepancies, reconciliation_metrics)

            result = {
                "audit_timestamp": datetime.now().isoformat(),
                "symbol": symbol,
                "hours_back": hours_back,
                "internal_trades_count": len(internal_trades),
                "binance_trades_count": len(binance_trades),
                "discrepancies": discrepancies,
                "reconciliation_metrics": reconciliation_metrics,
                "status": "completed",
            }

            self.logger.info(
                f"✅ Auditoría completada: {len(discrepancies)} discrepancias encontradas"
            )
            return result

        except Exception as e:
            self.logger.error(f"❌ Error en auditoría de trades: {e}")
            return {
                "audit_timestamp": datetime.now().isoformat(),
                "status": "error",
                "error": str(e),
            }

    async def _get_internal_trades(
        self, symbol: str = None, hours_back: int = 24
    ) -> List[Dict]:
        """Obtener trades del sistema interno"""
        try:
            db = SessionLocal()

            # Calcular timestamp de inicio
            start_time = datetime.now() - timedelta(hours=hours_back)

            query = db.query(Trade).filter(Trade.timestamp >= start_time)

            if symbol:
                query = query.filter(Trade.symbol == symbol)

            trades = query.order_by(desc(Trade.timestamp)).all()

            internal_trades = []
            for trade in trades:
                oid = trade.order_id
                order_id_norm: Union[int, str, None]
                if oid is not None and str(oid).isdigit():
                    order_id_norm = int(str(oid))
                else:
                    order_id_norm = oid
                internal_trades.append(
                    {
                        "id": trade.id,
                        "symbol": trade.symbol,
                        "side": trade.side,
                        "quantity": float(trade.quantity),
                        "price": float(trade.entry_price),
                        "timestamp": trade.timestamp,
                        "profit_loss": float(trade.profit_loss)
                        if trade.profit_loss is not None
                        else 0.0,
                        "order_id": order_id_norm,
                    }
                )

            db.close()
            return internal_trades

        except Exception as e:
            self.logger.error(f"Error obteniendo trades internos: {e}")
            return []

    async def _get_binance_trades(
        self, symbol: str = None, hours_back: int = 24
    ) -> List[Dict]:
        """Obtener trades de Binance"""
        try:
            # Calcular timestamp de inicio
            start_time = datetime.now() - timedelta(hours=hours_back)
            start_timestamp = int(start_time.timestamp() * 1000)

            if self.binance_service.simulation_mode:
                # En modo simulación, generar trades simulados
                return await self._get_simulated_binance_trades(symbol, hours_back)

            # Obtener trades de Binance
            binance_trades = []

            if symbol:
                # Obtener trades de un símbolo específico
                trades = self.binance_service.client.get_my_trades(
                    symbol=symbol, startTime=start_timestamp
                )
            else:
                # Obtener todos los trades
                trades = self.binance_service.client.get_my_trades(
                    startTime=start_timestamp
                )

            for trade in trades:
                binance_trades.append(
                    {
                        "id": trade["id"],
                        "symbol": trade["symbol"],
                        "side": trade["isBuyer"] and "BUY" or "SELL",
                        "quantity": float(trade["qty"]),
                        "price": float(trade["price"]),
                        "timestamp": datetime.fromtimestamp(trade["time"] / 1000),
                        "commission": float(trade["commission"]),
                        "commission_asset": trade["commissionAsset"],
                        "order_id": trade["orderId"],
                    }
                )

            return binance_trades

        except Exception as e:
            self.logger.error(f"Error obteniendo trades de Binance: {e}")
            return []

    async def _get_simulated_binance_trades(
        self, symbol: str = None, hours_back: int = 24
    ) -> List[Dict]:
        """Obtener trades simulados de Binance para testing"""
        # En modo simulación, devolver trades simulados
        simulated_trades = []

        if symbol == "ETHUSDT" or symbol is None:
            simulated_trades.append(
                {
                    "id": 12345,
                    "symbol": "ETHUSDT",
                    "side": "BUY",
                    "quantity": 0.1,
                    "price": 3000.0,
                    "timestamp": datetime.now() - timedelta(hours=1),
                    "commission": 0.3,
                    "commission_asset": "USDT",
                    "order_id": 67890,
                }
            )

        return simulated_trades

    async def _compare_trades(
        self, internal_trades: List[Dict], binance_trades: List[Dict]
    ) -> List[Dict]:
        """Comparar trades internos con Binance y detectar discrepancias"""
        discrepancies = []

        # Crear índices para comparación rápida (order_id alineado como string)
        internal_by_order = {
            self._normalize_order_id_key(trade.get("order_id")): trade
            for trade in internal_trades
            if trade.get("order_id") is not None
        }
        binance_by_order = {
            self._normalize_order_id_key(trade.get("order_id")): trade
            for trade in binance_trades
            if trade.get("order_id") is not None
        }

        # Verificar trades en Binance que no están en sistema interno
        for order_id_key, binance_trade in binance_by_order.items():
            if not order_id_key:
                continue
            if order_id_key not in internal_by_order:
                discrepancies.append(
                    {
                        "type": "missing_internal",
                        "order_id": binance_trade.get("order_id"),
                        "binance_trade": binance_trade,
                        "severity": "high",
                        "description": (
                            f"Trade {order_id_key} existe en Binance pero no "
                            "en sistema interno"
                        ),
                    }
                )

        # Verificar trades en sistema interno que no están en Binance
        for order_id_key, internal_trade in internal_by_order.items():
            if not order_id_key:
                continue
            if order_id_key not in binance_by_order:
                discrepancies.append(
                    {
                        "type": "missing_binance",
                        "order_id": internal_trade.get("order_id"),
                        "internal_trade": internal_trade,
                        "severity": "medium",
                        "description": (
                            f"Trade {order_id_key} existe en sistema interno "
                            "pero no en Binance"
                        ),
                    }
                )

        # Verificar discrepancias en trades que existen en ambos
        shared_keys = set(internal_by_order.keys()) & set(binance_by_order.keys())
        for order_id_key in shared_keys:
            if not order_id_key:
                continue
            internal_trade = internal_by_order[order_id_key]
            binance_trade = binance_by_order[order_id_key]
            raw_order_id = internal_trade.get("order_id")
            if raw_order_id is None:
                raw_order_id = binance_trade.get("order_id")

            # Comparar campos críticos
            discrepancies.extend(
                self._compare_trade_details(raw_order_id, internal_trade, binance_trade)
            )

        return discrepancies

    def _compare_trade_details(
        self, order_id: int, internal_trade: Dict, binance_trade: Dict
    ) -> List[Dict]:
        """Comparar detalles de un trade específico"""
        discrepancies = []

        # Comparar cantidad
        qty_diff = abs(internal_trade["quantity"] - binance_trade["quantity"])
        if qty_diff > 0.001:  # Tolerancia de 0.001
            discrepancies.append(
                {
                    "type": "quantity_mismatch",
                    "order_id": order_id,
                    "internal_value": internal_trade["quantity"],
                    "binance_value": binance_trade["quantity"],
                    "difference": qty_diff,
                    "severity": "high",
                    "description": f"Cantidad diferente para trade {order_id}",
                }
            )

        # Comparar precio
        price_diff = abs(internal_trade["price"] - binance_trade["price"])
        if price_diff > 0.01:  # Tolerancia de 0.01 USDT
            discrepancies.append(
                {
                    "type": "price_mismatch",
                    "order_id": order_id,
                    "internal_value": internal_trade["price"],
                    "binance_value": binance_trade["price"],
                    "difference": price_diff,
                    "severity": "medium",
                    "description": f"Precio diferente para trade {order_id}",
                }
            )

        # Comparar lado (BUY/SELL)
        if internal_trade["side"] != binance_trade["side"]:
            discrepancies.append(
                {
                    "type": "side_mismatch",
                    "order_id": order_id,
                    "internal_value": internal_trade["side"],
                    "binance_value": binance_trade["side"],
                    "severity": "critical",
                    "description": f"Lado diferente para trade {order_id}",
                }
            )

        return discrepancies

    def _calculate_reconciliation_metrics(
        self, discrepancies: List[Dict]
    ) -> Dict[str, Any]:
        """Calcular métricas de reconciliación"""
        total_discrepancies = len(discrepancies)

        # Clasificar por severidad
        critical_count = len(
            [d for d in discrepancies if d.get("severity") == "critical"]
        )
        high_count = len([d for d in discrepancies if d.get("severity") == "high"])
        medium_count = len([d for d in discrepancies if d.get("severity") == "medium"])

        # Calcular precisión (0-100%)
        accuracy = max(0, 100 - (total_discrepancies * 10))  # -10% por discrepancia

        return {
            "total_discrepancies": total_discrepancies,
            "critical_discrepancies": critical_count,
            "high_discrepancies": high_count,
            "medium_discrepancies": medium_count,
            "accuracy_percent": accuracy,
            "reconciliation_status": "excellent"
            if accuracy >= 95
            else "good"
            if accuracy >= 80
            else "needs_attention",
        }

    def _update_prometheus_metrics(
        self, discrepancies: List[Dict], metrics: Dict[str, Any]
    ):
        """Actualizar métricas de Prometheus"""
        try:
            # Contador de discrepancias
            reconciliation_discrepancies_total.labels(type="total").inc(
                len(discrepancies)
            )

            # Gauge de precisión
            reconciliation_accuracy_percent.set(metrics["accuracy_percent"])

        except Exception as e:
            self.logger.error(f"Error actualizando métricas de Prometheus: {e}")

    async def auto_reconcile_discrepancies(
        self, discrepancies: List[Dict]
    ) -> Dict[str, Any]:
        """
        Intentar reconciliar discrepancias automáticamente

        Args:
            discrepancies: Lista de discrepancias detectadas

        Returns:
            Resultado de la reconciliación automática
        """
        reconciled = []
        failed = []

        for discrepancy in discrepancies:
            try:
                if discrepancy["type"] == "missing_internal":
                    # Crear trade faltante en sistema interno
                    await self._create_missing_internal_trade(discrepancy)
                    reconciled.append(discrepancy["order_id"])

                elif discrepancy["type"] == "quantity_mismatch":
                    # Actualizar cantidad en sistema interno
                    await self._update_trade_quantity(discrepancy)
                    reconciled.append(discrepancy["order_id"])

                elif discrepancy["type"] == "price_mismatch":
                    # Actualizar precio en sistema interno
                    await self._update_trade_price(discrepancy)
                    reconciled.append(discrepancy["order_id"])

            except Exception as e:
                self.logger.error(
                    f"Error reconciliando discrepancia {discrepancy.get('order_id')}: {e}"
                )
                failed.append(
                    {
                        "order_id": discrepancy.get("order_id"),
                        "error": str(e),
                    }
                )

        return {
            "reconciled_count": len(reconciled),
            "failed_count": len(failed),
            "reconciled_orders": reconciled,
            "failed_orders": failed,
        }

    def _require_binance_fields_for_create(
        self, binance_trade: Dict[str, Any]
    ) -> tuple[str, str, float, float]:
        symbol = binance_trade.get("symbol")
        side_raw = binance_trade.get("side")
        quantity = binance_trade.get("quantity")
        price = binance_trade.get("price")
        if not symbol or not side_raw:
            raise ValueError(
                "binance_trade debe incluir symbol y side para crear trade interno"
            )
        if quantity is None or price is None:
            raise ValueError(
                "binance_trade debe incluir quantity y price para crear trade interno"
            )
        return str(symbol), str(side_raw).upper(), float(quantity), float(price)

    async def _create_missing_internal_trade(self, discrepancy: Dict[str, Any]) -> None:
        """Insertar en BD un trade reportado en Binance y ausente localmente."""
        binance_trade = discrepancy.get("binance_trade")
        if not isinstance(binance_trade, dict):
            raise ValueError("missing_internal requiere binance_trade (dict)")
        order_id_raw = discrepancy.get("order_id")
        if order_id_raw is None:
            raise ValueError("missing_internal requiere order_id")
        order_id_str = self._normalize_order_id_key(order_id_raw)
        if not order_id_str:
            raise ValueError("order_id inválido para reconciliación")

        symbol, side, quantity, price = self._require_binance_fields_for_create(
            binance_trade
        )
        ts_raw: Optional[datetime] = binance_trade.get("timestamp")
        ts: Optional[datetime] = ts_raw if isinstance(ts_raw, datetime) else None

        db = SessionLocal()
        try:
            existing = db.query(Trade).filter(Trade.order_id == order_id_str).first()
            if existing:
                self.logger.info(
                    "Reconciliación: trade ya existe para order_id=%s, omitiendo",
                    order_id_str,
                )
                return

            row = Trade(
                symbol=symbol,
                side=side,
                quantity=quantity,
                entry_price=price,
                exit_price=None,
                profit_loss=None,
                order_id=order_id_str,
                client_order_id=None,
                strategy="reconciled_from_binance",
            )
            if ts is not None:
                row.timestamp = ts
            db.add(row)
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            self.logger.warning(
                "IntegrityError al crear trade reconciliado order_id=%s: %s",
                order_id_str,
                exc,
            )
            raise
        finally:
            db.close()

    async def _update_trade_quantity(self, discrepancy: Dict[str, Any]) -> None:
        """Actualizar quantity local al valor de Binance."""
        order_id_raw = discrepancy.get("order_id")
        binance_value = discrepancy.get("binance_value")
        if order_id_raw is None or binance_value is None:
            raise ValueError("quantity_mismatch requiere order_id y binance_value")
        order_id_str = self._normalize_order_id_key(order_id_raw)
        new_qty = float(binance_value)

        db = SessionLocal()
        try:
            row = db.query(Trade).filter(Trade.order_id == order_id_str).first()
            if row is None:
                raise ValueError(f"No hay trade interno con order_id={order_id_str}")
            row.quantity = new_qty
            db.commit()
        finally:
            db.close()

    async def _update_trade_price(self, discrepancy: Dict[str, Any]) -> None:
        """Actualizar entry_price local al valor de Binance."""
        order_id_raw = discrepancy.get("order_id")
        binance_value = discrepancy.get("binance_value")
        if order_id_raw is None or binance_value is None:
            raise ValueError("price_mismatch requiere order_id y binance_value")
        order_id_str = self._normalize_order_id_key(order_id_raw)
        new_price = float(binance_value)

        db = SessionLocal()
        try:
            row = db.query(Trade).filter(Trade.order_id == order_id_str).first()
            if row is None:
                raise ValueError(f"No hay trade interno con order_id={order_id_str}")
            row.entry_price = new_price
            db.commit()
        finally:
            db.close()


# Instancia global para uso en el sistema
trade_auditor = TradeAuditor()
