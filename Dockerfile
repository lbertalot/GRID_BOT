# Dockerfile - GridBot v2.5 OPTIMIZADO
# MEJORA: Remover scripts de verificacion innecesarios, logging simplificado
FROM python:3.11-slim

LABEL maintainer="GridBot Team"
LABEL version="2.5.1-optimized"
LABEL description="Grid Trading Bot - Optimizado para performance, seguridad y logging JSON"

# Evitar bytecode y buffering para logs limpios en Docker
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Dependencias del sistema (minimas)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Usuario no-root para seguridad
RUN groupadd -r gridbot && useradd -r -g gridbot gridbot

WORKDIR /app

# Copiar requirements primero para aprovechar layer cache de Docker
COPY requirements.txt requirements-ml.txt ./

# Instalar dependencias Python
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r requirements-ml.txt

COPY . .

# Crear directorios de runtime
RUN mkdir -p logs cache data monitoring_data reports /tmp/matplotlib && \
    chown -R gridbot:gridbot /app /tmp/matplotlib

USER gridbot

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=20s --start-period=60s --retries=3 \
    CMD curl -sf http://localhost:8000/health || exit 1

# Worker Celery: prefetch_multiplier=1 para mejor distribucion
# Si necesitas API: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
CMD ["celery", "-A", "app.core.celery_app", "worker", \
     "--loglevel=info", "--concurrency=4", "--prefetch-multiplier=1", \
     "--max-tasks-per-child=1000", "--queues=celery,low"]
