# Tear Capa A — Día 1 (2026-08-06 UTC)

**Ventana:** paper L0 · Día **1/30** · ancla `DESK_WINDOW_DAY0_ANCHOR=2026-08-06`  
**E_0:** 1000 USDT · **hash freeze:** `630abf63e4ff9e3a…`  
**Modo:** PAPER · **PROMOTE_LIVE:** NO · sizing 200  
**Owner:** product + desk/quant (acta post-facto 2026-08-07)  
**SoT:** `paper_telemetry/paper_equity_series.json` + ledger

---

## Checklist A1–A8

| ID | Check | Resultado | Nota |
|----|-------|-----------|------|
| **A1** | `config_hash` = freeze | **PASS** | homogéneo `630abf63…` en samples día 1 |
| **A2** | Gaps serie ≤2h | **FAIL** | 1 gap 2.15h (05:10→07:19Z). **Además (post-día):** hueco **~19h** 17:14Z→07 12:11Z — samples tarde/noche del 06 y madrugada del 07 **ausentes** en SoT actual (n=53 vs ~76 vistos el 06) |
| **A3** | `effective_mode=paper` | **PASS** | stack healthy; flags paper |
| **A4** | Equity SoT coherente | **PASS** | E=1000 flat todo el día (min=max=1000) |
| **A5** | Cierre diario ±30m 00:00Z | **FAIL / deuda** | Solo closes ancla `2026-08-06T00:00:00Z` (capturados 05-ago noche). **Falta** marca `daily_close_at` para fin día 1 → `2026-08-07T00:00:00Z`. Fuera de ventana ahora: **no forzar** write (runbook) |
| **A6** | Sin live / FORCE vacío | **PASS** | |
| **A7** | Breakers / integridad | **PASS con incidente** | Reset paper `system_integrity` (binance_net_fail stale) ~17:48Z día 1. Recurrencia día 2 12:03Z por **-2015 IP** |
| **A8** | Costos / fills honestos | **PASS (vacío)** | 0 fills · PnL 0 · fees 0 — sin claim de edge |

---

## Rendimiento (honesto)

| Métrica | Valor |
|---------|-------|
| E_open / E_close (día) | 1000 / 1000 |
| Δ vs E_0 | 0.00% |
| Fills / cycles | 0 / 0 |
| Sharpe / Calmar / MaxDD | **N/A** (sin actividad) |

**Lectura producto:** Día 1 = evidencia de **plataforma paper**, no de estrategia.

---

## Go / no-go día

- **Día 1 como evidencia de integridad:** **ITERATE** (A2+A5 en rojo).  
- **No reiniciar ventana** salvo decisión Desk (hash OK, mode OK, sin wipe intencional documentado).  
- **PROMOTE_LIVE:** **NO**.

## Acciones Día 2 (07-ago)

1. Allowlist Binance IP actual egress (host reportó `153.67.15.120` al triaje).  
2. Breaker `system_integrity`: reset solo si `auth_ok`+`net_ok` (hecho en triaje si aplica).  
3. Próximo cierre: **2026-08-07 23:30–00:30Z** — capturar `daily_close_at=2026-08-08T00:00:00Z` (no backfill inventado).  
4. Investigar por qué la serie perdió samples post-17:14Z del 06 (posible recreate/volumen) — owner devops+backend.
