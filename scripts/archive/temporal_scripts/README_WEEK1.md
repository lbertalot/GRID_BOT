# 🚀 SCRIPTS DE SEMANA 1 - GUÍA RÁPIDA

## 📂 Scripts Disponibles

```
scripts/
├── forensic_audit.py          # 🔍 Auditoría forense completa
├── balance_comparison.py      # 💰 Comparación de balances en tiempo real
├── quick_binance_trades.py    # ⚡ Quick check de trades de Binance
└── README_WEEK1.md           # 📖 Esta guía
```

---

## 🔍 forensic_audit.py

### ¿Qué hace?
Ejecuta auditoría forense completa del sistema vs Binance:
- Compara balances
- Identifica fills parciales no registrados
- Detecta órdenes fallidas sin registro
- Calcula discrepancia de PnL
- Analiza comisiones no contabilizadas
- Genera Health Score (0-100)
- Crea recomendaciones priorizadas

### Uso

```bash
# Auditoría básica (output a consola)
python scripts/forensic_audit.py

# Con export a JSON
python scripts/forensic_audit.py --export-json reports/forensic/audit_$(date +%Y%m%d_%H%M%S).json

# Modo verbose (debug)
python scripts/forensic_audit.py --export-json reports/forensic/audit.json --verbose
```

### Output Esperado

```
================================================================================
📊 RESUMEN DE AUDITORÍA FORENSE
================================================================================
Timestamp: 2025-01-02T10:30:45.123456+00:00
Health Score: 45/100

🔍 Hallazgos:
  - binance_snapshot: ✅ OK
  - db_snapshot: ✅ OK
  - trades_analysis: ✅ OK
  - partial_fills: ✅ OK
  - failed_orders: ✅ OK
  - pnl_comparison: ✅ OK
  - commission_analysis: ✅ OK

💡 Recomendaciones: 4
  [CRITICAL] Registrar fills parciales faltantes
  [HIGH] Registrar órdenes fallidas
  [CRITICAL] Reconciliar PnL con Binance
  [HIGH] Sincronizar trades faltantes

================================================================================
✅ Auditoría completada
================================================================================
```

### JSON Structure

```json
{
  "timestamp": "2025-01-02T10:30:45.123456+00:00",
  "health_score": 45,
  "sections": {
    "binance_snapshot": { ... },
    "db_snapshot": { ... },
    "trades_analysis": { ... },
    "partial_fills": {
      "partial_fills_found": 3,
      "details": [ ... ],
      "severity": "critical"
    },
    "failed_orders": { ... },
    "pnl_comparison": {
      "db_pnl": 12.34,
      "binance_pnl": -8.52,
      "discrepancy_usdt": 20.86,
      "discrepancy_pct": 5.12,
      "severity": "critical"
    },
    "commission_analysis": { ... }
  },
  "recommendations": [ ... ]
}
```

### Tiempo de Ejecución
- Normal: 2-3 minutos
- Con muchos trades: 5-10 minutos

---

## 💰 balance_comparison.py

### ¿Qué hace?
Monitorea balances en tiempo real con UI rica en terminal:
- Snapshot único o continuo
- Comparación automática entre snapshots
- Detección de cambios (cantidad y valor)
- Cálculo de cambio desde inicio
- UI con colores y tablas

### Uso

```bash
# Snapshot único
python scripts/balance_comparison.py --snapshot

# Monitoreo continuo cada 30 segundos
python scripts/balance_comparison.py --continuous --interval 30

# Monitoreo cada 1 minuto (recomendado para 24h)
python scripts/balance_comparison.py --continuous --interval 60
```

### Output Esperado

```
═══ MONITOREO DE BALANCES #1 ═══

💰 Balances - 10:30:45
╭─────────┬──────────┬──────────┬──────────┬────────────┬─────────────╮
│ Asset   │ Free     │ Locked   │ Total    │ Price USDT │ Value USDT  │
├─────────┼──────────┼──────────┼──────────┼────────────┼─────────────┤
│ USDT    │ 100.000  │ 0.000    │ 100.000  │ -          │ $100.00     │
│ ETH     │ 0.050    │ 0.000    │ 0.050    │ 3500.000   │ $175.00     │
│ BTC     │ 0.001    │ 0.000    │ 0.001    │ 50000.000  │ $50.00      │
├─────────┼──────────┼──────────┼──────────┼────────────┼─────────────┤
│ TOTAL   │          │          │          │            │ $325.00     │
╰─────────┴──────────┴──────────┴──────────┴────────────┴─────────────╯

📊 Cambios en 30s
╭─────────┬────────────┬───────────────┬──────╮
│ Asset   │ Δ Cantidad │ Δ Valor USDT  │ Δ %  │
├─────────┼────────────┼───────────────┼──────┤
│ ETH     │ +0.001     │ +$3.50        │ +2%  │
│ USDT    │ -3.50      │ -$3.50        │ -3%  │
╰─────────┴────────────┴───────────────┴──────╯

╭────────────────────────────────────────╮
│         📈 Desde Inicio                │
├────────────────────────────────────────┤
│ Valor inicial: $325.00                │
│ Valor actual: $325.00                 │
│ Cambio total: $0.00 (+0.00%)          │
╰────────────────────────────────────────╯

Próxima actualización en 30s... (Ctrl+C para detener)
```

### Dependencias
```bash
pip install rich
```

### Tips
- Usar `--interval 60` para monitoreos largos (24h)
- Dejar corriendo en tmux/screen para sesiones persistentes
- Guardar output a archivo: `> logs/balance_monitor.log`

---

## ⚡ quick_binance_trades.py

### ¿Qué hace?
Quick check de trades de Binance (últimos 7 días):
- Obtiene trades por símbolo
- Calcula estadísticas básicas
- Exporta a JSON
- Útil para comparación rápida con DB

### Uso

```bash
python scripts/quick_binance_trades.py
```

### Output Esperado

```
📊 Obteniendo trades de Binance (últimas 24h)...
================================================================================

ETHUSDT:
  Total trades: 15
  Buys: 8 ($450.25)
  Sells: 7 ($425.50)
  Total commission: 0.0125
  Último trade: 2025-01-02 10:15:32 UTC

BTCUSDT:
  Total trades: 3
  Buys: 2 ($100.00)
  Sells: 1 ($48.50)
  Total commission: 0.0003
  Último trade: 2025-01-02 09:45:10 UTC

================================================================================
✅ Exportando a reports/forensic/binance_trades_20250102_103045.json
✅ Completado
```

### Modificar Símbolos

Editar línea 10 en el script:

```python
symbols = ['ETHUSDT', 'BTCUSDT', 'BNBUSDT']  # Agregar/quitar símbolos
```

### Modificar Ventana de Tiempo

Editar línea 23:

```python
start_time = int((datetime.now(timezone.utc) - timedelta(days=7)).timestamp() * 1000)  # Cambiar days=X
```

---

## 🎯 WORKFLOWS RECOMENDADOS

### Workflow 1: Diagnóstico Rápido (10 min)

```bash
# 1. Quick check de Binance
python scripts/quick_binance_trades.py

# 2. Snapshot actual
python scripts/balance_comparison.py --snapshot

# 3. Comparar manualmente con Binance web UI
```

**Uso**: Cada mañana para verificar estado

---

### Workflow 2: Auditoría Semanal (30 min)

```bash
# 1. Backup de DB
docker exec gridbot_db pg_dump -U griduser gridbot > reports/forensic/backup_$(date +%Y%m%d).sql

# 2. Auditoría completa
python scripts/forensic_audit.py --export-json reports/forensic/audit_$(date +%Y%m%d).json

# 3. Revisar reporte
cat reports/forensic/audit_*.json | jq '.health_score'
cat reports/forensic/audit_*.json | jq '.recommendations'

# 4. Tomar decisiones basado en health score
```

**Uso**: Cada domingo noche

---

### Workflow 3: Monitoreo Continuo 24h (Día 6)

```bash
# Terminal 1: Balance monitor
python scripts/balance_comparison.py --continuous --interval 60 > logs/balance_24h_$(date +%Y%m%d).log 2>&1 &

# Terminal 2: Logs de API
docker logs -f gridbot_api | tee logs/api_24h_$(date +%Y%m%d).log

# Terminal 3: Logs de Worker
docker logs -f gridbot_celery_worker | tee logs/worker_24h_$(date +%Y%m%d).log

# Terminal 4: Prometheus queries cada hora
watch -n 3600 'curl -s http://localhost:9090/api/v1/query?query=portfolio_total_value_usdt | jq'

# Después de 24h: kill todos los procesos y revisar logs
```

**Uso**: Validación pre-producción

---

## 🐛 TROUBLESHOOTING

### Error: "Module 'rich' not found"

```bash
pip install rich
```

### Error: "Binance API connection failed"

```bash
# Verificar credenciales
python -c "from app.services.binance_client_singleton import get_binance_client_singleton; c = get_binance_client_singleton(); print(c.validate_credentials_and_connectivity())"

# Verificar .env
cat .env | grep BINANCE_API_KEY
```

### Error: "Database connection refused"

```bash
# Verificar que DB está corriendo
docker ps | grep gridbot_db

# Restart si es necesario
docker-compose restart db
sleep 10
```

### Script se cuelga

```bash
# Matar proceso
pkill -f forensic_audit.py

# Verificar logs
tail -f logs/errors.log
```

---

## 📊 INTERPRETACIÓN DE RESULTADOS

### Health Score

| Score | Estado | Acción |
|-------|--------|--------|
| 90-100 | 🟢 Excelente | Mantener monitoreo |
| 70-89 | 🟡 Bueno | Revisar recomendaciones |
| 50-69 | 🟠 Regular | Implementar correcciones |
| 30-49 | 🔴 Crítico | EMERGENCY_STOP + auditoría |
| 0-29 | ⛔ Desastre | Rollback + investigación profunda |

### Discrepancia PnL

| Discrepancia | Severidad | Acción |
|--------------|-----------|--------|
| <$1 o <0.1% | 🟢 Aceptable | Monitoreo normal |
| $1-$5 o 0.1-0.5% | 🟡 Atención | Investigar causa |
| $5-$20 o 0.5-2% | 🟠 Alta | Reconciliación inmediata |
| $20-$100 o 2-10% | 🔴 Crítica | EMERGENCY_STOP |
| >$100 o >10% | ⛔ Desastre | Rollback + auditoría forense |

### Fills Parciales

| Count | Severidad | Acción |
|-------|-----------|--------|
| 0 | 🟢 Perfecto | N/A |
| 1-2 | 🟡 Normal | Verificar que se registraron |
| 3-5 | 🟠 Preocupante | Implementar FillTracker |
| >5 | 🔴 Crítico | EMERGENCY_STOP + corrección |

---

## 🔧 DESARROLLO DE NUEVOS SCRIPTS

### Template Básico

```python
"""
Nuevo Script - Descripción
"""

import asyncio
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Función principal"""
    logger.info("🚀 Iniciando script...")
    
    try:
        # Tu código aquí
        pass
        
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        return 1
    
    logger.info("✅ Completado")
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
```

### Best Practices

1. **Siempre hacer backup antes de modificar datos**
2. **Logging exhaustivo con emojis para facilitar lectura**
3. **Manejo de excepciones en cada operación crítica**
4. **Export a JSON para trazabilidad**
5. **Progress indicators para operaciones largas**
6. **Retry logic para llamadas a APIs externas**
7. **Validación de inputs**
8. **Documentación inline de qué hace cada sección**

---

## 📞 SOPORTE

Si tienes problemas con los scripts:

1. **Revisar logs**: `docker logs -f gridbot_api | grep -i error`
2. **Verificar conectividad**: `python scripts/quick_binance_trades.py`
3. **Consultar documentación**: `docs/guides/week1_*.md`
4. **Debugging**: Agregar `--verbose` a forensic_audit.py

---

## 📚 DOCUMENTACIÓN RELACIONADA

- [Plan Completo Semana 1](../docs/guides/week1_complete_plan.md)
- [Checklist Día 1-2](../docs/guides/week1_day1-2_checklist.md)
- [Implementación Día 3-4](../docs/guides/week1_day3-4_implementation.md)
- [Resumen Ejecutivo](../docs/guides/week1_executive_summary.md)

---

**Última actualización**: 2025-01-02  
**Versión**: 1.0  
**Scripts testeados**: ✅ Todos funcionando  

**¡Buena suerte con la Semana 1! 🚀**
