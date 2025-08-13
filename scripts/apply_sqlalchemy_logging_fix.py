#!/usr/bin/env python3
"""
Script para aplicar la configuración de SQLAlchemy directamente en el código
"""

import os
import re

def apply_sqlalchemy_logging_fix():
    """Aplica la configuración de SQLAlchemy directamente"""
    try:
        print("🔧 Aplicando Configuración de SQLAlchemy")
        print("=" * 50)
        
        # 1. Crear archivo de configuración SQLAlchemy
        print("1️⃣ Creando configuración SQLAlchemy...")
        
        sqlalchemy_config = """
# Configuración específica para SQLAlchemy logging
import logging

def configure_sqlalchemy_logging():
    \"\"\"Configura el logging de SQLAlchemy para reducir verbosidad\"\"\"
    
    # Reducir logs de SQLAlchemy a solo warnings y errores
    sqlalchemy_logger = logging.getLogger('sqlalchemy.engine')
    sqlalchemy_logger.setLevel(logging.WARNING)
    
    sqlalchemy_pool_logger = logging.getLogger('sqlalchemy.pool')
    sqlalchemy_pool_logger.setLevel(logging.WARNING)
    
    sqlalchemy_dialects_logger = logging.getLogger('sqlalchemy.dialects')
    sqlalchemy_dialects_logger.setLevel(logging.WARNING)
    
    sqlalchemy_orm_logger = logging.getLogger('sqlalchemy.orm')
    sqlalchemy_orm_logger.setLevel(logging.WARNING)
    
    # Configurar handler específico para SQLAlchemy
    sqlalchemy_handler = logging.StreamHandler()
    sqlalchemy_handler.setLevel(logging.WARNING)
    
    # Formatter específico para SQLAlchemy
    formatter = logging.Formatter(
        '%(asctime)s | SQLAlchemy | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    sqlalchemy_handler.setFormatter(formatter)
    
    # Aplicar handler a todos los loggers de SQLAlchemy
    for logger_name in ['sqlalchemy.engine', 'sqlalchemy.pool', 'sqlalchemy.dialects', 'sqlalchemy.orm']:
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()  # Limpiar handlers existentes
        logger.addHandler(sqlalchemy_handler)
        logger.propagate = False  # Evitar propagación al logger raíz
    
    print("✅ Configuración de SQLAlchemy aplicada")

# Aplicar configuración inmediatamente
configure_sqlalchemy_logging()
"""
        
        with open('app/core/sqlalchemy_logging.py', 'w') as f:
            f.write(sqlalchemy_config)
        
        print("   ✅ Configuración SQLAlchemy creada")
        
        # 2. Modificar archivos principales para importar la configuración
        print("2️⃣ Integrando configuración en archivos principales...")
        
        # Modificar main_simple.py
        main_content = """from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import os
from datetime import datetime
import requests
import json
from prometheus_client import generate_latest, Counter, Histogram, Gauge
import asyncio

# Importar configuración de SQLAlchemy ANTES de cualquier import de SQLAlchemy
from app.core.sqlalchemy_logging import configure_sqlalchemy_logging
configure_sqlalchemy_logging()

# Importar el servicio de sincronización de Binance
from app.services.binance_data_sync import binance_sync

# Configurar logging optimizado
from app.core.optimized_logging import setup_optimized_logging
logger = setup_optimized_logging()
"""
        
        with open('app/main_simple.py', 'r') as f:
            content = f.read()
        
        # Reemplazar las primeras líneas
        lines = content.split('\n')
        new_lines = main_content.split('\n')
        lines[:len(new_lines)] = new_lines
        
        with open('app/main_simple.py', 'w') as f:
            f.write('\n'.join(lines))
        
        print("   ✅ main_simple.py actualizado")
        
        # 3. Modificar grid manager
        grid_content = """\"\"\"
Optimized Grid Manager for Multi-Asset Trading
Following FastAPI best practices and .cursorrules
\"\"\"

import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import json
import os
import asyncpg
import math

import requests
from pydantic import BaseModel, Field, validator
from binance import Client
from dotenv import load_dotenv

# Importar configuración de SQLAlchemy ANTES de cualquier import de SQLAlchemy
from app.core.sqlalchemy_logging import configure_sqlalchemy_logging
configure_sqlalchemy_logging()

# Cargar variables de entorno desde .env
load_dotenv()

from app.services.telegram_alert import send_telegram_alert
from app.services.grid_strategy import decide_grid_action, calculate_grid_levels
from app.services.order_validation import OrderValidator
from app.models.asset_limit import AssetLimit
from app.services.risk_manager import risk_manager, RiskStatus
from app.services.metrics_service import metrics_service

# Configurar logging optimizado
from app.core.optimized_logging import setup_optimized_logging
logger = setup_optimized_logging()
"""
        
        with open('app/core/optimized_grid_manager.py', 'r') as f:
            content = f.read()
        
        # Reemplazar las primeras líneas
        lines = content.split('\n')
        new_lines = grid_content.split('\n')
        lines[:len(new_lines)] = new_lines
        
        with open('app/core/optimized_grid_manager.py', 'w') as f:
            f.write('\n'.join(lines))
        
        print("   ✅ optimized_grid_manager.py actualizado")
        
        # 4. Crear script de aplicación
        print("3️⃣ Creando script de aplicación...")
        
        apply_script = """#!/bin/bash
# Script para aplicar configuración de SQLAlchemy

echo "🔧 Aplicando configuración de SQLAlchemy..."

# 1. Reiniciar servicios
echo "1️⃣ Reiniciando servicios..."
docker-compose restart api celery_worker

# 2. Esperar a que los servicios estén listos
echo "2️⃣ Esperando que los servicios estén listos..."
sleep 15

# 3. Verificar logs
echo "3️⃣ Verificando logs de SQLAlchemy..."
echo "   📊 Logs en los últimos 2 minutos:"
docker-compose logs --since=2m | grep -E "(sqlalchemy|SELECT|INSERT|UPDATE)" | wc -l

echo "   🚨 Errores en los últimos 2 minutos:"
docker-compose logs --since=2m | grep "ERROR" | wc -l

echo "   📈 Eventos de trading en los últimos 2 minutos:"
docker-compose logs --since=2m | grep -E "(Resumen|orden|trade)" | wc -l

echo "✅ Configuración de SQLAlchemy aplicada"
"""
        
        with open('scripts/apply_sqlalchemy_fix.sh', 'w') as f:
            f.write(apply_script)
        
        os.chmod('scripts/apply_sqlalchemy_fix.sh', 0o755)
        print("   ✅ Script de aplicación creado")
        
        # 5. Resumen
        print("4️⃣ Resumen de cambios:")
        print("   ✅ Configuración SQLAlchemy creada")
        print("   ✅ Integración en main_simple.py")
        print("   ✅ Integración en optimized_grid_manager.py")
        print("   ✅ Script de aplicación creado")
        
        print("\n🚀 PRÓXIMOS PASOS:")
        print("   1. Ejecutar: ./scripts/apply_sqlalchemy_fix.sh")
        print("   2. Verificar reducción de logs SQLAlchemy")
        print("   3. Monitorear durante 24h")
        
        print("\n✅ Configuración de SQLAlchemy completada")
        
    except Exception as e:
        print(f"❌ Error aplicando configuración: {e}")

if __name__ == "__main__":
    apply_sqlalchemy_logging_fix() 