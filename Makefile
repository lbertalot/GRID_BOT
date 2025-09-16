PYTHON?=python3

.PHONY: retention-cleanup retention-dry dry-run

retention-cleanup:
	MONITORING_DIR=monitoring_data REPORTS_DIR=reports $(PYTHON) scripts/retention_cleanup.py --verbose

retention-dry:
	MONITORING_DIR=monitoring_data REPORTS_DIR=reports $(PYTHON) scripts/retention_cleanup.py --dry-run --verbose


# Ejecuta una simulación PAPER para validar filtros/notional sin enviar órdenes
# Uso: make dry-run SYMBOL=BTCUSDT QTY=0.0002 SIDE=BUY TYPE=MARKET
dry-run:
	@SYMBOL=$(SYMBOL); \
	QTY=$(QTY); \
	SIDE?=BUY; \
	TYPE?=MARKET; \
	if [ -z "$$SYMBOL" ] || [ -z "$$QTY" ]; then \
		echo "Uso: make dry-run SYMBOL=BTCUSDT QTY=0.0002 [SIDE=BUY] [TYPE=MARKET]"; \
		exit 1; \
	fi; \
	docker compose exec -T -e PAPER_TRADING=true -e SYMBOL=$$SYMBOL -e QTY=$$QTY -e SIDE=$$SIDE -e TYPE=$$TYPE api python - <<'PY'
from pprint import pprint
import os
symbol = os.getenv('SYMBOL')
qty = float(os.getenv('QTY'))
side = os.getenv('SIDE', 'BUY')
otype = os.getenv('TYPE', 'MARKET')
os.environ['PAPER_TRADING'] = 'true'
from app.services.binance_service import BinanceService
svc = BinanceService()
svc.simulation_mode = True
val = svc.validate_order_parameters(symbol, qty, side=side, order_type=otype)
pprint({'validation': val})
if val.get('is_valid'):
    order = svc.execute_trading_order(symbol, side, otype, val['recommended_quantity'])
    pprint({'order': order})
else:
    print('Validation failed:', val.get('errors'))
PY


# Logging en vivo de Docker hacia logs/dockers.log con rotación simple
.PHONY: logs-tail-start logs-tail-stop

logs-tail-start:
	@mkdir -p logs
	@# Rotación simple si el archivo supera ~10MB
	@if [ -f logs/dockers.log ] && [ $$(wc -c < logs/dockers.log) -gt 10485760 ]; then \
		mv logs/dockers.log logs/dockers.log.1; \
		touch logs/dockers.log; \
		echo "Rotado logs/dockers.log -> logs/dockers.log.1"; \
	fi
	@# Evitar duplicar tails
	@if [ -f logs/.tail_dockers.pid ] && kill -0 $$(cat logs/.tail_dockers.pid) 2>/dev/null; then \
		echo "Tail ya en ejecución (PID $$(cat logs/.tail_dockers.pid))"; \
		exit 0; \
	fi
	@nohup sh -c 'docker compose logs -f --no-color --timestamps >> logs/dockers.log' >/dev/null 2>&1 & echo $$! > logs/.tail_dockers.pid && echo "Tail iniciado (PID $$(cat logs/.tail_dockers.pid))"

logs-tail-stop:
	@# Detener tail si existe
	@if [ -f logs/.tail_dockers.pid ]; then \
		kill $$(cat logs/.tail_dockers.pid) 2>/dev/null || true; \
		rm -f logs/.tail_dockers.pid; \
		echo "Tail detenido"; \
	else \
		echo "No hay tail activo"; \
	fi

