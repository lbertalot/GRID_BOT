release: python scripts/release.py
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1
worker: celery -A app.core.celery_app worker --loglevel=info --concurrency=2
beat: celery -A app.core.celery_app beat --loglevel=warning
