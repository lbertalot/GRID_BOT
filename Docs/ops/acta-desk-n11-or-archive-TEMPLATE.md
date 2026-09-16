# Acta Desk — N11 / archivo (plantilla)

**Rol:** Desk Lead (humano). Cursor **no** firma, **no** desactiva `system_integrity`, **no** wipe.  
**Ancla:** `GRID_BOT/` · paper-only · **PROMOTE_LIVE: NO**  
**Copiar a** `acta-desk-n11-or-archive-YYYY-MM-DD.md` el día de la sesión.

**Precondiciones:**

- [ ] PR G18/G19 código mergeado (lock Redis en git, no solo bind-mount).
- [ ] Acta 72h [`acta-g18g19-72h-2026-09-18.md`](acta-g18g19-72h-2026-09-18.md) con veredicto (PASS habilita A; FAIL → solo B o ITERATE con RCA).

---

## Fork (marcar **una**)

### Opción A — ejecución y cierre técnico limpio (recomendada)

Tras PASS 72h: congelar hash N11 (candidata sidecar `ff6a35fcf84bf91c1da9ea81116265a3789f1d85e5456d19622897c82ed7f5c4`, 10×20, 100 bps — [`fase2-gate-2026-09-22.md`](fase2-gate-2026-09-22.md)), levantar HOLD `system_integrity` **con runbook** (no wipe racha, `GRIDBOT_ALLOW_BREAKER_STORE_WIPE` unset), correr **14–21 días** ininterrumpidos para Capa B honesta.

**Límite A:** un incidente de integridad P0/P1 **o** un gap >2h en esa ventana → **archivo definitivo** de GRID_BOT.

- [ ] **A** — MM+TS alinean `GRID_CONFIG_HASH` env = sidecar **antes** de unfreeze.
- Hash N11 estampado: `________________`
- Ventana Capa B: desde `________` UTC hasta `________` UTC (14–21 d)

### Opción B — archivar ahora

Sin N11. Paper off / no ticks de grid. Gobernanza y docs se conservan.

- [ ] **B** — archivo ahora. Motivo de una línea: ____

Si 72h = FAIL, A no aplica; default B salvo ITERATE documentado (RCA nuevo + nueva ventana 72h).

---

## Vencimiento de SI (obligatorio)

`system_integrity` en REDUCE_ONLY **no** puede quedar abierto sin fecha.

| Campo | Valor |
|-------|--------|
| `si_expires_at` (UTC) | ____ |
| Si vence sin firma A ni B | **default B** |

## Won't

Live · sizing >200 · wipe ledger/Redis/racha · segundo overlay 5×15 · `FORCE_REAL_MODE` · Cursor firma esta acta.

## Firma

Desk Lead (humano): ________    Fecha UTC: ________  
**PROMOTE_LIVE: NO.**
