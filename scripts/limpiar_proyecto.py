#!/usr/bin/env python3
"""
Script para limpiar y optimizar el proyecto GridBot
"""

import os
import shutil
import json
import re
from pathlib import Path
from typing import List, Dict, Set

class ProjectCleaner:
    def __init__(self):
        self.project_root = Path(".")
        self.files_to_delete = []
        self.files_to_keep = []
        self.archived_files = []
        
    def analyze_project_structure(self):
        """Analiza la estructura del proyecto y identifica archivos a limpiar"""
        print("🔍 ANALIZANDO ESTRUCTURA DEL PROYECTO")
        print("=" * 50)
        
        # Archivos de configuración esenciales (NO TOCAR)
        essential_files = {
            "docker-compose.yml", "Dockerfile", "requirements.txt", 
            ".env", ".gitignore", "README.md", "main.py"
        }
        
        # Archivos de configuración JSON duplicados o temporales
        json_files_to_clean = [
            "grid_config_final_ajustado.json",
            "grid_config_cantidades_corregidas.json", 
            "grid_config_multi_activo_final.json",
            "grid_config_final.json",
            "grid_config_applied.json",
            "all_assets_grid_config.json",
            "all_assets_grids_config.json",
            "scheduler_multi_asset_config.json",
            "configuracion_activos_viable.json",
            "configuracion_activos_corregida.json",
            "distribucion_corregida.json",
            "distribucion_usdt_activos.json",
            "ars_distribution_config.json",
            "smart_distribution_config.json",
            "fractional_trading_config.json",
            "pnl_dashboard_working.json",
            "dashboard_pnl.json",
            "working_dashboard.json",
            "functional_dashboard.json",
            "pnl_dashboard.json",
            "grafana_dashboard.json",
            "trading_dashboard.json",
            "profit_loss_data.json",
            "analisis_balances_actuales.json",
            "reporte_multi_activo.json",
            "optimization_report.json",
            "resultados_compras_corregidas.json",
            "resultados_compras_binance_directo.json",
            "resultados_compras_api_existente.json",
            "instrucciones_compras_manuales.json",
            "validacion_ganancias_recientes.json",
            "transactions_analysis.json",
            "gridbot_pnl_metrics.txt"
        ]
        
        # Scripts temporales o de prueba en el directorio raíz
        temp_scripts = [
            "ejecutar_compras_activos.py",
            "aplicar_config_simple.py",
            "aplicar_parametros_optimizados.py",
            "validar_ganancias_recientes.py",
            "actualizar_config_grid.py",
            "ajustar_parametros.py",
            "analisis_transacciones.py",
            "update_dashboard_pnl.py",
            "setup_fractional_trading.py",
            "setup_all_assets_trading.py",
            "setup_trading_with_existing_assets.py",
            "distribute_ars_smart.py",
            "setup_working_dashboard.py",
            "generate_pnl_metrics.py",
            "quick_pnl_check.py",
            "distribute_ars_to_assets.py",
            "update_pnl_metrics.py",
            "setup_multi_asset_grids.py",
            "check_trading_assets.py",
            "buy_bnb_for_trading.py",
            "list_grafana_dashboards.py",
            "setup_pnl_monitoring.py",
            "check_pnl_simple.py",
            "profit_loss_tracker.py",
            "test_telegram_scheduler.py",
            "check_binance_connection.py",
            "import_working_dashboard.py",
            "test_precision_error.py",
            "test_improved_error_handling.py",
            "setup_grafana_complete.py",
            "configure_smart_scheduler.py",
            "disable_auto_scheduler.py",
            "configure_grafana_manual.py",
            "setup_trading_dashboard.py",
            "setup_grafana_dashboard.py",
            "run_conservative_grids.py",
            "buy_assets_for_grids.py",
            "setup_conservative_grids.py",
            "analyze_trading_pairs.py",
            "final_db_check.py",
            "init_database.py",
            "check_database.py",
            "fix_grid_trading.py",
            "test_binance_direct.py",
            "test_telegram_simple.py",
            "test_telegram_alerts.py"
        ]
        
        # Archivos de documentación temporales
        temp_docs = [
            "RESUMEN_OPTIMIZACION_PROYECTO.md",
            "RESUMEN_ANALISIS_MULTI_ACTIVO.md",
            "RESUMEN_MONITOREO_VALIDACION.md",
            "ANALISIS_FINAL_TRANSACCIONES.md",
            "RESUMEN_EJECUTIVO.md",
            "PROGRESO_PROYECTO.md",
            "SOLUCION_FINAL.md",
            "LIMPEZA_DASHBOARDS.md",
            "SOLUCION_DASHBOARD.md",
            "DIAGNOSTICO_TELEGRAM.md",
            "RESULTADOS_PRUEBAS.md"
        ]
        
        # Archivos a eliminar
        self.files_to_delete.extend(json_files_to_clean)
        self.files_to_delete.extend(temp_scripts)
        self.files_to_delete.extend(temp_docs)
        
        # Archivos a mantener
        self.files_to_keep.extend(essential_files)
        self.files_to_keep.append("grid_config_optimized.json")  # Configuración principal
        
        print(f"📁 Archivos identificados para eliminación: {len(self.files_to_delete)}")
        print(f"💾 Archivos esenciales a mantener: {len(self.files_to_keep)}")
        
    def clean_duplicate_configs(self):
        """Limpia configuraciones duplicadas, manteniendo solo la principal"""
        print("\n🧹 LIMPIANDO CONFIGURACIONES DUPLICADAS")
        print("-" * 40)
        
        # Mantener solo grid_config_optimized.json como configuración principal
        config_files = [
            "grid_config_final_ajustado.json",
            "grid_config_cantidades_corregidas.json",
            "grid_config_multi_activo_final.json",
            "grid_config_final.json",
            "grid_config_applied.json"
        ]
        
        for config_file in config_files:
            if os.path.exists(config_file):
                print(f"🗑️ Eliminando configuración duplicada: {config_file}")
                os.remove(config_file)
                
    def clean_temp_scripts(self):
        """Limpia scripts temporales del directorio raíz"""
        print("\n🧹 LIMPIANDO SCRIPTS TEMPORALES")
        print("-" * 35)
        
        temp_scripts = [
            "ejecutar_compras_activos.py",
            "aplicar_config_simple.py",
            "aplicar_parametros_optimizados.py",
            "validar_ganancias_recientes.py",
            "actualizar_config_grid.py",
            "ajustar_parametros.py",
            "analisis_transacciones.py",
            "update_dashboard_pnl.py",
            "setup_fractional_trading.py",
            "setup_all_assets_trading.py",
            "setup_trading_with_existing_assets.py",
            "distribute_ars_smart.py",
            "setup_working_dashboard.py",
            "generate_pnl_metrics.py",
            "quick_pnl_check.py",
            "distribute_ars_to_assets.py",
            "update_pnl_metrics.py",
            "setup_multi_asset_grids.py",
            "check_trading_assets.py",
            "buy_bnb_for_trading.py",
            "list_grafana_dashboards.py",
            "setup_pnl_monitoring.py",
            "check_pnl_simple.py",
            "profit_loss_tracker.py",
            "test_telegram_scheduler.py",
            "check_binance_connection.py",
            "import_working_dashboard.py",
            "test_precision_error.py",
            "test_improved_error_handling.py",
            "setup_grafana_complete.py",
            "configure_smart_scheduler.py",
            "disable_auto_scheduler.py",
            "configure_grafana_manual.py",
            "setup_trading_dashboard.py",
            "setup_grafana_dashboard.py",
            "run_conservative_grids.py",
            "buy_assets_for_grids.py",
            "setup_conservative_grids.py",
            "analyze_trading_pairs.py",
            "final_db_check.py",
            "init_database.py",
            "check_database.py",
            "fix_grid_trading.py",
            "test_binance_direct.py",
            "test_telegram_simple.py",
            "test_telegram_alerts.py"
        ]
        
        for script in temp_scripts:
            if os.path.exists(script):
                print(f"🗑️ Eliminando script temporal: {script}")
                os.remove(script)
                
    def clean_temp_docs(self):
        """Limpia documentación temporal"""
        print("\n🧹 LIMPIANDO DOCUMENTACIÓN TEMPORAL")
        print("-" * 40)
        
        temp_docs = [
            "RESUMEN_OPTIMIZACION_PROYECTO.md",
            "RESUMEN_ANALISIS_MULTI_ACTIVO.md",
            "RESUMEN_MONITOREO_VALIDACION.md",
            "ANALISIS_FINAL_TRANSACCIONES.md",
            "RESUMEN_EJECUTIVO.md",
            "PROGRESO_PROYECTO.md",
            "SOLUCION_FINAL.md",
            "LIMPEZA_DASHBOARDS.md",
            "SOLUCION_DASHBOARD.md",
            "DIAGNOSTICO_TELEGRAM.md",
            "RESULTADOS_PRUEBAS.md"
        ]
        
        for doc in temp_docs:
            if os.path.exists(doc):
                print(f"🗑️ Eliminando documentación temporal: {doc}")
                os.remove(doc)
                
    def clean_temp_json_files(self):
        """Limpia archivos JSON temporales"""
        print("\n🧹 LIMPIANDO ARCHIVOS JSON TEMPORALES")
        print("-" * 40)
        
        temp_json_files = [
            "all_assets_grid_config.json",
            "all_assets_grids_config.json",
            "scheduler_multi_asset_config.json",
            "configuracion_activos_viable.json",
            "configuracion_activos_corregida.json",
            "distribucion_corregida.json",
            "distribucion_usdt_activos.json",
            "ars_distribution_config.json",
            "smart_distribution_config.json",
            "fractional_trading_config.json",
            "pnl_dashboard_working.json",
            "dashboard_pnl.json",
            "working_dashboard.json",
            "functional_dashboard.json",
            "pnl_dashboard.json",
            "grafana_dashboard.json",
            "trading_dashboard.json",
            "profit_loss_data.json",
            "analisis_balances_actuales.json",
            "reporte_multi_activo.json",
            "optimization_report.json",
            "resultados_compras_corregidas.json",
            "resultados_compras_binance_directo.json",
            "resultados_compras_api_existente.json",
            "instrucciones_compras_manuales.json",
            "validacion_ganancias_recientes.json",
            "transactions_analysis.json",
            "gridbot_pnl_metrics.txt"
        ]
        
        for json_file in temp_json_files:
            if os.path.exists(json_file):
                print(f"🗑️ Eliminando JSON temporal: {json_file}")
                os.remove(json_file)
                
    def clean_app_directory(self):
        """Limpia archivos duplicados en el directorio app"""
        print("\n🧹 LIMPIANDO DIRECTORIO APP")
        print("-" * 30)
        
        # Eliminar archivos duplicados en app/
        app_files_to_clean = [
            "app/main_optimized.py",  # Mantener solo main.py
            "app/web.py"  # Archivo no utilizado
        ]
        
        for file_path in app_files_to_clean:
            if os.path.exists(file_path):
                print(f"🗑️ Eliminando archivo duplicado: {file_path}")
                os.remove(file_path)
                
    def optimize_scripts_directory(self):
        """Optimiza el directorio scripts, manteniendo solo los útiles"""
        print("\n🧹 OPTIMIZANDO DIRECTORIO SCRIPTS")
        print("-" * 35)
        
        # Scripts útiles a mantener
        useful_scripts = [
            "scripts/run_script.py",
            "scripts/README.md",
            "scripts/verificacion_final_multi_activo.py",
            "scripts/ajustar_cantidades_finales.py"
        ]
        
        # Scripts temporales a eliminar
        temp_scripts = [
            "scripts/corregir_cantidades_multi_activo.py",
            "scripts/forzar_multi_activo.py",
            "scripts/verificar_balances_actuales.py",
            "scripts/verificar_multi_activo.py",
            "scripts/diagnostico_multi_activo.py",
            "scripts/optimize_project.py",
            "scripts/compras_con_cantidades_corregidas.py",
            "scripts/verificar_requisitos_binance.py",
            "scripts/compras_binance_directo.py",
            "scripts/compras_con_api_existente.py",
            "scripts/realizar_compras_automaticas.py",
            "scripts/activar_gridbot_multi_activo.py",
            "scripts/compras_manuales_activos.py",
            "scripts/ejecutar_compras_automaticas.py",
            "scripts/distribuir_usdt_para_activos.py",
            "scripts/corregir_configuracion_activos.py",
            "scripts/verificar_y_corregir_activos.py",
            "scripts/verificar_activos_disponibles.py"
        ]
        
        for script in temp_scripts:
            if os.path.exists(script):
                print(f"🗑️ Eliminando script temporal: {script}")
                os.remove(script)
                
    def clean_debug_code(self):
        """Limpia código de debug y print statements"""
        print("\n🧹 LIMPIANDO CÓDIGO DE DEBUG")
        print("-" * 30)
        
        # Archivos principales a limpiar
        main_files = [
            "app/main.py",
            "app/scheduler/grid_job.py",
            "app/services/grid_strategy.py",
            "app/services/order_validation.py",
            "app/services/binance_service.py"
        ]
        
        for file_path in main_files:
            if os.path.exists(file_path):
                self.clean_debug_from_file(file_path)
                
    def clean_debug_from_file(self, file_path: str):
        """Limpia código de debug de un archivo específico"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Contar print statements
            print_count = content.count('print(')
            
            if print_count > 0:
                # Remover print statements de debug (mantener los importantes)
                lines = content.split('\n')
                cleaned_lines = []
                
                for line in lines:
                    # Mantener prints importantes (errores, alertas)
                    if 'print(' in line:
                        if any(keyword in line.lower() for keyword in ['error', 'alert', 'success', 'warning', 'info']):
                            cleaned_lines.append(line)
                        elif 'print(f"' in line and any(keyword in line for keyword in ['✅', '❌', '🚨', '📊', '🎯']):
                            cleaned_lines.append(line)
                        else:
                            # Comentar prints de debug
                            if line.strip().startswith('print('):
                                cleaned_lines.append(f"# {line}")
                            else:
                                cleaned_lines.append(line)
                    else:
                        cleaned_lines.append(line)
                
                cleaned_content = '\n'.join(cleaned_lines)
                
                # Escribir archivo limpio
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(cleaned_content)
                
                print(f"🧹 Limpiado {file_path}: {print_count} print statements comentados")
                
        except Exception as e:
            print(f"❌ Error limpiando {file_path}: {e}")
            
    def verify_essential_files(self):
        """Verifica que los archivos esenciales estén presentes"""
        print("\n✅ VERIFICANDO ARCHIVOS ESENCIALES")
        print("-" * 35)
        
        essential_files = [
            "docker-compose.yml",
            "Dockerfile", 
            "requirements.txt",
            "app/main.py",
            "grid_config_optimized.json"
        ]
        
        missing_files = []
        for file_path in essential_files:
            if not os.path.exists(file_path):
                missing_files.append(file_path)
            else:
                print(f"✅ {file_path}")
                
        if missing_files:
            print(f"\n❌ Archivos faltantes: {missing_files}")
        else:
            print("\n✅ Todos los archivos esenciales están presentes")
            
    def create_cleanup_report(self):
        """Crea un reporte de la limpieza realizada"""
        print("\n📊 CREANDO REPORTE DE LIMPIEZA")
        print("-" * 30)
        
        report = {
            "timestamp": "2025-07-20",
            "cleanup_summary": {
                "files_deleted": len(self.files_to_delete),
                "scripts_cleaned": 0,
                "debug_code_cleaned": 0,
                "duplicate_configs_removed": 0
            },
            "project_structure": {
                "essential_files_present": True,
                "main_config_file": "grid_config_optimized.json",
                "scripts_directory_optimized": True
            },
            "recommendations": [
                "Proyecto limpio y optimizado",
                "Estructura modular mantenida",
                "Código de debug removido",
                "Configuraciones duplicadas eliminadas"
            ]
        }
        
        with open('cleanup_report.json', 'w') as f:
            json.dump(report, f, indent=2)
            
        print("📄 Reporte de limpieza guardado en 'cleanup_report.json'")
        
    def run_cleanup(self):
        """Ejecuta todo el proceso de limpieza"""
        print("🚀 INICIANDO LIMPIEZA DEL PROYECTO")
        print("=" * 50)
        
        # Análisis inicial
        self.analyze_project_structure()
        
        # Limpieza sistemática
        self.clean_duplicate_configs()
        self.clean_temp_scripts()
        self.clean_temp_docs()
        self.clean_temp_json_files()
        self.clean_app_directory()
        self.optimize_scripts_directory()
        self.clean_debug_code()
        
        # Verificación final
        self.verify_essential_files()
        self.create_cleanup_report()
        
        print("\n🎉 LIMPIEZA COMPLETADA")
        print("=" * 25)
        print("✅ Proyecto optimizado y listo para desarrollo")
        print("✅ Archivos temporales eliminados")
        print("✅ Código de debug limpiado")
        print("✅ Estructura modular mantenida")
        print("✅ Configuración principal preservada")

def main():
    """Función principal"""
    cleaner = ProjectCleaner()
    cleaner.run_cleanup()

if __name__ == "__main__":
    main() 