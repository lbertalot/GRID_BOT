#!/usr/bin/env python3
"""
Script de Backup de Configuración para GridBot v2.5
Crea backups automáticos de la configuración crítica del sistema
"""

import os
import sys
import json
import shutil
import tarfile
from datetime import datetime, timezone
from typing import Dict, List, Any
import logging

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler('logs/backup_configuration.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ConfigurationBackup:
    def __init__(self):
        self.backup_dir = "backups"
        self.critical_files = [
            ".env",
            "production.env",
            "docker-compose.yml",
            "gridbot.rules.yml",
            "grafana-roi-dashboard.json",
            "launch.sh",
            "setup-monitoring.sh"
        ]
        self.critical_directories = [
            "app/core",
            "app/api",
            "app/services",
            "docker",
            "scripts"
        ]
        self.database_backup_queries = [
            "SELECT * FROM system_settings;",
            "SELECT * FROM circuit_breakers;",
            "SELECT * FROM strategy_blacklist;"
        ]
        
    def create_backup_directory(self) -> str:
        """Crear directorio de backup con timestamp"""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(self.backup_dir, f"gridbot_config_{timestamp}")
        os.makedirs(backup_path, exist_ok=True)
        return backup_path
    
    def backup_critical_files(self, backup_path: str) -> List[str]:
        """Backup de archivos críticos"""
        backed_up_files = []
        
        for file_path in self.critical_files:
            if os.path.exists(file_path):
                try:
                    dest_path = os.path.join(backup_path, file_path)
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                    shutil.copy2(file_path, dest_path)
                    backed_up_files.append(file_path)
                    logger.info(f"✅ Archivo respaldado: {file_path}")
                except Exception as e:
                    logger.error(f"❌ Error respaldando {file_path}: {e}")
            else:
                logger.warning(f"⚠️ Archivo no encontrado: {file_path}")
        
        return backed_up_files
    
    def backup_critical_directories(self, backup_path: str) -> List[str]:
        """Backup de directorios críticos"""
        backed_up_dirs = []
        
        for dir_path in self.critical_directories:
            if os.path.exists(dir_path):
                try:
                    dest_path = os.path.join(backup_path, dir_path)
                    shutil.copytree(dir_path, dest_path, dirs_exist_ok=True)
                    backed_up_dirs.append(dir_path)
                    logger.info(f"✅ Directorio respaldado: {dir_path}")
                except Exception as e:
                    logger.error(f"❌ Error respaldando directorio {dir_path}: {e}")
            else:
                logger.warning(f"⚠️ Directorio no encontrado: {dir_path}")
        
        return backed_up_dirs
    
    def backup_database_config(self, backup_path: str) -> bool:
        """Backup de configuración de base de datos"""
        try:
            import subprocess
            
            # Crear backup de la base de datos
            db_backup_file = os.path.join(backup_path, "database_backup.sql")
            
            result = subprocess.run([
                "docker-compose", "exec", "-T", "db", 
                "pg_dump", "-U", "griduser", "-d", "gridbot"
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                with open(db_backup_file, 'w') as f:
                    f.write(result.stdout)
                logger.info(f"✅ Base de datos respaldada: {db_backup_file}")
                return True
            else:
                logger.error(f"❌ Error respaldando base de datos: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error en backup de base de datos: {e}")
            return False
    
    def create_backup_manifest(self, backup_path: str, backed_up_files: List[str], 
                             backed_up_dirs: List[str], db_backup_success: bool) -> str:
        """Crear manifiesto del backup"""
        manifest = {
            "backup_timestamp": datetime.now(timezone.utc).isoformat(),
            "backup_version": "1.0",
            "gridbot_version": "2.5",
            "backed_up_files": backed_up_files,
            "backed_up_directories": backed_up_dirs,
            "database_backup_success": db_backup_success,
            "total_files": len(backed_up_files),
            "total_directories": len(backed_up_dirs),
            "backup_size_mb": self.calculate_backup_size(backup_path)
        }
        
        manifest_file = os.path.join(backup_path, "backup_manifest.json")
        with open(manifest_file, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        logger.info(f"✅ Manifiesto creado: {manifest_file}")
        return manifest_file
    
    def calculate_backup_size(self, backup_path: str) -> float:
        """Calcular tamaño del backup en MB"""
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(backup_path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if os.path.exists(filepath):
                    total_size += os.path.getsize(filepath)
        return round(total_size / (1024 * 1024), 2)
    
    def create_compressed_backup(self, backup_path: str) -> str:
        """Crear backup comprimido"""
        try:
            compressed_file = f"{backup_path}.tar.gz"
            with tarfile.open(compressed_file, "w:gz") as tar:
                tar.add(backup_path, arcname=os.path.basename(backup_path))
            
            # Eliminar directorio original
            shutil.rmtree(backup_path)
            
            logger.info(f"✅ Backup comprimido creado: {compressed_file}")
            return compressed_file
        except Exception as e:
            logger.error(f"❌ Error creando backup comprimido: {e}")
            return backup_path
    
    def cleanup_old_backups(self, max_backups: int = 10):
        """Limpiar backups antiguos"""
        try:
            if not os.path.exists(self.backup_dir):
                return
            
            backups = []
            for item in os.listdir(self.backup_dir):
                item_path = os.path.join(self.backup_dir, item)
                if os.path.isfile(item_path) and item.endswith('.tar.gz'):
                    backups.append((item_path, os.path.getmtime(item_path)))
            
            # Ordenar por fecha de modificación (más antiguos primero)
            backups.sort(key=lambda x: x[1])
            
            # Eliminar backups antiguos si excedemos el límite
            if len(backups) > max_backups:
                for i in range(len(backups) - max_backups):
                    old_backup = backups[i][0]
                    os.remove(old_backup)
                    logger.info(f"🗑️ Backup antiguo eliminado: {old_backup}")
            
        except Exception as e:
            logger.error(f"❌ Error limpiando backups antiguos: {e}")
    
    def run_backup(self, compress: bool = True, max_backups: int = 10) -> str:
        """Ejecutar backup completo"""
        logger.info("🚀 Iniciando backup de configuración de GridBot v2.5...")
        
        # Crear directorio de backup
        backup_path = self.create_backup_directory()
        logger.info(f"📁 Directorio de backup: {backup_path}")
        
        # Backup de archivos críticos
        backed_up_files = self.backup_critical_files(backup_path)
        logger.info(f"📄 Archivos respaldados: {len(backed_up_files)}")
        
        # Backup de directorios críticos
        backed_up_dirs = self.backup_critical_directories(backup_path)
        logger.info(f"📁 Directorios respaldados: {len(backed_up_dirs)}")
        
        # Backup de base de datos
        db_backup_success = self.backup_database_config(backup_path)
        logger.info(f"🗄️ Backup de base de datos: {'✅' if db_backup_success else '❌'}")
        
        # Crear manifiesto
        manifest_file = self.create_backup_manifest(
            backup_path, backed_up_files, backed_up_dirs, db_backup_success
        )
        
        # Comprimir backup si se solicita
        if compress:
            final_backup_path = self.create_compressed_backup(backup_path)
        else:
            final_backup_path = backup_path
        
        # Limpiar backups antiguos
        self.cleanup_old_backups(max_backups)
        
        logger.info(f"🎉 Backup completado: {final_backup_path}")
        return final_backup_path

def main():
    backup_manager = ConfigurationBackup()
    
    # Crear directorio de backups si no existe
    os.makedirs(backup_manager.backup_dir, exist_ok=True)
    
    # Ejecutar backup
    backup_path = backup_manager.run_backup(compress=True, max_backups=10)
    
    print(f"\n🎉 Backup de configuración completado!")
    print(f"📁 Ubicación: {backup_path}")
    print(f"📊 Para restaurar: tar -xzf {backup_path}")
    print(f"📋 Manifiesto: {backup_path.replace('.tar.gz', '')}/backup_manifest.json")

if __name__ == "__main__":
    main()

