# Guía de Despliegue de GridBot en Heroku

Esta guía describe paso a paso cómo desplegar GridBot v2.5 en Heroku.

## Prerrequisitos

1. **Cuenta de Heroku**: Crear cuenta en [heroku.com](https://www.heroku.com)
2. **Heroku CLI**: Instalar desde [devcenter.heroku.com/articles/heroku-cli](https://devcenter.heroku.com/articles/heroku-cli)
3. **Git**: Repositorio Git del proyecto
4. **API Keys de Binance**: Credenciales válidas para trading

## Arquitectura en Heroku

GridBot se despliega usando:

- **3 dynos**:
  - `web`: FastAPI API (puerto asignado dinámicamente por Heroku)
  - `worker`: Celery worker para tareas asíncronas
  - `beat`: Celery beat para tareas programadas (trading cycles)

- **2 addons**:
  - PostgreSQL (base de datos)
  - Redis (broker de Celery y cache)

## Paso 1: Instalación de Heroku CLI

### macOS
```bash
brew tap heroku/brew && brew install heroku
```

### Linux
```bash
curl https://cli-assets.heroku.com/install.sh | sh
```

### Windows
Descargar instalador desde [devcenter.heroku.com/articles/heroku-cli](https://devcenter.heroku.com/articles/heroku-cli)

## Paso 2: Login en Heroku

```bash
heroku login
```

Esto abrirá el navegador para autenticarte.

## Paso 3: Crear la Aplicación

```bash
# Desde el directorio raíz del proyecto
heroku create gridbot-production
# o con un nombre personalizado:
heroku create tu-nombre-gridbot
```

Esto creará una aplicación en Heroku y añadirá un remoto Git llamado `heroku`.

## Paso 4: Añadir Addons

### PostgreSQL (Base de datos)

Para producción, se recomienda `essential-1` o superior:

```bash
heroku addons:create heroku-postgresql:essential-1
```

Para desarrollo/pruebas, puedes usar el plan gratuito:

```bash
heroku addons:create heroku-postgresql:essential-0
```

### Redis (Broker y Cache)

Para producción, se recomienda `premium-0` o superior:

```bash
heroku addons:create heroku-redis:premium-0
```

Heroku automáticamente añadirá las variables `DATABASE_URL` y `REDIS_URL` a tu aplicación.

## Paso 5: Configurar Variables de Entorno

### Variables Obligatorias

```bash
# API Keys de Binance
heroku config:set BINANCE_API_KEY=tu_api_key_aqui
heroku config:set BINANCE_SECRET_KEY=tu_secret_key_aqui

# Clave secreta para JWT (generar una segura)
heroku config:set SECRET_KEY=$(openssl rand -hex 32)
```

### Variables Recomendadas para Producción

```bash
heroku config:set TRADING_ENABLED=true
heroku config:set PAPER_TRADING=false
heroku config:set EMERGENCY_STOP=false
heroku config:set ENVIRONMENT=production
heroku config:set LOG_LEVEL=WARNING
heroku config:set DEBUG=false
```

### Variables Opcionales

```bash
# Telegram para alertas
heroku config:set TELEGRAM_BOT_TOKEN=tu_bot_token
heroku config:set TELEGRAM_CHAT_ID=tu_chat_id

# Configuración de rebalanceo
heroku config:set MIN_USDT_BALANCE=15.0
heroku config:set TARGET_USDT_BALANCE=30.0
heroku config:set ENABLE_AUTO_REBALANCE=true
```

### Ver todas las variables configuradas

```bash
heroku config
```

## Paso 6: Desplegar el Código

### Primera vez

```bash
# Asegúrate de estar en la rama main/master
git push heroku main
# o si estás en master:
git push heroku master
```

### Deployments subsecuentes

```bash
git push heroku main
```

El release phase en el `Procfile` ejecutará automáticamente las migraciones de Alembic antes de iniciar la aplicación.

## Paso 7: Escalar Dynos

```bash
heroku ps:scale web=1 worker=1 beat=1
```

Esto iniciará los 3 procesos necesarios:
- `web`: API FastAPI
- `worker`: Celery worker
- `beat`: Celery beat scheduler

## Paso 8: Verificar el Despliegue

### Ver logs en tiempo real

```bash
heroku logs --tail
```

### Verificar estado de dynos

```bash
heroku ps
```

### Probar endpoint de salud

```bash
curl https://tu-app.herokuapp.com/health
```

Deberías recibir:
```json
{"status":"ok","timestamp":"2025-01-XX..."}
```

### Probar endpoints críticos

```bash
# Resumen de breakers
curl https://tu-app.herokuapp.com/breakers/summary

# Estado de integridad
curl https://tu-app.herokuapp.com/integrity/status
```

## Paso 9: Ejecutar Migraciones Manualmente (si es necesario)

Si el release phase falló o necesitas ejecutar migraciones manualmente:

```bash
heroku run alembic upgrade head
```

## Paso 10: Configurar Healthchecks (Opcional)

En el Dashboard de Heroku:
1. Ve a **Settings** → **Health checks**
2. Configura el path: `/health`
3. Selecciona método: `GET`

Heroku verificará automáticamente la salud de tu aplicación.

## Verificación Post-Despliegue

### 1. Verificar Base de Datos

```bash
heroku run python -c "from app.db.session import engine; print('✅ DB conectada')"
```

### 2. Verificar Redis

```bash
heroku run python -c "import redis; r=redis.from_url('$REDIS_URL'); print('✅ Redis conectado' if r.ping() else '❌ Redis falló')"
```

### 3. Verificar Celery Worker

Revisar logs:
```bash
heroku logs --tail --dyno worker
```

Deberías ver mensajes como:
```
[tasks]
  . app.services.trading_tasks.trading_cycle_tick
```

### 4. Verificar Celery Beat

Revisar logs:
```bash
heroku logs --tail --dyno beat
```

Deberías ver mensajes de scheduling:
```
beat: Starting...
DatabaseScheduler: Schedule changed.
```

### 5. Verificar Trading Cycle

Revisar logs del worker para ver si los trading cycles se ejecutan:
```bash
heroku logs --tail --dyno worker | grep "trading_cycle"
```

## Comandos Útiles

### Ver logs de un dyno específico

```bash
heroku logs --tail --dyno web
heroku logs --tail --dyno worker
heroku logs --tail --dyno beat
```

### Reiniciar todos los dynos

```bash
heroku restart
```

### Reiniciar un dyno específico

```bash
heroku restart web
heroku restart worker
heroku restart beat
```

### Acceder a la consola de Heroku

```bash
heroku run bash
```

### Ver métricas de uso de recursos

```bash
heroku ps:exec
```

### Ver información de la base de datos

```bash
heroku pg:info
```

### Ver información de Redis

```bash
heroku redis:info
```

## Monitoreo y Observabilidad

### Heroku Metrics (Built-in)

Heroku proporciona métricas básicas:
- CPU usage
- Memory usage
- Request rate
- Response time

Acceder desde el Dashboard → Metrics.

### Logs Aggregation

```bash
# Descargar logs recientes
heroku logs --num 1500 > logs.txt

# Filtrar errores
heroku logs --tail | grep ERROR
```

### External Monitoring (Recomendado)

Para métricas avanzadas, considera:
- **Datadog**: Addon de Heroku, ~$31/mes
- **New Relic**: Addon de Heroku, plan gratuito disponible
- **Sentry**: Para error tracking

## Troubleshooting

### Error: "No web processes running"

```bash
heroku ps:scale web=1
```

### Error: "Database connection failed"

Verificar que el addon PostgreSQL esté activo:
```bash
heroku addons:info heroku-postgresql
```

### Error: "Redis connection failed"

Verificar que el addon Redis esté activo:
```bash
heroku addons:info heroku-redis
```

### Error: "Migration failed"

Ejecutar migraciones manualmente:
```bash
heroku run alembic upgrade head
```

### Dynos se duermen (Sleep Mode)

Los dynos gratuitos se duermen después de 30 minutos de inactividad. Para producción, usar dynos pagos:

```bash
heroku ps:type standard-1x
```

### Memory Limit Exceeded

Si ves errores de memoria:

1. Monitorear uso:
```bash
heroku logs --tail | grep "Memory"
```

2. Escalar a dyno más grande:
```bash
heroku ps:resize web=standard-2x
```

3. Optimizar workers:
   - Reducir `--workers` en Procfile web
   - Reducir `--concurrency` en Procfile worker

## Costos Estimados

### Plan Mínimo (Desarrollo/Pruebas)
- Dynos: ~$7/mes (3 basic dynos)
- PostgreSQL essential-0: Gratis
- Redis premium-0: ~$15/mes
- **Total: ~$22/mes**

### Plan Producción Recomendado
- Dynos: ~$25/mes (3 standard-1x dynos)
- PostgreSQL essential-1: ~$9/mes
- Redis premium-0: ~$15/mes
- **Total: ~$49/mes**

### Plan Producción Escalado
- Dynos: ~$50/mes (3 standard-2x dynos)
- PostgreSQL standard-0: ~$50/mes
- Redis premium-3: ~$60/mes
- **Total: ~$160/mes**

## Consideraciones Importantes

### Filesystem Efímero

Heroku tiene un filesystem de solo lectura excepto `/tmp`. Los directorios `monitoring_data` y `reports` se redirigen automáticamente a `/tmp` usando `app/core/paths.py`.

**⚠️ Importante**: Los datos en `/tmp` se pierden cuando el dyno se reinicia. Para persistencia, usar:
- Base de datos (PostgreSQL)
- Servicios externos (S3, Google Cloud Storage)
- Redis para cache temporal

### WebSockets

Heroku soporta WebSockets, pero pueden requerir configuración adicional para producción.

### SSL/TLS

Heroku proporciona SSL automático en dominios `.herokuapp.com`. Para dominios personalizados, configurar SSL en Settings → Domains.

### Backup de Base de Datos

Configurar backups automáticos:

```bash
heroku pg:backups:schedule DATABASE_URL --at '02:00 UTC'
```

## Despliegue Automático con GitHub

1. En Heroku Dashboard → Deploy → GitHub
2. Conectar repositorio
3. Habilitar "Wait for CI to pass before deploy"
4. Habilitar "Enable Automatic Deploys"

Ahora cada push a `main` desplegará automáticamente.

## Rollback

Si necesitas revertir a una versión anterior:

```bash
# Ver releases
heroku releases

# Rollback a release anterior
heroku rollback vXX
```

## Siguientes Pasos

1. Configurar monitoreo avanzado (Datadog, New Relic)
2. Configurar alertas de Telegram
3. Configurar backups automáticos de PostgreSQL
4. Implementar CI/CD pipeline completo
5. Configurar staging environment separado

## Soporte

Para problemas o preguntas:
- Revisar logs: `heroku logs --tail`
- Documentación Heroku: [devcenter.heroku.com](https://devcenter.heroku.com)
- Documentación GridBot: Ver `README.md` y `AGENTS.md`
