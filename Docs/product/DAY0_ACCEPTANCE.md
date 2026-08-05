# AC producto — Día 0 ventana paper L0

| Campo | Valor |
|-------|--------|
| **Owner** | `trading-product-expert` |
| **Repo ancla** | `GRID_BOT/` |
| **Veredicto de negocio** | `L0_DAY0_WINDOW_GO` \| `L0_DAY0_WINDOW_NO_GO` |
| **Política** | monorepo [`desk-policy-l0.md`](../../../Docs/squad/desk-policy-l0.md) v2 §2 / §3 / §6 |
| **Canónicos técnicos** | [`L0_PAPER_FREEZE_PARAMS.md`](../L0_PAPER_FREEZE_PARAMS.md) · [`S_TICK_EXECUTION_LOG.md`](../S_TICK_EXECUTION_LOG.md) · [`PAPER_WINDOW_DAY0.md`](../PAPER_WINDOW_DAY0.md) · [`TEAR_SHEET_PAPER_30D.md`](../TEAR_SHEET_PAPER_30D.md) |
| **Modo** | **Paper-only.** Este documento **no** autoriza live ni claim de edge. |

> **Propósito:** criterios de aceptación de *producto* para declarar el **día 0 de ventana** válido.  
> No mide rentabilidad. No sube sizing. No emite `PROMOTE_LIVE`.

---

## 0. Qué es (y qué no es) el día 0

| Es | No es |
|----|--------|
| Primer día calendario UTC con serie equity paper **contable y congelada** | Evidencia de edge / Sharpe / “el bot gana” |
| Arranque del conteo de 30 retornos diarios (ventana canónica) | Autorización de go-live |
| Go de integridad + UX paper inequívoca + freeze A1 | Promoción de capital desplegado por encima de **USD 200** |
| Firma dual Desk Lead + market-maker | Emisión de `PROMOTE_LIVE` (prohibido en este artefacto) |

**Claim prohibido en cualquier copy, acta o dashboard día 0:**

- “Paper demostró rentabilidad / edge / alpha.”
- “Listos para live” / “PROMOTE_LIVE” / sugerir `FORCE_REAL_MODE`.
- Presentar ceros inventados como PnL “neutro” cuando la fuente no existe.

**Sizing inmutable en L0-A:** capital desplegado **USD 200** (10 × USD 20, spacing 100 bps, ETHUSDT). Subir sizing = **NO-GO de producto** y reinicio de ventana (desk A1).

---

## 1. AC UX — `effective_mode=paper` inequívoco

**Persona:** CEO / Desk Lead / MM / retail observando el stack.  
**KPI producto:** time-to-trust del modo (cero ambigüedad paper vs live).

### 1.1 Health (fuente pública)

| ID | Criterio | Evidencia testable | Go | No-go |
|----|----------|--------------------|----|-------|
| **UX-H1** | `GET /health/trading-mode` reporta `trading.effective_mode == "paper"` | `curl` + jq | ☐ | ☐ |
| **UX-H2** | Flags coherentes: `paper_trading=true`, `force_real_mode=false`, `trading_enabled=false`, `live_gate_signed=false` | mismo endpoint | ☐ | ☐ |
| **UX-H3** | `GET /health` 200; stack compose healthy | `docker compose … ps` + health | ☐ | ☐ |
| **UX-H4** | Badge / texto de modo **no** dice “live”, “real”, “armed” ni “producción” | UI o payload health | ☐ | ☐ |

### 1.2 CEO (fuente autenticada)

| ID | Criterio | Evidencia testable | Go | No-go |
|----|----------|--------------------|----|-------|
| **UX-C1** | `GET /api/ceo/overview` → campo raíz `effective_mode == "paper"` | Bearer `API_KEY` | ☐ | ☐ |
| **UX-C2** | Dashboard CEO (`/api/ceo/dashboard` o UI) muestra modo paper con el **mismo** valor que health | comparación health ↔ CEO | ☐ | ☐ |
| **UX-C3** | Gate live: badge `live_gate_signed=false` (fail-closed) | overview / trading-mode | ☐ | ☐ |
| **UX-C4** | Si health y CEO discrepan en modo → **NO-GO UX** hasta alinear | diff de payloads | ☐ | ☐ |

**Regla de producto:** el operador no debe necesitar leer `.env` para saber que está en paper. Si hace falta “adivinar”, el AC falla.

Smoke de referencia (no sustituye el checklist §3):

```bash
curl -sf http://localhost:8000/health/trading-mode | jq .trading.effective_mode
# → "paper"
curl -sf -H "Authorization: Bearer $API_KEY" \
  http://localhost:8000/api/ceo/overview | jq .effective_mode
# → "paper"
```

---

## 2. AC CEO cards — honestidad > ceros inventados

Cards en alcance día 0: **breakers**, **ops**, **equity**, **`pnl_mtd`**.

Contrato de widget (implementación `app/core/ceo_overview.py`):

| `status` | Significado de producto | `value` |
|----------|-------------------------|---------|
| `ok` / `stale` | Dato real de la fuente (puede ser viejo) | número o estructura real |
| `unavailable` | Fuente ausente, adapter caído, o serie inexistente | **`null`** — **nunca** `0` fingido |

### 2.1 Matriz por card

| Card | Campo overview | Día 0 — aceptable | Día 0 — prohibido |
|------|----------------|-------------------|-------------------|
| **Breakers** | `breakers` | `ok` con lista real (`open_breakers` / `any_open`); o `unavailable` si la fuente falla | Inventar `any_open=false` / lista vacía cuando el adapter falló |
| **Ops** | `ops_burn_mtd`, reservas (`ops_reserve_*`) | `ok`/`stale` con Decimal real del ledger ops; o `unavailable` | Rellenar `0` “porque aún no hubo gasto” si el ledger no respondió |
| **Equity** | `equity_reconciled` (+ capital relacionado) | `ok`/`stale` desde capital risk / ledger; o `unavailable` | Mostrar `0` o `200` inventados sin reconciliación |
| **`pnl_mtd`** | `pnl_mtd` | **`unavailable` es GO de producto** si aún no hay serie MtM del mes / facade sin datos | Mostrar `pnl_mtd.value = 0` (o “±0%”) como si fuera flat real |

### 2.2 Criterios binarios

| ID | Criterio | Go | No-go |
|----|----------|----|-------|
| **CEO-1** | Toda card degradada usa `status=unavailable` y `value=null` (o equivalente UI “sin dato”) | ☐ | ☐ |
| **CEO-2** | Sin serie equity / sin `pnl_ledger` usable → `pnl_mtd` **unavailable**; copy UI no implica “break-even” | ☐ | ☐ |
| **CEO-3** | Breakers: si `ok`, el conteo coincide con `GET /api/breakers/status` (no badge cosmético contradictorio) | ☐ | ☐ |
| **CEO-4** | Ops/equity en `ok` o `stale` **no** son 500; overview degrada, no rompe el pantallazo | ☐ | ☐ |
| **CEO-5** | **Forbidden:** sustituir ausencia de dato por cero monetario, cero %, o “sin cambios” | ☐ | ☐ |

> **Por qué importa:** un cero inventado se lee como “no perdimos”. Eso es claim implícito de resultado. Día 0 acepta **opacidad honesta**, no neutralidad falsa.

---

## 3. Checklist go/no-go de **negocio** — `L0_DAY0_WINDOW_GO`

Alineado a [`L0_PAPER_FREEZE_PARAMS.md`](../L0_PAPER_FREEZE_PARAMS.md) §3–§4 y al camino operativo de [`S_TICK_EXECUTION_LOG.md`](../S_TICK_EXECUTION_LOG.md).  
Un solo rojo de negocio → **`L0_DAY0_WINDOW_NO_GO`**.

### 3.1 GO — declarar día 0 de ventana

Todas las filas en verde:

| # | Criterio de negocio | Ancla técnica | ☐ |
|---|---------------------|---------------|---|
| **B1** | Modo paper inequívoco (AC §1 health + CEO) | A8 / UX-H* / UX-C* | ☐ |
| **B2** | Freeze A1 cerrado: status `PAPER_FROZEN`, un solo `config_hash` = sidecar `grid_config_paper_l0.hash` | L0 §4.1.1 · S-TICK §3.2 | ☐ |
| **B3** | Params freeze intactos: ETHUSDT, **USD 200**, 10×20, 100 bps, ±5%, IC-1/IC-2 en metadata | desk §2.4 · L0 §1 | ☐ |
| **B4** | ≥ 1 **primer tick válido** (T1–T10) persistido con ese hash | L0 §3.4 | ☐ |
| **B5** | Cierre diario 00:00 UTC (±30 min) con `E_0` de referencia | L0 §3.3 / §4.1.3 | ☐ |
| **B6** | Capa A preliminar local: A1, A6, A8; A3/A5 verificables sobre marcas del día | tear sheet §1 · L0 §4.1.4 | ☐ |
| **B7** | Sin rebuys fuera de rango el día 0; IC flags activos (implementación IC cableada o owner A2 con fecha) | L0 §2 / §4.1.5 | ☐ |
| **B8** | Stack paper-safe + obs up (compose, metrics, sin keys prod, `FORCE_REAL_MODE` vacío) | PAPER_WINDOW_DAY0 · S-TICK §3.1 | ☐ |
| **B9** | CEO cards: AC §2 cumplido (`pnl_mtd` unavailable OK; sin ceros inventados) | este doc §2 | ☐ |
| **B10** | Acta firmada Desk Lead + market-maker: hash + `E_0` + timestamp UTC + veredicto | L0 §4.3 | ☐ |
| **B11** | Copy del acta / dashboard: **sin claim de rentabilidad**; sizing **no** subido; **sin** `PROMOTE_LIVE` | este doc §0 / §4 | ☐ |

### 3.2 NO-GO — no declarar día 0

Cualquiera (unión de L0 §4.2 + producto):

| # | Condición |
|---|-----------|
| **N1** | `config_hash` ausente, múltiple, o ≠ sidecar / `GRID_CONFIG_HASH` runtime |
| **N2** | Tick con mid inventado o feed caído forzado a constante |
| **N3** | Fills sin `commission` o fees no descontadas del cash |
| **N4** | `deployed_capital` ≠ 200 **o** intento de subir sizing / bajar spacing “para ciclos” |
| **N5** | `effective_mode ≠ paper` o cualquier orden real |
| **N6** | Reconciliación A3 > 0,1% sin causa raíz cerrada |
| **N7** | Wipe de ledger / `./data` / `paper_telemetry` tras sample “válido” |
| **N8** | Contar jornadas previas a instrumentación S10 / freeze como días de ventana |
| **N9** | CEO cards con ceros inventados (esp. `pnl_mtd`) |
| **N10** | Acta con claim de edge, “listos para live”, o mención de `PROMOTE_LIVE` como siguiente paso |
| **N11** | Blockers S-TICK B1–B5 abiertos sin mitigación verificada (hash runtime, mounts L0, telemetría, freeze `--write`, tick E2E) |

### 3.3 Plantilla de veredicto (negocio)

```
Fecha UTC: ________
config_hash: ________________________________
E_0 (cierre día 0): ________ USDT
deployed_capital: 200
effective_mode: paper
primer_tick_at: ________

UX paper (health=CEO): PASS | FAIL
CEO cards honestas (pnl_mtd unavailable OK): PASS | FAIL
Claim de rentabilidad en acta/UI: AUSENTE (requerido) | PRESENTE → NO-GO
Sizing subido sobre 200: NO (requerido) | SÍ → NO-GO
PROMOTE_LIVE emitido: NO (requerido) | SÍ → NO-GO

Veredicto: L0_DAY0_WINDOW_GO | L0_DAY0_WINDOW_NO_GO
Razones / owner gaps: ________
Firmas: Desk Lead ________  Market Maker ________
```

**Estado de referencia (S-TICK 2026-08-05):** camino prep **GO condicional**; **`L0_DAY0_WINDOW_GO` = NO-GO** hasta cerrar freeze `--write`, hash runtime, tick válido y cierre diario. Este AC no cambia ese hecho: solo fija qué debe cumplir producto cuando se pida el GO.

---

## 4. Explicit non-goals (día 0)

| Non-goal | Qué hacer en su lugar |
|----------|------------------------|
| Claim de rentabilidad / edge | Reportar solo integridad, modo, freeze, `E_0`, gaps honestos |
| Subir sizing > USD 200 | Mantener L0-A; cualquier aumento = nueva política desk + reinicio A1 |
| `PROMOTE_LIVE` | Veredictos de ventana al cierre: `ITERATE` \| `PROMOTE_PAPER` \| `REJECT` ([`TEAR_SHEET_PAPER_30D.md`](../TEAR_SHEET_PAPER_30D.md)); live solo con gate dual + regla `40-no-live-without-gate` |
| Usar CEO `pnl_mtd` como SoT del tear sheet 30d | SoT = `PaperEquityLedger` / serie S10 |
| Declarar día 0 por smoke HTTP solo | Exige tick válido + cierre diario (L0 §3–§4) |

---

## 5. Handoff

| Rol | Acción tras este AC |
|-----|---------------------|
| `trading-engineering-manager` | Trazar B1–B11 a checks automatizables / smoke; no relajar unavailable→0 |
| `trader-market-maker` | Freeze `--write` + primer tick según L0 §3 |
| Desk Lead | Firmar `L0_DAY0_WINDOW_GO` solo con §3.1 completo |
| `trading-devops` | Cerrar blockers S-TICK que bloquean B2/B8 |
| Quant | Medición tear sheet 30d **después** del día 0; sin reinterpretar este GO como edge |

**Paper-first. Este AC no autoriza live.**

---

## Changelog

| Fecha | Cambio | Autor |
|-------|--------|-------|
| 2026-08-05 | C4 — AC producto día 0: UX paper, CEO cards honestas, checklist L0_DAY0_WINDOW_GO, non-goals sizing/PROMOTE_LIVE/edge | trading-product-expert |
