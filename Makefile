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


