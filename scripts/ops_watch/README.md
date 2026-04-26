# Ops watch (esqueleto)

Ciclo **local** cada N minutos: recoger logs de `docker compose`, aplicar **heurísticas** (sin LLM) y escribir informes en `reports/ops_watch/`.

La capa **Antigravity** (skills + workflow) vive en `docs/OPS_WATCH_ANTIGRAVITY.md` y en el workflow `observability-docker-ops-agent` del repo *antigravity-awesome-skills*: ahí se enlaza el análisis profundo, posibles fixes y despliegue con barandillas.

## Configuración

```bash
cp scripts/ops_watch/config.example.json scripts/ops_watch/config.json
# editar compose_file, services, since, límites
```

## Una ejecución

Desde la raíz del repo:

```bash
python3 scripts/ops_watch/run_once.py
# o explícito:
python3 scripts/ops_watch/run_once.py --config scripts/ops_watch/config.json
```

`make ops-watch-once` hace lo mismo.

Pruebas rápidas de heurísticas (sin cargar el `conftest` pesado del repo):

```bash
make ops-watch-test
```

## Salida

- `reports/ops_watch/raw_*.log` — volcado bruto (posible truncado por `max_log_bytes`)
- `reports/ops_watch/report_*.md` y `.json` — resumen heurístico
- `LATEST.md` / `LATEST.json` / `LATEST.meta.json` — punteros al último ciclo

Códigos de salida: `0` green, `1` yellow, `2` red, `3` error de ejecución.

## Cron (cada 10 min)

```cron
*/10 * * * * cd /ruta/al/grid_bot && /usr/bin/python3 scripts/ops_watch/run_once.py >> logs/ops_watch.cron.log 2>&1
```

## Barandillas (recomendado)

- Este script **no** modifica código ni ejecuta `docker compose up`. Eso queda en **Agent mode** + skills, con revisión humana o entorno sin trading real.
- Para trading: mantener políticas explícitas en compose/`x-app-env` y no automatizar despliegue a producción sin gates.
