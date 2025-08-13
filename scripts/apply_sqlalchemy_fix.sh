#!/bin/bash
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
