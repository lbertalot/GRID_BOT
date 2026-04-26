# Checklist de Configuración para Heroku

## ✅ Pasos Previos

### 1. Autenticación en Heroku
```bash
heroku login
```

### 2. Información del Pipeline
- Pipeline ID: `afd9fd09-5489-42a8-b256-8611d5cee54a`
- URL: https://dashboard.heroku.com/pipelines/afd9fd09-5489-42a8-b256-8611d5cee54a

### 3. Apps en el Pipeline
Ejecuta para ver las apps:
```bash
heroku pipelines:apps afd9fd09-5489-42a8-b256-8611d5cee54a
```

## 📋 Información Necesaria

Completa la siguiente información para el despliegue:

### A. Nombre de la App de Producción
- [ ] Nombre de la app: `___________________`

### B. Credenciales de Binance (OBLIGATORIAS)
- [ ] BINANCE_API_KEY: `___________________`
- [ ] BINANCE_SECRET_KEY: `___________________`

### C. Configuración de Trading
- [ ] TRADING_ENABLED: `true` / `false` (por defecto: `true`)
- [ ] PAPER_TRADING: `true` / `false` (por defecto: `false` para producción)
- [ ] EMERGENCY_STOP: `true` / `false` (por defecto: `false`)

### D. Telegram (Opcional)
- [ ] TELEGRAM_BOT_TOKEN: `___________________` (opcional)
- [ ] TELEGRAM_CHAT_ID: `___________________` (opcional)

### E. Addons
Verifica si ya existen o indica qué planes quieres:
- [ ] PostgreSQL: Plan actual: `___________________`
  - Opciones: `essential-0` (gratis), `essential-1` (~$9/mes), `standard-0` (~$50/mes)
- [ ] Redis: Plan actual: `___________________`
  - Opciones: `premium-0` (~$15/mes), `premium-3` (~$60/mes)

### F. Otras Variables de Entorno
- [ ] ENVIRONMENT: `production` (por defecto)
- [ ] LOG_LEVEL: `WARNING` (por defecto)
- [ ] DEBUG: `false` (por defecto)

## 🔧 Comandos para Ejecutar

Una vez tengas la información, ejecuta estos comandos o proporciona la información y yo los ejecutaré:

### 1. Verificar apps del pipeline
```bash
heroku pipelines:apps afd9fd09-5489-42a8-b256-8611d5cee54a
```

### 2. Si necesitas crear la app (si no existe)
```bash
# Reemplaza APP_NAME con el nombre deseado
heroku apps:create APP_NAME --region us
heroku pipelines:add afd9fd09-5489-42a8-b256-8611d5cee54a --app APP_NAME --stage production
```

### 3. Añadir addons (si no existen)
```bash
# PostgreSQL
heroku addons:create heroku-postgresql:essential-1 --app APP_NAME

# Redis
heroku addons:create heroku-redis:premium-0 --app APP_NAME
```

### 4. Configurar variables de entorno
```bash
heroku config:set BINANCE_API_KEY=tu_key --app APP_NAME
heroku config:set BINANCE_SECRET_KEY=tu_secret --app APP_NAME
heroku config:set SECRET_KEY=$(openssl rand -hex 32) --app APP_NAME
heroku config:set TRADING_ENABLED=true --app APP_NAME
heroku config:set PAPER_TRADING=false --app APP_NAME
heroku config:set EMERGENCY_STOP=false --app APP_NAME
heroku config:set ENVIRONMENT=production --app APP_NAME
heroku config:set LOG_LEVEL=WARNING --app APP_NAME
heroku config:set DEBUG=false --app APP_NAME
```

### 5. Configurar Git remote (si no existe)
```bash
heroku git:remote -a APP_NAME
```

### 6. Escalar dynos
```bash
heroku ps:scale web=1 worker=1 beat=1 --app APP_NAME
```

## ⚠️ Notas Importantes

1. **Seguridad**: Nunca compartas tus API keys públicamente
2. **Costos**: Los addons y dynos tienen costos mensuales
3. **Backups**: Configura backups automáticos para PostgreSQL
4. **Monitoreo**: Revisa los logs regularmente: `heroku logs --tail --app APP_NAME`
