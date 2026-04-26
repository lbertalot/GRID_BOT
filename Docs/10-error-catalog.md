## Catálogo de Errores

### HTTP (API)
| Código | Contexto | Causa probable | Acción |
|---|---|---|---|
| 400 | Validación de orden | Filtros Binance/precisión/balance | Revisar request y filtros de símbolo |
| 401 | Autenticación | API key inválida/ausente | Revisar header/secretos |
| 503 | Componentes no inicializados | Servicios base no listos | Verificar health de DB/Redis |

### Binance API
| Código | Descripción | Causa | Remediación |
|---|---|---|---|
| -1021 | Timestamp out of sync | TZ no UTC/sincronización | Forzar `TZ=UTC`, verificar hora contenedor |
| -1013 | Filter failure LOT_SIZE | Cantidad inválida | Ajustar a `step_size` y `minQty` |
| -1111 | Precision overflow | Decimales excedidos | Redondear según filtros de `exchange_info` |
