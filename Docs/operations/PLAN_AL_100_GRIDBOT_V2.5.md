# Plan para que GridBot v2.5 funcione al 100% en producción

**Basado en:** [VERIFICACION_GRIDBOT_V2.5_EN_PRODUCCION.md](./VERIFICACION_GRIDBOT_V2.5_EN_PRODUCCION.md)
**Objetivo:** Activar y verificar todos los componentes descritos en la oferta pública de GridBot v2.5 (incluido ML para régimen) y asegurar operación estable y observable.

---

## Estado actual (resumen)

| Área | Estado | Acción necesaria |
|------|--------|------------------|
| Binance spot, Kelly, breakers, filtros, reconciliación, idempotencia, Decimal, emergencia | ✅ OK | Solo verificación operativa continua |
| **ML (LSTM/Transformer + River)** | ⚠️ En prod `ML_ENABLED=false`; el **ciclo de trading no usa** predicción real | Conectar ciclo con ML y activar en prod con fallback |
| Endpoints `/metrics`, `/breakers/summary` | Pueden dar timeout (cold start) | Mejorar disponibilidad y/o documentar |
| Observabilidad en Heroku (Grafana/Prometheus) | Métricas en `/metrics`; Grafana no corre en Heroku | Definir scraping externo o add-on |

---

## Fase 1: Conectar el ciclo de trading con la predicción de régimen (ML)

**Problema:** En `app/services/trading_tasks.py` el ciclo de evaluación (0–240 s) **nunca** llama a `predict_regime`; siempre usa un `RegimePrediction(long_regime=RANGE, short_regime=RANGE)` fijo. Por tanto, el StrategySelector no recibe predicción real aunque el ML esté disponible.

**Tareas:**

1. **Leer `ML_ENABLED` en el ciclo**
   - En `trading_tasks.py`, obtener `ml_enabled = os.getenv("ML_ENABLED", "false").lower() == "true"`.
   - Si `ml_enabled` es `True`, intentar obtener `RegimePrediction` desde el motor de ML antes de elegir estrategia.
   - Si `ml_enabled` es `False` o hay excepción/timeout, usar el fallback actual (RANGE, RANGE).

2. **Usar MLEngine (River) en el ciclo cuando ML_ENABLED=true**
   - El ciclo ya instancia `MLEngine()` y tiene `kl` (klines). `MLEngine.predict_regime(symbol, "1m", 60)` devuelve `ml_engine.RegimePrediction` (label, proba), no `risk_manager.RegimePrediction`.
   - Añadir una función helper (p. ej. en `ml_engine.py` o en un módulo compartido) que convierta la salida de `MLEngine.predict_regime` a `app.core.risk_manager.RegimePrediction`:
     - Mapear `label`/`proba` a `long_regime`/`short_regime` (p. ej. label 0 → RANGE, label 1 → BULL_TREND; o heurística por volatilidad/RSI ya computada).
     - `long_conf`/`short_conf` = `proba` (o valor por defecto si no hay confianza).
   - En el bucle por símbolo del ciclo: si `ml_enabled`, llamar `rp = await ml.predict_regime(sym, "1m", 60)` y convertir a `RegimePrediction`; en caso de error, usar fallback RANGE.

3. **Opcional: soporte a HybridMLEngine en el ciclo**
   - Si se quiere usar LSTM/Transformer en producción, el ciclo podría usar `HybridMLEngine` cuando existan modelos cargados para el símbolo (y `ML_ENABLED=true`), y si no, usar `MLEngine` (River). Dejar para una iteración posterior si se prioriza primero River-only.

4. **Métricas y logs**
   - Añadir/actualizar métricas (p. ej. `regime_predictions_total` o contador `ml_regime_used_in_cycle_total` vs `ml_regime_fallback_total`) y logs estructurados cuando se use predicción real vs fallback.

5. **Tests**
   - Añadir o ajustar tests que verifiquen: con `ML_ENABLED=true` y MLEngine operativo el ciclo usa `RegimePrediction` del ML; con `ML_ENABLED=false` o error del ML se usa fallback RANGE.

**Criterio de éxito:** Con `ML_ENABLED=true` y River operativo, el ciclo de trading toma la decisión de estrategia (grid/DCA/etc.) basada en la predicción de régimen del ML; con `ML_ENABLED=false` o fallo del ML, el comportamiento actual (fallback RANGE) se mantiene.

---

## Fase 2: Habilitar ML en producción de forma segura

**Objetivo:** Poner `ML_ENABLED=true` en la app **grid-bot-ia-eu** sin degradar defensas.

**Tareas:**

1. **Requisitos para River (MLEngine)**
   - River ya funciona sin fichero de modelo previo (entrenamiento online). El modelo se persiste en `ML_MODEL_PATH` (default `data/ml/regime_model.joblib`).
   - En Heroku el filesystem es efímero: cada deploy o reinicio pierde el modelo. Opciones:
     - **A)** Dejar que cada dyno entrene desde cero (comportamiento aceptable para River online; el ciclo sigue con fallback si el modelo no está listo).
     - **B)** Persistir modelo en Redis o en almacenamiento externo (S3, etc.) y cargar al arranque (requiere desarrollo adicional).
   - Decisión inicial recomendada: **A)** Activar `ML_ENABLED=true` sin persistencia externa; documentar que el régimen puede tardar unos ciclos en ser “útil” tras un restart.

2. **Variables de entorno en Heroku**
   - `ML_ENABLED=true`
   - Opcional: `ML_MODEL_PATH` si se usa persistencia (p. ej. ruta montada o descargada desde S3).
   - No exponer claves en logs; verificar que `env.example` y documentación estén al día.

3. **Rollout**
   - Desplegar primero el código de la Fase 1 (ciclo usando ML cuando `ML_ENABLED=true`).
   - Activar `ML_ENABLED=true` en staging o en un horario de bajo riesgo si existe.
   - Revisar logs y métricas (regime predictions, fallbacks, errores).
   - Activar en producción (grid-bot-ia-eu) y monitorear; mantener posibilidad de volver a `ML_ENABLED=false` si hay incidencias.

4. **LSTM/Transformer (HybridMLEngine)**
   - Requieren artefactos (model.h5, scaler.pkl, label_encoder.pkl, config.json) por símbolo en un directorio `models/` o configurable. En Heroku habría que generarlos en CI o subirlos a un almacenamiento y descargarlos al arranque.
   - Dejar para una **fase posterior** una vez River en ciclo esté estable; el plan “100%” puede cumplirse primero con River + StrategySelector, y los modelos deep como mejora opcional.

**Criterio de éxito:** En producción, `ML_ENABLED=true`, el ciclo usa predicción de régimen cuando River responde y fallback cuando no; no se incrementan errores ni breakers por el cambio.

---

## Fase 3: Estabilidad y disponibilidad de endpoints

**Problema:** Llamadas a `/metrics` y `/breakers/summary` pueden dar timeout (p. ej. cold start del dyno).

**Tareas:**

1. **Health y listos**
   - Mantener `GET /health` ligero y rápido; si se usa un endpoint “ready” (p. ej. `/health/ready`) que dependa de DB/Redis, documentar que puede ser más lento.
   - Considerar un endpoint mínimo tipo `GET /ping` que solo devuelva 200 para comprobar que el proceso responde (útil para comprobar antes de cold start completo).

2. **Timeouts y cold start**
   - Documentar en operaciones que la primera petición tras idle puede tardar varios segundos; si hay balanceador o monitor, configurar timeouts acordes (p. ej. 30 s para `/metrics` en el primer request).
   - Opcional: configurar “keep-alive” o scheduler que golpee un endpoint interno cada X minutos para reducir probabilidad de cold start cuando se consulte Prometheus/Grafana.

3. **Verificación rutinaria**
   - Incluir en el runbook (o en Fase 5) comprobación periódica de `GET /health`, `GET /metrics` (al menos que responda 200), `GET /breakers/summary`.

**Criterio de éxito:** Documentación clara sobre cold start y timeouts; comprobaciones definidas para operaciones.

---

## Fase 4: Observabilidad en producción (Prometheus / Grafana)

**Estado:** La app expone `GET /metrics`; los dashboards están en `docker/grafana` (entorno local). En Heroku no se ejecuta Prometheus ni Grafana.

**Tareas:**

1. **Scraping de métricas**
   - Opción A: **Heroku Prometheus add-on** (si existe y está permitido) para que scrapee la app y exporte a Prometheus.
   - Opción B: **Prometheus externo** (VPS, Grafana Cloud, etc.) que scrapee `https://grid-bot-ia-eu-3ded46704cc4.herokuapp.com/metrics` con un intervalo razonable (p. ej. 60 s) y timeout adecuado (ver Fase 3).
   - Documentar en `Docs/operations` la opción elegida y la URL de la app.

2. **Grafana**
   - Conectar Grafana (Cloud o self-hosted) al mismo Prometheus que scrapea la app; importar o adaptar los dashboards de `docker/grafana/dashboards` para producción.
   - Incluir paneles útiles: breakers, reconciliación, regime predictions, latencia API, órdenes, errores.

3. **Alertas**
   - Definir alertas básicas (breaker activo, salud del proceso, caída de `/health`) según `PRODUCTION_LAUNCH_GUIDE.md` o runbook existente.

**Criterio de éxito:** Métricas de la app en producción visibles en Prometheus y Grafana; dashboards y alertas documentados.

---

## Fase 5: Verificación operativa continua

**Objetivo:** Tener un checklist o script que compruebe que todo lo verificado en VERIFICACION_GRIDBOT_V2.5_EN_PRODUCCION.md sigue operativo.

**Tareas:**

1. **Checklist en Docs/operations**
   - Añadir un apartado “Verificación operativa” en el runbook (o en VERIFICACION_GRIDBOT_V2.5_EN_PRODUCCION.md) con:
     - Comandos `curl` (o equivalentes) para: `GET /health`, `GET /metrics`, `GET /breakers/summary`, `GET /api/reconciliation/summary` (si existe).
     - Comprobación de variables críticas: `TRADING_ENABLED`, `EMERGENCY_STOP`, `PAPER_TRADING`, `ML_ENABLED` (vía Heroku config o panel).
     - Frecuencia sugerida (diaria/semanal) y qué hacer si algo falla (revisar logs, breakers, reinicio controlado).

2. **Script opcional de verificación**
   - Script (shell o Python) que ejecute los curls anteriores y devuelva OK/KO por ítem; puede ejecutarse manualmente o desde un cron/CI.
   - Guardar en `scripts/` o `Docs/operations/` y referenciarlo desde el runbook.

**Criterio de éxito:** Operaciones puede seguir el checklist (o script) de forma periódica y actuar ante fallos.

---

## Orden de ejecución recomendado

1. **Fase 1** (código): Conectar ciclo de trading con ML y variable `ML_ENABLED`; tests y métricas.
2. **Fase 3** (documentación y opcionalmente keep-alive): Estabilidad de endpoints y documentación de timeouts.
3. **Fase 5** (documentación + script opcional): Checklist y script de verificación.
4. **Fase 2** (config + rollout): Activar `ML_ENABLED=true` en producción y monitorear.
5. **Fase 4** (infra): Configurar scraping Prometheus y Grafana para producción.

Las fases 3 y 5 pueden hacerse en paralelo con la 1; la 2 debe ir después de la 1; la 4 puede hacerse en cualquier momento pero es más útil una vez los endpoints son estables (Fase 3).

---

## Resumen de entregables

| Fase | Entregables |
|------|-------------|
| 1 | Código en `trading_tasks.py` (y helper de mapeo) que use ML cuando `ML_ENABLED=true`; tests; métricas/logs. |
| 2 | `ML_ENABLED=true` en grid-bot-ia-eu; documentación de persistencia (o decisión de no persistir modelo); notas de rollout. |
| 3 | Documentación de cold start/timeouts; opcional: `/ping` o keep-alive. |
| 4 | Configuración y documentación de Prometheus (scraping) y Grafana para prod. |
| 5 | Checklist de verificación operativa y, opcionalmente, script de comprobación. |

Al completar las cinco fases, GridBot v2.5 quedará funcionando al 100% respecto a la descripción verificada: ML para régimen integrado en el ciclo con fallback seguro, defensas y observabilidad operativas y verificables de forma continua.
