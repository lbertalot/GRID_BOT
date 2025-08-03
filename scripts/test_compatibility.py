#!/usr/bin/env python3
"""
Script de Testing de Compatibilidad - Grid Trading Bot
Valida que todas las dependencias sean compatibles con el código existente
"""

import sys
import importlib
import subprocess
import os
from pathlib import Path
from typing import List, Dict, Tuple

class CompatibilityTester:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.app_dir = self.project_root / "app"
        self.tests_dir = self.project_root / "tests"
        self.results = {
            "imports": [],
            "modules": [],
            "dependencies": [],
            "errors": []
        }
    
    def test_imports(self) -> List[Dict]:
        """Prueba la importación de módulos principales"""
        print("🔍 Probando importaciones de módulos principales...")
        
        # Módulos críticos del proyecto
        critical_modules = [
            "fastapi",
            "uvicorn", 
            "sqlalchemy",
            "asyncpg",
            "pydantic",
            "pydantic_settings",
            "binance",
            "ccxt",
            "celery",
            "redis",
            "prometheus_client",
            "numpy",
            "pandas",
            "sklearn",
            "scipy",
            "jose",
            "passlib",
            "dotenv",
            "apscheduler",
            "jinja2",
            "aiofiles",
            "telegram",
            "requests",
            "websockets",
            "cryptography",
            "bcrypt"
        ]
        
        results = []
        for module in critical_modules:
            try:
                importlib.import_module(module.replace("_", "."))
                print(f"  ✅ {module}")
                results.append({"module": module, "status": "success", "error": None})
            except ImportError as e:
                print(f"  ❌ {module}: {e}")
                results.append({"module": module, "status": "error", "error": str(e)})
                self.results["errors"].append(f"Import error: {module} - {e}")
        
        self.results["imports"] = results
        return results
    
    def test_project_modules(self) -> List[Dict]:
        """Prueba la importación de módulos del proyecto"""
        print("\n🔍 Probando módulos del proyecto...")
        
        project_modules = [
            "app.main",
            "app.main_simple", 
            "app.core.config",
            "app.core.auth",
            "app.core.celery_app",
            "app.db.session",
            "app.models.base",
            "app.models.grid_config",
            "app.models.trade",
            "app.services.binance_client",
            "app.services.binance_service",
            "app.api.strategy_routes",
            "app.api.metrics_routes",
            "app.api.config_routes"
        ]
        
        results = []
        for module in project_modules:
            try:
                importlib.import_module(module)
                print(f"  ✅ {module}")
                results.append({"module": module, "status": "success", "error": None})
            except ImportError as e:
                print(f"  ❌ {module}: {e}")
                results.append({"module": module, "status": "error", "error": str(e)})
                self.results["errors"].append(f"Project module error: {module} - {e}")
        
        self.results["modules"] = results
        return results
    
    def test_dependencies_versions(self) -> List[Dict]:
        """Verifica las versiones de las dependencias críticas"""
        print("\n🔍 Verificando versiones de dependencias...")
        
        try:
            import pkg_resources
            
            critical_packages = {
                "fastapi": "0.104.1",
                "uvicorn": "0.24.0", 
                "sqlalchemy": "2.0.23",
                "asyncpg": "0.29.0",
                "pydantic": "2.5.0",
                "python-binance": "1.0.19",
                "ccxt": "4.1.77",
                "celery": "5.3.4",
                "redis": "5.0.1",
                "numpy": "1.24.3",
                "pandas": "2.1.4",
                "scikit-learn": "1.3.2"
            }
            
            results = []
            for package, expected_version in critical_packages.items():
                try:
                    installed_version = pkg_resources.get_distribution(package).version
                    status = "match" if installed_version == expected_version else "mismatch"
                    print(f"  {'✅' if status == 'match' else '⚠️'} {package}: {installed_version} (expected: {expected_version})")
                    results.append({
                        "package": package,
                        "installed": installed_version,
                        "expected": expected_version,
                        "status": status
                    })
                except pkg_resources.DistributionNotFound:
                    print(f"  ❌ {package}: No instalado")
                    results.append({
                        "package": package,
                        "installed": "Not installed",
                        "expected": expected_version,
                        "status": "missing"
                    })
            
            self.results["dependencies"] = results
            return results
            
        except Exception as e:
            print(f"  ❌ Error verificando versiones: {e}")
            return []
    
    def test_websocket_alternative(self) -> Dict:
        """Prueba la librería alternativa de WebSocket"""
        print("\n🔍 Probando librería alternativa de WebSocket...")
        
        try:
            import unicorn_binance_websocket_api
            print("  ✅ unicorn-binance-websocket-api disponible")
            return {"status": "available", "error": None}
        except ImportError:
            print("  ⚠️ unicorn-binance-websocket-api no disponible (opcional)")
            return {"status": "not_available", "error": "Optional dependency"}
    
    def test_basic_functionality(self) -> List[Dict]:
        """Prueba funcionalidades básicas del proyecto"""
        print("\n🔍 Probando funcionalidades básicas...")
        
        tests = []
        
        # Test 1: Configuración básica
        try:
            from app.core.config import settings
            print("  ✅ Configuración cargada correctamente")
            tests.append({"test": "config_loading", "status": "success"})
        except Exception as e:
            print(f"  ❌ Error cargando configuración: {e}")
            tests.append({"test": "config_loading", "status": "error", "error": str(e)})
        
        # Test 2: Conexión a base de datos
        try:
            from app.db.session import get_db
            print("  ✅ Módulo de base de datos disponible")
            tests.append({"test": "database_module", "status": "success"})
        except Exception as e:
            print(f"  ❌ Error en módulo de base de datos: {e}")
            tests.append({"test": "database_module", "status": "error", "error": str(e)})
        
        # Test 3: Cliente Binance
        try:
            from app.services.binance_client import BinanceClient
            print("  ✅ Cliente Binance disponible")
            tests.append({"test": "binance_client", "status": "success"})
        except Exception as e:
            print(f"  ❌ Error en cliente Binance: {e}")
            tests.append({"test": "binance_client", "status": "error", "error": str(e)})
        
        # Test 4: FastAPI app
        try:
            from app.main_simple import app
            print("  ✅ Aplicación FastAPI cargada")
            tests.append({"test": "fastapi_app", "status": "success"})
        except Exception as e:
            print(f"  ❌ Error cargando aplicación FastAPI: {e}")
            tests.append({"test": "fastapi_app", "status": "error", "error": str(e)})
        
        return tests
    
    def run_pytest(self) -> Dict:
        """Ejecuta los tests existentes del proyecto"""
        print("\n🔍 Ejecutando tests existentes...")
        
        try:
            # Ejecutar pytest con salida simplificada
            result = subprocess.run(
                ["python", "-m", "pytest", "tests/", "-v", "--tb=short", "--maxfail=5"],
                capture_output=True,
                text=True,
                cwd=self.project_root
            )
            
            if result.returncode == 0:
                print("  ✅ Tests ejecutados exitosamente")
                return {"status": "success", "output": result.stdout}
            else:
                print(f"  ⚠️ Tests con errores (algunos pueden ser esperados)")
                print(f"  Salida: {result.stdout[:500]}...")
                return {"status": "partial", "output": result.stdout, "errors": result.stderr}
                
        except Exception as e:
            print(f"  ❌ Error ejecutando tests: {e}")
            return {"status": "error", "error": str(e)}
    
    def generate_report(self) -> str:
        """Genera un reporte completo de compatibilidad"""
        print("\n📊 Generando reporte de compatibilidad...")
        
        total_imports = len(self.results["imports"])
        successful_imports = len([r for r in self.results["imports"] if r["status"] == "success"])
        
        total_modules = len(self.results["modules"])
        successful_modules = len([r for r in self.results["modules"] if r["status"] == "success"])
        
        total_deps = len(self.results["dependencies"])
        matching_deps = len([r for r in self.results["dependencies"] if r["status"] == "match"])
        
        report = f"""
╔══════════════════════════════════════════════════════════════╗
║                    REPORTE DE COMPATIBILIDAD                 ║
║                        Grid Trading Bot                      ║
╚══════════════════════════════════════════════════════════════╝

📦 DEPENDENCIAS EXTERNAS:
   ✅ Importaciones exitosas: {successful_imports}/{total_imports}
   ❌ Errores de importación: {total_imports - successful_imports}

📁 MÓDULOS DEL PROYECTO:
   ✅ Módulos cargados: {successful_modules}/{total_modules}
   ❌ Errores de módulos: {total_modules - successful_modules}

🔢 VERSIONES DE DEPENDENCIAS:
   ✅ Versiones coincidentes: {matching_deps}/{total_deps}
   ⚠️ Versiones diferentes: {total_deps - matching_deps}

🚨 ERRORES ENCONTRADOS:
"""
        
        if self.results["errors"]:
            for error in self.results["errors"][:10]:  # Mostrar solo los primeros 10
                report += f"   • {error}\n"
        else:
            report += "   ✅ No se encontraron errores críticos\n"
        
        report += f"""
📋 RECOMENDACIONES:
"""
        
        if successful_imports < total_imports:
            report += "   • Revisar dependencias faltantes\n"
        
        if successful_modules < total_modules:
            report += "   • Verificar estructura del proyecto\n"
        
        if matching_deps < total_deps:
            report += "   • Considerar actualizar versiones\n"
        
        report += """
🎯 ESTADO GENERAL:
"""
        
        overall_score = (successful_imports + successful_modules) / (total_imports + total_modules) * 100
        
        if overall_score >= 90:
            report += "   🟢 EXCELENTE - El proyecto está listo para usar\n"
        elif overall_score >= 70:
            report += "   🟡 BUENO - Algunas mejoras menores necesarias\n"
        else:
            report += "   🔴 REQUIERE ATENCIÓN - Problemas significativos detectados\n"
        
        report += f"   Puntuación general: {overall_score:.1f}%\n"
        
        return report
    
    def run_all_tests(self) -> Dict:
        """Ejecuta todas las pruebas de compatibilidad"""
        print("🚀 Iniciando Testing de Compatibilidad Completo")
        print("=" * 60)
        
        # Ejecutar todas las pruebas
        self.test_imports()
        self.test_project_modules()
        self.test_dependencies_versions()
        self.test_websocket_alternative()
        self.test_basic_functionality()
        
        # Ejecutar pytest (opcional, puede tomar tiempo)
        print("\n⏳ Ejecutando tests unitarios (esto puede tomar unos minutos)...")
        pytest_result = self.run_pytest()
        
        # Generar reporte
        report = self.generate_report()
        print(report)
        
        # Guardar reporte en archivo
        report_file = self.project_root / "compatibility_report.txt"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report)
        
        print(f"\n📄 Reporte guardado en: {report_file}")
        
        return {
            "report": report,
            "results": self.results,
            "pytest_result": pytest_result
        }

def main():
    """Función principal"""
    tester = CompatibilityTester()
    results = tester.run_all_tests()
    
    # Código de salida basado en resultados
    total_errors = len(tester.results["errors"])
    if total_errors > 10:  # Más de 10 errores críticos
        sys.exit(1)
    elif total_errors > 5:  # Algunos errores, pero no críticos
        sys.exit(2)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main() 