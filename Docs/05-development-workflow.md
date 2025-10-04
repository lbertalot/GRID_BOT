## Flujo de Trabajo de Desarrollo

### Guía de Estilo
- Python 3.11+, funciones puras cuando sea posible; `async def` para I/O.
- Pydantic v2 para validación de entrada/salida; tipado estricto en funciones.
- Patrón RORO (Receive an Object, Return an Object).
- Nombres descriptivos en `snake_case`; evita abreviaturas.
- Validación temprana (guard clauses); evita `else` innecesarios.
- `Decimal` para cantidades y precios.

### Ejecutar Tests
```bash
# Local (contenedor API)
docker compose up -d api
docker exec -it gridbot_api pytest -q

# Host (sin Docker)
python -m pip install -r requirements.txt
pytest --cov=app --cov-report=term-missing
```

### Proceso de Contribución
```bash
git checkout -b feat/nueva-funcionalidad
# Implementa con tests y docs
pytest -q && pytest --cov=app
git commit -m "feat: añade X con métricas y validación"
git push origin feat/nueva-funcionalidad
# Abre Pull Request con checklist:
# - Tests pasan y cobertura ≥ 85%
# - Sin secretos en commits/logs
# - Validación/Decimal en cálculos críticos
# - Métricas Prometheus actualizadas
# - Documentación actualizada
```

### Utilidades
```bash
# Dry-run validado (sin enviar órdenes reales)
make dry-run SYMBOL=BTCUSDT QTY=0.0002 SIDE=BUY TYPE=MARKET

# Logs centralizados
make logs-tail-start
```


