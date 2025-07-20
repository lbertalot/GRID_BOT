#!/usr/bin/env python3
"""
Sistema completo de seguimiento de Profit/Loss para GridBot
"""

import os
import sys
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any
from dotenv import load_dotenv

# Agregar el directorio del proyecto al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from binance import Client
from app.services.telegram_alert import send_telegram_alert

class ProfitLossTracker:
    """Sistema de seguimiento de ganancias y pérdidas"""
    
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("BINANCE_API_KEY")
        self.api_secret = os.getenv("BINANCE_API_SECRET")
        self.client = Client(self.api_key, self.api_secret)
        
        # Archivo para almacenar datos de P&L
        self.pnl_file = "profit_loss_data.json"
        self.load_pnl_data()
    
    def load_pnl_data(self):
        """Carga datos históricos de P&L"""
        try:
            if os.path.exists(self.pnl_file):
                with open(self.pnl_file, 'r') as f:
                    self.pnl_data = json.load(f)
            else:
                self.pnl_data = {
                    "initial_balance": {},
                    "current_balance": {},
                    "trades": [],
                    "strategies": {},
                    "daily_pnl": {},
                    "total_pnl": 0.0
                }
        except Exception as e:
            print(f"Error cargando datos P&L: {e}")
            self.pnl_data = {
                "initial_balance": {},
                "current_balance": {},
                "trades": [],
                "strategies": {},
                "daily_pnl": {},
                "total_pnl": 0.0
            }
    
    def save_pnl_data(self):
        """Guarda datos de P&L"""
        try:
            with open(self.pnl_file, 'w') as f:
                json.dump(self.pnl_data, f, indent=2)
        except Exception as e:
            print(f"Error guardando datos P&L: {e}")
    
    def get_current_balances(self) -> Dict[str, float]:
        """Obtiene balances actuales"""
        try:
            account_info = self.client.get_account()
            balances = {}
            for balance in account_info['balances']:
                free = float(balance['free'])
                locked = float(balance['locked'])
                total = free + locked
                if total > 0:
                    balances[balance['asset']] = total
            return balances
        except Exception as e:
            print(f"Error obteniendo balances: {e}")
            return {}
    
    def get_current_prices(self, symbols: List[str]) -> Dict[str, float]:
        """Obtiene precios actuales"""
        try:
            prices = {}
            for symbol in symbols:
                ticker = self.client.get_symbol_ticker(symbol=symbol)
                prices[symbol] = float(ticker['price'])
            return prices
        except Exception as e:
            print(f"Error obteniendo precios: {e}")
            return {}
    
    def calculate_portfolio_value(self, balances: Dict[str, float], prices: Dict[str, float]) -> Dict[str, Any]:
        """Calcula el valor total del portfolio en USDT"""
        try:
            total_value_usdt = 0.0
            asset_values = {}
            
            for asset, amount in balances.items():
                if asset == 'USDT':
                    value_usdt = amount
                else:
                    symbol = f"{asset}USDT"
                    if symbol in prices:
                        value_usdt = amount * prices[symbol]
                    else:
                        value_usdt = 0.0
                
                asset_values[asset] = {
                    "amount": amount,
                    "value_usdt": value_usdt,
                    "price_usdt": prices.get(f"{asset}USDT", 0.0)
                }
                total_value_usdt += value_usdt
            
            return {
                "total_value_usdt": total_value_usdt,
                "asset_values": asset_values,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            print(f"Error calculando valor del portfolio: {e}")
            return {"total_value_usdt": 0.0, "asset_values": {}, "timestamp": datetime.now().isoformat()}
    
    def initialize_tracking(self):
        """Inicializa el seguimiento con balances actuales"""
        print("🎯 Inicializando seguimiento de P&L...")
        
        balances = self.get_current_balances()
        if not balances:
            print("❌ No se pudieron obtener balances")
            return False
        
        # Obtener precios para todos los assets
        symbols = [f"{asset}USDT" for asset in balances.keys() if asset != 'USDT']
        prices = self.get_current_prices(symbols)
        
        # Calcular valor inicial
        portfolio_value = self.calculate_portfolio_value(balances, prices)
        
        self.pnl_data["initial_balance"] = {
            "balances": balances,
            "portfolio_value": portfolio_value,
            "timestamp": datetime.now().isoformat()
        }
        
        self.save_pnl_data()
        
        print(f"✅ Seguimiento inicializado")
        print(f"💰 Valor inicial del portfolio: ${portfolio_value['total_value_usdt']:.2f} USDT")
        print(f"📊 Assets: {list(balances.keys())}")
        
        # Enviar alerta de Telegram
        alert_message = "🎯 Seguimiento de P&L Inicializado\n\n"
        alert_message += f"💰 Valor inicial: ${portfolio_value['total_value_usdt']:.2f} USDT\n"
        alert_message += f"📊 Assets: {', '.join(balances.keys())}\n"
        alert_message += f"📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        send_telegram_alert(alert_message)
        
        return True
    
    def update_current_status(self):
        """Actualiza el estado actual y calcula P&L"""
        print("📊 Actualizando estado actual...")
        
        balances = self.get_current_balances()
        if not balances:
            print("❌ No se pudieron obtener balances")
            return False
        
        # Obtener precios
        symbols = [f"{asset}USDT" for asset in balances.keys() if asset != 'USDT']
        prices = self.get_current_prices(symbols)
        
        # Calcular valor actual
        current_portfolio = self.calculate_portfolio_value(balances, prices)
        
        # Calcular P&L
        initial_value = self.pnl_data.get("initial_balance", {}).get("portfolio_value", {}).get("total_value_usdt", 0.0)
        current_value = current_portfolio["total_value_usdt"]
        
        pnl_absolute = current_value - initial_value
        pnl_percentage = (pnl_absolute / initial_value * 100) if initial_value > 0 else 0.0
        
        # Actualizar datos
        self.pnl_data["current_balance"] = {
            "balances": balances,
            "portfolio_value": current_portfolio,
            "timestamp": datetime.now().isoformat()
        }
        
        self.pnl_data["total_pnl"] = pnl_absolute
        
        # Agregar P&L diario
        today = datetime.now().strftime("%Y-%m-%d")
        if today not in self.pnl_data["daily_pnl"]:
            self.pnl_data["daily_pnl"][today] = []
        
        self.pnl_data["daily_pnl"][today].append({
            "timestamp": datetime.now().isoformat(),
            "value_usdt": current_value,
            "pnl_absolute": pnl_absolute,
            "pnl_percentage": pnl_percentage
        })
        
        self.save_pnl_data()
        
        # Mostrar resultados
        print(f"📈 Estado Actual del Portfolio:")
        print(f"   💰 Valor inicial: ${initial_value:.2f} USDT")
        print(f"   💰 Valor actual: ${current_value:.2f} USDT")
        print(f"   📊 P&L absoluto: ${pnl_absolute:.2f} USDT")
        print(f"   📈 P&L porcentual: {pnl_percentage:.2f}%")
        
        # Determinar estado
        if pnl_absolute > 0:
            status = "🟢 GANANDO"
            emoji = "📈"
        elif pnl_absolute < 0:
            status = "🔴 PERDIENDO"
            emoji = "📉"
        else:
            status = "🟡 NEUTRAL"
            emoji = "➡️"
        
        print(f"   {emoji} Estado: {status}")
        
        # Enviar alerta de Telegram
        alert_message = f"{emoji} Reporte de P&L\n\n"
        alert_message += f"💰 Valor actual: ${current_value:.2f} USDT\n"
        alert_message += f"📊 P&L: ${pnl_absolute:.2f} USDT ({pnl_percentage:.2f}%)\n"
        alert_message += f"📈 Estado: {status}\n"
        alert_message += f"📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        send_telegram_alert(alert_message)
        
        return True
    
    def get_detailed_report(self) -> Dict[str, Any]:
        """Genera un reporte detallado de P&L"""
        if not self.pnl_data.get("initial_balance"):
            return {"error": "No hay datos iniciales"}
        
        initial_value = self.pnl_data["initial_balance"]["portfolio_value"]["total_value_usdt"]
        current_value = self.pnl_data["current_balance"]["portfolio_value"]["total_value_usdt"]
        pnl_absolute = current_value - initial_value
        pnl_percentage = (pnl_absolute / initial_value * 100) if initial_value > 0 else 0.0
        
        # Calcular P&L por asset
        initial_assets = self.pnl_data["initial_balance"]["portfolio_value"]["asset_values"]
        current_assets = self.pnl_data["current_balance"]["portfolio_value"]["asset_values"]
        
        asset_pnl = {}
        for asset in set(initial_assets.keys()) | set(current_assets.keys()):
            initial_val = initial_assets.get(asset, {}).get("value_usdt", 0.0)
            current_val = current_assets.get(asset, {}).get("value_usdt", 0.0)
            asset_pnl[asset] = {
                "initial_value": initial_val,
                "current_value": current_val,
                "pnl_absolute": current_val - initial_val,
                "pnl_percentage": ((current_val - initial_val) / initial_val * 100) if initial_val > 0 else 0.0
            }
        
        return {
            "summary": {
                "initial_value": initial_value,
                "current_value": current_value,
                "pnl_absolute": pnl_absolute,
                "pnl_percentage": pnl_percentage,
                "status": "GANANDO" if pnl_absolute > 0 else "PERDIENDO" if pnl_absolute < 0 else "NEUTRAL"
            },
            "asset_breakdown": asset_pnl,
            "daily_pnl": self.pnl_data["daily_pnl"],
            "timestamp": datetime.now().isoformat()
        }
    
    def print_detailed_report(self):
        """Imprime un reporte detallado"""
        report = self.get_detailed_report()
        
        if "error" in report:
            print(f"❌ {report['error']}")
            return
        
        summary = report["summary"]
        asset_breakdown = report["asset_breakdown"]
        
        print("\n" + "="*60)
        print("📊 REPORTE DETALLADO DE P&L")
        print("="*60)
        
        print(f"\n🎯 RESUMEN GENERAL:")
        print(f"   💰 Valor inicial: ${summary['initial_value']:.2f} USDT")
        print(f"   💰 Valor actual: ${summary['current_value']:.2f} USDT")
        print(f"   📊 P&L absoluto: ${summary['pnl_absolute']:.2f} USDT")
        print(f"   📈 P&L porcentual: {summary['pnl_percentage']:.2f}%")
        print(f"   📊 Estado: {summary['status']}")
        
        print(f"\n📋 DESGLOSE POR ASSET:")
        for asset, data in asset_breakdown.items():
            if data['initial_value'] > 0 or data['current_value'] > 0:
                status_emoji = "🟢" if data['pnl_absolute'] > 0 else "🔴" if data['pnl_absolute'] < 0 else "🟡"
                print(f"   {status_emoji} {asset}:")
                print(f"      Inicial: ${data['initial_value']:.2f} → Actual: ${data['current_value']:.2f}")
                print(f"      P&L: ${data['pnl_absolute']:.2f} ({data['pnl_percentage']:.2f}%)")
        
        print(f"\n📅 P&L DIARIO:")
        for date, entries in report["daily_pnl"].items():
            if entries:
                latest = entries[-1]
                print(f"   📅 {date}: ${latest['pnl_absolute']:.2f} ({latest['pnl_percentage']:.2f}%)")
        
        print("="*60)

def main():
    """Función principal"""
    
    print("🎯 Sistema de Seguimiento de Profit/Loss")
    print("=" * 50)
    
    tracker = ProfitLossTracker()
    
    # Verificar si ya está inicializado
    if not tracker.pnl_data.get("initial_balance"):
        print("🔧 Primera ejecución - Inicializando seguimiento...")
        if not tracker.initialize_tracking():
            print("❌ Error inicializando seguimiento")
            return
    else:
        print("✅ Seguimiento ya inicializado")
    
    # Actualizar estado actual
    if tracker.update_current_status():
        print("✅ Estado actualizado correctamente")
    else:
        print("❌ Error actualizando estado")
        return
    
    # Mostrar reporte detallado
    tracker.print_detailed_report()

if __name__ == "__main__":
    main() 