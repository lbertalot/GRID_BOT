#!/usr/bin/env python3
"""
Auditoría Final Pre-Lanzamiento - GridBot v2.5
Verificación de coherencia entre GridBot y Binance (fuente de la verdad)
"""

import os
import sys
import requests
import json
from decimal import Decimal
from binance.client import Client
from binance.exceptions import BinanceAPIException

# Configuración
GRIDBOT_API_URL = "http://localhost:8000"
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY")

def run_final_audit():
    """Ejecutar auditoría final de coherencia"""
    print("🔍 === INICIANDO AUDITORÍA FINAL PRE-LANZAMIENTO ===")
    print(f"📅 Fecha: {os.popen('date').read().strip()}")
    print(f"🌐 GridBot API: {GRIDBOT_API_URL}")
    
    results = {
        'balance_audit': {'status': 'pending', 'details': {}},
        'orders_audit': {'status': 'pending', 'details': {}},
        'overall_status': 'pending'
    }
    
    try:
        # Inicializar cliente de Binance
        print("\n🔑 Inicializando cliente de Binance...")
        binance_client = Client(BINANCE_API_KEY, BINANCE_SECRET_KEY)
        
        # 1. Auditoría de Balance USDT
        print("\n[1. AUDITANDO BALANCE USDT...]")
        try:
            # Obtener balance de Binance
            binance_balance_response = binance_client.get_asset_balance(asset='USDT')
            binance_balance_str = binance_balance_response['free']
            binance_balance = Decimal(binance_balance_str)
            
            print(f"   📊 Saldo real (Binance): {binance_balance} USDT")
            
            # Obtener balance de GridBot
            try:
                response = requests.get(f"{GRIDBOT_API_URL}/api/portfolio/summary", timeout=10)
                response.raise_for_status()
                gridbot_data = response.json()
                gridbot_balance = Decimal(str(gridbot_data.get('cash_usdt', 0)))
                
                print(f"   📊 Saldo reportado (GridBot): {gridbot_balance} USDT")
                
                # Comparar balances
                difference = abs(binance_balance - gridbot_balance)
                if difference < Decimal('0.01'):  # Tolerancia de 0.01 USDT
                    print("   ✅ ÉXITO: Los saldos coinciden perfectamente.")
                    results['balance_audit'] = {
                        'status': 'success',
                        'details': {
                            'binance_balance': float(binance_balance),
                            'gridbot_balance': float(gridbot_balance),
                            'difference': float(difference)
                        }
                    }
                else:
                    print(f"   ❌ FALLO CRÍTICO: Discrepancia de saldo de {difference} USDT.")
                    results['balance_audit'] = {
                        'status': 'critical_failure',
                        'details': {
                            'binance_balance': float(binance_balance),
                            'gridbot_balance': float(gridbot_balance),
                            'difference': float(difference)
                        }
                    }
                    
            except requests.exceptions.RequestException as e:
                print(f"   ❌ ERROR: No se pudo conectar a GridBot API: {e}")
                results['balance_audit'] = {
                    'status': 'api_error',
                    'details': {'error': str(e)}
                }
                
        except BinanceAPIException as e:
            print(f"   ❌ ERROR: Error de API de Binance: {e}")
            results['balance_audit'] = {
                'status': 'binance_error',
                'details': {'error': str(e)}
            }
        
        # 2. Auditoría de Órdenes Abiertas
        print("\n[2. AUDITANDO ÓRDENES ABIERTAS...]")
        try:
            # Obtener órdenes abiertas de Binance
            binance_open_orders = binance_client.get_open_orders()
            print(f"   📊 Órdenes abiertas (Binance): {len(binance_open_orders)}")
            
            # Obtener órdenes abiertas de GridBot
            try:
                response = requests.get(f"{GRIDBOT_API_URL}/api/portfolio/positions", timeout=10)
                response.raise_for_status()
                gridbot_data = response.json()
                gridbot_positions = gridbot_data.get('positions', [])
                print(f"   📊 Posiciones abiertas (GridBot): {len(gridbot_positions)}")
                
                # Verificar que no hay órdenes abiertas
                if len(binance_open_orders) == 0 and len(gridbot_positions) == 0:
                    print("   ✅ ÉXITO: No hay órdenes abiertas en ningún sistema.")
                    results['orders_audit'] = {
                        'status': 'success',
                        'details': {
                            'binance_orders': len(binance_open_orders),
                            'gridbot_positions': len(gridbot_positions)
                        }
                    }
                else:
                    print("   ❌ FALLO CRÍTICO: Se detectaron órdenes abiertas inesperadas.")
                    results['orders_audit'] = {
                        'status': 'critical_failure',
                        'details': {
                            'binance_orders': len(binance_open_orders),
                            'gridbot_positions': len(gridbot_positions)
                        }
                    }
                    
            except requests.exceptions.RequestException as e:
                print(f"   ❌ ERROR: No se pudo conectar a GridBot API: {e}")
                results['orders_audit'] = {
                    'status': 'api_error',
                    'details': {'error': str(e)}
                }
                
        except BinanceAPIException as e:
            print(f"   ❌ ERROR: Error de API de Binance: {e}")
            results['orders_audit'] = {
                'status': 'binance_error',
                'details': {'error': str(e)}
            }
        
        # 3. Verificación de Estado de Cuenta General
        print("\n[3. AUDITANDO ESTADO DE CUENTA GENERAL...]")
        try:
            # Obtener estado de cuenta de Binance
            binance_account = binance_client.get_account()
            binance_balances = [b for b in binance_account['balances'] if float(b['free']) > 0]
            
            print(f"   📊 Activos con balance > 0 (Binance): {len(binance_balances)}")
            for balance in binance_balances[:5]:  # Mostrar primeros 5
                print(f"      - {balance['asset']}: {balance['free']}")
            
            # Obtener estado de cuenta de GridBot
            try:
                response = requests.get(f"{GRIDBOT_API_URL}/api/portfolio/summary", timeout=10)
                response.raise_for_status()
                gridbot_summary = response.json()
                
                print(f"   📊 Resumen GridBot:")
                print(f"      - Total USDT: {gridbot_summary.get('total_usdt', 'N/A')}")
                print(f"      - Cash USDT: {gridbot_summary.get('cash_usdt', 'N/A')}")
                print(f"      - Total Value: {gridbot_summary.get('total_value_usdt', 'N/A')}")
                
            except requests.exceptions.RequestException as e:
                print(f"   ❌ ERROR: No se pudo obtener resumen de GridBot: {e}")
                
        except BinanceAPIException as e:
            print(f"   ❌ ERROR: Error obteniendo estado de cuenta de Binance: {e}")
        
        # Determinar estado general
        balance_ok = results['balance_audit']['status'] == 'success'
        orders_ok = results['orders_audit']['status'] == 'success'
        
        if balance_ok and orders_ok:
            results['overall_status'] = 'success'
            print("\n🎉 === AUDITORÍA COMPLETADA EXITOSAMENTE ===")
        else:
            results['overall_status'] = 'critical_failure'
            print("\n❌ === AUDITORÍA FALLÓ - CRÍTICO ===")
        
        # Guardar resultados
        with open('final_audit_results.json', 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n📄 Resultados guardados en: final_audit_results.json")
        
        return results
        
    except Exception as e:
        print(f"\n❌ ERROR CRÍTICO EN AUDITORÍA: {e}")
        results['overall_status'] = 'critical_error'
        return results

if __name__ == "__main__":
    results = run_final_audit()
    
    # Exit code basado en resultado
    if results['overall_status'] == 'success':
        print("\n✅ VEREDICTO: GO FOR LAUNCH")
        sys.exit(0)
    else:
        print("\n❌ VEREDICTO: NO-GO - ABORTAR LANZAMIENTO")
        sys.exit(1)
