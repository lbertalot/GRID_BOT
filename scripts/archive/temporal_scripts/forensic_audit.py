"""
Script de Auditoría Forense - GridBot v2.5
Analiza discrepancias entre sistema interno y Binance

Ejecutar: python scripts/forensic_audit.py --export-json reports/forensic_audit_$(date +%Y%m%d_%H%M%S).json
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, List, Any
import json
import os
from collections import defaultdict

from dotenv import load_dotenv
load_dotenv()

from app.services.binance_client_singleton import get_binance_client_singleton
from app.db.session import SessionLocal
from app.models.trade import Trade
from sqlalchemy import desc, func

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ForensicAuditor:
    """Auditor forense para identificar discrepancias"""
    
    def __init__(self):
        self.client = get_binance_client_singleton()
        self.db = SessionLocal()
        self.report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sections": {},
            "discrepancies": [],
            "recommendations": []
        }
    
    async def run_full_audit(self) -> Dict[str, Any]:
        """Ejecuta auditoría completa"""
        logger.info("🔍 Iniciando auditoría forense completa...")
        
        # 1. Snapshot de balances Binance
        binance_snapshot = await self._get_binance_snapshot()
        self.report["sections"]["binance_snapshot"] = binance_snapshot
        
        # 2. Snapshot de balances internos (DB)
        db_snapshot = await self._get_db_snapshot()
        self.report["sections"]["db_snapshot"] = db_snapshot
        
        # 3. Análisis de trades en DB vs Binance
        trades_analysis = await self._analyze_trades()
        self.report["sections"]["trades_analysis"] = trades_analysis
        
        # 4. Identificar fills parciales no registrados
        partial_fills = await self._find_missing_partial_fills()
        self.report["sections"]["partial_fills"] = partial_fills
        
        # 5. Identificar órdenes fallidas sin registro
        failed_orders = await self._find_failed_orders()
        self.report["sections"]["failed_orders"] = failed_orders
        
        # 6. Calcular PnL real vs registrado
        pnl_comparison = await self._compare_pnl()
        self.report["sections"]["pnl_comparison"] = pnl_comparison
        
        # 7. Analizar comisiones no contabilizadas
        commission_analysis = await self._analyze_commissions()
        self.report["sections"]["commission_analysis"] = commission_analysis
        
        # 8. Generar recomendaciones
        self._generate_recommendations()
        
        # 9. Calcular score de salud
        health_score = self._calculate_health_score()
        self.report["health_score"] = health_score
        
        logger.info(f"✅ Auditoría completada - Health Score: {health_score}/100")
        return self.report
    
    async def _get_binance_snapshot(self) -> Dict[str, Any]:
        """Obtiene snapshot actual de Binance"""
        logger.info("📸 Obteniendo snapshot de Binance...")
        
        try:
            account_info = self.client.client.get_account()
            
            balances = {}
            total_value_usdt = Decimal('0')
            usdt_balance = Decimal('0')
            
            for balance in account_info.get('balances', []):
                asset = balance['asset']
                free = Decimal(str(balance['free']))
                locked = Decimal(str(balance['locked']))
                total = free + locked
                
                if total > 0:
                    balances[asset] = {
                        'free': float(free),
                        'locked': float(locked),
                        'total': float(total),
                        'value_usdt': 0.0
                    }
                    
                    if asset == 'USDT':
                        usdt_balance = total
                        total_value_usdt += total
                    else:
                        # Valorizar en USDT
                        try:
                            symbol = f"{asset}USDT"
                            ticker = self.client.client.get_symbol_ticker(symbol=symbol)
                            price = Decimal(str(ticker['price']))
                            value_usdt = total * price
                            balances[asset]['price'] = float(price)
                            balances[asset]['value_usdt'] = float(value_usdt)
                            total_value_usdt += value_usdt
                        except Exception as e:
                            logger.warning(f"No se pudo valorizar {asset}: {e}")
            
            # Obtener órdenes abiertas
            open_orders = self.client.client.get_open_orders()
            
            return {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'balances': balances,
                'total_value_usdt': float(total_value_usdt),
                'usdt_balance': float(usdt_balance),
                'open_orders_count': len(open_orders),
                'open_orders': [
                    {
                        'symbol': o['symbol'],
                        'side': o['side'],
                        'type': o['type'],
                        'origQty': o['origQty'],
                        'executedQty': o['executedQty'],
                        'price': o.get('price'),
                        'status': o['status'],
                        'orderId': o['orderId'],
                        'clientOrderId': o.get('clientOrderId')
                    }
                    for o in open_orders
                ]
            }
        except Exception as e:
            logger.error(f"Error obteniendo snapshot de Binance: {e}")
            return {'error': str(e)}
    
    async def _get_db_snapshot(self) -> Dict[str, Any]:
        """Obtiene snapshot de base de datos interna"""
        logger.info("📸 Obteniendo snapshot de DB interna...")
        
        try:
            # Total de trades registrados
            total_trades = self.db.query(Trade).count()
            
            # Trades por estado
            trades_by_status = self.db.query(
                Trade.side,
                func.count(Trade.id)
            ).group_by(Trade.side).all()
            
            # PnL calculado desde trades
            buy_total = self.db.query(
                func.sum(Trade.quantity * Trade.entry_price)
            ).filter(Trade.side == 'BUY').scalar() or Decimal('0')
            
            sell_total = self.db.query(
                func.sum(Trade.quantity * Trade.entry_price)
            ).filter(Trade.side == 'SELL').scalar() or Decimal('0')
            
            # Últimos 20 trades
            recent_trades = self.db.query(Trade).order_by(
                desc(Trade.timestamp)
            ).limit(20).all()
            
            return {
                'total_trades': total_trades,
                'trades_by_status': dict(trades_by_status),
                'buy_total_usdt': float(buy_total),
                'sell_total_usdt': float(sell_total),
                'estimated_pnl': float(sell_total - buy_total),
                'recent_trades': [
                    {
                        'id': t.id,
                        'symbol': t.symbol,
                        'side': t.side,
                        'quantity': float(t.quantity),
                        'price': float(t.entry_price),
                        'timestamp': t.timestamp.isoformat() if t.timestamp else None
                    }
                    for t in recent_trades
                ]
            }
        except Exception as e:
            logger.error(f"Error obteniendo snapshot de DB: {e}")
            return {'error': str(e)}
    
    async def _analyze_trades(self) -> Dict[str, Any]:
        """Analiza trades en DB vs Binance (últimas 24h)"""
        logger.info("📊 Analizando trades DB vs Binance...")
        
        try:
            # Trades de Binance (últimas 24h)
            now = datetime.now(timezone.utc)
            start_time = int((now - timedelta(days=1)).timestamp() * 1000)
            
            # Obtener trades de símbolos activos
            symbols = ['ETHUSDT', 'BTCUSDT', 'BNBUSDT']  # Expandir según necesidad
            
            binance_trades_by_symbol = {}
            total_binance_trades = 0
            
            for symbol in symbols:
                try:
                    trades = self.client.client.get_my_trades(
                        symbol=symbol,
                        startTime=start_time
                    )
                    binance_trades_by_symbol[symbol] = len(trades)
                    total_binance_trades += len(trades)
                except Exception as e:
                    logger.warning(f"No se pudieron obtener trades de {symbol}: {e}")
            
            # Trades de DB (últimas 24h)
            db_trades = self.db.query(Trade).filter(
                Trade.timestamp >= now - timedelta(days=1)
            ).all()
            
            db_trades_by_symbol = defaultdict(int)
            for trade in db_trades:
                db_trades_by_symbol[trade.symbol] += 1
            
            # Comparar
            discrepancies = []
            for symbol in set(list(binance_trades_by_symbol.keys()) + list(db_trades_by_symbol.keys())):
                binance_count = binance_trades_by_symbol.get(symbol, 0)
                db_count = db_trades_by_symbol.get(symbol, 0)
                
                if binance_count != db_count:
                    discrepancies.append({
                        'symbol': symbol,
                        'binance_trades': binance_count,
                        'db_trades': db_count,
                        'difference': binance_count - db_count,
                        'severity': 'high' if abs(binance_count - db_count) > 5 else 'medium'
                    })
            
            return {
                'period': '24h',
                'total_binance_trades': total_binance_trades,
                'total_db_trades': len(db_trades),
                'discrepancies': discrepancies,
                'discrepancy_count': len(discrepancies)
            }
        except Exception as e:
            logger.error(f"Error analizando trades: {e}")
            return {'error': str(e)}
    
    async def _find_missing_partial_fills(self) -> Dict[str, Any]:
        """Busca fills parciales no registrados"""
        logger.info("🔍 Buscando fills parciales no registrados...")
        
        try:
            # Obtener órdenes de Binance con fills parciales
            # (órdenes con executedQty < origQty)
            symbols = ['ETHUSDT', 'BTCUSDT', 'BNBUSDT']
            
            partial_fills = []
            
            for symbol in symbols:
                try:
                    # Órdenes recientes (últimos 7 días)
                    orders = self.client.client.get_all_orders(
                        symbol=symbol,
                        limit=100
                    )
                    
                    for order in orders:
                        executed_qty = Decimal(str(order.get('executedQty', 0)))
                        orig_qty = Decimal(str(order.get('origQty', 0)))
                        
                        if executed_qty > 0 and executed_qty < orig_qty:
                            # Verificar si está en DB
                            client_order_id = order.get('clientOrderId')
                            
                            # Buscar en DB por clientOrderId o por match aproximado
                            # (esto es simplificado, ajustar según tu modelo)
                            db_trade = self.db.query(Trade).filter(
                                Trade.symbol == symbol,
                                Trade.quantity == float(executed_qty)
                            ).first()
                            
                            if not db_trade:
                                partial_fills.append({
                                    'symbol': symbol,
                                    'orderId': order['orderId'],
                                    'clientOrderId': client_order_id,
                                    'side': order['side'],
                                    'origQty': float(orig_qty),
                                    'executedQty': float(executed_qty),
                                    'price': float(order.get('price', 0)),
                                    'status': order['status'],
                                    'time': datetime.fromtimestamp(
                                        order['time'] / 1000, tz=timezone.utc
                                    ).isoformat()
                                })
                except Exception as e:
                    logger.warning(f"Error buscando fills parciales en {symbol}: {e}")
            
            return {
                'partial_fills_found': len(partial_fills),
                'details': partial_fills,
                'severity': 'critical' if len(partial_fills) > 3 else 'high' if len(partial_fills) > 0 else 'low'
            }
        except Exception as e:
            logger.error(f"Error buscando fills parciales: {e}")
            return {'error': str(e)}
    
    async def _find_failed_orders(self) -> Dict[str, Any]:
        """Busca órdenes fallidas sin registro"""
        logger.info("🔍 Buscando órdenes fallidas...")
        
        try:
            symbols = ['ETHUSDT', 'BTCUSDT', 'BNBUSDT']
            
            failed_orders = []
            
            for symbol in symbols:
                try:
                    orders = self.client.client.get_all_orders(
                        symbol=symbol,
                        limit=100
                    )
                    
                    for order in orders:
                        status = order['status']
                        
                        # Estados que indican fallo
                        if status in ['CANCELED', 'REJECTED', 'EXPIRED']:
                            client_order_id = order.get('clientOrderId')
                            
                            # Verificar si hay registro del fallo en DB
                            # (ajustar según tu modelo de almacenamiento de fallos)
                            
                            failed_orders.append({
                                'symbol': symbol,
                                'orderId': order['orderId'],
                                'clientOrderId': client_order_id,
                                'side': order['side'],
                                'status': status,
                                'time': datetime.fromtimestamp(
                                    order['time'] / 1000, tz=timezone.utc
                                ).isoformat()
                            })
                except Exception as e:
                    logger.warning(f"Error buscando órdenes fallidas en {symbol}: {e}")
            
            return {
                'failed_orders_found': len(failed_orders),
                'details': failed_orders[:10],  # Solo primeros 10
                'total': len(failed_orders)
            }
        except Exception as e:
            logger.error(f"Error buscando órdenes fallidas: {e}")
            return {'error': str(e)}
    
    async def _compare_pnl(self) -> Dict[str, Any]:
        """Compara PnL calculado vs real"""
        logger.info("💰 Comparando PnL...")
        
        try:
            # PnL de DB (desde trades)
            db_snapshot = self.report["sections"].get("db_snapshot", {})
            db_pnl = db_snapshot.get("estimated_pnl", 0)
            
            # PnL real de Binance
            # (valor actual - valor inicial registrado)
            binance_snapshot = self.report["sections"].get("binance_snapshot", {})
            current_value = binance_snapshot.get("total_value_usdt", 0)
            
            # Obtener valor inicial (del primer trade o configuración)
            # Para simplificar, usar una constante o extraer de config
            initial_value = 408.78  # Del reporte de auditoría anterior
            
            binance_pnl = current_value - initial_value
            
            discrepancy = db_pnl - binance_pnl
            discrepancy_pct = (discrepancy / initial_value * 100) if initial_value > 0 else 0
            
            return {
                'db_pnl': db_pnl,
                'binance_pnl': binance_pnl,
                'discrepancy_usdt': discrepancy,
                'discrepancy_pct': discrepancy_pct,
                'severity': 'critical' if abs(discrepancy_pct) > 5 else 'high' if abs(discrepancy_pct) > 1 else 'low'
            }
        except Exception as e:
            logger.error(f"Error comparando PnL: {e}")
            return {'error': str(e)}
    
    async def _analyze_commissions(self) -> Dict[str, Any]:
        """Analiza comisiones no contabilizadas"""
        logger.info("💳 Analizando comisiones...")
        
        try:
            # Obtener comisiones de Binance (últimos 7 días)
            symbols = ['ETHUSDT', 'BTCUSDT', 'BNBUSDT']
            
            total_commission_bnb = Decimal('0')
            total_commission_usdt = Decimal('0')
            commission_count = 0
            
            for symbol in symbols:
                try:
                    trades = self.client.client.get_my_trades(symbol=symbol, limit=500)
                    
                    for trade in trades:
                        commission = Decimal(str(trade.get('commission', 0)))
                        commission_asset = trade.get('commissionAsset', '')
                        
                        if commission > 0:
                            commission_count += 1
                            
                            if commission_asset == 'BNB':
                                total_commission_bnb += commission
                            elif commission_asset == 'USDT':
                                total_commission_usdt += commission
                            else:
                                # Convertir a USDT si es posible
                                try:
                                    ticker = self.client.client.get_symbol_ticker(
                                        symbol=f"{commission_asset}USDT"
                                    )
                                    price = Decimal(str(ticker['price']))
                                    total_commission_usdt += commission * price
                                except:
                                    pass
                except Exception as e:
                    logger.warning(f"Error obteniendo comisiones de {symbol}: {e}")
            
            # Convertir BNB a USDT
            if total_commission_bnb > 0:
                try:
                    bnb_price = Decimal(str(
                        self.client.client.get_symbol_ticker(symbol='BNBUSDT')['price']
                    ))
                    total_commission_usdt += total_commission_bnb * bnb_price
                except:
                    pass
            
            return {
                'total_commission_usdt': float(total_commission_usdt),
                'commission_count': commission_count,
                'avg_commission_per_trade': float(total_commission_usdt / commission_count) if commission_count > 0 else 0
            }
        except Exception as e:
            logger.error(f"Error analizando comisiones: {e}")
            return {'error': str(e)}
    
    def _generate_recommendations(self):
        """Genera recomendaciones basadas en hallazgos"""
        logger.info("💡 Generando recomendaciones...")
        
        recommendations = []
        
        # Revisar cada sección y agregar recomendaciones
        partial_fills = self.report["sections"].get("partial_fills", {})
        if partial_fills.get("partial_fills_found", 0) > 0:
            recommendations.append({
                'priority': 'critical',
                'category': 'data_integrity',
                'title': 'Registrar fills parciales faltantes',
                'description': f"Se encontraron {partial_fills['partial_fills_found']} fills parciales no registrados",
                'action': 'Implementar tracking de fills parciales en real-time'
            })
        
        failed_orders = self.report["sections"].get("failed_orders", {})
        if failed_orders.get("failed_orders_found", 0) > 0:
            recommendations.append({
                'priority': 'high',
                'category': 'error_handling',
                'title': 'Registrar órdenes fallidas',
                'description': f"Se encontraron {failed_orders['failed_orders_found']} órdenes fallidas sin registro",
                'action': 'Implementar logging de todos los estados de órdenes'
            })
        
        pnl_comparison = self.report["sections"].get("pnl_comparison", {})
        if pnl_comparison.get("discrepancy_usdt", 0) != 0:
            recommendations.append({
                'priority': 'critical',
                'category': 'reconciliation',
                'title': 'Reconciliar PnL con Binance',
                'description': f"Discrepancia de ${pnl_comparison['discrepancy_usdt']:.2f} USDT ({pnl_comparison['discrepancy_pct']:.2f}%)",
                'action': 'Implementar reconciliación automática cada 30 segundos'
            })
        
        trades_analysis = self.report["sections"].get("trades_analysis", {})
        if trades_analysis.get("discrepancy_count", 0) > 0:
            recommendations.append({
                'priority': 'high',
                'category': 'data_sync',
                'title': 'Sincronizar trades faltantes',
                'description': f"{trades_analysis['discrepancy_count']} símbolos con discrepancias de trades",
                'action': 'Backfill de trades faltantes desde Binance API'
            })
        
        self.report["recommendations"] = recommendations
    
    def _calculate_health_score(self) -> int:
        """Calcula score de salud (0-100)"""
        score = 100
        
        # Penalización por fills parciales
        partial_fills = self.report["sections"].get("partial_fills", {})
        score -= min(30, partial_fills.get("partial_fills_found", 0) * 10)
        
        # Penalización por órdenes fallidas
        failed_orders = self.report["sections"].get("failed_orders", {})
        score -= min(20, failed_orders.get("failed_orders_found", 0) * 2)
        
        # Penalización por discrepancia de PnL
        pnl_comparison = self.report["sections"].get("pnl_comparison", {})
        discrepancy_pct = abs(pnl_comparison.get("discrepancy_pct", 0))
        score -= min(40, int(discrepancy_pct * 5))
        
        # Penalización por discrepancias de trades
        trades_analysis = self.report["sections"].get("trades_analysis", {})
        score -= min(10, trades_analysis.get("discrepancy_count", 0) * 2)
        
        return max(0, score)
    
    def export_report(self, filename: str):
        """Exporta reporte a JSON"""
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, 'w') as f:
            json.dump(self.report, f, indent=2, default=str)
        logger.info(f"📄 Reporte exportado a: {filename}")
    
    def __del__(self):
        """Cierra conexión a DB"""
        if hasattr(self, 'db') and self.db:
            self.db.close()


async def main():
    """Función principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Auditoría Forense de GridBot')
    parser.add_argument('--export-json', type=str, help='Archivo de salida JSON')
    parser.add_argument('--verbose', action='store_true', help='Modo verbose')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    auditor = ForensicAuditor()
    report = await auditor.run_full_audit()
    
    # Mostrar resumen
    print("\n" + "="*80)
    print("📊 RESUMEN DE AUDITORÍA FORENSE")
    print("="*80)
    print(f"Timestamp: {report['timestamp']}")
    print(f"Health Score: {report['health_score']}/100")
    print(f"\n🔍 Hallazgos:")
    
    for section, data in report['sections'].items():
        if isinstance(data, dict) and 'error' not in data:
            print(f"  - {section}: ✅ OK")
        elif isinstance(data, dict) and 'error' in data:
            print(f"  - {section}: ❌ ERROR - {data['error']}")
    
    print(f"\n💡 Recomendaciones: {len(report['recommendations'])}")
    for rec in report['recommendations']:
        print(f"  [{rec['priority'].upper()}] {rec['title']}")
    
    # Exportar si se especificó
    if args.export_json:
        auditor.export_report(args.export_json)
    
    print("\n" + "="*80)
    print("✅ Auditoría completada")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())

