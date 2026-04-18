# Plan de migración: Heroku → Postgres y Redis con tier gratis

**Objetivo**: Sustituir los add-ons de pago de Heroku (heroku-postgresql, heroku-redis) por servicios con tier gratis que exponen URL estándar.

**Servicios elegidos**:
- **PostgreSQL**: [Neon](https://neon.tech) (o [Supabase](https://supabase.com))
- **Redis**: [Upstash](https://upstash.com)

**Variables afectadas**: `DATABASE_URL`, `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`.

---

## Fase 0 – Prerrequisitos (manual)

| Paso | Acción | Estado |
|------|--------|--------|
| 0.1 | Crear cuenta en [Neon](https://neon.tech) | ☐ |
| 0.2 | Crear cuenta en [Upstash](https://upstash.com) | ☐ |
| 0.3 | Tener Heroku CLI instalado y `heroku login` | ☐ |
| 0.4 | Conocer el nombre de la app Heroku (ej. `grid-bot-ia`) | ☐ |

**App actual**: `grid-bot-ia`. URL web: ver con `heroku info -a grid-bot-ia` (p. ej. `https://YOUR-APP-NAME.herokuapp.com/`).

---

## Fase 1 – Crear recursos externos

### 1.1 Neon (PostgreSQL)

1. En [Neon Console](https://console.neon.tech): **New Project** → nombre ej. `gridbot-prod`.
2. Crear base de datos (viene una por defecto).
3. En **Connection string** elegir **Pooled** (recomendado para serverless) o **Direct**.
4. Copiar la URL. Formato esperado:
   ```
   postgresql://USER:PASSWORD@ep-XXX-XXX.region.aws.neon.tech/neondb?sslmode=require
   ```
5. Guardar en local (no commitear): `NEON_DATABASE_URL=<esa_url>`

**Verificación**: La URL debe ser `postgresql://`. El código ya convierte `postgres://` → `postgresql://` si fuera necesario.

### 1.2 Upstash (Redis)

1. En [Upstash Console](https://console.upstash.com): **Create Database**.
2. Nombre ej. `gridbot-redis`, región cercana a Heroku (ej. `us-east-1`).
3. Tipo **Regional** (tier gratis).
4. Crear y abrir la base.
5. En **REST API** o pestaña de conexión, copiar la URL. Formato esperado:
   ```
   rediss://default:PASSWORD@XXX.upstash.io:6379
   ```
6. Guardar en local: `UPSTASH_REDIS_URL=<esa_url>`

**Verificación**: Debe ser `rediss://` (SSL). El proyecto ya soporta `rediss://` en `app/core/celery_app.py`.

---

## Fase 2 – Backup de datos actuales (Heroku)

Ejecutar **antes** de cambiar variables en producción.

```bash
# Reemplazar TU_APP_NAME por el nombre de tu app Heroku
export HEROKU_APP=TU_APP_NAME

heroku pg:backups:capture -a $HEROKU_APP
heroku pg:backups:download -a $HEROKU_APP
# Genera latest.dump en el directorio actual
```

Opcional: guardar `latest.dump` en un lugar seguro (S3, disco). Si no necesitas migrar datos, puedes omitir el download y solo hacer capture por seguridad.

---

## Fase 3 – Restaurar datos en Neon (solo si hay backup)

Solo si tienes `latest.dump` y quieres migrar datos existentes.

```bash
# NEON_DATABASE_URL debe estar definida con la URL de Neon
pg_restore -d "$NEON_DATABASE_URL" --no-owner --no-acl -v latest.dump
```

Si aparecen errores de roles/owner, suelen ser seguros; comprobar que tablas y datos existen.

Luego aplicar migraciones si hace falta:

```bash
DATABASE_URL="$NEON_DATABASE_URL" alembic upgrade head
```

---

## Fase 4 – Configurar Heroku

Establecer las nuevas URLs **sin eliminar** aún los add-ons (por si hay que hacer rollback).

```bash
export HEROKU_APP=TU_APP_NAME
# Usar las URLs reales de Neon y Upstash (no commitear)
export NEON_DATABASE_URL="postgresql://..."
export UPSTASH_REDIS_URL="rediss://..."

heroku config:set DATABASE_URL="$NEON_DATABASE_URL" -a $HEROKU_APP
heroku config:set REDIS_URL="$UPSTASH_REDIS_URL" -a $HEROKU_APP
heroku config:set CELERY_BROKER_URL="$UPSTASH_REDIS_URL" -a $HEROKU_APP
heroku config:set CELERY_RESULT_BACKEND="$UPSTASH_REDIS_URL" -a $HEROKU_APP
```

Comprobar:

```bash
heroku config -a $HEROKU_APP | grep -E "DATABASE_URL|REDIS_URL|CELERY"
```

---

## Fase 5 – Verificar aplicación

1. **Migraciones** (si no restauraste dump):
   ```bash
   heroku run alembic upgrade head -a $HEROKU_APP
   ```

2. **Reiniciar**:
   ```bash
   heroku restart -a $HEROKU_APP
   ```

3. **Logs**:
   ```bash
   heroku logs --tail -a $HEROKU_APP
   ```

4. **Health**:
   ```bash
   curl https://$HEROKU_APP.herokuapp.com/health
   ```

5. Si usas workers/beat de Celery, comprobar que las tareas se encolan y ejecutan (logs o Flower).

Si algo falla, hacer rollback restableciendo las variables anteriores (URLs de los add-ons de Heroku) y no destruir los add-ons hasta estar seguro.

---

## Fase 6 – Retirar add-ons de Heroku (solo cuando todo esté estable)

**Solo después** de confirmar que la app y Celery funcionan correctamente con Neon y Upstash.

```bash
heroku addons:destroy heroku-postgresql:essential-0 -a $HEROKU_APP
heroku addons:destroy heroku-redis:premium-0 -a $HEROKU_APP
```

Confirmar cuando Heroku lo pida. A partir de aquí esos cargos desaparecen de la factura.

---

## Rollback rápido

Si tras Fase 4 o 5 algo falla, volver a las URLs de los add-ons de Heroku:

```bash
# Restaurar DATABASE_URL y REDIS_URL que tenías antes (desde backup de config o historial)
heroku config:set DATABASE_URL="postgres://..." REDIS_URL="redis://..." ...
heroku restart -a $HEROKU_APP
```

No destruyas los add-ons (Fase 6) hasta estar seguro de que Neon + Upstash funcionan bien.

---

## Compatibilidad con el código (GridBot v2.5) – Verificado

| Componente | Archivo | Comportamiento | ¿Listo para Neon/Upstash? |
|------------|---------|----------------|----------------------------|
| Postgres URL | `app/db/session.py` | Convierte `postgres://` → `postgresql://` | Sí. Neon da `postgresql://`. |
| Postgres URL | `app/core/config.py` | Prioriza `DATABASE_URL` del entorno | Sí. |
| Postgres URL | `alembic/env.py` | Usa `DATABASE_URL` y convierte `postgres://` | Sí. |
| Redis URL | `app/core/celery_app.py` | Prioriza `REDIS_URL`; si `rediss://` activa SSL (`ssl.CERT_NONE`) | Sí. Upstash usa `rediss://`. |
| Celery broker/backend | `app/core/celery_app.py` | Misma URL para broker y result backend | Sí. Definir `CELERY_BROKER_URL` y `CELERY_RESULT_BACKEND` igual que `REDIS_URL`. |

**Neon**: La URL debe incluir `?sslmode=require` (Neon la incluye en el connection string por defecto).

**Upstash**: La URL es `rediss://` (SSL). No requiere cambios de código.

Ver también: `env.example` (sección "Producción Heroku con Neon + Upstash") y [CHECKLIST_MIGRATION_HEROKU.md](./CHECKLIST_MIGRATION_HEROKU.md).
