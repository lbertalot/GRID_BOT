#!/usr/bin/env python3
"""
Análisis detallado de logs para identificar información relevante
"""

import re
from collections import defaultdict, Counter
from datetime import datetime

def detailed_log_analysis():
    """Análisis detallado de los logs"""
    try:
        print("🔍 Análisis Detallado de Logs - Información Relevante")
        print("=" * 70)
        
        # Contadores
        total_lines = 0
        sql_queries = defaultdict(int)
        trading_events = defaultdict(int)
        errors = defaultdict(int)
        warnings = defaultdict(int)
        api_calls = defaultdict(int)
        
        # Información relevante
        trading_summaries = []
        balance_checks = []
        order_executions = []
        profit_loss = []
        
        print("📊 Analizando logs para extraer información relevante...")
        
        with open('logs/dockers.log', 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                total_lines += 1
                
                # Extraer información de trading
                if 'Resumen del ciclo' in line:
                    trading_summaries.append({
                        'line': line_num,
                        'content': line.strip(),
                        'timestamp': extract_timestamp(line)
                    })
                
                # Extraer información de balances
                if 'saldo' in line.lower() or 'balance' in line.lower():
                    balance_checks.append({
                        'line': line_num,
                        'content': line.strip(),
                        'timestamp': extract_timestamp(line)
                    })
                
                # Extraer ejecuciones de órdenes
                if any(keyword in line for keyword in ['orden ejecutada', 'order executed', 'trade executed']):
                    order_executions.append({
                        'line': line_num,
                        'content': line.strip(),
                        'timestamp': extract_timestamp(line)
                    })
                
                # Extraer información de ganancias/pérdidas
                if any(keyword in line for keyword in ['profit', 'ganancia', 'pérdida', 'loss']):
                    profit_loss.append({
                        'line': line_num,
                        'content': line.strip(),
                        'timestamp': extract_timestamp(line)
                    })
                
                # Categorizar consultas SQL
                if 'SELECT' in line:
                    if 'trades' in line:
                        sql_queries['trades_queries'] += 1
                    elif 'asset_limits' in line:
                        sql_queries['asset_limits_queries'] += 1
                    else:
                        sql_queries['other_select'] += 1
                elif 'INSERT' in line:
                    sql_queries['insert_queries'] += 1
                elif 'UPDATE' in line:
                    sql_queries['update_queries'] += 1
                
                # Categorizar errores
                if 'ERROR' in line:
                    if 'Invalid symbol' in line:
                        errors['invalid_symbol'] += 1
                    elif 'NOTIONAL' in line:
                        errors['notional_filter'] += 1
                    elif 'Saldo insuficiente' in line:
                        errors['insufficient_balance'] += 1
                    elif 'APIError' in line:
                        errors['api_error'] += 1
                    else:
                        errors['other_errors'] += 1
                
                # Categorizar warnings
                if 'WARNING' in line:
                    if 'saldo' in line.lower():
                        warnings['balance_warnings'] += 1
                    else:
                        warnings['other_warnings'] += 1
                
                # Contar llamadas a API
                if 'binance' in line.lower() and 'api' in line.lower():
                    api_calls['binance_api'] += 1
        
        # Mostrar análisis de información relevante
        print(f"\n📈 INFORMACIÓN MÁS RELEVANTE ENCONTRADA:")
        print("-" * 50)
        
        print(f"🔄 Resúmenes de Trading: {len(trading_summaries)}")
        if trading_summaries:
            print("   Últimos 3 resúmenes:")
            for summary in trading_summaries[-3:]:
                print(f"   • {summary['timestamp']}: {summary['content'][:100]}...")
        
        print(f"\n💰 Verificaciones de Balance: {len(balance_checks)}")
        if balance_checks:
            print("   Últimas 3 verificaciones:")
            for balance in balance_checks[-3:]:
                print(f"   • {balance['timestamp']}: {balance['content'][:100]}...")
        
        print(f"\n📊 Ejecuciones de Órdenes: {len(order_executions)}")
        if order_executions:
            print("   Últimas 3 ejecuciones:")
            for order in order_executions[-3:]:
                print(f"   • {order['timestamp']}: {order['content'][:100]}...")
        
        print(f"\n💵 Información de Ganancias/Pérdidas: {len(profit_loss)}")
        if profit_loss:
            print("   Últimas 3 entradas:")
            for pl in profit_loss[-3:]:
                print(f"   • {pl['timestamp']}: {pl['content'][:100]}...")
        
        # Análisis de consultas SQL
        print(f"\n🗄️ ANÁLISIS DE CONSULTAS SQL:")
        print("-" * 50)
        total_sql = sum(sql_queries.values())
        if total_sql > 0:
            for query_type, count in sql_queries.items():
                percentage = (count / total_sql) * 100
                relevance = "🔴 Irrelevante" if percentage > 30 else "🟡 Moderada" if percentage > 10 else "🟢 Relevante"
                print(f"   • {query_type}: {count:,} ({percentage:.1f}%) - {relevance}")
        
        # Análisis de errores
        print(f"\n🚨 ANÁLISIS DE ERRORES:")
        print("-" * 50)
        total_errors = sum(errors.values())
        if total_errors > 0:
            for error_type, count in errors.items():
                percentage = (count / total_errors) * 100
                severity = "🔴 Crítico" if error_type in ['api_error', 'insufficient_balance'] else "🟡 Moderado" if error_type == 'notional_filter' else "🟢 Menor"
                print(f"   • {error_type}: {count:,} ({percentage:.1f}%) - {severity}")
        
        # Recomendaciones específicas
        print(f"\n💡 RECOMENDACIONES ESPECÍFICAS:")
        print("-" * 50)
        
        # 1. Consultas SQL
        if sql_queries['trades_queries'] > 1000:
            print("   🔴 PROBLEMA: Demasiadas consultas a tabla trades")
            print("      💡 SOLUCIÓN: Implementar cache y reducir frecuencia")
        
        if sql_queries['other_select'] > 5000:
            print("   🔴 PROBLEMA: Consultas SQL excesivas")
            print("      💡 SOLUCIÓN: Reducir logging de SQLAlchemy a WARNING")
        
        # 2. Errores
        if errors['invalid_symbol'] > 100:
            print("   🔴 PROBLEMA: Muchos errores de símbolos inválidos")
            print("      💡 SOLUCIÓN: Filtrar símbolos antes de consultar API")
        
        if errors['notional_filter'] > 50:
            print("   🟡 PROBLEMA: Errores de filtro NOTIONAL")
            print("      💡 SOLUCIÓN: Validar cantidades mínimas")
        
        # 3. Información relevante
        if len(trading_summaries) < 10:
            print("   🟡 PROBLEMA: Pocos resúmenes de trading")
            print("      💡 SOLUCIÓN: Verificar que se estén generando")
        
        if len(order_executions) < 5:
            print("   🟡 PROBLEMA: Pocas ejecuciones de órdenes")
            print("      💡 SOLUCIÓN: Verificar estrategia de trading")
        
        # Propuesta de logging optimizado
        print(f"\n🎯 PROPUESTA DE LOGGING OPTIMIZADO:")
        print("-" * 50)
        
        print("📝 INFORMACIÓN A MANTENER (Relevante):")
        print("   ✅ Resúmenes de ciclo de trading")
        print("   ✅ Ejecuciones de órdenes")
        print("   ✅ Verificaciones de balance críticas")
        print("   ✅ Errores de API y balance")
        print("   ✅ Información de ganancias/pérdidas")
        
        print("\n🗑️ INFORMACIÓN A REDUCIR (Menos relevante):")
        print("   ❌ Logs de SQLAlchemy verbosos")
        print("   ❌ Consultas SQL repetitivas")
        print("   ❌ Errores de símbolos inválidos repetitivos")
        print("   ❌ Warnings de balance no críticos")
        
        print("\n⚙️ CONFIGURACIÓN RECOMENDADA:")
        print("   • SQLAlchemy: WARNING (solo errores)")
        print("   • Trading events: INFO (consolidados)")
        print("   • API errors: ERROR (con contexto)")
        print("   • Balance checks: WARNING (solo problemas)")
        print("   • Metrics: INFO (resumidos)")
        
        # Estimación de mejora
        current_verbose = sql_queries['other_select'] + errors['invalid_symbol']
        estimated_reduction = current_verbose * 0.8  # 80% reducción
        
        print(f"\n📊 IMPACTO ESPERADO:")
        print(f"   • Logs verbosos actuales: {current_verbose:,}")
        print(f"   • Reducción estimada: {estimated_reduction:,}")
        print(f"   • Logs relevantes mantenidos: {len(trading_summaries) + len(order_executions) + len(profit_loss)}")
        print(f"   • Mejora en legibilidad: ~80%")
        
        print(f"\n✅ ANÁLISIS COMPLETADO")
        print("💡 Los logs se pueden optimizar significativamente manteniendo solo la información más relevante")
        
    except Exception as e:
        print(f"❌ Error en análisis: {e}")

def extract_timestamp(line):
    """Extrae timestamp de una línea de log"""
    timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
    return timestamp_match.group(1) if timestamp_match else "N/A"

if __name__ == "__main__":
    detailed_log_analysis() 