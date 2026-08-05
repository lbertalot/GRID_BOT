# Protocolo de Investigación Técnica y Estratégica — Bot “Passive Income” v1.0

**Versión del documento:** 1.1
**Ámbito:** Arquitectura de alta disponibilidad, ingresos pasivos orientados a calidad de ejecución y riesgo acotado.
**Mercados objetivo:** Criptomonedas (**Binance por defecto**, con alternativas y política de IP en §2.4), vía abstracción tipo CCXT; mercado argentino (BYMA / Rofex), como segunda fase de integración.
**Alineación con GridBot v2.5:** FastAPI, PostgreSQL/SQLAlchemy/Alembic, Redis/Celery, River/TensorFlow, Prometheus/Grafana, OpenTelemetry, Docker; Kelly fraccional, circuit breakers y paper trading ya presentes como patrones en el ecosistema del repo.

---

## 1. Filosofía de inversión y estrategia

### 1.1 Enfoque direccional y universo de activos

- **Direccional** sobre activos de **alta capitalización y liquidez relativa:** BTC, ETH en cripto; en Argentina, **acciones líderes y CEDEARs** con volumen y spread acotados (criterio cuantitativo de elegibilidad, no solo ticker).
- **“Passive income” operativo:** no scalping de microsegundos; priorizar **menos turnover, más consistencia**, coherente con minimizar comisiones e impacto de mercado.

### 1.2 Mix de análisis

| Capa | Rol | Notas de implementación |
|------|-----|-------------------------|
| **Técnico** | Momentum (p. ej. ROC, RSI filtrado), volatilidad realizada/ATR | Señales de régimen y tamaño de stop; evitar sobre-ajuste con muchos indicadores en el mismo horizonte. |
| **Cuantitativo** | Series temporales, **EMAs** multi-escala, estadística de retornos | Combinar con tests de estabilidad de parámetros (walk-forward, ver §6). |
| **Sentimiento (NLP)** | **Validación** de entradas (filtro de cola), no única fuente de verdad | Scores continuos por ventana temporal; versionar corpus y modelo; fallback determinístico si NLP falla o drift severo. |

### 1.3 Horizonte: balance Day Trading vs Swing Trading

- **Objetivo de investigación:** encontrar el **mínimo número de rotaciones** que mantenga edge estadístico después de costos, dado el par y el venue.
- **Heurística inicial:** operativa **intra-día conservadora** (1–N señales por día) o **swing de varios días** para CEDEARs/BYMA donde el ticket mínimo y comisiones castigan el day trading agresivo.
- **Métrica de decisión:** *after-cost Sharpe*, *turnover*, *avg holding period*, y fracción de trades donde el edge bruto supera **comisión + slippage estimado + spread** (auditoría obligatoria, §5).

---

## 2. Arquitectura de sistemas (stack)

### 2.1 Componentes lógicos

```
┌─────────────────────────────────────────────────────────────────┐
│  API Gateway / Reverse Proxy (p. ej. Nginx) → FastAPI (async)   │
└────────────────────────────┬────────────────────────────────────┘
                             │
     ┌───────────────────────┼───────────────────────┐
     ▼                       ▼                       ▼
 PostgreSQL            Redis                  Workers Celery
 (OLTP + historia      Broker/cache            Estrategia, ingestión,
  ticks agregados*)    colas                   ML batch, reconciliación
     │                       │
     └───────────────────────┴──── Prometheus (métricas) + Grafana
                               OpenTelemetry (trazas) → OTLP
```

\* Para **ticks de alta frecuencia**, ver §4 (extensión recomendada: TimescaleDB o almacén columnar).

### 2.2 Stack tecnológico objetivo

| Capa | Tecnología |
|------|------------|
| Backend | Python 3.11+, **FastAPI**, Uvicorn |
| Persistencia | **PostgreSQL**, **SQLAlchemy 2**, **Alembic** |
| Colas | **Redis**, **Celery** (worker + beat) |
| ML online | **River** (streaming / drift) |
| ML pesado | **TensorFlow** (entrenamiento/scoring batch o servicio lateral) |
| Cripto | **CCXT** + conectores nativos donde haga falta (latencia, websockets) |
| Local | **BYMA / Rofex** | Capa `ExchangeAdapter` / `BrokerAdapter` con contrato unificado (órdenes, balances, posición); integración **por protocolo o proveedor** acordado (no asumir API pública homogénea a Binance). |
| Observabilidad | **prometheus-client**, **Grafana**, **OpenTelemetry** (FastAPI, DB, HTTP saliente) |
| Despliegue | **Docker Compose** en servidor local (perfiles dev/prod como en GridBot) |

### 2.3 Principios de alta disponibilidad

- **Idempotencia** en órdenes (`client_order_id` o equivalente por venue).
- **Degradación graceful:** si NLP o TF no responden, reglas técnicas/cuantitativas + bloqueo de nuevas entradas si supera umbral de incertidumbre.
- **Separación de lectura crítica vs batch:** scoring pesado fuera del hot path de la API.

### 2.4 Venues de criptomonedas: alternativas a Binance, API y whitelist de IPs

Esta sección cierra un gap operativo frecuente: **API keys ligadas a whitelist de IP** en un entorno donde la IP de salida **cambia** (ISP residencial, redes Docker sin egress fijo, despliegues en la nube sin NAT estático, balanceo entre nodos, etc.). Actualizar la whitelist **a mano** cada vez no escala para un bot de **alta disponibilidad** ni para pipelines CI/CD.

#### 2.4.1 Por qué evaluar otros venues además de Binance

| Factor | Implicación para research |
|--------|---------------------------|
| **Liquidez spot BTC/ETH** | Binance sigue siendo referencia global; alternativas “tier-1” suelen cubrir el par spot principal con profundidad aceptable para estrategias no-HFT. |
| **Comisiones y programa maker/taker** | Comparar fee effectivo **after-cost** (§3.4) por volumen y tipo de orden. |
| **Geografía y compliance** | Restricciones por país o KYC pueden excluir venues; validar disponibilidad desde la jurisdicción operativa (p. ej. Argentina). |
| **Modelo de seguridad API** | Bind de IP obligatorio vs opcional, subcuentas, permisos granulares (trade sin withdraw), límites de rate. |
| **Estabilidad WS/REST** | CCXT unifica mucho, pero en producción suelen necesitarse **adaptadores** o reconexión robusta por venue. |

#### 2.4.2 Opciones típicas si se migra (o se multiplica venue)

Ningún ranking es definitivo; la elección debe pasar por **checklist**: pares necesarios, profundidad, fees, latencia aceptable, soporte CCXT (`ExchangeId`), y política de IP.

**Grupo A — Liquidez institucional / very high volume (spot y derivados en parte):**

- **OKX**, **Bybit** (muy fuerte en derivados; spot BTC/ETH usualmente bien). API madura; revisar términos y restricciones regionales.
- **Kraken** — históricamente muy citada para API y seguridad; spot sólido en pares principales; conviene validar latencia y estructura de mercados vs el propio bot.

**Grupo B — Regulados / onboarding distinto (según perfil):**

- **Coinbase (Advanced Trade API)** — enfoque distinto a Binance; útil si la estrategia prioriza el ecosistema Coinbase y la disponibilidad regional.
- **Bitstamp**, **Gemini** — menor universo pero API estable para spot mayorista en algunos casos.

**Grupo C — Mantener Binance pero abstraer**

- La capa **CCXT** + `ExchangeAdapter` interno permite **routing por símbolo o por cartera** sin reescribir la estrategia; investigación: **multi-venue** (arbitraje de ejecución o fallback si un venue cae).

**Tarea de research explícita:** para cada candidato corto, documentar: `(1)` IDs CCXT, `(2)` si la clave permite **operar sin whitelist** (solo trade, sin retiros), `(3)` límites REST/WS, `(4)` disponibilidad geográfica, `(5)` costo transaccional modelo para BTC/ETH spot.

#### 2.4.3 El problema de la whitelist de IP (y por qué “manual” rompe el diseño)

En exchanges como **Binance**, la **restricción por IP** en la API key es una **medida de seguridad recomendada**: solo las IPs listadas pueden firmar requests con esa clave. Si el bot corre en un lugar cuya IP de salida a Internet **no es estable**:

- Cada cambio de IP ⇒ **401/invalid signature** o rechazo hasta actualizar la whitelist en el panel.
- Entornos **Docker en laptop**, **Kubernetes** sin egress fijo, **serverless** o **múltiples egress** multiplican el problema.
- No es viable para **ejecución continua**, ni para **réplicas** ni para **drains** de mantenimiento sin orquestación previa.

**Aclaración:** en Binance la whitelist es **opcional a nivel de configuración de la key**; si se desactiva la restricción de IP, el trade funciona con IP cambiante pero **sube la superficie de ataque** (clave robada usable desde cualquier origen). El equilibrio típico en producción profesional es **IP fija en salida + claves sin permiso de retiro + lista de permitidos de retiro on-chain**.

#### 2.4.4 Patrones que sí permiten operar sin tocar el panel cada semana

| Patrón | Idea | Cuándo usarlo |
|--------|------|----------------|
| **Egress IP estático (cloud)** | NAT Gateway / Cloud NAT con **IP elástica estática** asociada; todo el tráfico del clúster sale por una sola IP conocida. | AWS, GCP, Azure — estándar para bots y microservicios que llaman APIs con IP bind. |
| **VPS / bare metal dedicado** | Una máquina (o pequeño pool detrás del mismo NAT del proveedor) con IP ficha que no rota. | MVP y workloads pequeños; atención a failover (IP única = SPOF salvo HA DNS/scripted failover). |
| **Nodo único “ejecutor de órdenes”** | Toda firma de órdenes sale de un **solo** servicio desplegado donde la IP está controlada; el resto del stack (API, ML, Grafana) puede estar en otro lado. | Separa investigación de **señal** de **ejecución**; reduce exposure de secretos. |
| **Clave API “solo trading”, retiros bloqueados** | Combinar egress estático **o** (solo en entornos muy controlados) key sin bind de IP pero **sin withdraw** y direcciones blancas. | Mitiga robo de clave; no sustituye egress fijo si la política de seguridad exige IP bind. |
| **Proxy de salida fijo** | Túnel/application proxy con IP estática delante del worker. | Viable si el proveedor y los ToS del exchange lo permiten; auditar latencia y fiabilidad. |

**Antipatrón:** depender de la IP pública del hogar o de contenedores que **heredan** una IP que el ISP o el proveedor renueva sin aviso.

#### 2.4.5 Criterio de aceptación para el research de venue + red

1. Definir **una IP (o rango acotado muy pequeño)** de producción documentada y **monitoreada** (alerta si el healthcheck de “egress check” cambia).
2. Decidir si la estrategia es **un solo exchange** o **multi-venue**; en el segundo caso, repetir el análisis de IP/fees por venue.
3. Incluir en el runbook: **rotación de API keys** sin downtime (keys duales + cutover), alineado con kill-switch y breakers.

---

## 3. Gestión de riesgos y capital

### 3.1 Kelly fraccional (criterio explícito)

Definición adoptada para investigación y alineación con documentación:

\[
f^* = \frac{p \cdot (b + 1) - 1}{b} \cdot 0.25
\]

donde:

- \(p\): probabilidad de trade ganador (estimación out-of-sample, no in-sample crudo).
- \(b\): relación beneficio medio / pérdida media (payoff ratio).
- **0.25**: fracción de Kelly (misma filosofía que Kelly fraccional ~25% ya usada en `RiskManager` del proyecto).

**Reglas de investigación:**

- Recalibrar \(p\) y \(b\) por **régimen** o ventana rodante; prohibir usar solo el mejor período histórico.
- Cap duro adicional por símbolo y por equity (como en endpoints de `risk_routes`), coherente con límites operativos.

### 3.2 Drawdown máximo tolerado

- **Investigación y diseño:** banda objetivo **10%–20%** máximo drawdown de cartera estrategia (o sub-cuenta dedicada), antes de:
  - reducir agresivamente tamaño,
  - deshabilitar nuevas entradas,
  - o activar kill-switch automático (ver siguiente).

### 3.3 Stop-loss dinámico, circuit breakers y kill-switch

- **Stop dinámico:** basado en volatilidad (ATR/multiplicador) o trailing; parámetros dependen del activo y del venue.
- **Circuit breakers a nivel cuenta:** latencia API, rechazos consecutivos, discrepancias de reconciliación, límites de pérdida diaria, anomalías de volatilidad (patrón ya conceptualizado en GridBot).
- **Kill-switch:** `EMERGENCY_STOP` / `TRADING_ENABLED` (manual + automático por breaker); middleware tipo *integrity guard* para bloquear operaciones de escritura cuando el sistema declare estado inseguro.

### 3.4 Costos: auditoría obligatoria

Cada simulación y cada backtest deben registrar:

- Comisión maker/taker o arancel aplicable por venue.
- **Spread** (median/mean en ventana de entrada o modelo estimado).
- **Slippage** modelado (fijo, proporcional a volatilidad, o basado en profundidad si hay datos).

Sin bloque “after-cost”, **no se acepta** promoción de estrategia a paper/live.

---

## 4. Diseño de datos (ticks y sentimiento)

### 4.1 Estrategia de almacenamiento

- **PostgreSQL** como fuente de verdad para **órdenes, posiciones, estados de riesgo, features agregados, eventos de NLP** y **candles/bars** (1m, 5m, 1h según estrategia).
- Para **ticks crudos de muy alto volumen**, valorar:
  - **TimescaleDB** (extensión hypertable), o
  - tabla particionada por **rango de tiempo** + retención (TTL jobs).

### 4.2 Esquema sugerido (entidades centrales)

**Convención:** `timestamptz` UTC, `Numeric`/`Decimal` para precios y tamaños; índices `(symbol_id, bucket_start DESC)` para series.

#### A) Mercado y ticks agregados

```text
symbols
  id, venue (BINANCE|BYMA|ROFEX), code, asset_class, tick_size, lot_step,
  active, metadata_json

market_candles
  id, symbol_id, timeframe, bucket_start, open, high, low, close, volume,
  quote_volume, trade_count, source, UNIQUE(symbol_id, timeframe, bucket_start)

-- Opcional alto volumen: market_ticks (hypertable o partición por mes)
market_ticks
  time, symbol_id, price, size, side, trade_id?, source
  PRIMARY KEY (symbol_id, time, trade_id) -- o (symbol_id, time) si agregado
```

#### B) Sentimiento y NLP

```text
sentiment_sources
  id, name (twitter_rss|news_api|internal), reliability_weight, active

sentiment_raw_documents
  id, source_id, fetched_at, published_at?, url_hash UNIQUE, title, body, lang,
  raw_metadata_json

sentiment_scores
  id, document_id?, symbol_id NULLABLE, -- NULL = mercado general
  score (-1..1 or 0..1), confidence, model_name, model_version,
  window_start, window_end, created_at
```

**Enriquecimiento:** tabla puente `sentiment_symbol_mentions` si un documento afecta varios tickers (CEDEAR ↔ subyacente).

#### C) Estrategia, ML y ejecución

```text
strategy_runs / signals
  id, symbol_id, strategy_version, decided_at, horizon_class (DAY|SWING),
  features_json, technical_vote, quant_vote, sentiment_vote, final_score,
  action (BUY|SELL|HOLD), status

ml_model_registry
  id, name, framework (RIVER|TF), artifact_path, checksum, promoted_at,
  metrics_json

ml_predictions
  id, model_id, symbol_id, predicted_at, horizon, value, uncertainty

orders / fills / positions
  (alineados con idempotencia venue y reconciliación)
```

#### D) Backtesting y simulación

```text
backtest_runs
  id, name, config_json, cost_model_json, started_at, finished_at, status

backtest_metrics
  id, backtest_run_id, sharpe, sortino, max_dd, cagr, turnover, after_cost_pnl, ...
```

Este diseño permite **auditoría de costos** guardando `cost_model_json` por corrida y comparando con fills reales en paper/live.

---

## 5. Lógica de backtesting y validación

### 5.1 Capas de prueba (pytest)

1. **Unitarias:** sizing Kelly, aplicación de filtros de venue, parsing de features, serialización de órdenes.
2. **Integración:** mocks de exchange; verificar que `TRADING_ENABLED=false` o paper no envíe órdenes reales.
3. **Regresión de estrategia:** datasets pequeños fijados en repo (fixtures) con resultados *golden* de métricas dentro de tolerancia.

### 5.2 Protocolo Monte Carlo (“cisne negro”)

Objetivo: medir **robustez** ante colas gruesas y rupturas de correlaciones, no solo optimizar media histórica.

**Pasos sugeridos:**

1. **Baseline:** distribución empírica de retornos residuales del modelo o del factor de mercado relevante.
2. **Perturbaciones:**
   - *Bootstrap* bloqueado (preserva dependencia temporal corta).
   - Inyectar **shocks** multiplicativos en retornos (−X% día único, −Y% tres días consecutivos).
   - Subir **slippage** y **spread** en +2σ respecto a histórico de venue.
3. **Métricas por trayectoria simulada:** drawdown, tiempo de recuperación, probabilidad de tocar kill-switch, fracción de capital perdida bajo reglas actuales.
4. **Criterio de aceptación investigación:** p. ej. percentil 95 de drawdown simulado < umbral acordado (≤20%) **y** fracaso controlado del sistema (sin órdenes duplicadas, sin estado inconsistente).

Implementación práctica: módulo `research/monte_carlo.py` con API pura (RORO) + tests que fijen semilla.

### 5.3 Walk-forward y leakage

- Entrenamiento/validación en ventanas rodantes; prohibido usar datos posteriores al timestamp de las decisiones simulados (validación de **point-in-time** para NLP si se usa histórico de noticias).

---

## 6. Métrica P99 y plan de optimización (~250 ms, Docker local)

**Objetivo:** `api_request_duration_seconds` P99 ≤ **250 ms** en rutas críticas de lectura/acción ligera, en entorno local dockerizado (similar a reglas del proyecto).

### 6.1 Medición

- Histogramas Prometheus ya alineados con middleware existente; etiquetas de **baja cardinalidad** (`route`, `method` normalizados).
- **OpenTelemetry:** spans en FastAPI, cliente HTTP hacia exchanges, y consultas DB lentas.

### 6.2 Plan de optimización (orden sugerido)

| Prioridad | Acción |
|-----------|--------|
| P0 | Ninguna lógica pesada (TF inference, agregaciones masivas) en `async` request path; delegar a Celery o cache. |
| P0 | Pool de conexiones asyncpg/SQLAlchemy acorde a workers; evitar N+1 en lecturas. |
| P1 | Redis para snapshots de mercado y último score de sentiment con TTL; invalidación explícita. |
| P1 | Uvicorn workers: equilibrar CPU vs memoria; en local, 2–4 workers según host. |
| P2 | Red Docker: colocar API, Redis y DB en red interna; evitar volúmenes lentos en hot path. |
| P2 | Compilar/teager features en batch en beat (precálculo por barra cerrada). |

### 6.3 Gate de release

- Presupuesto de latencia por endpoint documentado; fallos de P99 disparan investigación antes de subir flags de trading real.

---

## 7. Flujo de trabajo ML y reconciliación con Paper / Testnet

### 7.1 Flujo end-to-end

1. **Ingesta:** precios y candles → features técnicos/cuantitativos; documentos → pipeline NLP → `sentiment_scores`.
2. **River (online):** actualiza componentes incrementales (drift, clasificadores ligeros); persiste estado versionado en disco (patrón híbrido GridBot).
3. **TensorFlow (pesado):** reentrenamiento o scoring batch; artefacto registrado en `ml_model_registry`; promoción solo si gating de backtest + Monte Carlo pasa **after-cost**.
4. **Decisión:** motor de estrategia combina votos; Kelly y límites recortan tamaño; NLP **solo confirma o vet** según policy (p. ej. score < umbral → no abrir nuevas posiciones).
5. **Paper / testnet:** mismas rutas de orden que producción pero con flags (`PAPER_TRADING`, `BINANCE_TESTNET`) y simulación de fills si aplica.

### 7.2 Reconciliación periódica modelo ↔ mercado

- **Cadencia:** alineada con la filosofía del proyecto (≤ **60 s** para detectar divergencias operativas cuando el sistema esté en modo activo).
- **Qué comparar:**
  - Posición interna vs broker/exchange.
  - Órdenes abiertas vs estados remotos.
  - PnL teórico vs realizado (paper: vs motor de simulación).
- **Drift de ML:** comparar distribución de features recientes vs entrenamiento; si excede umbral → degradar a reglas estáticas y alertar.
- **Registro:** cada corrida de reconciliación escribe evento/métrica (`reconciliation_discrepancy`, latencia); breakers si hay discrepancia persistente.

### 7.3 Promoción de modelo

```
Backtest after-cost OK → Monte Carlo OK → Paper trading (N semanas) →
métricas de slippage real vs modelo → promote en registry → canary (10% tamaño) → full
```

---

## 8. Roadmap de integración BYMA / Rofex

1. **Fase 0:** Contrato de `BrokerAdapter`; paper manual + CSV histórico para backtests.
2. **Fase 1:** Conectividad read-only (posiciones, fills); reconciliación sin órdenes automáticas.
3. **Fase 2:** Órdenes limitadas, tamaños mínimos, horarios de sesión y **calendar argentino** en el scheduler.
4. **Rofex:** reglas de margen y instrumentos distintos al cash equity; módulo de riesgo separado o flags por `asset_class`.

---

## 9. Entregables sugeridos para el equipo

| Entregable | Descripción |
|------------|-------------|
| ADR | Elección TimescaleDB vs solo Postgres particionado para ticks. |
| ADR | Política exacta NLP como filtro vs peso en score final. |
| ADR | **Venue cripto:** Binance vs alternativas (§2.4); egress IP estático y modelo de API keys. |
| Esquema Alembic | Migraciones para tablas §4. |
| Suite pytest | Unit + integración + golden backtests + Monte Carlo con semilla. |
| Dashboard Grafana | P99, errores de venue, drawdown, estado breakers, drift ML. |
| Runbook | Kill-switch, recuperación tras discrepancia de reconciliación. |

---

## 10. Referencias cruzadas en el repo

- Arquitectura general: `Docs/architecture.md`
- Guía operativa y stack: `AGENTS.md`
- Kelly y sizing: `app/core/risk_manager.py`, `app/api/risk_routes.py`
- Multi-venue (Passive Income §8): `app/services/broker_adapter/` (`BROKER_PRIMARY_VENUE`, `USE_BROKER_ADAPTER` → `TradeExecutor` MARKET).
- Breakers e integridad: `app/core/circuit_breakers.py`, `app/core/middleware/integrity_guard.py`

---

*Documento generado como base de investigación para “Passive Income” v1.0; evolucionar con ADRs a medida que BYMA/Rofex y políticas de datos reales se concreten.*
