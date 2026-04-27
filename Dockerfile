# Dockerfile — GridBot v2.5
FROM python:3.11-slim

LABEL maintainer="GridBot Team"
LABEL version="2.5.0"
LABEL description="Grid Trading Bot con tracing OTel, risk metrics y grilla adaptativa"

# Evitar bytecode y buffering para logs limpios en Docker
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Usuario no-root para seguridad
RUN groupadd -r gridbot && useradd -r -g gridbot gridbot

WORKDIR /app

# Copiar requirements primero para aprovechar el layer cache de Docker
COPY requirements.txt requirements-ml.txt ./

# Instalar dependencias Python
# Las dependencias de OpenTelemetry son opcionales; si fallan no rompen el build
RUN pip install --no-cache-dir -r requirements.txt || \
    (echo "⚠️  Algunas dependencias opcionales fallaron, reintentando sin OTel..." && \
     grep -v "^opentelemetry" requirements.txt > /tmp/req_core.txt && \
     pip install --no-cache-dir -r /tmp/req_core.txt)

# El despliegue local completo exige el motor híbrido (TensorFlow/Keras + River).
RUN pip install --no-cache-dir -r requirements-ml.txt

# Verificar dependencias críticas
RUN python -c "\
import sys; \
critical = ['fastapi','uvicorn','sqlalchemy','pydantic','celery','redis','numpy','pandas','tensorflow']; \
missing = [p for p in critical if not __import__(p, globals(), locals(), [], 0)]; \
sys.exit(1) if missing else print('✅ Dependencias críticas OK')"

# Copiar el código de la aplicación
COPY . .

RUN python -c "from app.services.hybrid_ml_engine import HybridMLEngine; HybridMLEngine(); print('✅ HybridMLEngine OK')"

# Crear directorios de runtime
RUN mkdir -p logs cache data monitoring_data reports /tmp/matplotlib && \
    chown -R gridbot:gridbot /app /tmp/matplotlib

USER gridbot

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=20s --start-period=60s --retries=3 \
    CMD curl -sf http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
