# Runbook: API keys, whitelist de IP y egress estático

**Contexto:** `Docs/PROTOCOL_PASSIVE_INCOME_BOT_V1_ARCHITECTURE.md` §2.4 y §2.4.5.
**Objetivo:** operar el bot sin actualizar manualmente la whitelist cada vez que cambia la IP de salida.

## 1. Principios

1. **Claves con permiso mínimo:** trading spot habilitado; **sin retiro** (`withdraw` deshabilitado) si el exchange lo permite; lista blanca de direcciones de retiro en el panel.
2. **Una IP de salida conocida** por entorno (`staging` / `prod`) cuando la clave tenga restricción por IP (**egress** controlado).
3. **Rotación**: mantener dos claves en periodo de transición; cortar la vieja tras verificar la nueva (ver §6).

## 2. Patrones de despliegue

| Patrón | Descripción breve |
|--------|-------------------|
| NAT con IP elástica | En cloud: todo el tráfico saliente del VPC pasa por una IP pública fija (ej. NAT Gateway + EIP en AWS; Cloud NAT estático en GCP). |
| VPS dedicado | Una VM con IP fija; el worker que firma órdenes corre solo ahí. |
| Ejecutor único | Solo un servicio/contenedor tiene las API keys; el resto de la app puede escalar en otra red. |

**Evitar:** IP dinámica de hogar o contenedores sin control de **egress**.

## 3. Checklist pre-producción

- [ ] Documentar la **IP pública de salida** real (`curl -4 ifconfig.me` desde el mismo host que el worker).
- [ ] Cargar esa IP en la **whitelist** del exchange (o desactivar bind solo en entornos de dev con riesgo aceptado).
- [ ] Verificar que **no** hay secretos en git; usar `.env` o secret manager.
- [ ] Tras rotación de IP de infraestructura: actualizar whitelist **antes** de mover tráfico (automatizar con IaC si es posible).

## 4. GridBot — variables relacionadas

- `BINANCE_API_KEY` / `BINANCE_SECRET_KEY` — nunca en logs.
- `PAPER_TRADING=true` y `TRADING_ENABLED=false` para validar conectividad sin riesgo hasta completar checklist.
- `EMERGENCY_STOP` y flags de integridad: revisar `AGENTS.md` antes de pasar a real.

## 5. Monitoreo mínimo (§2.4.5)

Hasta existir un exporter o job dedicado en el repo, el operador debe:

1. **Registrar periódicamente** la IP vista por el exchange: desde el mismo path de red que el worker, ejecutar `curl -4 ifconfig.me` (o endpoint equivalente) y guardar el resultado en el ticket de cambio o en el CMDB.
2. **Comparar** con la IP documentada en la whitelist. Si difiere, tratar como incidente P0: posible corta de firmas / órdenes rechazadas.
3. **Correlacionar** con alertas de rechazo de API (401/418) en logs de la API o del cliente Binance.

Cuando se implemente automatización, enlazar aquí el nombre de la métrica o el job (prefijo `gridbot_` según `.cursorrules`).

## 6. Cutover dual-key (rotación sin downtime)

1. **Crear segunda clave** en el exchange con los mismos permisos (spot; **sin retiro**); asociarla a la misma **whitelist** / **NAT** egress.
2. **Desplegar en staging** con la clave nueva (`BINANCE_*` en secreto); smoke: health, una lectura de balance en `PAPER_TRADING=true`, luego prueba acotada con `TRADING_ENABLED` según política.
3. **Promover a prod**: actualizar secretos; mantener la clave antigua en fallback interno (no en el mismo proceso activo) durante la ventana acordada.
4. **Verificar** firmas y ausencia de errores de IP por 24–72 h.
5. **Revocar** la clave antigua en el panel del exchange y rotar auditoría (quién tenía acceso al secreto viejo).

## 7. Si cambia la egress (IP de salida)

1. Detener o poner en modo seguro el trading (`TRADING_ENABLED=false`, `EMERGENCY_STOP` si aplica) si la whitelist quedará desalineada.
2. Actualizar **whitelist** en el exchange con la nueva IP **antes** de reanudar órdenes.
3. Re-ejecutar checklist §3 y registrar nueva IP en §5.

## 8. Referencias

- `AGENTS.md` — stack y secretos críticos.
- `Docs/PASSIVE_INCOME_IMPLEMENTATION_INVENTORY_AND_PLAN.md` — fase P0 ops.
- `Docs/PASSIVE_INCOME_EVOLUTION_PHASED_PLAN.md` — contrato de evolución y tests de documentación.
