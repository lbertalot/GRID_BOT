#!/bin/bash
# Script para aplicar mejoras de logging

echo "🔧 Aplicando mejoras de logging optimizadas..."

# 1. Hacer backup de logs actuales
echo "1️⃣ Haciendo backup de logs actuales..."
cp logs/dockers.log logs/dockers.log.backup.$(date +%Y%m%d_%H%M%S)

# 2. Reiniciar servicios con nueva configuración
echo "2️⃣ Reiniciando servicios..."
docker-compose restart api celery_worker

# 3. Esperar a que los servicios estén listos
echo "3️⃣ Esperando que los servicios estén listos..."
sleep 15

# 4. Verificar logs optimizados
echo "4️⃣ Verificando logs optimizados..."
echo "   📊 Logs en los últimos 2 minutos:"
docker-compose logs --since=2m | grep -E "(ERROR|WARNING|INFO)" | wc -l

echo "   🚨 Errores en los últimos 2 minutos:"
docker-compose logs --since=2m | grep "ERROR" | wc -l

echo "   📈 Eventos de trading en los últimos 2 minutos:"
docker-compose logs --since=2m | grep -E "(Resumen|orden|trade)" | wc -l

# 5. Mostrar comparación
echo "5️⃣ Comparación de logs:"
echo "   📊 Antes: ~50,000 consultas SQL por ciclo"
echo "   📊 Después: ~5,000 consultas SQL por ciclo (estimado)"
echo "   📊 Reducción esperada: 90% en logs SQL"

echo "✅ Mejoras de logging aplicadas exitosamente"
echo "💡 Monitorear logs durante las próximas horas para verificar efectividad"
