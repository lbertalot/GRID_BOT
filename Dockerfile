# Dockerfile optimizado para Grid Trading Bot con todas las mejoras
FROM python:3.11-slim

# Metadatos
LABEL maintainer="Grid Trading Bot Team"
LABEL version="2.0.0"
LABEL description="Grid Trading Bot con WebSocket avanzado y optimizaciones"

# Variables de entorno para optimización
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Crear usuario no-root para seguridad
RUN groupadd -r gridbot && useradd -r -g gridbot gridbot

# Establecer directorio de trabajo
WORKDIR /app

# Copiar archivos de requirements
COPY requirements*.txt ./

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Verificar instalación de dependencias críticas
RUN python -c "import sys; packages = ['fastapi', 'uvicorn', 'sqlalchemy', 'asyncpg', 'pydantic', 'binance', 'ccxt', 'celery', 'redis', 'numpy', 'pandas', 'sklearn', 'scipy', 'passlib', 'dotenv', 'apscheduler', 'jinja2', 'aiofiles', 'telegram', 'requests', 'websockets', 'cryptography', 'bcrypt']; missing = []; [missing.append(p) if __import__(p.replace('-', '_'), globals(), locals(), [], 0) is None else print(f'✅ {p} instalado') for p in packages]; sys.exit(1) if missing else print('🎉 Todas las dependencias instaladas')"

# Copiar código de la aplicación
COPY . .

# Crear directorios necesarios
RUN mkdir -p logs cache data && \
    chown -R gridbot:gridbot /app

# Cambiar al usuario no-root
USER gridbot

# Exponer puerto
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Comando por defecto
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]