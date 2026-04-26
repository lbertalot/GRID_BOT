# Runbook Paper Local - Version Rapida (10 comandos)

Objetivo: validacion operativa diaria en modo paper en menos de 10 minutos.

Uso:
- Ejecutar de arriba hacia abajo.
- Si un paso falla, detenerse y abrir el runbook completo:
  `Docs/operations/RUNBOOK_CERTIFICACION_PAPER_LOCAL.md`.

---

## Precondiciones

- Estar en la raiz del repo `grid_bot`.
- Docker Desktop levantado.

---

## Checklist ultra rapido

- [ ] 1) Confirmar override paper en compose

```bash
docker compose -f docker-compose.local.yml config | rg "PAPER_TRADING|FORCE_REAL_MODE|TRADING_ENABLED"
```

Esperado:
- `PAPER_TRADING: "true"`
- `FORCE_REAL_MODE` vacio o `false`

- [ ] 2) Levantar stack

```bash
docker compose -f docker-compose.local.yml up --build -d
```

- [ ] 3) Estado de contenedores

```bash
docker compose -f docker-compose.local.yml ps
```

Esperado:
- `db` y `redis` healthy
- `migrate` exited(0)
- `api`, `worker`, `beat` running

- [ ] 4) Health API

```bash
curl -sf http://localhost:8000/health
```

- [ ] 5) Smoke de Celery (worker responde)

```bash
docker compose -f docker-compose.local.yml exec -T worker celery -A app.core.celery_app inspect ping --timeout=10
```

- [ ] 6) Verificar que tick/beat no exploten

```bash
docker compose -f docker-compose.local.yml logs --since 10m beat worker | rg -i "error|traceback|exception" || true
```

Esperado:
- Sin errores repetitivos criticos.

- [ ] 7) Dry-run paper

```bash
make dry-run SYMBOL=BTCUSDT QTY=0.0002 SIDE=BUY TYPE=MARKET
```

- [ ] 8) Ops watch rapido

```bash
python3 scripts/ops_watch/run_once.py
```

Esperado:
- `reports/ops_watch/LATEST.md` en `green` o hallazgos explicables.

- [ ] 9) Snapshot de portfolio (si existe dato)

```bash
curl -sf "http://localhost:8000/api/v1/portfolio/snapshot/latest" || true
```

Esperado:
- Respuesta valida o mensaje controlado de "no hay snapshots aun".

- [ ] 10) Cierre y evidencia minima

```bash
mkdir -p reports/certificacion_paper && docker compose -f docker-compose.local.yml ps > reports/certificacion_paper/ps_rapido.txt
```

---

## Criterio GO / NO-GO rapido

GO si:
- Stack saludable (pasos 2-4).
- Worker/beat estables (pasos 5-6).
- Dry-run paper OK (paso 7).
- Ops watch sin alertas criticas (paso 8).

NO-GO si:
- `migrate` falla.
- `api` no responde `/health`.
- Errores repetitivos en beat/worker.
- Dry-run falla por validaciones no esperadas.

