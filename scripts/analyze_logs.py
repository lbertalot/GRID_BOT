#!/usr/bin/env python3
"""
Script para analizar logs y proponer mejoras
"""

import re
from collections import defaultdict

def analyze_logs():
    """Analiza los logs y propone mejoras"""
    try:
        print("🔍 Análisis de Logs del Sistema de Trading")
        print("=" * 60)
        
        # Estadísticas
        total_lines = 0
        error_count = 0
        sql_count = 0
        trading_count = 0
        
        # Patrones
        error_patterns = defaultdict(int)
        sql_patterns = defaultdict(int)
        
        print("📊 Analizando logs...")
        
        with open('logs/dockers.log', 'r', encoding='utf-8') as f:
            for line in f:
                total_lines += 1
                
                # Contar errores
                if 'ERROR' in line:
                    error_count += 1
                    if 'Invalid symbol' in line:
                        error_patterns['Invalid symbol'] += 1
                    elif 'NOTIONAL' in line:
                        error_patterns['NOTIONAL filter'] += 1
                    elif 'Saldo insuficiente' in line:
                        error_patterns['Insufficient balance'] += 1
                
                # Contar SQL
                if 'sqlalchemy' in line or 'SELECT' in line:
                    sql_count += 1
                
                # Contar trading
                if 'Resumen del ciclo' in line or 'operaciones' in line:
                    trading_count += 1
        
        # Mostrar resultados
        print(f"\n📈 ESTADÍSTICAS:")
        print(f"   Total líneas: {total_lines:,}")
        print(f"   Errores: {error_count:,} ({error_count/total_lines*100:.1f}%)")
        print(f"   SQL: {sql_count:,} ({sql_count/total_lines*100:.1f}%)")
        print(f"   Trading: {trading_count:,} ({trading_count/total_lines*100:.1f}%)")
        
        print(f"\n🚨 ERRORES MÁS COMUNES:")
        for error_type, count in error_patterns.items():
            print(f"   • {error_type}: {count:,}")
        
        print(f"\n💡 PROBLEMAS IDENTIFICADOS:")
        if sql_count > total_lines * 0.5:
            print("   ❌ Demasiadas consultas SQL (más del 50%)")
        if error_patterns['Invalid symbol'] > 100:
            print("   ❌ Muchos errores de símbolos inválidos")
        
        print(f"\n🎯 MEJORAS PROPUESTAS:")
        print("   1. Reducir logging de SQLAlchemy")
        print("   2. Filtrar símbolos inválidos")
        print("   3. Consolidar logs de trading")
        print("   4. Implementar logging estructurado")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    analyze_logs() 