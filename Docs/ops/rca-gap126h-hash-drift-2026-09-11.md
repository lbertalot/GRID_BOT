# RCA — Gap 126 h (A2) + hash drift `ac1cb596` vs `ff6a35fc` (A1)

| Campo | Valor |
|-------|-------|
| Fecha | 2026-09-11 |
| Modo | paper-only · **PROMOTE_LIVE: NO** |
| Roles | `trading-quant-engineer` + `trading-engineering-manager` (auditoría de datos) |
| Insumo | dossier [dossier-live-ready-or-nogo-2026-09-11.md](dossier-live-ready-or-nogo-2026-09-11.md); tear [tear-sheet-paper-30d-fase0-2026-09-10.md](tear-sheet-paper-30d-fase0-2026-09-10.md) |
| Alcance | Solo lectura / docs. **No** breakers, wipe, racha, N10 JSON, ni firma Fase 0 |
| Owner follow-up | Desk Lead (14-sep firma) + EM (fix instrumentación, tras confirmación) |

---

## Hallazgo 1 — Gap ~126 h en la serie de equity

### Rango exacto (SoT)

| | Timestamp (UTC) | Índice sample | Equity | `config_hash` |
|--|-----------------|---------------|--------|---------------|
| Último antes | **2026-09-04T11:07:22.439878+00:00** | 456 | 999.0232991152 | `ac1cb596…` |
| Primero después | **2026-09-09T17:11:26.343985+00:00** | 457 | 999.0232991152 | `ac1cb596…` |
| Duración | **126.0678 h** (~5 d 6 h) | | sin cambio de equity | sin cambio de hash |

Fuente: `paper_telemetry/paper_equity_series.json` (581 samples al muestreo).  
Es el máximo de los 17 gaps >2 h; el 2.º es ~14.8 h (02→03-sep).

### Cruce de evidencia

| Fuente | Evidencia |
|--------|-----------|
| `logs/gridbot.log.2` | Última línea **2026-09-04T11:07:24Z** (digest desk + pipeline health OK). Silencio absoluto después. |
| `logs/gridbot.log` | Reanuda **2026-09-09T17:11:23Z** con cold start (`Sistema de logging optimizado configurado`). |
| `reports/pipeline_health/` | Último pre-gap: `health_20260904T110723Z.json` (`checked_at` = gap start; `portfolio_snapshots.max_captured_at` alineado). Siguiente: `health_20260909T173935Z.json`. **Cero** reports 05–08-sep. |
| Docker inspect | `gridbot_redis` / `gridbot_db` **StartedAt = 2026-09-09T17:42:53Z** (compose up del stack). Api/worker/beat recreados después (11-sep en el muestreo actual). |
| Day plans | Existen `day22` (04-sep) y `day27` (09-sep 17:44Z). **No** hay day23–day26. |
| Git | Sin commits en la ventana 04–09-sep que expliquen un deploy. |
| RCA beat pidfile | [exec-ola0-beat-pidfile-2026-08-28.md](exec-ola0-beat-pidfile-2026-08-28.md) — **2026-08-28**, stall ~4 h. **No** es este gap. |
| RCA Redis DEL | [rca-si-redis-hash-wipe-2026-08-30.md](rca-si-redis-hash-wipe-2026-08-30.md) — **2026-08-30 ~01:05Z**, ~minutos. **No** es este gap. |

### Veredicto (causa raíz)

**Pausa operativa / stack caído (compose u host off) ~5 días**, no un bug silencioso de telemetría ni un refechado de incidentes previos.

- El proceso se cortó a mitad de un ciclo sano (digest + health OK).
- La reanudación es un **cold start** de procesos + Redis/DB nuevos el 09-sep ~17:11–17:42Z (coincidente con preparación del trial 5×15 intento 3, t0 `2026-09-09T18:01:46Z`).
- Equity idéntica antes/después → no hubo fills ni corrupción de ledger en el hueco; el daño es **cobertura A2** (daily_close ausentes 05–08-sep).

**Clasificación de severidad:** **P1 integridad de serie (A2)** — agujero real de evidencia en la ventana 30d. **No P0 de freeze/ejecución** (no hubo trades bajo config desconocida en el hueco).  
**No** “no aplica”: invalida A2 y debe citarse en la firma Desk del 14-sep.

### Fix (documental)

1. Citar en acta 14-sep: gap 04→09-sep = stack offline; no imputar a beat/Redis.
2. O-3 E2E de `PaperSnapshotStale20m` (post-firma).
3. **No** rellenar samples sintéticos. **No** wipe serie.

---

## Hallazgo 2 — Hash drift `ac1cb596…` vs `ff6a35fc…`

### Qué genera cada hash

| Hash | Algoritmo | Origen concreto |
|------|-----------|-----------------|
| **`ff6a35fc…7f5c4`** | Subconjunto canónico de `scripts/freeze_paper_l0_config.py` (ETHUSDT: symbol/grids/quantity/investment/notional/spacing/range/min/max/mid/trading_mode + `deployed_capital_usd` + `ic_controls`) | Sidecar `grid_config_paper_l0.hash` (N10 post qty-fix, `quantity=0.0082`, mid `2459.72`). También `GRID_CONFIG_HASH` en runtime docker **hoy**. Reproducido byte-a-byte desde el JSON actual. |
| **`ac1cb596…4b219`** | **El mismo** algoritmo de freeze-subset | Primer freeze N10 **pre** qty-fix: `quantity=0.008131` (ROUND_DOWN a 6 decimales). Documentado en [rca-pnl-dd-2026-08-20.md](rca-pnl-dd-2026-08-20.md) §16.2–16.3. Reproducido: `quantity=0.008131` + resto N10 → `ac1cb596…` exacto. |

**No** es el hash de `compute_config_hash()` (JSON entero): ese da `d2d1bf03…` sobre el N10 actual — **tercer** valor, hoy no usado en serie ni sidecar.

### ¿Config no autorizada o artefacto?

| Pregunta | Respuesta con evidencia |
|----------|-------------------------|
| ¿La serie tiene un solo hash? | Sí: **581/581** samples = `ac1cb596…` (desde `2026-08-26T12:11:32Z`). |
| ¿Ese hash corresponde a un freeze real distinto? | **Sí, históricamente:** el freeze N10 de ~12:11–12:20Z del 26-ago con qty `0.008131` (antes del fix). |
| ¿Algún ciclo/fill corrió bajo qty `0.008131`? | **No en el ledger actual.** 38/38 fills tienen `quantity=0.0082` (primer BUY `2026-08-26T12:36:37Z`, post re-freeze §16.5). Disco: `grid_config_paper_l0.json` qty `0.0082`. |
| ¿Por qué la serie sigue diciendo `ac1cb596` con env/`resolve()` = `ff6a35fc`? | **Bug de instrumentación sticky-hash:** `get_paper_equity_series()` rehidrata el header desde JSON; `PaperEquitySeries.record()` hace `config_hash or self.config_hash` y **ningún caller** pasa `resolve_grid_config_hash()`. El label de la serie quedó congelado en el hash del seed inicial y nunca se actualizó al re-freeze. |
| ¿MM OFF_TRACK es correcto? | Parcialmente: compara `last_sample.config_hash` vs `GRID_CONFIG_HASH`/`sidecar` ([desk_hourly_status.py](../../app/core/desk_hourly_status.py) `_area_mm`). Detecta el síntoma; **no** distingue “config distinta en ejecución” vs “label sticky”. |

### Veredicto (causa raíz)

1. **Origen del valor `ac1cb596`:** freeze N10 pre-qty-fix (qty `0.008131`), confirmado por RCA §16.2 + reproducción local.  
2. **Persistencia 2+ semanas:** artefacto de cómputo/telemetría (header sticky), **no** una segunda config N10 distinta operando en paralelo tras el fix.  
3. **Ejecución real de la ventana:** alineada a N10 final (`0.0082` / sidecar `ff6a35fc`) en fills.  
4. **Gate A1 engañoso:** auto-tear marca A1 PASS por “un solo hash en serie”, mientras A1 vs sidecar (expected) está en deuda desde All Hands / advisory 26-ago.

**Clasificación de severidad:**

| Dimensión | Severidad | Motivo |
|-----------|-----------|--------|
| Ejecución / freeze params | **Informativo → no P0 de trading** | Fills = qty autorizada post-fix; no hay evidencia de ciclos con `0.008131` en el ledger N10 actual |
| Gate A1 / gobernanza obs | **P0 instrumentación (retroactivo)** | Ver §2.1: A1 auto PASS en falso vs sidecar/expected |

### 2.1 ¿El sticky hash alimentó un gate de integridad? (respuesta auditada)

**Sí.** No era solo telemetría decorativa.

| Control | ¿Usa `config_hash` de serie/samples? | ¿Compara vs sidecar / `GRID_CONFIG_HASH`? | Resultado N10 (26-ago → 11-sep) |
|---------|--------------------------------------|-------------------------------------------|----------------------------------|
| **A1 auto-tear** `desk_tear_capa_a._a_checks` | **Sí** — unicidad de hashes en samples | **No** | **PASS en falso** EOD con `ac1cb596…` (p. ej. tear-capa-a 27-ago…11-sep) mientras expected = `ff6a35fc…` |
| **`PaperEquitySeries.config_is_frozen()`** | **Sí** — `len(hashes) ≤ 1` | **No** | **True** mientras solo existía el sticky |
| Spec `TEAR_SHEET_PAPER_30D.md` A1 | Un solo hash punta a punta | No exige igualdad a sidecar | Spec estrecha; hueco vs T2 (`L0_PAPER_FREEZE_PARAMS`: sample = sidecar) |
| **Desk MM** `collect_desk_digest` | **Sí** — `last_hash` | **Sí** vs env | **OFF_TRACK correcto** — **no** pasó en falso |
| Tear manual Fase 0 10-sep | Serie vs sidecar | **Sí** (humano) | **FAIL / deuda** correcto |

**Qué pasó en falso:** el gate A1 automático (y `config_is_frozen`) certificó “config congelada” porque el label sticky era **único**, no porque coincidiera con el freeze N10 autorizado. Daño = **confianza diaria de integridad**, no un go-live: Fase 0 sigue **ITERATE**; **PROMOTE_PAPER/LIVE: NO**.

Tras el fix (11-sep): serie con **2 hashes** → `config_is_frozen()=False` / A1 auto **FAIL** honesto.

**Clasificación formal:** **P0 retroactivo de instrumentación del gate A1**. No P0 de ejecución con params no autorizados.

### Fix — estado

**APLICADO** (código + tests, 2026-09-11). Samples históricos no reescritos.

- **A/B:** `resolve()` en marca + `tests/test_config_hash_freeze_contract.py`.
- **C:** acta 14-sep: A1 auto PASS 27-ago→11-sep = falso positivo vs expected; Fase 2 = ventana nueva.
- **D:** no wipe / no rewrite / no tocar N10 JSON.
- **E:** **APLICADO** — A1 auto + `config_is_frozen` exigen unicidad **y** `hash == GRID_CONFIG_HASH|sidecar` (fail-closed sin expected). Regresión sticky≠expected → FAIL.

---

## Relación con Fase 0 (14-sep)

Este RCA es **insumo** para el Desk Lead. Cursor **no** firma DL-4.

Lectura sugerida (no vinculante):

- A2 sigue **FAIL** (gap 126 h + otros); causa del max-gap = stack offline 04→09-sep.  
- A1 vs sidecar sigue **deuda**; causa = sticky pre-qty-fix label, no config pirateada post-12:36Z.  
- Veredicto paper preliminar **ITERATE** del dossier **no** se sustituye aquí.

**PROMOTE_LIVE: NO.**
