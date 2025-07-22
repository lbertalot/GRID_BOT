#!/usr/bin/env python3
"""
Script Runner Utility for GridBot Scripts
Facilita la ejecución de scripts de utilidad
"""

import sys
import os
import subprocess
import json
from typing import Dict, List, Optional

# Agregar el directorio padre al path para importaciones
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class ScriptRunner:
    """Utilidad para ejecutar scripts de manera organizada"""
    
    def __init__(self):
        self.scripts_dir = os.path.dirname(os.path.abspath(__file__))
        self.project_root = os.path.dirname(self.scripts_dir)
        
        # Definir scripts disponibles
        self.available_scripts = {
            # Análisis y Verificación
            "verificar-activos": {
                "file": "verificar_activos_disponibles.py",
                "description": "Verificar activos disponibles en Binance",
                "category": "Análisis"
            },
            "verificar-config": {
                "file": "verificar_y_corregir_activos.py",
                "description": "Verificar y corregir configuración de activos",
                "category": "Análisis"
            },
            "verificar-requisitos": {
                "file": "verificar_requisitos_binance.py",
                "description": "Verificar requisitos exactos de Binance",
                "category": "Análisis"
            },
            
            # Configuración
            "corregir-config": {
                "file": "corregir_configuracion_activos.py",
                "description": "Corregir configuración de activos",
                "category": "Configuración"
            },
            "activar-gridbot": {
                "file": "activar_gridbot_multi_activo.py",
                "description": "Activar GridBot multi-activo",
                "category": "Configuración"
            },
            
            # Gestión de Capital
            "distribuir-usdt": {
                "file": "distribuir_usdt_para_activos.py",
                "description": "Calcular distribución de USDT",
                "category": "Capital"
            },
            "compras-manuales": {
                "file": "compras_manuales_activos.py",
                "description": "Generar instrucciones de compras manuales",
                "category": "Capital"
            },
            
            # Compras Automáticas
            "compras-corregidas": {
                "file": "compras_con_cantidades_corregidas.py",
                "description": "Compras con cantidades optimizadas",
                "category": "Compras"
            },
            "compras-api": {
                "file": "compras_con_api_existente.py",
                "description": "Compras usando API existente",
                "category": "Compras"
            },
            "compras-binance": {
                "file": "compras_binance_directo.py",
                "description": "Compras directas con Binance",
                "category": "Compras"
            },
            "compras-auto": {
                "file": "realizar_compras_automaticas.py",
                "description": "Compras automáticas completas",
                "category": "Compras"
            },
            
            # Optimización
            "optimizar": {
                "file": "optimize_project.py",
                "description": "Optimización completa del proyecto",
                "category": "Optimización"
            }
        }
    
    def show_help(self):
        """Mostrar ayuda y scripts disponibles"""
        print("🚀 GridBot Script Runner")
        print("=" * 50)
        print()
        print("📋 Scripts disponibles:")
        print()
        
        # Agrupar por categoría
        categories = {}
        for script_id, script_info in self.available_scripts.items():
            category = script_info["category"]
            if category not in categories:
                categories[category] = []
            categories[category].append((script_id, script_info))
        
        # Mostrar por categoría
        for category, scripts in categories.items():
            print(f"📁 {category}:")
            for script_id, script_info in scripts:
                print(f"  • {script_id:20} - {script_info['description']}")
            print()
        
        print("💡 Uso:")
        print("  python3 scripts/run_script.py <script-id>")
        print()
        print("📊 Ejemplos:")
        print("  python3 scripts/run_script.py verificar-activos")
        print("  python3 scripts/run_script.py distribuir-usdt")
        print("  python3 scripts/run_script.py compras-corregidas")
        print("  python3 scripts/run_script.py optimizar")
        print()
        print("🔍 Para ver esta ayuda:")
        print("  python3 scripts/run_script.py --help")
    
    def run_script(self, script_id: str) -> bool:
        """Ejecutar un script específico"""
        if script_id not in self.available_scripts:
            print(f"❌ Script '{script_id}' no encontrado")
            print("💡 Usa '--help' para ver scripts disponibles")
            return False
        
        script_info = self.available_scripts[script_id]
        script_file = script_info["file"]
        script_path = os.path.join(self.scripts_dir, script_file)
        
        if not os.path.exists(script_path):
            print(f"❌ Archivo '{script_file}' no encontrado")
            return False
        
        print(f"🚀 Ejecutando: {script_info['description']}")
        print(f"📁 Archivo: {script_file}")
        print(f"📂 Categoría: {script_info['category']}")
        print("-" * 50)
        
        try:
            # Cambiar al directorio del proyecto
            os.chdir(self.project_root)
            
            # Ejecutar el script
            result = subprocess.run(
                [sys.executable, script_path],
                cwd=self.project_root,
                capture_output=False
            )
            
            if result.returncode == 0:
                print("-" * 50)
                print("✅ Script ejecutado exitosamente")
                return True
            else:
                print("-" * 50)
                print("❌ Script falló")
                return False
                
        except Exception as e:
            print(f"❌ Error ejecutando script: {e}")
            return False
    
    def run_workflow(self, workflow_name: str) -> bool:
        """Ejecutar un flujo de trabajo predefinido"""
        workflows = {
            "setup-completo": [
                "verificar-activos",
                "verificar-requisitos",
                "distribuir-usdt",
                "compras-corregidas",
                "activar-gridbot",
                "optimizar"
            ],
            "analisis": [
                "verificar-activos",
                "verificar-requisitos",
                "verificar-config"
            ],
            "compras": [
                "distribuir-usdt",
                "compras-corregidas"
            ],
            "configuracion": [
                "corregir-config",
                "activar-gridbot"
            ]
        }
        
        if workflow_name not in workflows:
            print(f"❌ Workflow '{workflow_name}' no encontrado")
            print("💡 Workflows disponibles:", list(workflows.keys()))
            return False
        
        print(f"🔄 Ejecutando workflow: {workflow_name}")
        print("=" * 50)
        
        success_count = 0
        total_scripts = len(workflows[workflow_name])
        
        for i, script_id in enumerate(workflows[workflow_name], 1):
            print(f"\n📋 Paso {i}/{total_scripts}: {script_id}")
            if self.run_script(script_id):
                success_count += 1
            else:
                print(f"⚠️ Paso {i} falló, continuando...")
        
        print("\n" + "=" * 50)
        print(f"📊 Workflow completado: {success_count}/{total_scripts} exitosos")
        
        return success_count == total_scripts
    
    def list_workflows(self):
        """Listar workflows disponibles"""
        workflows = {
            "setup-completo": "Configuración completa del sistema",
            "analisis": "Análisis inicial de activos",
            "compras": "Proceso de compras",
            "configuracion": "Configuración del GridBot"
        }
        
        print("🔄 Workflows disponibles:")
        print()
        for workflow_id, description in workflows.items():
            print(f"  • {workflow_id:15} - {description}")
        print()
        print("💡 Uso:")
        print("  python3 scripts/run_script.py --workflow <workflow-id>")


def main():
    """Función principal"""
    runner = ScriptRunner()
    
    if len(sys.argv) < 2:
        runner.show_help()
        return
    
    command = sys.argv[1]
    
    if command in ["--help", "-h", "help"]:
        runner.show_help()
    elif command == "--workflows":
        runner.list_workflows()
    elif command.startswith("--workflow"):
        if len(sys.argv) < 3:
            print("❌ Especifica un workflow")
            runner.list_workflows()
            return
        workflow_name = sys.argv[2]
        runner.run_workflow(workflow_name)
    else:
        script_id = command
        runner.run_script(script_id)


if __name__ == "__main__":
    main() 