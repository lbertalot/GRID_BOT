## Automatización de Retención y Limpieza de Artefactos

Este documento explica cómo programar la tarea de retención/compresión definida en `scripts/retention_cleanup.py`.

Prerrequisitos:
- Variables de entorno: `MONITORING_DIR` (por defecto `monitoring_data/`), `REPORTS_DIR` (por defecto `reports/`).
- Python 3 disponible.

### Opción 1: crontab (Linux/macOS)

Ejecutar semanalmente con logs básicos:

```bash
crontab -e
```

Agregar (ajusta la ruta del proyecto):

```bash
# Ejecuta los domingos a las 03:15
15 3 * * 0 cd /Users/leandrobertalot/Documents/grid_bot && \
  MONITORING_DIR=monitoring_data REPORTS_DIR=reports \
  /usr/bin/env python3 scripts/retention_cleanup.py --verbose >> logs/retention.log 2>&1
```

Ver ejecución en seco diaria (opcional):

```bash
# Todos los días a las 03:10 (dry-run)
10 3 * * * cd /Users/leandrobertalot/Documents/grid_bot && \
  MONITORING_DIR=monitoring_data REPORTS_DIR=reports \
  /usr/bin/env python3 scripts/retention_cleanup.py --dry-run >> logs/retention_dry.log 2>&1
```

### Opción 2: systemd (Linux)

Crear los archivos de unidad (ajusta rutas):

`/etc/systemd/system/gridbot-retention.service`

```ini
[Unit]
Description=GridBot Retention Cleanup
Wants=gridbot-retention.timer

[Service]
Type=oneshot
WorkingDirectory=/opt/grid_bot
Environment=MONITORING_DIR=monitoring_data
Environment=REPORTS_DIR=reports
ExecStart=/usr/bin/env python3 scripts/retention_cleanup.py --verbose
StandardOutput=append:/opt/grid_bot/logs/retention.log
StandardError=append:/opt/grid_bot/logs/retention.log

[Install]
WantedBy=multi-user.target
```

`/etc/systemd/system/gridbot-retention.timer`

```ini
[Unit]
Description=Schedule GridBot Retention Cleanup Weekly

[Timer]
OnCalendar=Sun *-*-* 03:15:00
Persistent=true

[Install]
WantedBy=timers.target
```

Activar:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now gridbot-retention.timer
sudo systemctl status gridbot-retention.timer
```

### Opción 3: Docker Compose (cron en contenedor sidecar)

Agregar un contenedor sidecar con cron que ejecute la tarea (ejemplo simplificado):

```yaml
services:
  retention:
    image: python:3.11-slim
    working_dir: /app
    volumes:
      - ./:/app
      - ./logs:/app/logs
    environment:
      - MONITORING_DIR=/app/monitoring_data
      - REPORTS_DIR=/app/reports
    command: /bin/sh -c "echo '15 3 * * 0 python scripts/retention_cleanup.py --verbose >> logs/retention.log 2>&1' | crontab - && cron -f"
    profiles:
      - maintenance
```

Levantar el perfil maintenance cuando sea necesario:

```bash
docker compose --profile maintenance up -d retention
```

### Notas operativas
- Ejecuta `make retention-dry` para validar qué se afectará sin cambios.
- Monitorea el tamaño de `monitoring_data/` y `reports/` y ajusta retenciones si es necesario.
- Si usas `ndjson.gz`, considera exportar agregados para BI antes de purgar.


