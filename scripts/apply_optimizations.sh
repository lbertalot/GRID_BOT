#!/bin/bash
# Script para aplicar optimizaciones de mejores prácticas

echo "🚀 Aplicando optimizaciones de mejores prácticas..."

# 1. Hacer backup del código actual
echo "1️⃣ Haciendo backup del código actual..."
cp -r app app.backup.$(date +%Y%m%d_%H%M%S)

# 2. Aplicar refactoring funcional
echo "2️⃣ Aplicando refactoring funcional..."
python3 scripts/apply_best_practices_optimization.py

# 3. Actualizar imports en archivos existentes
echo "3️⃣ Actualizando imports..."
find app -name "*.py" -exec sed -i '' 's/from app.services.commission_manager import/from app.services.commission import/g' {} \;
find app -name "*.py" -exec sed -i '' 's/from app.core.error_handler import/from app.core.trading_errors import/g' {} \;

# 4. Reiniciar servicios
echo "4️⃣ Reiniciando servicios..."
docker-compose restart api celery_worker

# 5. Ejecutar tests
echo "5️⃣ Ejecutando tests..."
python3 -m pytest tests/ -v

# 6. Verificar funcionamiento
echo "6️⃣ Verificando funcionamiento..."
sleep 10
curl -s http://localhost:8000/health

echo "✅ Optimizaciones aplicadas exitosamente"
echo "💡 Revisar logs para verificar que todo funciona correctamente"
