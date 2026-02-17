# GridBot v2.5 — Invariantes del Sistema

## Propósito
Este documento define las **invariantes** que NUNCA deben violarse durante la ejecución de GridBot v2.5.
Toda modificación de código debe verificar que no rompe ninguna de estas invariantes.

---

## INV-001: Precisión Monetaria — Solo Decimal para Dinero

**Descripción:** Todo cálculo que involucre precios, cantidades, balances, comisiones, notional o PnL DEBE usar `decimal.Decimal`.

**Prohibido:**
- `float` en precios, cantidades, balances, comisiones, notional, PnL.
- Operaciones aritméticas entre `float` y valores monetarios.
- `round()` de Python sobre valores monetarios (usar `Decimal.quantize()`).

**Permitido:**
- `float` SOLO en métricas Prometheus (`.set(float(...))`) y logs no financieros.
- Conversión a `float` SOLO al serializar JSON de respuesta API (punto final de salida).

**Verificación:**
```python
# Correcto
price = Decimal(str(raw_price))
qty = qty.quantize(Decimal(step_size), rounding=ROUND_DOWN)

# Incorrecto
price = float(raw_price)
qty = round(qty, precision)
```

---

## INV-002: Validación de Filtros Pre-Orden

**Descripción:** Toda orden enviada al exchange DEBE pasar por validación de filtros ANTES del envío.

**Filtros obligatorios:**
1. **PRICE_FILTER:** precio ajustado a `tickSize`, dentro de `[minPrice, maxPrice]`.
2. **LOT_SIZE:** cantidad ajustada a `stepSize`, dentro de `[minQty, maxQty]`.
3. **MIN_NOTIONAL:** `price * quantity >= minNotional` (verificar DESPUÉS de redondeo).

**Regla:** Si la validación falla, la orden NO se envía. Se registra el rechazo con métrica Prometheus.

---

## INV-003: Circuit Breakers Consultados Antes de Operar

**Descripción:** Toda operación de trading (BUY/SELL) DEBE consultar el estado de los circuit breakers antes de ejecutarse.

**Regla:**
- Si `CircuitBreakers.is_trading_halted()` retorna `True`, la operación se bloquea.
- El bloqueo se registra con métrica y log.
- NUNCA se envía una orden al exchange con breakers activos.

---

## INV-004: Idempotencia de Órdenes

**Descripción:** Toda orden enviada al exchange DEBE incluir un `newClientOrderId` determinístico.

**Regla:**
- El `clientOrderId` se genera como hash determinístico de `(symbol, side, quantity, price, timestamp_bucket)`.
- Prefijo: `GRIDBOT_`.
- Máximo 36 caracteres (límite de Binance).
- Si se reintenta una orden, se usa el MISMO `clientOrderId`.

---

## INV-005: Reconciliación Activa ≤ 60s

**Descripción:** El sistema DEBE reconciliar su estado interno contra el exchange al menos cada 60 segundos.

**Regla:**
- La reconciliación compara balances internos vs balances del exchange.
- Si la discrepancia supera el umbral configurable (default 1%), se activa el breaker `balance_discrepancy`.
- Si la discrepancia supera el umbral crítico (default 5%), se activa el modo crítico.
- La latencia de reconciliación se registra en `reconciliation_latency_seconds`.

---

## INV-006: Equity Nunca Inconsistente

**Descripción:** El equity calculado internamente NUNCA debe divergir del equity real del exchange más allá del umbral configurable.

**Regla:**
- `|equity_interno - equity_exchange| / equity_exchange <= threshold_pct`.
- Si se viola, activar breaker y registrar discrepancia.

---

## INV-007: ML No Controla Sizing Directamente

**Descripción:** El módulo ML puede recomendar regímenes y estrategias, pero NUNCA determina directamente el tamaño de posición.

**Regla:**
- ML emite `RegimePrediction` con `confidence`.
- `StrategySelector` convierte predicción en `StrategySpec`.
- `RiskManager.calculate_dynamic_position_size()` calcula el tamaño final.
- Si `confidence < min_kelly_confidence`, se usa fallback determinista.

---

## INV-008: Confirmación Post-Orden

**Descripción:** Después de enviar una orden al exchange, SIEMPRE se debe confirmar el estado real de la orden.

**Regla:**
- Verificar `order_result['status']` tras cada envío.
- Si `status` no es `FILLED` ni `PARTIALLY_FILLED`, registrar como pendiente y reconciliar.
- NUNCA asumir que una orden se ejecutó correctamente sin confirmación.

---

## INV-009: Separación de Responsabilidades

**Descripción:** La lógica de riesgo NUNCA se mezcla con la lógica de ejecución.

**Regla:**
- `RiskManager` evalúa riesgo y calcula sizing.
- `TradeExecutor` ejecuta órdenes validadas.
- `OrderValidator` valida filtros del exchange.
- `ReconciliationService` reconcilia estado.
- `CircuitBreakers` controla el estado de operación.

---

## INV-010: Sin Dependencias Circulares

**Descripción:** El grafo de dependencias entre módulos DEBE ser acíclico.

**Regla:**
- `services/` puede importar de `core/` pero NO al revés.
- `api/` puede importar de `services/` y `core/`.
- `core/` NO importa de `services/` ni de `api/`.
- Excepciones: lazy imports explícitos y documentados.

---

## INV-011: Balance Check Pre-Orden

**Descripción:** Antes de enviar una orden BUY, se DEBE verificar que el balance disponible sea suficiente.

**Regla:**
- Para BUY: `available_quote_balance >= price * quantity + estimated_commission`.
- Para SELL: `available_base_balance >= quantity`.
- Si no se cumple, la orden se rechaza ANTES de enviarla al exchange.

---

## INV-012: Manejo de Partial Fills

**Descripción:** Las órdenes parcialmente ejecutadas DEBEN manejarse explícitamente.

**Regla:**
- Registrar la cantidad ejecutada y la cantidad restante.
- Actualizar balances internos solo por la cantidad ejecutada.
- Crear operación de seguimiento para la cantidad restante si aplica.
- Incrementar métrica `partial_fills_total`.

---

## Verificación de Invariantes

Cada PR debe incluir en su checklist:
- [ ] No introduce `float` en cálculos monetarios (INV-001)
- [ ] Valida filtros del exchange antes de enviar órdenes (INV-002)
- [ ] Consulta circuit breakers antes de operar (INV-003)
- [ ] Usa `clientOrderId` determinístico (INV-004)
- [ ] No rompe reconciliación (INV-005)
- [ ] Confirma estado post-orden (INV-008)
- [ ] Separa riesgo de ejecución (INV-009)
- [ ] No introduce dependencias circulares (INV-010)
