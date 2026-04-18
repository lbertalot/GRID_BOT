# Oracle Cloud Free Tier — Proxy para Binance (GridBot)

**Objetivo:** Montar un proxy Squid gratuito con IP estática en EU para que GridBot en Heroku pueda operar en Binance con restricción de IP habilitada.

**Costo:** $0 (Oracle Cloud Always Free Tier — sin límite de tiempo)
**Tiempo estimado:** 10-15 minutos
**Resultado:** `BINANCE_PROXY_URL` configurada en Heroku, spot trading habilitado en Binance.

---

## Resumen del flujo

```
Heroku (GridBot) → Oracle Cloud VM (Squid proxy, IP fija EU) → Binance API
```

- El proxy solo permite tráfico a `*.binance.com` (no sirve como proxy general).
- Autenticación por usuario/contraseña (no se expone al público).
- IP fija → se puede whitelistear en Binance → se puede habilitar spot trading.

---

## Paso 1 — Crear cuenta Oracle Cloud (solo si no tienes)

1. Ve a **https://cloud.oracle.com/** y haz clic en **"Sign Up"**
2. Usa tu email y datos. **Region:** selecciona una en EU (ej: `eu-amsterdam-1`, `eu-frankfurt-1`)
3. Te pedirá tarjeta de crédito para verificación (NO se cobra, es solo validación)
4. Una vez verificado, entras al dashboard de Oracle Cloud

> **Importante:** La región que elijas al crear la cuenta es tu "home region". Elige una en EU.

---

## Paso 2 — Crear la VM (instancia de cómputo)

1. En el dashboard, busca **"Instances"** en el menú de la izquierda (o busca "Compute" en la barra superior)
2. Clic en **"Create Instance"**
3. Configura:

| Campo | Valor |
|-------|-------|
| **Name** | `gridbot-proxy` |
| **Compartment** | Dejar el default |
| **Placement** | Dejar default (tu home region EU) |
| **Image** | **Ubuntu 22.04** (Canonical Ubuntu) — clic en "Change image" si no está seleccionado |
| **Shape** | **VM.Standard.E2.1.Micro** (AMD, 1 OCPU, 1 GB RAM) — **Always Free eligible** |
| **Networking** | Dejar defaults (crea VCN automática). Asegúrate de que "Assign a public IPv4 address" esté **marcado** |
| **SSH keys** | Selecciona **"Generate a key pair"** y **descarga ambas keys** (privada y pública). Guárdalas bien. |

4. **Antes de crear**, despliega **"Show advanced options"** → pestaña **"Management"**
5. En la sección **"Cloud-init script"**, selecciona **"Paste cloud-init script"**
6. Pega el contenido completo del archivo: **`scripts/proxy/cloud-init-proxy.yaml`** de este repo
7. Clic en **"Create"**

> La VM tardará ~2-3 minutos en provisionar. El cloud-init script instalará Squid automáticamente.

---

## Paso 3 — Abrir el puerto 3128 en la Security List de Oracle Cloud

Oracle Cloud bloquea puertos por defecto. Hay que abrir el 3128:

1. Ve a **Networking → Virtual Cloud Networks** (en el menú izquierdo)
2. Clic en la VCN que se creó (nombre tipo `vcn-2024xxxx-xxxx`)
3. Clic en la **subnet** (la pública, tipo `subnet-2024xxxx-xxxx`)
4. Clic en la **Security List** (tipo `Default Security List for vcn-...`)
5. Clic en **"Add Ingress Rules"**
6. Llena:

| Campo | Valor |
|-------|-------|
| Source Type | CIDR |
| Source CIDR | `0.0.0.0/0` |
| IP Protocol | TCP |
| Destination Port Range | `3128` |
| Description | `Squid proxy for GridBot` |

7. Clic en **"Add Ingress Rules"**

---

## Paso 4 — Obtener la IP pública y las credenciales

1. Ve a **Compute → Instances** y clic en `gridbot-proxy`
2. Copia la **Public IP** (ej: `141.148.xx.xx`)
3. Conéctate por SSH para ver las credenciales generadas:

```bash
ssh -i /ruta/a/tu/clave_privada.key ubuntu@<IP_PUBLICA>
```

4. Una vez dentro, lee las credenciales:

```bash
sudo cat /opt/gridbot-proxy/credentials.txt
```

Verás algo como:

```
============================================
 GridBot Proxy — Credenciales
============================================
 Usuario:  gridbot
 Password: aBcDeFgH12345678xYzW
 Puerto:   3128
============================================
```

5. **Anota** el usuario, password e IP pública.

> Si el archivo no existe aún, el cloud-init puede estar ejecutándose todavía. Espera 2-3 minutos y revisa:
> ```bash
> sudo cat /opt/gridbot-proxy/setup.log
> ```

---

## Paso 5 — Verificar que el proxy funciona

Desde tu máquina local (donde tienes el repo de GridBot):

```bash
./scripts/proxy/verify_proxy.sh <IP_PUBLICA> gridbot <PASSWORD>
```

Deberías ver 4 checks en OK. Si algo falla, el script indica qué verificar.

---

## Paso 6 — Lo que hago yo (configurar Heroku y Binance)

Una vez que me des estos 3 datos, yo ejecuto todo lo demás:

1. **IP pública** de la VM
2. **Usuario** del proxy (normalmente `gridbot`)
3. **Password** del proxy

Yo haré:
- `heroku config:set BINANCE_PROXY_URL=http://gridbot:<PASS>@<IP>:3128 -a grid-bot-ia-eu`
- Verificar logs y conectividad
- Indicarte exactamente qué marcar en Binance

---

## Paso 7 — Configurar Binance (te indicaré exactamente)

En **Binance → API Management**:

1. **Restricciones de acceso IP:** Seleccionar **"Restringir el acceso solo para direcciones IP confiables"**
2. Agregar la **IP pública de la VM de Oracle Cloud**
3. Marcar **"Habilitar spot y trading de margen"** (además de "Habilitar lectura")
4. Guardar cambios

---

## Troubleshooting

### El proxy no responde (test 1 falla)
- Verifica que la Security List de Oracle Cloud tenga el puerto 3128 abierto
- Verifica el firewall en la VM: `sudo ufw status` y `sudo iptables -L INPUT -n`
- Verifica que Squid esté corriendo: `sudo systemctl status squid`

### Binance responde 403 via proxy (test 2 falla)
- Verifica credenciales: `sudo cat /opt/gridbot-proxy/credentials.txt`
- Verifica Squid logs: `sudo tail -50 /var/log/squid/access.log`
- Reinicia Squid: `sudo systemctl restart squid`

### Error -2015 en Heroku después de configurar todo
- Verifica que la IP de la VM esté en la whitelist de Binance
- Verifica que "Habilitar spot y trading" esté marcado en Binance
- Verifica en Heroku: `heroku config:get BINANCE_PROXY_URL -a grid-bot-ia-eu`

### Cloud-init no completó
```bash
sudo cat /var/log/cloud-init-output.log | tail -50
# Si falló, ejecutar manualmente:
sudo bash /opt/gridbot-proxy/setup.sh
```

---

## Mantenimiento

- **La VM no requiere mantenimiento** — Oracle Cloud Free Tier no expira
- **Updates de seguridad:** se instalan automáticamente en el cloud-init (`package_upgrade: true`)
- Para updates futuros: `ssh ubuntu@<IP> && sudo apt update && sudo apt upgrade -y`
- **Si la VM se reinicia:** Squid arranca automáticamente (`systemctl enable squid`)
- **Si Oracle cambia la IP** (raro): actualizar whitelist en Binance y `BINANCE_PROXY_URL` en Heroku
