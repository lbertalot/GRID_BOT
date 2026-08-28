# GridBot - Diagnóstico de Logs y Mejoras

## Resumen Ejecutivo
- **Errores totales**: 51 (obsoletos, del 2026-08-05)
- **Warnings activos**: 26 (reales, del 2026-08-28)
- **Info/debug**: 1918 (normales)
- **Estado actual**: Sistema operando bajo circuit breaker (protección activa)

---

## 🔴 CRÍTICO (Acción inmediata requerida)

### 1. **Sistema en protección: 19 pérdidas consecutivas**
- **Ubicación**: Logs del 2026-08-28 13:08+
- **Problema**: Circuit breaker `system_integrity` activado
- **Síntoma**: `consecutive_losses=19` vs `threshold=5`
- **Impacto**: Bot pausado automáticamente, no abre nuevas posiciones
- **Root cause**: Estrategia de grid trading no está adaptándose a volatilidad del mercado
- **Acción**:
  1. Revisar parámetros del grid en `grid_config_paper_l0.json` (grid levels, spread)
  2. Analizar las 19 pérdidas: ¿son cierres en rojo o falsos positivos del detector?
  3. Ajustar `MAX_CONSECUTIVE_LOSSES` threshold si es demasiado sensible
  4. Validar que el stop-loss (`STOP_LOSS_PERCENT=10.0`) está funcionando correctamente

### 2. **Conexión a Redis perdida durante reinicio**
- **Ubicación**: gridbot.log 13:07:17
- **Error**: `ConnectionError: Connection closed by server` + `Error 111 connecting to redis:6379`
- **Causa**: Contenedor beat reiciándose infinitamente (ya reparado)
- **Residual**: Worker puede tener reconexiones fantasma
- **Acción**:
  1. ✅ Ya reparado (pidfile ahora en `/app/data` persistente)
  2. Monitorear Redis uptime próximas 24h

### 3. **Celery worker con deprecation warning**
- **Ubicación**: gridbot.log 13:07:17 (py.warnings)
- **Aviso**: `worker_cancel_long_running_tasks_on_connection_loss` será default=True en Celery 6.0
- **Impacto**: Futuro; hoy no afecta (default=False)
- **Acción**:
  1. Establecer explícitamente en celery.py:
     ```python
     app.conf.worker_cancel_long_running_tasks_on_connection_loss = True
     ```

---

## 🟠 ALTO (Dentro de 48h)

### 4. **Redundancia de logs de inicialización**
- **Ubicación**: gridbot.log ~cada 10-15s
- **Patrón**: Mismo bloque 6 veces por ciclo:
  ```
  ✅ Sistema de logging optimizado configurado
  🔄 Redis Cache inicializado
  🛡️ Auto Circuit Breaker inicializado
  🚫 Strategy Blacklist inicializado con 5 símbolos bloqueados
  ```
- **Causa**: Probable recarga de módulos en worker o lazy-loading excesivo
- **Impacto**: Ruido en logs (5-10MB/día); dificulta debugging
- **Acción**:
  1. Identificar dónde se llama a `initialize_core_modules()` múltiples veces
  2. Refactorizar para singleton pattern en boot
  3. Usar `@lru_cache` o `__once__` decorator

### 5. **Estrategia con baja confianza (0.60)**
- **Ubicación**: gridbot.log 13:09:40+
- **Log**: `Strategy selected for ETHUSDT: GridTrading (confidence: 0.60, ...)`
- **Contexto**: "Range-bound market with low volatility"
- **Problema**: 0.60 es arbitrario; no hay explicación de cálculo
- **Acción**:
  1. Aumentar threshold mínimo a 0.75 (hoy no rechaza posiciones débiles)
  2. Loguear cálculo completo: `regime_score`, `volatility_index`, etc.
  3. Documentar matriz de decisión en `strategy_selector.py`

### 6. **Position size calculation de respaldo (ATR method)**
- **Ubicación**: gridbot.log 13:09:41
- **Log**: `Position size for GENERIC: 199.80400 USDT (ATR method)`
- **Issue**: "GENERIC" es fallback; ¿por qué no está usando pares específicos?
- **Acción**:
  1. Verificar si falla mapeo de pares → risk tiers
  2. Loguear fallback path cuando ocurra

---

## 🟡 MEDIO (Próximas 2 semanas)

### 7. **Errores obsoletos de 2026-08-05 todavía en logs**
- **Ubicación**: `errors.log` completo
- **Contenido**: "Credenciales de Binance no configuradas" (x51)
- **Edad**: 23 días sin limpiar
- **Acción**:
  1. Implementar rotación automática: `logs/errors.log.1`, `.2`, etc.
  2. Borrar archivos > 30 días
  3. En `logging.config`:
     ```python
     handlers:
       error_file:
         class: logging.handlers.RotatingFileHandler
         maxBytes: 10485760  # 10MB
         backupCount: 5
     ```

### 8. **ROI anormalmente bajo (0.1766%)**
- **Ubicación**: gridbot.log 13:11:46
- **Log**: `profit=15.681037 USDT, invested=8879.472162 USDT, roi=0.1766%`
- **Contexto**: Paper trading; números pequeños normales, pero mira:
  - Profit: ~$15
  - Invested: ~$8879
  - Ratio: ~0.18% en días
- **Problema**: ¿Está el equity realmente así de bajo? ¿O hay skew en cálculo?
- **Acción**:
  1. Comparar con `paper_trading_state.json` + `ops_ledger.json`
  2. Validar fórmula ROI en `metrics_service.py`
  3. Si es real: revisar por qué trading está paralizado bajo protección

### 9. **Métrica de "Diario=0.00%" sospechosa**
- **Ubicación**: gridbot.log 13:09:40+
- **Log**: `📊 Métricas: Total=0.10%, Diario=0.00%`
- **Problema**: Diario=0% pero Total=0.10% implica toda ganancia fue ayer+
- **Acción**:
  1. Revisar lógica de ventana diaria en `circuit_breaker.py`
  2. Verificar timestamp del `latest_closed_at` (2026-08-26, hace 2 días)

---

## 🟢 BAJO (Nice-to-have / Próximo ciclo)

### 10. **SQLAlchemy "Configuración aplicada" x2 por ciclo**
- **Ubicación**: gridbot.log (aparece 2 veces seguidas siempre)
- **Log**: 
  ```
  ✅ Configuración de SQLAlchemy aplicada
  ✅ Configuración de SQLAlchemy aplicada
  ```
- **Causa**: Probable dual import o listener registrado 2x
- **Impacto**: Cero; solo ruido
- **Acción**: Buscar `on_connect` duplicate en `database.py`

### 11. **Circuit breaker message sin timestamp en Telegram**
- **Ubicación**: gridbot.log 13:08:40
- **Mensaje**: Telegram recibe notificación pero sin timezone local
- **Acción**: Agregar `TZ-aware datetime` en `telegram_alert` builder

### 12. **Log line "trading_cycle_tick[uuid] succeeded in X.XXs"**
- **Ubicación**: gridbot.log 13:08:40+
- **Métrica**: Duración de ciclo es excelente (~1.0-1.3s)
- **Acción**: Excelente; solo monitorear que no cruce 5s (timeout=300s total)

### 13. **Balances paper solo mostrado 1 activo**
- **Ubicación**: gridbot.log 13:09:40
- **Log**: `📄 Balances paper (ledger): 1 activos — USDT=999.0232991152`
- **Esperado**: Debería haber posiciones abiertas en ETHUSDT o similares
- **Causa**: Circuit breaker impide abrir posiciones (esperado actualmente)
- **Acción**: Revertir cuando se levante el freno

---

## 📊 Matriz de Riesgo

| Criticidad | Count | Latencia | Impacto |
|---|---|---|---|
| 🔴 CRÍTICO | 3 | Inmediato | Trading pausado, reinicio roto (reparado) |
| 🟠 ALTO | 3 | 1-2 días | Ruido de logs, decisiones débiles, overhead |
| 🟡 MEDIO | 3 | 2 semanas | Disk space, métricas confusas, validación |
| 🟢 BAJO | 4 | 1 mes | UX/cosmética |

---

## ✅ Acciones Recomendadas (Prioridad)

1. **[INMEDIATO]** Validar si 19 pérdidas consecutivas es legítimo o bug
2. **[HOY]** Refactorizar inicializadores para eliminar redundancia (ahorra 100s MB/mes)
3. **[24h]** Implementar rotación de logs con cleanup automático
4. **[48h]** Revisar matriz de decisión de confianza en strategy selector (0.60→0.75)
5. **[1 semana]** Auditar cálculo de ROI/métricas daily vs total
6. **[Próximo sprint]** Establecer Celery worker_cancel config explícito

---

## 📈 Métricas de Salud

- ✅ Worker reconecta a Redis correctamente
- ✅ Distributed locks funcionan (trading_cycle lock adquirido/liberado sin deadlock)
- ✅ Celery beat ahora estable (ya no reinicia)
- ⚠️ Circuit breaker muy activo (legítimo durante paper trading riesgoso)
- ⚠️ Logs crecen ~5-10MB/día sin rotación (preocupación a 1 mes)
