# LIVE CHECKLIST — solo documental (no ejecutado)

**Repo:** GRID_BOT  
**Fecha del artefacto:** 2026-08-05  
**Modo:** paper-first · **No autoriza live** · **Prohibido** `PROMOTE_LIVE` automático  
**Norma:** `.cursor/rules/40-no-live-without-gate.mdc` · Acta CEO 02 · ADR-007 / RFC-004

> Este documento es un **checklist de readiness**. No firma gate. No arma
> `FORCE_REAL_MODE`. No sustituye la confirmación humana escrita
> («autorizo live en \<exchange\> con capital \<X\>»).

---

## Estado de firmas (Acta 02 / ADR-007)

| Rol | Estado | Nota |
|-----|--------|------|
| CEO | **NO firmado** | Acta 02 desbloquea sprint paper; **no** es autorización live |
| Desk Lead | **NO firmado** | Firma dual pendiente |
| Artefacto `LIVE_GATE_<YYYYMMDD>.md` | **NO generado / NO firmado** | Usar plantilla `Docs/gates/LIVE_GATE_TEMPLATE.md` fuera de git |

**Veredicto documental:** `NO-GO` live. Firma dual **no ejecutada**.

---

## Gate Acta 02 (precondiciones sprint → live-ready)

Orden de sprint autorizado (ya en curso / done según backlog):  
`S-GATE` → `S-PAPER-ISO` → `S-BREAKERS` → `S-TICK`.

Antes de cualquier conversación de firma live, todos deben estar **verdes**:

| ID | Requisito Acta 02 | Evidencia en código / tests | Estado checklist |
|----|-------------------|-----------------------------|------------------|
| B15 | Live gate bloquea **órdenes**, no solo el label | `assert_real_order_allowed` + `live_gate_signed` → `real_armed` | [ ] humano confirma en host |
| B26 | `EMERGENCY_STOP` / `TRADING_ENABLED=false` cortan path real | `trading_mode.compute_effective_mode` + guard; `tests/test_order_execution_guard.py` | [ ] humano confirma E2E |
| B27 | Paper no pega al exchange por comisiones | `CommissionManager` paper-iso; `test_commission_manager_paper_iso.py` | [ ] humano confirma en paper |
| Calendario | Target go-live **2026-09-15**; contingencia **2026-09-22** | Acta 02 | [ ] solo tras tear sheet |
| Firma dual | CEO + Desk Lead explícitos | ADR-007 + `LIVE_GATE_*.md` | [ ] **pendiente — no ejecutada** |

---

## Kill-switch (verificación D2 — 2026-08-05)

Choke-point: `app/core/order_execution_guard.py` → `assert_real_order_allowed`.

| Flag | Efecto en `effective_mode` | ¿Corta órdenes reales? |
|------|----------------------------|-------------------------|
| `EMERGENCY_STOP=true` | `real_blocked` | **Sí** (`RealOrderBlocked: EMERGENCY_STOP`) |
| `TRADING_ENABLED=false` | `real_blocked` | **Sí** (`RealOrderBlocked: TRADING_ENABLED=false`) |
| `PAPER_TRADING=true` sin `FORCE_REAL_MODE` | `paper` | **Sí** (path real prohibido) |
| Sin live gate dual firmado | `real_blocked` | **Sí** (`live_gate_unsigned`) |

Tests de regresión (paper / sin red):  
`pytest tests/test_order_execution_guard.py tests/test_security_post_47.py`

Defaults paper-safe: `env.example` + compose (`PAPER_TRADING=true`, `TRADING_ENABLED=false`, `FORCE_REAL_MODE` vacío, `EMERGENCY_STOP=false`).

---

## Checklist gate humano (regla 40) — no marcar aquí como done de live

- [ ] Tear sheet paper con umbrales OK (Sharpe/Calmar, MaxDD, costos netos)
- [ ] Tests de integridad financiera en verde (Decimal, filtros, breakers, reconciliación)
- [ ] Confirmación escrita del usuario: «autorizo live en \<exchange\> con capital \<X\>»
- [ ] `EMERGENCY_STOP` probado end-to-end en el host de deploy
- [ ] Circuit breakers verificados (estado API alineado con worker — ver B1 si aplica)
- [ ] Observabilidad operativa (métricas, alertas, logs)
- [ ] Secrets fuera de git; keys solo en secret manager / env runtime
- [ ] Keys de exchange **sin** permiso de withdraw
- [ ] `FORCE_REAL_MODE=true` solo tras checklist + gate firmado
- [ ] `PAPER_TRADING=false` consciente y reversible
- [ ] Rollback plan escrito y ensayado
- [ ] Reconciliación contra exchange en verde (paper primero)

Plantilla operativa de firmas: [`Docs/gates/LIVE_GATE_TEMPLATE.md`](gates/LIVE_GATE_TEMPLATE.md).  
Checklist monorepo (referencia): `Docs/engineering/deploy-checklist-live-gate.md`.

---

## Prohibiciones de este artefacto

- No emitir `PROMOTE_LIVE`.
- No activar `FORCE_REAL_MODE` ni `TRADING_ENABLED=true` con `PAPER_TRADING=false`.
- No pegar API keys / secrets reales.
- No tratar Acta 02 ni este checklist como firma dual.

**Siguiente paso permitido:** continuar paper / dry-run y completar evidencias del tear sheet. Live solo con gate firmado + confirmación humana explícita.
