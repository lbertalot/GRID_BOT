#!/usr/bin/env python3
"""
Monitor de Balance de Binance para GridBot v2.5
Monitorea cambios en el balance y detecta discrepancias
"""

import asyncio
import os
import sys
import time
import logging
import json
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
import httpx
from decimal import Decimal

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler('logs/binance_balance_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class BinanceBalanceMonitor:
    def __init__(self):
        self.api_base_url = "http://localhost:8000"
        self.balance_history = []
        self.alert_thresholds = {
            "balance_change_pct": 5.0,  # 5% de cambio en balance
            "unexpected_withdrawal": 10.0,  # 10 USDT de retiro inesperado
            "discrepancy_threshold": 1.0,  # 1 USDT de discrepancia
            "monitoring_interval": 60  # 60 segundos entre verificaciones
        }
        self.last_balance = None
        self.initial_balance = None
        
    async def get_binance_balance(self) -> Dict[str, Any]:
        """Obtener balance actual desde Binance a través de la API"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.api_base_url}/api/portfolio/summary")
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "status": "ok",
                        "cash_usdt": float(data.get("cash_usdt", 0)),
                        "portfolio_total_usdt": float(data.get("portfolio_total_usdt", 0)),
                        "assets": data.get("assets", []),
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                else:
                    return {
                        "status": "error",
                        "error": f"HTTP {response.status_code}"
                    }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    def calculate_balance_change(self, current_balance: float, previous_balance: float) -> Dict[str, float]:
        """Calcular cambios en el balance"""
        if previous_balance is None or previous_balance == 0:
            return {
                "absolute_change": 0.0,
                "percentage_change": 0.0,
                "direction": "stable"
            }
        
        absolute_change = current_balance - previous_balance
        percentage_change = (absolute_change / previous_balance) * 100
        
        direction = "stable"
        if absolute_change > 0:
            direction = "increase"
        elif absolute_change < 0:
            direction = "decrease"
        
        return {
            "absolute_change": absolute_change,
            "percentage_change": percentage_change,
            "direction": direction
        }
    
    def check_balance_alerts(self, balance_data: Dict[str, Any]) -> List[str]:
        """Verificar alertas de balance"""
        alerts = []
        
        if balance_data["status"] != "ok":
            alerts.append(f"❌ Error obteniendo balance: {balance_data.get('error', 'Unknown')}")
            return alerts
        
        current_balance = balance_data["cash_usdt"]
        
        # Establecer balance inicial si es la primera vez
        if self.initial_balance is None:
            self.initial_balance = current_balance
            logger.info(f"💰 Balance inicial establecido: {current_balance} USDT")
            return alerts
        
        # Calcular cambios
        if self.last_balance is not None:
            change_data = self.calculate_balance_change(current_balance, self.last_balance)
            
            # Alertar por cambios significativos
            if abs(change_data["percentage_change"]) > self.alert_thresholds["balance_change_pct"]:
                alerts.append(
                    f"⚠️ Cambio significativo en balance: "
                    f"{change_data['absolute_change']:.2f} USDT "
                    f"({change_data['percentage_change']:.2f}%)"
                )
            
            # Alertar por retiros inesperados
            if (change_data["direction"] == "decrease" and 
                abs(change_data["absolute_change"]) > self.alert_thresholds["unexpected_withdrawal"]):
                alerts.append(
                    f"🚨 Retiro inesperado detectado: "
                    f"{abs(change_data['absolute_change']):.2f} USDT"
                )
        
        # Verificar discrepancia con balance inicial
        if self.initial_balance is not None:
            total_change = current_balance - self.initial_balance
            if abs(total_change) > self.alert_thresholds["discrepancy_threshold"]:
                alerts.append(
                    f"📊 Discrepancia con balance inicial: "
                    f"{total_change:.2f} USDT desde el inicio"
                )
        
        return alerts
    
    def save_balance_snapshot(self, balance_data: Dict[str, Any]):
        """Guardar snapshot del balance para historial"""
        snapshot = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cash_usdt": balance_data.get("cash_usdt", 0),
            "portfolio_total_usdt": balance_data.get("portfolio_total_usdt", 0),
            "assets_count": len(balance_data.get("assets", [])),
            "status": balance_data.get("status", "unknown")
        }
        
        self.balance_history.append(snapshot)
        
        # Mantener solo los últimos 100 snapshots
        if len(self.balance_history) > 100:
            self.balance_history = self.balance_history[-100:]
    
    def generate_balance_report(self) -> Dict[str, Any]:
        """Generar reporte de balance"""
        if not self.balance_history:
            return {"status": "no_data"}
        
        current_balance = self.balance_history[-1]["cash_usdt"]
        initial_balance = self.initial_balance or current_balance
        
        total_change = current_balance - initial_balance
        total_change_pct = (total_change / initial_balance * 100) if initial_balance > 0 else 0
        
        # Calcular estadísticas
        balances = [snapshot["cash_usdt"] for snapshot in self.balance_history]
        max_balance = max(balances) if balances else 0
        min_balance = min(balances) if balances else 0
        
        return {
            "status": "ok",
            "current_balance": current_balance,
            "initial_balance": initial_balance,
            "total_change": total_change,
            "total_change_pct": total_change_pct,
            "max_balance": max_balance,
            "min_balance": min_balance,
            "snapshots_count": len(self.balance_history),
            "monitoring_duration_hours": len(self.balance_history) * (self.alert_thresholds["monitoring_interval"] / 3600)
        }
    
    async def run_monitoring_cycle(self):
        """Ejecutar un ciclo de monitoreo"""
        logger.info("🔍 Iniciando ciclo de monitoreo de balance...")
        
        # Obtener balance actual
        balance_data = await self.get_binance_balance()
        
        # Guardar snapshot
        self.save_balance_snapshot(balance_data)
        
        # Verificar alertas
        alerts = self.check_balance_alerts(balance_data)
        
        # Mostrar estado actual
        if balance_data["status"] == "ok":
            logger.info(f"💰 Balance actual: {balance_data['cash_usdt']} USDT")
            logger.info(f"📊 Portfolio total: {balance_data['portfolio_total_usdt']} USDT")
            logger.info(f"🏦 Activos: {len(balance_data['assets'])}")
        else:
            logger.error(f"❌ Error obteniendo balance: {balance_data.get('error', 'Unknown')}")
        
        # Mostrar alertas
        for alert in alerts:
            logger.warning(alert)
        
        # Generar reporte
        report = self.generate_balance_report()
        if report["status"] == "ok":
            logger.info(f"📈 Cambio total: {report['total_change']:.2f} USDT ({report['total_change_pct']:.2f}%)")
            logger.info(f"📊 Balance máximo: {report['max_balance']:.2f} USDT")
            logger.info(f"📊 Balance mínimo: {report['min_balance']:.2f} USDT")
        
        # Actualizar balance anterior
        if balance_data["status"] == "ok":
            self.last_balance = balance_data["cash_usdt"]
        
        logger.info("✅ Ciclo de monitoreo de balance completado")
    
    async def start_monitoring(self):
        """Iniciar monitoreo continuo de balance"""
        logger.info("🚀 Iniciando monitoreo de balance de Binance...")
        logger.info(f"⏰ Intervalo: {self.alert_thresholds['monitoring_interval']} segundos")
        logger.info(f"📊 Umbrales: {self.alert_thresholds}")
        
        while True:
            try:
                await self.run_monitoring_cycle()
                logger.info(f"⏳ Esperando {self.alert_thresholds['monitoring_interval']} segundos...")
                await asyncio.sleep(self.alert_thresholds["monitoring_interval"])
            except KeyboardInterrupt:
                logger.info("🛑 Monitoreo de balance detenido por el usuario")
                break
            except Exception as e:
                logger.error(f"❌ Error en ciclo de monitoreo: {e}")
                logger.info("⏳ Esperando 30 segundos antes de reintentar...")
                await asyncio.sleep(30)

async def main():
    monitor = BinanceBalanceMonitor()
    await monitor.start_monitoring()

if __name__ == "__main__":
    asyncio.run(main())

