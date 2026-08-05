# GridBot × Passive Income — Documento maestro de producción (consolidado)

**Versión:** 1.0 (fusión de research)
**Fuentes integradas:**

| Fuente | Aportes principales |
|--------|---------------------|
| `Docs/PROTOCOL_PASSIVE_INCOME_BOT_V1_ARCHITECTURE.md` | Arquitectura, esquema datos/NLP, Monte Carlo, P99, reconciliación ≤60s, venues/IP whitelist, alineación GridBot v2.5 |
| `docs/deep-research-report.md` | Referencias metodológicas (sentimiento + técnicos, costos que erosionan resultados, Kelly fraccional, day vs swing) |
| `docs/PassiveIncomeBot_v1.0_Arquitectura.docx` | Modelo **TQS** detallado, universos concretos (Binance/BYMA/Rofex), reparto **20% DT / 80% ST**, Redis Streams/workers, presupuesto P99 por etapa, escenarios cisne negro, gates de promoción ML, roadmap por fases, compliance AR |

**Objetivo del documento:** una sola brújula técnica y de estrategia para **evolucionar GridBot** hacia un despliegue **production-grade**, con validación estricta **after-cost**.
**No constituye asesoramiento financiero.** Ningún sistema documentado garantiza **ROI positivo**; lo que se define aquí son **gates, riesgo acotado y proceso reproducible** para **perse** una **expectativa razonable después de costos y slippage**, sujeta a validación empírica (paper → real mínimo).

---

## 1. Principios rectores (fusión)

1. **Preservación de capital primero, retorno segundo.** Toda señal está subordinada a límites de riesgo y a breakers ya presentes en el ecosistema GridBot (`EMERGENCY_STOP`, `TRADING_ENABLED`, circuit breakers, integridad).
2. **No perseguir retornos extremos; perseguir consistencia estadística** después de comisiones, spread y slippage (auditoría obligatoria en cada backtest y en paper).
3. **Estrategia direccional** sobre activos de **alta capi y liquidez relativa**, con criterios cuantitativos de elegibilidad (no solo “nombre del ticker”).
4. **Separación señal vs ejecución:** scoring y ML pueden correr desacoplados; la **ejecución** debe salir de un camino acotado, idempotente y observable (patrón alineado con `client_order_id`, reconciliación, métricas).

---

## 2. Universo de activos y horizonte (lo más preciso de cada research)

### 2.1 Cripto (Binance Spot — alineado a GridBot actual)

- **Pares núcleo:** BTC/USDT, ETH/USDT (profundidad 24/7, spreads habitualmente ajustados).
- **Criterio cualitativo docx:** capitalización muy alta como filtro conceptual; en implementación usar **filtros de exchange** (notional, `LOT_SIZE`, `PRICE_FILTER`) ya exigidos por `.cursorrules` / servicios del proyecto.

**Asignación de capital sugerida (docx, a validar con tu perfil de riesgo):**

- **~20% del portafolio estrategia** orientado a **day trading intradía** solo en BTC/ETH (donde la latencia y liquidez lo permiten).
- **~80% swing** (varios días), priorizando **menor frecuencia** para reducir “rake” acumulado por comisiones — coherente con `deep-research` (swing reduce carga operativa y costos transaccionales).

**Nota de síntesis:** el protocolo original enfatizaba swing/CEDEARs para costos; el docx **cuantifica** el reparto DT/ST. **Adoptar el reparto 20/80 como hipótesis operativa** sujeta a backtest after-cost y a límites de volatilidad/región.

### 2.2 Argentina — BYMA / CEDEARs / Rofex (fase siguiente al núcleo cripto)

Tomado del docx con matices de ingeniería:

| Bucket | Instrumentos ejemplo | Condición de elegibilidad (indicativa) |
|--------|----------------------|----------------------------------------|
| Panel líder BYMA | GGAL, YPF, PAMP, TXAR, BMA | Volumen diario alto (docx: > ARS 500M — **recalibrar con datos reales**) |
| CEDEARs líquidos | AAPL, MSFT, AMZN, NVDA | Proxy dolarizado; validar spread y horario de sesión |
| Rofex | Ej. dólar futuro como cobertura | Reglas de margen y roll distintas al spot; **módulo de riesgo separado** |

**Integración técnica:** capa `BrokerAdapter` / API específica (referencias: CCXT para cripto; **pyRofex** u homólogos para Rofex; APIs de datos/ejecución BYMA según proveedor acordado). No asumir paridad con Binance.

---

## 3. Modelo de señal TQS (Técnico + Cuantitativo +-sentimiento)

### 3.1 Capa T — Técnica (docx, compactado)

Indicadores candidatos (evitar redundancia multicolineal en el mismo horizonte):

| Indicador | Parámetros | Uso |
|-----------|------------|-----|
| EMA cross | 9 / 21 / 55 | Tendencia |
| RSI | 14, 30/70 | Filtro sobrecompra/sobreventa |
| MACD | 12/26/9 | Confirmación momentum |
| ATR | 14 | Stop dinámico / sizing volatilidad |
| Bandas Bollinger | 20, 2σ | Régimen volatilidad / mean reversion contextual |
| VWAP | intradía/semanal | Referencia institucional (donde aplique) |

### 3.2 Capa Q — Cuantitativa (docx + protocolo)

- EMA adaptativa tipo **KAMA** para reducir *whipsaws* en rangos.
- **GARCH(1,1)** o similar sobre retornos log para **escalar riesgo** en períodos de volatilidad elevada (no como única señal direccional).
- **Correlaciones rodantes** (~60d) para **techo de exposición** por cluster correlacionado (evita “apostar dos veces” al mismo factor).
- Series tipo **ARIMA** solo con **selección penalizada (AIC/BIC)** y validación *walk-forward* (anti-overfitting).

### 3.3 Capa S — Sentimiento (síntesis protocolo + docx + deep-research)

**Tensión resuelta entre fuentes:**

- *Protocolo:* NLP como **validación / veto** (no verdad única).
- *Docx:* NLP como **multiplicador de Kelly** (p.ej. Kelly × 0.5 si sentimiento negativo).

**Regla fusionada recomendada para producción:**

1. **Veto duro (protocolo):** si el sentimiento es fuertemente antagónico a la señal (docx: ej. score < −0.3 veta compra; > 0.3 veta venta), **no ejecutar** la entrada (solo salidas gestionadas según reglas de riesgo).
2. **Escalado acotado (docx, acotado):** si no hay veto, permitir **ajuste de tamaño** en un rango limitado (p.ej. 0.5×–1.0× del Kelly ya fraccionado), **nunca** duplicar agresividad por sentimiento.
3. **Versionado:** `model_ver`, fuente y timestamp en BD (`sentiment_scores` / `sentiment_events` del protocolo o DDL del docx).

**Fuentes candidatas (docx):** X/Twitter API v2 (cashtags), Reddit, Telegram monitoreado, Fear & Greed (Alternative.me). **Cumplimiento de ToS y rate limits** obligatorio.

**Modelo:** FinBERT o equivalente; **inferencia fuera del hot path** — cache en Redis (TTL 5 min DT / 15 min ST sugerido en docx).

---

## 4. Arquitectura alineada a GridBot (stack y capas)

### 4.1 Stack (sin reescribir lo que ya existe)

- **Python 3.11+** (coherente con `AGENTS.md`; el docx citaba 3.12 — subir cuando el repo formalice 3.12).
- **FastAPI**, **PostgreSQL**, **SQLAlchemy 2**, **Alembic**, **Redis**, **Celery** (+ Beat), **Prometheus/Grafana**, **OpenTelemetry** opcional.
- **River** + **TensorFlow** según `HybridMLEngine` / `requirements-ml.txt`.
- **CCXT** + adaptadores; **egress IP estático** donde haya whitelist (ver `PROTOCOL` §2.4 — **no pérdida**: es crítico para producción).

### 4.2 Capas lógicas (docx) mapeadas al repo actual

```
INGESTA:  Binance WS/REST (existente) → BYMA/Rofex (futuro adapter)
PROCESO:  Redis (cache/queues) → Celery workers (tasks existentes + nuevos)
          Opción evolutiva: Redis Streams para bus de ticks (docx) si el volumen lo exige
DECISIÓN: signal_engine (nuevo o evolución de services) + RiskManager / breakers
EJECUCIÓN: order path existente + idempotencia + audit log DB
OBS:      métricas en app/core/metrics.py + dashboards bajo docker/grafana
```

**Colas Celery (docx — guía de concurrencia):**

| Worker | Rol | Concurrencia sugerida |
|--------|-----|----------------------|
| ingesta | Normalizar ticks / WS | 4, prefetch 1 |
| señales | Pipeline TQS | 2 |
| órdenes | Envío FIFO crítico | **1** (evitar condiciones de carrera) |
| ml_sync | Retrain / evaluación | 1 (GPU opcional) |

---

## 5. Diseño de datos (fusión esquema)

**Base:** tablas del protocolo (`symbols`, `market_candles`, `sentiment_*`, `strategy_runs`, `ml_*`, `backtest_*`).

**Incorporar del docx:**

- Particionamiento de `market_ticks` por **rango temporal**; índice `(symbol, ts DESC)`.
- `sentiment_events` con `CHECK (score BETWEEN -1 AND 1)`, `confidence`, `model_ver`.
- `trading_signals` con `tech_score`, `quant_score`, `sent_score`, `composite`, `executed`.
- `orders` con **audit trail inmutable** (commission, slippage_bps, `signal_id` FK).

**Extensión recomendada:** **TimescaleDB** hypertable para ticks y *continuous aggregates* si el volumen histórico crece (docx + protocolo convergen).

**Tipos monetarios:** `Numeric`/`Decimal` en Python en todas las rutas críticas (regla del proyecto).

---

## 6. Gestión de riesgo y capital

### 6.1 Kelly fraccional (una sola definición)

Usar la forma ya alineada al código y al deep-research:

\[
f^* = \frac{p(b+1)-1}{b} \cdot \alpha, \quad \alpha = 0.25 \text{ (fracción Kelly)}
\]

Con **caps** explícitos por símbolo, equity y pérdida diaria (como en `risk_routes`). **Más** el **escalado por sentimiento acotado** de §3.3 (nunca sin caps).

### 6.2 Drawdown y límites operativos

- **Drawdown máximo de estrategia:** banda **10%–20%** (protocolo + docx): reduce tamaño, bloquea nuevas entradas o dispara kill-switch.
- **Pérdida diaria dura:** docx/deep-research citan umbrales del orden **5%–10%** para suspender aperturas — **parametrizar** en configuración y conectar a `CircuitBreakers` / `RiskManager`.

### 6.3 Stop-loss dinámico, breakers, kill-switch

- Stops basados en **ATR** / trailing coherente con `RiskManager`.
- Breakers: API errors, reconciliación, latencia anómala (extender métricas existentes).
- **Kill-switch** manual + automático; integridad de escritura cuando breakers activos (`IntegrityGuardMiddleware`).

### 6.4 Costos y “ROI” — trato honesto

- Deep-research: ignorar comisiones puede **inflar** resultados; modelar slippage puede recortar retornos simulados **materialmente**.
- **Gate de promoción:** ningún modelo ni parámetro pasa a paper extendido sin **PNL y Sharpe after-cost** en walk-forward.

**ROI positivo en producción** exige que el **edge neto > 0** de forma **estable** fuera de muestra; este documento define **cómo medirlo**, no **cómo garantizarlo**.

---

## 7. Backtesting, Monte Carlo y cisnes negros

### 7.1 Protocolo común

1. **pytest:** unidades (sizing, filtros, órdenes), integración (sin orden real con flags off), golden files en datasets fijos.
2. **Walk-forward** (docx): train largo / test desplazado; **anti data leakage**, especialmente NLP *point-in-time*.
3. **Monte Carlo:**
   - Bootstrap bloqueado (protocolo).
   - Colas gruesas: ajuste **t-Student** u otra distribución con colas sobre retornos (docx) en lugar de solo Gaussiana.
4. **Escenarios docx (ejemplos de stress a automatizar):**
   - Flash crash (−30% en 1h) → DD bajo techo, sin “ruina” de cuenta simulada.
   - Bear prolongado (−50% en 30d) → modo solo cierre / reducción exposure.
   - Spread ×10 durante 60m → slippage acotado; breakers activados.
   - Timeouts API 20% → circuit breaker sin pérdida descontrolada.
   - 10% ticks corruptos → ingesta pausada, alertas.

**Criterio:** percentil alto de DD simulado dentro del presupuesto (p.ej. P95 DD ≤ 20%) **y** comportamiento del sistema **seguro** (sin órdenes duplicadas, estado consistente).

---

## 8. Latencia P99 ≤ 250 ms (fusión protocolo + docx)

### 8.1 Alcance realista

El target de **250 ms P99** aplica a **rutas ligeras** y al **camino crítico interno** en Docker local; **no** incluye garantizar cola en el matching engine del exchange ni latencia WAN adversa.

### 8.2 Presupuesto indicativo (docx) — usar como checklist de profiling

| Etapa | Presupuesto P99 | Nota |
|-------|-----------------|------|
| WS tick → normalize | ~5–15 ms | asyncio; valorar `uvloop` en Linux si el stack lo permite |
| Features | ~30 ms | NumPy vectorizado; evitar Python puro en bucle |
| River | ~15 ms | modelo en memoria |
| TF / LSTM | ~60 ms o **fuera de path** | TF-Lite / servicio lateral; **no bloquear** API |
| Sentimiento | ~5 ms | solo Redis GET en hot path |
| Riesgo (Kelly/CB) | ~10 ms | puro CPU |
| Envío orden | variable | pool HTTP; lo externo domina a veces |
| Persistencia | async / write-behind | Celery o `BackgroundTasks` para no bloquear |

### 8.3 Docker / host

- `network_mode: host` en Linux puede recortar overhead (docx); evaluar trade-off de seguridad/portabilidad.
- `shared_buffers` Postgres, `nofile`, backlog Redis según docx.
- Mantener alineación con `Docs/PROTOCOL` §6 (cache, workers, DB pool).

---

## 9. Ciclo ML y reconciliación (paper ↔ producción)

### 9.1 Máquina de estados (docx, adaptada a GridBot)

```
TRAIN (histórico + WF) → PAPER/TESTNET (2–4 semanas mínimo) → CANARY capital real → FULL
         ↑                                                      ↓
         └──────────── ROLLBACK si drift / Δ métricas ─────────┘
```

### 9.2 Gates cuantitativos sugeridos (docx — calibrar)

Un candidato **no** promueve a real sin cumplir **simultáneamente** (valores iniciales de diseño):

| Gate | Umbral inicial |
|------|----------------|
| AUC (u otra métrica out-of-sample) | ≥ **0.56** en WF agregado |
| Sharpe after-cost | ≥ **1.0** (ventana acordada) |
| Max DD en paper | < **15%** |
| Trades mínimos en paper | ≥ **100** (evitar estadística espuria) |

**Aprobación final a producción:** **manual** del operador (docx) — mantener en runbook.

### 9.3 Reconciliación periódica (fusión)

- **Operativa:** ≤ **60 s** para detectar divergencias posición/órdenes (protocolo GridBot).
- **ML vs realidad (docx):**
  - Diaria: Δ win rate real vs paper > **15 pp** → alerta.
  - Semanal: Δ P&L > **20%** relativo → investigación.
  - Mensual: AUC < **0.55** → retrain o degradación a reglas.

---

## 10. Roadmap de implementación sobre GridBot (priorizado)

Orden práctico **sobre el código existente** (no reescribir desde cero):

| Fase | Enfoque | Criterio de éxito |
|------|---------|-------------------|
| P0 | **Egress IP + claves** solo-trade sin withdraw; runbook rotación keys | Operación estable sin tocar whitelist a mano |
| P0 | **Modelo de costos** central (comisión, spread, slippage) en backtest y paper | Reportes after-cost automáticos |
| P1 | Esquema BD: señales, sentimiento, costos en fills | Migraciones Alembic + tests |
| P1 | Pipeline TQS en Celery; cola órdenes concurrency 1 | P99 interno bajo presupuesto en rutas definidas |
| P2 | Integración NLP con cache Redis + veto + escala acotada | Sin inferencia BERT en request path |
| P2 | Monte Carlo + escenarios cisne negro en CI opcional | Gates en research antes de subir `TRADING_ENABLED` |
| P3 | LSTM/TF con WF + promoción manual | Registro en `ml_model_registry` |
| P4 | Adapters BYMA/Rofex tras asesoría legal/técnica | Solo tras paper y límites de riesgo separados |

---

## 11. Legal, compliance y operación (docx — obligatorio antes de real)

- Asesoría en **Argentina (CNV, AFIP)** para algoritmos, cuenta propia vs terceros, y registro fiscal de operaciones.
- Revisión **ToS** de Binance (y cualquier exchange) respecto a bots y automatización.
- **Capital de riesgo:** asumir pérdida total del capital asignado al bot en stress extremo.
- **Auditoría / logs** inmutables de órdenes para cumplimiento y post-mortems.

---

## 12. Próximo paso inmediato (acordado entre fuentes)

1. Baseline de **latencia red** hacia Bin desde el entorno de ejecución definitivo (egress fijo).
2. Fijar **cost model** y reproducir **Sharpe/DD after-cost** en walk-forward sobre BTC/ETH.
3. Implementar o endurecer **breakers** ligados a DD diario y a reconciliación.

---

## 13. Referencias en el repositorio

- `Docs/PROTOCOL_PASSIVE_INCOME_BOT_V1_ARCHITECTURE.md` — protocolo base y §venues/IP.
- `Docs/architecture.md` — arquitectura GridBot v2.5.
- `AGENTS.md` — comandos, stack, seguridad.
- `app/core/risk_manager.py`, `app/core/circuit_breakers.py`, `app/core/middleware/integrity_guard.py`
- `docs/deep-research-report.md`, `docs/PassiveIncomeBot_v1.0_Arquitectura.docx` — research fusionado aquí.

---

*Documento maestro consolidado. Actualizar versión cuando cambien umbrales de gates, universos de activos o proveedores de datos.*
