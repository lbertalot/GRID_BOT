#!/usr/bin/env python3
"""
Auditoría Final Pre-Lanzamiento GridBot v2.5
Verifica sincronización entre GridBot y Binance API
"""

import os
import sys
import requests
import json
from decimal import Decimal
from datetime import datetime, timezone
import logging

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler('logs/final_audit.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class FinalAuditor:
    def __init__(self):
        self.binance_api_key = os.getenv("BINANCE_API_KEY")
        self.binance_secret_key = os.getenv("BINANCE_SECRET_KEY")
        self.gridbot_api_url = "http://localhost:8000"
        self.audit_results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "balance_audit": {},
            "orders_audit": {},
            "overall_status": "PENDING"
        }
        
    def check_credentials(self):
        """Verificar que las credenciales de Binance estén disponibles"""
        if not self.binance_api_key or not self.binance_secret_key:
            logger.error("❌ CREDENCIALES DE BINANCE NO CONFIGURADAS")
            logger.error("   Configure BINANCE_API_KEY y BINANCE_SECRET_KEY")
            return False
        return True
    
    def get_binance_balance(self):
        """Obtener balance real de Binance"""
        try:
            from binance.client import Client
            client = Client(self.binance_api_key, self.binance_secret_key)
            
            # Obtener balance de USDT
            account_info = client.get_account()
            usdt_balance = None
            
            for balance in account_info['balances']:
                if balance['asset'] == 'USDT':
                    usdt_balance = Decimal(balance['free'])
                    break
            
            if usdt_balance is None:
                usdt_balance = Decimal('0')
            
            logger.info(f"💰 Balance Binance USDT: {usdt_balance}")
            return usdt_balance
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo balance de Binance: {e}")
            return None
    
    def get_gridbot_balance(self):
        """Obtener balance reportado por GridBot"""
        try:
            response = requests.get(f"{self.gridbot_api_url}/api/portfolio/summary", timeout=10)
            response.raise_for_status()
            
            data = response.json()
            balance = Decimal(str(data.get('cash_usdt', 0)))
            
            logger.info(f"💰 Balance GridBot USDT: {balance}")
            return balance
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo balance de GridBot: {e}")
            return None
    
    def get_binance_open_orders(self):
        """Obtener órdenes abiertas de Binance"""
        try:
            from binance.client import Client
            client = Client(self.binance_api_key, self.binance_secret_key)
            
            open_orders = client.get_open_orders()
            logger.info(f"📋 Órdenes abiertas Binance: {len(open_orders)}")
            return open_orders
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo órdenes de Binance: {e}")
            return None
    
    def get_gridbot_open_orders(self):
        """Obtener órdenes abiertas de GridBot"""
        try:
            response = requests.get(f"{self.gridbot_api_url}/api/positions", timeout=10)
            response.raise_for_status()
            
            orders = response.json()
            logger.info(f"📋 Órdenes abiertas GridBot: {len(orders)}")
            return orders
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo órdenes de GridBot: {e}")
            return None
    
    def audit_balance_sync(self):
        """Auditar sincronización de balances"""
        logger.info("\n[1. AUDITANDO BALANCE USDT...]")
        
        binance_balance = self.get_binance_balance()
        gridbot_balance = self.get_gridbot_balance()
        
        if binance_balance is None or gridbot_balance is None:
            self.audit_results["balance_audit"] = {
                "status": "ERROR",
                "binance_balance": None,
                "gridbot_balance": None,
                "discrepancy": None,
                "message": "Error obteniendo balances"
            }
            return False
        
        discrepancy = abs(binance_balance - gridbot_balance)
        tolerance = Decimal('0.01')  # Tolerancia de 1 centavo
        
        if discrepancy <= tolerance:
            logger.info("   ✅ ÉXITO: Los saldos coinciden perfectamente.")
            self.audit_results["balance_audit"] = {
                "status": "SUCCESS",
                "binance_balance": float(binance_balance),
                "gridbot_balance": float(gridbot_balance),
                "discrepancy": float(discrepancy),
                "message": "Balances sincronizados"
            }
            return True
        else:
            logger.error(f"   ❌ FALLO CRÍTICO: Discrepancia de saldo de {discrepancy} USDT.")
            self.audit_results["balance_audit"] = {
                "status": "FAILURE",
                "binance_balance": float(binance_balance),
                "gridbot_balance": float(gridbot_balance),
                "discrepancy": float(discrepancy),
                "message": f"Discrepancia crítica: {discrepancy} USDT"
            }
            return False
    
    def audit_orders_sync(self):
        """Auditar sincronización de órdenes abiertas"""
        logger.info("\n[2. AUDITANDO ÓRDENES ABIERTAS...]")
        
        binance_orders = self.get_binance_open_orders()
        gridbot_orders = self.get_gridbot_open_orders()
        
        if binance_orders is None or gridbot_orders is None:
            self.audit_results["orders_audit"] = {
                "status": "ERROR",
                "binance_orders": None,
                "gridbot_orders": None,
                "message": "Error obteniendo órdenes"
            }
            return False
        
        binance_count = len(binance_orders)
        gridbot_count = len(gridbot_orders)
        
        if binance_count == 0 and gridbot_count == 0:
            logger.info("   ✅ ÉXITO: No hay órdenes abiertas en ningún sistema.")
            self.audit_results["orders_audit"] = {
                "status": "SUCCESS",
                "binance_orders": binance_count,
                "gridbot_orders": gridbot_count,
                "message": "Sin órdenes abiertas en ambos sistemas"
            }
            return True
        else:
            logger.error(f"   ❌ FALLO CRÍTICO: Se detectaron órdenes abiertas inesperadas.")
            logger.error(f"      Binance: {binance_count} órdenes")
            logger.error(f"      GridBot: {gridbot_count} órdenes")
            self.audit_results["orders_audit"] = {
                "status": "FAILURE",
                "binance_orders": binance_count,
                "gridbot_orders": gridbot_count,
                "message": f"Órdenes abiertas detectadas: Binance={binance_count}, GridBot={gridbot_count}"
            }
            return False
    
    def run_final_audit(self):
        """Ejecutar auditoría final completa"""
        logger.info("--- INICIANDO AUDITORÍA FINAL PRE-LANZAMIENTO ---")
        
        # Verificar credenciales
        if not self.check_credentials():
            logger.error("❌ AUDITORÍA ABORTADA: Credenciales no configuradas")
            return False
        
        # Ejecutar auditorías
        balance_success = self.audit_balance_sync()
        orders_success = self.audit_orders_sync()
        
        # Determinar estado general
        if balance_success and orders_success:
            self.audit_results["overall_status"] = "SUCCESS"
            logger.info("\n🎉 AUDITORÍA COMPLETADA: TODOS LOS PUNTOS DE CONTROL VERIFICADOS")
            return True
        else:
            self.audit_results["overall_status"] = "FAILURE"
            logger.error("\n❌ AUDITORÍA FALLIDA: SE DETECTARON DISCREPANCIAS CRÍTICAS")
            return False
    
    def save_results(self):
        """Guardar resultados de auditoría"""
        with open('logs/final_audit_results.json', 'w') as f:
            json.dump(self.audit_results, f, indent=2)
        logger.info("📋 Resultados guardados en: logs/final_audit_results.json")

def main():
    auditor = FinalAuditor()
    success = auditor.run_final_audit()
    auditor.save_results()
    
    if success:
        print("\n🎉 VEREDICTO: GO FOR LAUNCH")
        sys.exit(0)
    else:
        print("\n❌ VEREDICTO: NO-GO - ABORTAR LANZAMIENTO")
        sys.exit(1)

if __name__ == "__main__":
    main()

