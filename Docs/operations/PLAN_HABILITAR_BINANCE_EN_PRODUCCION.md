# Plan: Habilitar Binance en producción (Heroku) de forma ininterrumpida

**Objetivo:** Que la app en Heroku pueda usar la API y el User Data Stream de Binance de forma estable, cumpliendo con la documentación de Binance (restricciones por ubicación/IP) y las prácticas de Heroku (configuración, add-ons, dev/prod parity).

**Referencias:**
- [Binance API – IP whitelist / restricciones](https://dev.binance.vision/t/whitelisting-ip-address/15369)
- [Heroku – QuotaGuard Shield Static IPs](https://devcenter.heroku.com/articles/quotaguardshield)
- [Heroku – Development configuration / dev-prod parity](https://devcenter.heroku.com/articles/development-configuration)
- [Análisis de logs](PAPERTRAIL_ANALYSIS_AND_ACTION_PLAN.md) (error 451 / ubicación restringida)

---

## 1. Contexto del problema

| Fuente | Hecho |
|--------|--------|
| **Binance** | Devuelve **451** (“Service unavailable from a restricted location”) cuando la petición sale desde regiones/IPs no elegibles (p. ej. ciertos datacenters o países). Permite **whitelist de IP** en la API key (hasta 30 IPs). |
| **Heroku** | Los dynos usan IPs salientes compartidas y en la región del stack (p. ej. US). Esas IPs suelen estar bloqueadas por Binance. Heroku no ofrece IP estática nativa. |
| **Dev/prod parity** | Usar el mismo stack (Postgres, Redis, código) en dev y prod reduce sorpresas; la única diferencia aceptable es el **proxy de salida** en prod para Binance. |

Para que producción quede funcionando de forma ininterrumpida hace falta:

1. **IP de salida fija** en una región permitida por Binance (p. ej. UE).
2. **Enrutar solo el tráfico a Binance** por esa IP (proxy).
3. **Registrar esa IP** en la API key de Binance (whitelist).
4. **Mantener** el resto del diseño (build → release → run, Procfile, add-ons, logging) según Heroku.

---

## 2. Enfoque recomendado: Heroku en Europa + QuotaGuard Shield + proxy en código

Resumen:

- **Heroku en región Europa** (p. ej. `eu-west-1`), para que el add-on de IP estática también use IPs en UE (permitidas por Binance).
- **Add-on QuotaGuard Shield** para obtener 2 IPs estáticas de salida y `QUOTAGUARDSHIELD_URL` (HTTPS proxy).
- **Uso explícito del proxy** solo en clientes que hablan con Binance (REST y, si aplica, WebSocket), sin tocar Redis, Postgres ni otros servicios.
- **Whitelist en Binance** de las 2 IPs que asigna QuotaGuard.

Ventajas: compatible con la documentación de Binance (IP whitelist), con Heroku (add-on oficial, build/release/run), y con dev/prod parity (mismo código; en prod se activa proxy vía env).

---

## 3. Fases del plan

### Fase 1 – Preparación (sin cortes)

| Paso | Acción | Responsable | Verificación |
|------|--------|-------------|---------------|
| 1.1 | Confirmar región actual de la app: `heroku regions -a grid-bot-ia` (o en Dashboard). Si está en US, anotar que habrá que crear/migrar a EU. | Ops | Región anotada |
| 1.2 | Crear app en Europa **o** usar la existente si ya está en EU. Si se crea nueva: `heroku create grid-bot-ia-eu --region eu-west-1` (o migrar según [Heroku regions](https://devcenter.heroku.com/articles/regions)). | Ops | App en `eu-west-1` (o región EU elegida) |
| 1.3 | Contratar **QuotaGuard Shield** en esa app EU: `heroku addons:create quotaguardshield:starter -a grid-bot-ia` (o el plan que corresponda). Anotar las 2 IPs estáticas que devuelve el add-on. | Ops | `QUOTAGUARDSHIELD_URL` configurado; IPs anotadas |
| 1.4 | En Binance (API Key): activar **Restrict access to trusted IPs only** y añadir las **2 IPs** de QuotaGuard. Guardar cambios. | Ops | Whitelist con 2 IPs |
| 1.5 | Documentar en `env.example` y en este doc: `QUOTAGUARDSHIELD_URL` (solo prod; no commitear valor real). Opcional: `BINANCE_USE_PROXY=true` para activar proxy solo cuando exista la URL. | Dev | Variables documentadas |

**Criterio de éxito Fase 1:** Tienes app en EU con QuotaGuard, IPs whitelisted en Binance, y variables documentadas. La app actual puede seguir en la región actual hasta la Fase 3.

---

### Fase 2 – Cambios en el código (compatible con prod y dev)

Objetivo: que todos los clientes que llaman a Binance (REST y User Data Stream) usen el proxy cuando `QUOTAGUARDSHIELD_URL` esté definido.

| Paso | Acción | Archivos / detalle |
|------|--------|--------------------|
| 2.1 | **Proxy helper:** Crear en `app/core/` (p. ej. `binance_proxy.py`) una función que devuelva `proxies = {"http": url, "https": url}` si existe `QUOTAGUARDSHIELD_URL`, si no `None`. Usar solo para tráfico a Binance. | `app/core/binance_proxy.py` (nuevo) |
| 2.2 | **Cliente REST (python-binance):** Pasar proxy al `Client`. La librería acepta `requests_params={"proxies": proxies}` en las llamadas, o un `requests.Session` con proxy. Centralizar en el Singleton: al crear `Client(api_key, api_secret, testnet=...)` usar un `requests.Session` con proxy (si hay `QUOTAGUARDSHIELD_URL`) y pasarlo vía el mecanismo que exponga python-binance (p. ej. sesión inyectada o `requests_params` por defecto). Revisar [python-binance](https://github.com/sammchardy/python-binance) para la firma exacta (session/proxy). | `app/services/binance_client_singleton.py` |
| 2.3 | **Otros usos de `Client`:** Misma lógica de proxy en los puntos donde se instancia `Client` (binance_service, trade_executor, api/trade, etc.): usar el helper de proxy y pasarlo al cliente. Idealmente un único punto de creación (p. ej. Singleton) y el resto usar ese cliente. | Varios; priorizar Singleton y rutas críticas |
| 2.4 | **User Data Stream (aiohttp):** En `binance_user_stream.py`, al crear `aiohttp.ClientSession` y al hacer `session.post(...)` / `session.ws_connect(...)` pasar proxy si existe `QUOTAGUARDSHIELD_URL`. aiohttp acepta `trust_env=True` (lee `HTTPS_PROXY`) o parámetro `proxy` en las peticiones. Configurar `HTTPS_PROXY` solo para el proceso que use Binance, o pasar `proxy` explícitamente en cada request/ws_connect. | `app/services/binance_user_stream.py` |
| 2.5 | **`requests.get` directo a Binance:** En `trade_executor.py` (y cualquier otro que llame a `api.binance.com`), usar el mismo helper de proxy y pasarlo en `requests.get(..., proxies=...)`. | `app/services/trade_executor.py` |
| 2.6 | **Tests:** Añadir tests unitarios que mockeen `QUOTAGUARDSHIELD_URL` y comprueben que se construye el proxy y que se pasa al cliente/session. No hacer llamadas reales a Binance. | `tests/` |
| 2.7 | **No usar proxy para:** Redis, Postgres, Telegram, Prometheus, Papertrail ni otros servicios. Solo tráfico a dominios Binance (`api.binance.com`, `stream.binance.com`, etc.). | Revisión de código |

**Criterio de éxito Fase 2:** En local con `QUOTAGUARDSHIELD_URL` vacío no se usa proxy; con `QUOTAGUARDSHIELD_URL` definido (ej. en .env de prueba) los clientes Binance usan ese proxy. Tests en verde.

---

### Fase 3 – Despliegue en producción (ventana mínima)

| Paso | Acción | Rollback si falla |
|------|--------|-------------------|
| 3.1 | Si la app actual está en US y decidiste usar una app nueva en EU: configurar la app EU con el mismo código (git remote), add-ons (Postgres, Redis, Papertrail) y variables de entorno (excepto las de Binance que ya tienen whitelist para las IPs EU). Replicar `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `LOG_LEVEL`, etc. | Volver a usar la app US |
| 3.2 | En la app de producción (sea la actual en EU o la nueva): `heroku config:set QUOTAGUARDSHIELD_URL=$(heroku config:get QUOTAGUARDSHIELD_URL -a <app>)` (ya viene del add-on). Opcional: `BINANCE_USE_PROXY=true`. | Quitar `BINANCE_USE_PROXY` y/o no usar proxy en código si no está la URL |
| 3.3 | Desplegar la versión que incluye los cambios de Fase 2: `git push heroku main` (o el flujo que uses). | `heroku releases:rollback` |
| 3.4 | Tras el deploy: comprobar `/health`, luego un endpoint que use Binance (p. ej. balances o tiempo de servidor). Revisar logs (Papertrail): no debe aparecer 451 ni “restricted location”. | Revisar logs y rollback si 451 |
| 3.5 | Comprobar User Data Stream (si lo usas): que no aparezca error -2015 por IP. | Igual |
| 3.6 | Dejar correr 24–48 h y revisar métricas (breakers, órdenes, reconciliación). | Rollback y análisis |

**Criterio de éxito Fase 3:** Producción responde bien, sin 451 ni -2015, y el circuito de integridad no se activa por Binance.

---

### Fase 4 – Operación continua (evitar interrupciones)

| Paso | Acción | Frecuencia |
|------|--------|------------|
| 4.1 | **Monitoreo:** Alertas en Papertrail (o tu canal) para “451”, “restricted location”, “binance_net_fail”. Revisar dashboard de QuotaGuard (uso, límites). | Continuo |
| 4.2 | **Rotación de IP/credenciales Binance:** Si Binance o QuotaGuard cambian IPs o políticas, actualizar whitelist en Binance y, si aplica, variables en Heroku. Documentar en runbook. | Según necesidad |
| 4.3 | **Dev/prod parity:** En local, no definir `QUOTAGUARDSHIELD_URL` (o usar un proxy de prueba solo para desarrollo). En prod, no quitar el add-on sin tener alternativa (otra región/proxy). | En cada cambio de entorno |
| 4.4 | **Backup de configuración:** Mantener documentadas las 2 IPs de QuotaGuard y el procedimiento para volver a whitelistear en Binance en caso de recrear la app o el add-on. | Una vez y al cambiar |

---

## 4. Alternativas consideradas

| Alternativa | Pros | Contras |
|-------------|------|--------|
| **Solo migrar Heroku a EU (sin proxy)** | Menos componentes | Las IPs de dynos en EU pueden seguir siendo dinámicas o no aceptadas por Binance; no hay IP whitelist posible. |
| **Proxy para todo el tráfico (QGPass en Procfile)** | Poco cambio en código | Redis, Postgres, etc. pasarían por el proxy; latencia y posible incompatibilidad. No recomendado. |
| **VPS fuera de Heroku para el bot** | Control total de IP/región | Más mantenimiento, menos alineado con “todo en Heroku” y con la doc de Heroku que estás siguiendo. |
| **Binance US API** | Permitida en US | Otro producto (Binance.US), límites y pares distintos; no sustituye a Binance global. |

Por eso el plan se centra en **Heroku EU + QuotaGuard Shield + proxy solo para Binance**.

---

## 5. Checklist resumido

- [ ] Fase 1: App en región EU (o decidir quedarse en US y contactar QuotaGuard para IPs en EU).
- [x] Fase 1: Add-on QuotaGuard Shield instalado; 2 IPs anotadas (3.222.129.4, 54.205.35.75 — US).
- [x] Fase 1: Esas 2 IPs en whitelist de la API key de Binance.
- [x] Fase 2: Helper de proxy y uso en Singleton, binance_user_stream y trade_executor.
- [ ] Fase 2: Tests que verifiquen uso de proxy cuando la env está definida.
- [x] Fase 3: `QUOTAGUARDSHIELD_URL` configurado en prod (add-on).
- [ ] Fase 3: Deploy y comprobación sin 451 ni -2015.
- [ ] Fase 4: Alertas y runbook para rotación de IPs/credenciales.

---

## 5.1 Estado tras implementación (feb 2026)

- **Hecho:** QuotaGuard Shield en app actual (grid-bot-ia, región **us**). Código de proxy desplegado; en logs aparece `QUOTAGUARDSHIELD_URL presente en env: True` y `Proxy QuotaGuard Shield activo para Binance`.
- **Problema:** Sigue apareciendo **451** ("Service unavailable from a restricted location"). Binance bloquea por **región/datacenter**: las IPs de QuotaGuard en US (3.222.129.4, 54.205.35.75) están en zona restringida aunque estén en la whitelist.
- **Próximo paso obligatorio:** Crear app Heroku en **EU** (Fase 1.2), instalar QuotaGuard en esa app para obtener **IPs europeas**, whitelistear esas IPs en Binance y desplegar el mismo código allí (o migrar la app actual a EU si Heroku lo permite).

### 5.2 App EU creada (feb 2026)

- **App:** `grid-bot-ia-eu` (región **eu**), URL: https://YOUR-APP-NAME.herokuapp.com/
- **Add-ons:** QuotaGuard Shield (IPs EU), Papertrail. Misma base de datos y Redis que la app US (misma `DATABASE_URL` y `REDIS_URL`).
- **IPs estáticas EU para whitelist en Binance:**
  - **3.251.32.127**
  - **54.195.145.1**
- **Deploy:** `git push heroku-eu main`. Dynos: web=1, worker=1 (límite 2 Eco dynos; beat=0).
- Tras añadir las 2 IPs EU en Binance, los errores -2015 deberían desaparecer; no hay 451 en región EU.

### 5.3 Verificación exitosa (feb 2026)

- **IPs EU whitelisteadas en Binance:** verificado por el usuario.
- **Ajuste adicional:** `CommissionManager` creaba su propio `Client` sin proxy; se actualizó para usar `get_binance_proxies()` y `requests_params` (commit: fix CommissionManager usa proxy QuotaGuard).
- **Logs app EU (tras deploy y restart):** no aparecen **451** ni **-2015**; proxy QuotaGuard activo en web y worker. **Plan cumplido.**

### 5.4 Eliminación de QuotaGuard Shield (feb 2026)

- **Problema:** QuotaGuard Shield Starter (free) suspendido por exceso de límite (250 requests).
  Un bot de trading con ciclos cada 60 s excede esa cuota rápidamente.
- **Diagnóstico:** Se verificó que desde Heroku EU el tráfico a `api.binance.com` llega sin error 451
  (endpoint público `/api/v3/ping` → 200 OK directo, sin proxy).
- **Acción:**
  1. Se eliminó el add-on QuotaGuard Shield y se borró `QUOTAGUARDSHIELD_URL` de config vars.
  2. Se desactivó "Restrict access to trusted IPs only" en la API Key de Binance
     (la key solo tiene permisos de spot trading, sin withdrawal ni transfer).
  3. Se actualizó `app/core/binance_proxy.py` para soportar `BINANCE_PROXY_URL` como alternativa genérica
     y loguear claramente cuando se opera sin proxy.
- **Resultado:** La app opera con conexión directa a Binance desde EU, sin costo de proxy,
  sin límite de requests. El proxy queda como opción configurable si el hosting cambia de región.

---

## 6. Referencia rápida Binance / Heroku

- **Binance:** Hasta 30 IPs por API key; restricción por ubicación (451); error -2015 en WS si la IP no está autorizada.
- **Heroku EU:** Los dynos en `eu-west-1` pueden conectar directamente a `api.binance.com` sin 451.
  Las IPs son dinámicas, por lo que se requiere API key **sin restricción de IP** (spot-only, sin withdrawal).
- **Proxy (opcional):** Si se necesita IP fija, definir `BINANCE_PROXY_URL` (o `QUOTAGUARDSHIELD_URL` legacy).
  El código de `app/core/binance_proxy.py` lo usará automáticamente.

Con esto, producción funciona de forma ininterrumpida con Binance desde Heroku EU, sin dependencia de proxy de pago.
