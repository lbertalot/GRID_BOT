# EMERGENCY_STOP — checklist E2E host (paper) — 2026-09-11

**Modo:** paper-only · **PROMOTE_LIVE: NO**  
**Cursor:** documenta; **no** ejecuta el flip en host en esta sesión (requiere OK Desk Lead — toca `.env` + recreate).

Código ya cubierto (unit): `tests/test_order_execution_guard.py::test_emergency_stop_blocks_even_with_force`.  
Choke-point: `app/core/order_execution_guard.assert_real_order_allowed` → reason `EMERGENCY_STOP`.  
Runbook recreate: [`breakers-process-scope.md`](breakers-process-scope.md) §Emergency stop.

---

## Qué falta para E2E “de punta a punta” en el host

Hoy: tests unitarios + defaults compose `EMERGENCY_STOP=false`.  
Falta: en el stack docker local, con procesos vivos:

1. Poner `EMERGENCY_STOP=true` en `.env` local (no git).
2. `docker compose -f docker-compose.local.yml up -d --no-deps --force-recreate api worker beat`.
3. Verificar `GET /health` → `emergency_stop=true` (y `effective_mode` ≠ `real_armed`).
4. Intentar path real bloqueado (p. ej. llamada que ejerza `assert_real_order_allowed` / create_order real) → `RealOrderBlocked: EMERGENCY_STOP` **sin** enviar orden a Binance.
5. Restaurar `EMERGENCY_STOP=false` + recreate `--no-deps`.
6. Confirmar `/health` vuelve a `emergency_stop=false`, paper, SI **intacta**.

### Prohibido durante el ensayo

- `FORCE_REAL_MODE`, live gate, `PAPER_TRADING=false`
- `DEL` Redis HASH, wipe ledger, reset racha, recreate redis/db
- Cambiar N10 / overlay 5×15

### Por qué Cursor no lo ejecuta solo

Flip de kill-switch en `.env` + recreate es **acción operativa del host** con efecto en todos los procesos; el Desk debe autorizar ventana y rollback. No es ambiguo en seguridad paper, pero **sí** en gobernanza (quién toca `.env`).

**Estado para dossier:** unit **OK**; E2E host **requiere decisión/ejecución Desk Lead** (esta checklist).
