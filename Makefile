PYTHON?=python3

.PHONY: retention-cleanup retention-dry dry-run ops-watch-once ops-watch-test ops-pipeline-audit cert-paper-quick cert-paper-full

retention-cleanup:
	MONITORING_DIR=monitoring_data REPORTS_DIR=reports $(PYTHON) scripts/retention_cleanup.py --verbose

retention-dry:
	MONITORING_DIR=monitoring_data REPORTS_DIR=reports $(PYTHON) scripts/retention_cleanup.py --dry-run --verbose


# Ejecuta una simulación PAPER para validar filtros/notional sin enviar órdenes
# Uso: make dry-run SYMBOL=BTCUSDT QTY=0.0002 [SIDE=BUY] [TYPE=MARKET]
SIDE?=BUY
TYPE?=MARKET
dry-run:
	@if [ -z "$(SYMBOL)" ] || [ -z "$(QTY)" ]; then \
		echo "Uso: make dry-run SYMBOL=BTCUSDT QTY=0.0002 [SIDE=BUY] [TYPE=MARKET]"; \
		exit 1; \
	fi
	docker compose exec -T \
		-w /app \
		-e PAPER_TRADING=true \
		-e SYMBOL=$(SYMBOL) \
		-e QTY=$(QTY) \
		-e SIDE=$(SIDE) \
		-e TYPE=$(TYPE) \
		api python -m scripts.dry_run_order


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

# Un ciclo: logs Docker Compose + heurísticas -> reports/ops_watch/
ops-watch-once:
	@$(PYTHON) scripts/ops_watch/run_once.py

# Heurísticas ops_watch sin cargar conftest del monolito de tests
ops-watch-test:
	@$(PYTHON) -m pytest tests/test_ops_watch_heuristics.py -q --noconftest

# Auditoría E2E de pipeline de datos (API -> servicios -> PostgreSQL)
ops-pipeline-audit:
	@$(PYTHON) scripts/ops_watch/audit_data_pipeline.py

# Certificación paper local rápida (runbook express)
# Ejecuta checks básicos y guarda evidencia mínima en reports/certificacion_paper/
cert-paper-quick:
	@set -e; \
	echo "== [1/10] Validando override paper en compose =="; \
	docker compose -f docker-compose.local.yml config | grep -E "PAPER_TRADING|FORCE_REAL_MODE|TRADING_ENABLED"; \
	echo "== [2/10] Levantando stack =="; \
	docker compose -f docker-compose.local.yml up --build -d; \
	echo "== [3/10] Estado de contenedores =="; \
	docker compose -f docker-compose.local.yml ps; \
	echo "== [4/10] Health API =="; \
	ok=0; \
	for i in $$(seq 1 30); do \
		if curl -sf http://localhost:8000/health >/dev/null; then ok=1; break; fi; \
		sleep 3; \
	done; \
	if [ $$ok -ne 1 ]; then echo "❌ API /health no respondió en 90s"; exit 56; fi; \
	echo "== [5/10] Celery worker ping =="; \
	docker compose -f docker-compose.local.yml exec -T worker celery -A app.core.celery_app inspect ping --timeout=10; \
	echo "== [6/10] Revisión rápida de errores en beat/worker (no bloqueante) =="; \
	docker compose -f docker-compose.local.yml logs --since 10m beat worker | grep -Ei "error|traceback|exception" || true; \
	echo "== [7/10] Dry-run paper =="; \
	$(MAKE) --no-print-directory dry-run SYMBOL=BTCUSDT QTY=0.0002 SIDE=BUY TYPE=MARKET; \
	echo "== [8/10] Ops watch =="; \
	$(PYTHON) scripts/ops_watch/run_once.py; \
	echo "== [9/10] Snapshot latest (no bloqueante) =="; \
	curl -sf "http://localhost:8000/api/v1/portfolio/snapshot/latest" >/dev/null || true; \
	echo "== [10/10] Guardando evidencia mínima =="; \
	mkdir -p reports/certificacion_paper; \
	docker compose -f docker-compose.local.yml ps > reports/certificacion_paper/ps_rapido.txt; \
	echo "✅ cert-paper-quick finalizado"

# Certificación paper local completa (alineada al runbook detallado)
cert-paper-full:
	@set -e; \
	TS=$$(date -u +%Y%m%dT%H%M%SZ); \
	EVIDENCE_DIR="reports/certificacion_paper/$$TS"; \
	NOGO=0; \
	NOGO_REASONS="$$EVIDENCE_DIR/no_go_reasons.txt"; \
	mkdir -p "$$EVIDENCE_DIR"; \
	: > "$$NOGO_REASONS"; \
	echo "== [0/14] Metadatos y entorno =="; \
	{ \
		echo "timestamp_utc=$$TS"; \
		echo "branch=$$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"; \
		echo "commit=$$(git rev-parse HEAD 2>/dev/null || echo unknown)"; \
		echo "os=$$(uname -a)"; \
		echo "objective=cert-paper-full"; \
	} > "$$EVIDENCE_DIR/metadata.txt"; \
	docker --version | tee "$$EVIDENCE_DIR/docker_version.txt"; \
	docker compose version | tee "$$EVIDENCE_DIR/compose_version.txt"; \
	echo "== [1/14] Validando override paper en compose =="; \
	docker compose -f docker-compose.local.yml config | tee "$$EVIDENCE_DIR/compose_config_full.txt" >/dev/null; \
	if ! grep -q 'PAPER_TRADING: "true"' "$$EVIDENCE_DIR/compose_config_full.txt"; then echo "❌ PAPER_TRADING no está en true"; exit 1; fi; \
	echo "✅ PAPER_TRADING=true detectado"; \
	echo "== [2/14] Levantando stack =="; \
	docker compose -f docker-compose.local.yml up --build -d; \
	echo "== [3/14] Estado de contenedores =="; \
	docker compose -f docker-compose.local.yml ps | tee "$$EVIDENCE_DIR/ps.txt"; \
	echo "== [4/14] Health API + Prometheus + metrics =="; \
	ok=0; \
	for i in $$(seq 1 30); do \
		if curl -sf http://localhost:8000/health > "$$EVIDENCE_DIR/health.json"; then ok=1; break; fi; \
		sleep 3; \
	done; \
	if [ $$ok -ne 1 ]; then echo "❌ API /health no respondió en 90s"; exit 56; fi; \
	curl -sf http://localhost:9090/-/ready > "$$EVIDENCE_DIR/prometheus_ready.txt"; \
	curl -sf http://localhost:8000/metrics > "$$EVIDENCE_DIR/api_metrics.txt"; \
	echo "== [5/14] Verificación de variables efectivas en API =="; \
	docker compose -f docker-compose.local.yml exec -T api python -c "import os; print('PAPER_TRADING=', os.getenv('PAPER_TRADING')); print('FORCE_REAL_MODE=', os.getenv('FORCE_REAL_MODE')); print('TRADING_ENABLED=', os.getenv('TRADING_ENABLED')); print('ML_ENABLED=', os.getenv('ML_ENABLED'))" | tee "$$EVIDENCE_DIR/api_env_effective.txt"; \
	if ! grep -q 'PAPER_TRADING= true' "$$EVIDENCE_DIR/api_env_effective.txt"; then echo "❌ PAPER_TRADING efectivo no es true"; exit 1; fi; \
	echo "== [6/14] Celery worker/beat =="; \
	docker compose -f docker-compose.local.yml exec -T worker celery -A app.core.celery_app inspect ping --timeout=10 | tee "$$EVIDENCE_DIR/celery_ping.txt"; \
	docker compose -f docker-compose.local.yml exec -T worker celery -A app.core.celery_app inspect registered --timeout=10 | tee "$$EVIDENCE_DIR/celery_registered.txt"; \
	docker compose -f docker-compose.local.yml logs --since 10m beat | tee "$$EVIDENCE_DIR/beat_logs_10m.txt"; \
	echo "== [7/14] DB conectividad y tablas operativas =="; \
	docker compose -f docker-compose.local.yml exec -T db psql -U griduser -d gridbot -c "select now();" | tee "$$EVIDENCE_DIR/db_now.txt"; \
	docker compose -f docker-compose.local.yml exec -T db psql -U griduser -d gridbot -c "SELECT (SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name='trades') as has_trades_table, (SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name='portfolio_snapshots') as has_portfolio_snapshots_table, (SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name='performance_metrics') as has_performance_metrics_table;" | tee "$$EVIDENCE_DIR/db_tables_check.txt"; \
	docker compose -f docker-compose.local.yml exec -T db psql -U griduser -d gridbot -c "SELECT (SELECT count(*) FROM trades) as trades_count, (SELECT count(*) FROM portfolio_snapshots) as snapshots_count, (SELECT max(captured_at) FROM portfolio_snapshots) as last_snapshot_at;" | tee "$$EVIDENCE_DIR/db_data_counts.txt"; \
	echo "== [8/14] Dry-run paper =="; \
	$(MAKE) --no-print-directory dry-run SYMBOL=BTCUSDT QTY=0.0002 SIDE=BUY TYPE=MARKET | tee "$$EVIDENCE_DIR/dry_run.txt"; \
	echo "== [9/14] Estado ML (artefactos + logs) =="; \
	docker compose -f docker-compose.local.yml exec -T api sh -lc "ls -la data/ml || true; ls -la models || true" | tee "$$EVIDENCE_DIR/ml_artifacts.txt"; \
	docker compose -f docker-compose.local.yml logs --since 15m worker | grep -E "ML|regime|fallback|predict" | tee "$$EVIDENCE_DIR/ml_logs_15m.txt" || true; \
	echo "== [10/14] Endpoints funcionales =="; \
	curl -sf "http://localhost:8000/openapi.json" > "$$EVIDENCE_DIR/openapi.json"; \
	eval "$$(python3 -c "import json; p=json.load(open('$$EVIDENCE_DIR/openapi.json')).get('paths',{}); keys=set(p.keys()); pick=lambda c: next((x for x in c if x in keys),''); h=pick(['/api/v1/portfolio/history','/api/portfolio/history']); s=pick(['/api/v1/portfolio/snapshot/latest','/api/portfolio/snapshot/latest']); st=pick(['/api/v2/strategies/execute_intelligent','/api/strategies/execute_intelligent','/api/strategies']); m='POST' if st.endswith('execute_intelligent') else ('GET' if st else ''); print(f'HISTORY_PATH=\"{h}\"'); print(f'SNAPSHOT_PATH=\"{s}\"'); print(f'STRATEGY_PATH=\"{st}\"'); print(f'STRATEGY_METHOD=\"{m}\"')")"; \
	{ \
		echo "history=$$HISTORY_PATH"; \
		echo "snapshot=$$SNAPSHOT_PATH"; \
		echo "strategy=$$STRATEGY_PATH"; \
		echo "strategy_method=$$STRATEGY_METHOD"; \
	} > "$$EVIDENCE_DIR/endpoints_detected.txt"; \
	if [ -z "$$HISTORY_PATH" ]; then echo "NO-GO: ruta de portfolio history no encontrada en OpenAPI" | tee -a "$$NOGO_REASONS"; NOGO=1; \
	else code=$$(curl -s -o "$$EVIDENCE_DIR/portfolio_history.json" -w "%{http_code}" "http://localhost:8000$$HISTORY_PATH?days=7"); \
		if [ $$code -ge 400 ]; then echo "NO-GO: $$HISTORY_PATH respondió HTTP $$code" | tee -a "$$NOGO_REASONS"; NOGO=1; fi; \
	fi; \
	if [ -z "$$SNAPSHOT_PATH" ]; then echo "NO-GO: ruta de snapshot latest no encontrada en OpenAPI" | tee -a "$$NOGO_REASONS"; NOGO=1; \
	else code=$$(curl -s -o "$$EVIDENCE_DIR/portfolio_snapshot_latest.json" -w "%{http_code}" "http://localhost:8000$$SNAPSHOT_PATH"); \
		if [ $$code -ge 400 ]; then echo "NO-GO: $$SNAPSHOT_PATH respondió HTTP $$code" | tee -a "$$NOGO_REASONS"; NOGO=1; fi; \
	fi; \
	if [ -z "$$STRATEGY_PATH" ]; then echo "NO-GO: ruta de estrategia no encontrada en OpenAPI" | tee -a "$$NOGO_REASONS"; NOGO=1; \
	elif [ "$$STRATEGY_METHOD" = "POST" ]; then code=$$(curl -s -o "$$EVIDENCE_DIR/strategy_execute_intelligent.json" -w "%{http_code}" -X POST "http://localhost:8000$$STRATEGY_PATH" -H "Content-Type: application/json" -d '{"symbol":"ETHUSDT","account_state":{"total_equity":1000,"available_balance":500,"total_exposure":0,"daily_pnl":0,"max_drawdown":0,"risk_score":0.1},"paper_mode":true,"quick_backtest":false}'); \
		if [ $$code -ge 400 ]; then echo "NO-GO: $$STRATEGY_PATH (POST) respondió HTTP $$code" | tee -a "$$NOGO_REASONS"; NOGO=1; fi; \
	else code=$$(curl -s -o "$$EVIDENCE_DIR/strategies_smoke.json" -w "%{http_code}" "http://localhost:8000$$STRATEGY_PATH"); \
		if [ $$code -ge 400 ]; then echo "NO-GO: $$STRATEGY_PATH (GET) respondió HTTP $$code" | tee -a "$$NOGO_REASONS"; NOGO=1; fi; \
	fi; \
	echo "== [11/14] Ops watch corrida 1 =="; \
	$(PYTHON) scripts/ops_watch/run_once.py | tee "$$EVIDENCE_DIR/ops_watch_run1.txt"; \
	cp reports/ops_watch/LATEST.md "$$EVIDENCE_DIR/ops_watch_latest_run1.md"; \
	echo "== [12/14] Ops watch corrida 2 =="; \
	sleep 5; \
	$(PYTHON) scripts/ops_watch/run_once.py | tee "$$EVIDENCE_DIR/ops_watch_run2.txt"; \
	cp reports/ops_watch/LATEST.md "$$EVIDENCE_DIR/ops_watch_latest_run2.md"; \
	echo "== [13/14] Snapshot final =="; \
	docker compose -f docker-compose.local.yml ps > "$$EVIDENCE_DIR/final_ps.txt"; \
	docker compose -f docker-compose.local.yml logs --since 15m > "$$EVIDENCE_DIR/final_logs_15m.txt"; \
	if [ $$NOGO -eq 1 ]; then \
		echo "NO-GO" > "$$EVIDENCE_DIR/result.txt"; \
		echo "❌ cert-paper-full finalizado (NO-GO explícito)"; \
		echo "Motivos:"; \
		cat "$$NOGO_REASONS"; \
		echo "📁 Evidencia: $$EVIDENCE_DIR"; \
		exit 1; \
	fi; \
	echo "GO" > "$$EVIDENCE_DIR/result.txt"; \
	echo "✅ cert-paper-full finalizado (GO)"; \
	echo "📁 Evidencia: $$EVIDENCE_DIR"
