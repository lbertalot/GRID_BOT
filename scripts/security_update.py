#!/usr/bin/env python3
"""
Script para actualizar dependencias de seguridad críticas
Actualiza las vulnerabilidades detectadas por Dependabot
"""

import subprocess
import sys
import json
from pathlib import Path
from typing import Dict, List, Tuple

def run_command(command: str) -> Tuple[int, str, str]:
    """Ejecuta un comando y retorna el código de salida, stdout y stderr"""
    try:
        result = subprocess.run(
            command.split(),
            capture_output=True,
            text=True,
            check=False
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return 1, "", str(e)

def check_package_version(package: str) -> str:
    """Verifica la versión actual de un paquete"""
    code, stdout, stderr = run_command(f"pip3 show {package}")
    if code == 0:
        for line in stdout.split('\n'):
            if line.startswith('Version:'):
                return line.split(':')[1].strip()
    return "No instalado"

def update_package(package: str, version: str = None) -> bool:
    """Actualiza un paquete a una versión específica"""
    if version:
        cmd = f"pip3 install {package}=={version}"
    else:
        cmd = f"pip3 install --upgrade {package}"
    
    print(f"Actualizando {package}...")
    code, stdout, stderr = run_command(cmd)
    
    if code == 0:
        print(f"✅ {package} actualizado exitosamente")
        return True
    else:
        print(f"❌ Error actualizando {package}: {stderr}")
        return False

def main():
    """Función principal para actualizar dependencias de seguridad"""
    print("🔒 Actualizando dependencias de seguridad críticas...")
    print("=" * 60)
    
    # Dependencias críticas que necesitan actualización
    critical_updates = {
        "python-jose": "3.3.0",  # Corrige algorithm confusion vulnerability
        "python-multipart": "0.0.7",  # Corrige DoS y ReDoS vulnerabilities
        "cryptography": "41.0.7",  # Corrige NULL pointer dereference y Bleichenbacher
    }
    
    # Verificar versiones actuales
    print("📋 Versiones actuales:")
    for package, target_version in critical_updates.items():
        current_version = check_package_version(package)
        print(f"  {package}: {current_version} -> {target_version}")
    
    print("\n🔄 Iniciando actualizaciones...")
    
    # Actualizar dependencias críticas
    success_count = 0
    for package, version in critical_updates.items():
        if update_package(package, version):
            success_count += 1
        print()
    
    # Verificar versiones después de la actualización
    print("✅ Verificación final de versiones:")
    for package, target_version in critical_updates.items():
        current_version = check_package_version(package)
        status = "✅" if current_version == target_version else "❌"
        print(f"  {status} {package}: {current_version}")
    
    print(f"\n📊 Resumen: {success_count}/{len(critical_updates)} dependencias actualizadas")
    
    if success_count == len(critical_updates):
        print("🎉 Todas las dependencias críticas han sido actualizadas exitosamente")
        return 0
    else:
        print("⚠️  Algunas dependencias no pudieron ser actualizadas")
        return 1

if __name__ == "__main__":
    sys.exit(main())
