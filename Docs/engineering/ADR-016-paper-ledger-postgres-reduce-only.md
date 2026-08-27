# ADR-016 — Ledger paper transaccional y contención REDUCE_ONLY

## Estado
Aceptado para implementación paper-only.

## Contexto
`paper_equity_ledger.json` es la fuente contable actual, pero no ofrece
serialización entre workers ni idempotencia por intent/fill. A la vez,
`system_integrity` usa un booleano que bloquea indiscriminadamente BUY y SELL.
Un fallo de lectura de Redis no puede interpretarse como ausencia de breaker.

## Decisión
- PostgreSQL será la fuente autoritativa para ciclos paper, fills, intents y
  reservas de inventario. El JSON queda como export/snapshot de compatibilidad.
- El breaker `system_integrity` tendrá estados operativos `CLOSED`, `OPEN`,
  `REDUCE_ONLY` y `REVIEW_REQUIRED`.
- Todo registro legacy activo sin estado operativo se interpreta como
  `REDUCE_ONLY`; se preservan `activated_at`, razón y contador.
- REDUCE_ONLY bloquea cualquier incremento de exposición y solo autoriza SELL
  asignados a ciclos abiertos, reservados atómicamente y con PnL neto esperado
  no negativo según la política configurada.
- Redis, Postgres, reconciliación, mark o estado inválido no verificables
  rechazan la orden. No hay fallback fail-open.
- Una transición hacia `CLOSED` requiere revisión humana posterior; timeout
  solo progresa a `REVIEW_REQUIRED`.

## Consecuencias
- La API y los workers deben usar una única autorización de ejecución.
- Las métricas de workers se publican mediante el sidecar existente.
- No se habilita live, no se resetea el breaker vigente y no se efectúan
  operaciones durante esta entrega.

## Rollback
Mantener el export JSON y los lectores de estado legacy. Ante fallo de la
migración, bloquear ejecución paper con `REVIEW_REQUIRED`; nunca volver al
fallback que asume breakers cerrados.
