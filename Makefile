PYTHON?=python3

.PHONY: retention-cleanup retention-dry

retention-cleanup:
	MONITORING_DIR=monitoring_data REPORTS_DIR=reports $(PYTHON) scripts/retention_cleanup.py --verbose

retention-dry:
	MONITORING_DIR=monitoring_data REPORTS_DIR=reports $(PYTHON) scripts/retention_cleanup.py --dry-run --verbose


