#!/usr/bin/env python3
"""
Script para verificar la efectividad de las mejoras de logging
"""

import subprocess
import re
from datetime import datetime, timedelta

def verify_logging_improvements():
    """Verifica la efectividad de las mejoras de logging"""
    try:
        print("🔍 Verificando Efectividad de las Mejoras de Logging")
        print("=" * 60)
        
        # 1. Verificar logs recientes
        print("1️⃣ Analizando logs de los últimos 5 minutos...")
        
        # Obtener logs recientes
        result = subprocess.run([
            'docker-compose', 'logs', '--since=5m'
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            print("   ❌ Error obteniendo logs")
            return
        
        recent_logs = result.stdout
        
        # Contar tipos de logs
        total_lines = len(recent_logs.split('\n'))
        sqlalchemy_logs = len(re.findall(r'sqlalchemy', recent_logs, re.IGNORECASE))
        error_logs = len(re.findall(r'ERROR', recent_logs))
        warning_logs = len(re.findall(r'WARNING', recent_logs))
        info_logs = len(re.findall(r'INFO', recent_logs))
        trading_logs = len(re.findall(r'(Resumen|trading|trade)', recent_logs, re.IGNORECASE))
        
        print(f"   📊 Total de líneas: {total_lines}")
        print(f"   🗄️ Logs SQLAlchemy: {sqlalchemy_logs}")
        print(f"   ❌ Errores: {error_logs}")
        print(f"   ⚠️ Warnings: {warning_logs}")
        print(f"   ℹ️ Info: {info_logs}")
        print(f"   📈 Trading: {trading_logs}")
        
        # 2. Comparar con logs anteriores
        print("\n2️⃣ Comparando con logs anteriores...")
        
        # Obtener logs de hace 10 minutos
        result_old = subprocess.run([
            'docker-compose', 'logs', '--since=15m', '--until=10m'
        ], capture_output=True, text=True, timeout=30)
        
        if result_old.returncode == 0:
            old_logs = result_old.stdout
            old_sqlalchemy = len(re.findall(r'sqlalchemy', old_logs, re.IGNORECASE))
            old_total = len(old_logs.split('\n'))
            
            if old_sqlalchemy > 0:
                reduction = ((old_sqlalchemy - sqlalchemy_logs) / old_sqlalchemy) * 100
                print(f"   📊 Reducción de logs SQLAlchemy: {reduction:.1f}%")
            else:
                print("   📊 No hay logs SQLAlchemy anteriores para comparar")
        else:
            print("   ⚠️ No se pudieron obtener logs anteriores")
        
        # 3. Verificar errores específicos
        print("\n3️⃣ Verificando errores específicos...")
        
        invalid_symbol_errors = len(re.findall(r'Invalid symbol', recent_logs))
        notional_errors = len(re.findall(r'NOTIONAL', recent_logs))
        balance_errors = len(re.findall(r'Saldo insuficiente', recent_logs))
        
        print(f"   🚨 Errores de símbolos inválidos: {invalid_symbol_errors}")
        print(f"   🚨 Errores NOTIONAL: {notional_errors}")
        print(f"   🚨 Errores de saldo: {balance_errors}")
        
        # 4. Verificar información relevante
        print("\n4️⃣ Verificando información relevante...")
        
        trading_summaries = len(re.findall(r'Resumen del ciclo', recent_logs))
        order_executions = len(re.findall(r'orden ejecutada|order executed', recent_logs, re.IGNORECASE))
        balance_checks = len(re.findall(r'Balance|saldo', recent_logs, re.IGNORECASE))
        
        print(f"   📊 Resúmenes de trading: {trading_summaries}")
        print(f"   📈 Ejecuciones de órdenes: {order_executions}")
        print(f"   💰 Verificaciones de balance: {balance_checks}")
        
        # 5. Evaluar efectividad
        print("\n5️⃣ Evaluación de efectividad...")
        
        # Calcular métricas de efectividad
        sqlalchemy_ratio = (sqlalchemy_logs / total_lines) * 100 if total_lines > 0 else 0
        relevant_ratio = ((trading_logs + error_logs) / total_lines) * 100 if total_lines > 0 else 0
        
        print(f"   📊 Ratio de logs SQLAlchemy: {sqlalchemy_ratio:.1f}%")
        print(f"   📊 Ratio de logs relevantes: {relevant_ratio:.1f}%")
        
        # Evaluar efectividad
        if sqlalchemy_ratio < 20:
            print("   ✅ Efectividad: EXCELENTE - Logs SQLAlchemy reducidos significativamente")
        elif sqlalchemy_ratio < 40:
            print("   ⚠️ Efectividad: BUENA - Logs SQLAlchemy moderadamente reducidos")
        else:
            print("   ❌ Efectividad: POBRE - Logs SQLAlchemy aún muy altos")
        
        if relevant_ratio > 60:
            print("   ✅ Calidad: EXCELENTE - Alta proporción de logs relevantes")
        elif relevant_ratio > 40:
            print("   ⚠️ Calidad: BUENA - Proporción moderada de logs relevantes")
        else:
            print("   ❌ Calidad: POBRE - Baja proporción de logs relevantes")
        
        # 6. Recomendaciones
        print("\n6️⃣ Recomendaciones:")
        
        if sqlalchemy_ratio > 30:
            print("   🔧 Necesario: Integrar configuración de SQLAlchemy en el código")
            print("   🔧 Necesario: Aplicar filtros de logging en tiempo de ejecución")
        
        if invalid_symbol_errors > 10:
            print("   🔧 Necesario: Implementar filtro de símbolos inválidos")
        
        if relevant_ratio < 50:
            print("   🔧 Necesario: Consolidar más logs de trading")
        
        # 7. Próximos pasos
        print("\n7️⃣ Próximos pasos:")
        print("   📊 Monitorear logs durante las próximas 24 horas")
        print("   🔧 Integrar configuración de logging en el código principal")
        print("   📈 Verificar que la información relevante se mantiene")
        print("   ⚙️ Ajustar configuración según resultados")
        
        print("\n✅ Verificación completada")
        
    except Exception as e:
        print(f"❌ Error en verificación: {e}")

if __name__ == "__main__":
    verify_logging_improvements() 