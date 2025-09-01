# Usar imagen base de Python 3.11 slim para mayor compatibilidad
FROM python:3.11-slim

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    wget \
    git \
    && rm -rf /var/lib/apt/lists/*

# Crear usuario no-root para seguridad
RUN groupadd -r gridbot && useradd -r -g gridbot gridbot

# Establecer directorio de trabajo
WORKDIR /app

# Copiar requirements primero para aprovechar cache de Docker
COPY requirements.txt .

# Instalar dependencias de Python con variables de entorno para compilación
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Configurar numba para evitar problemas de cache en Docker
ENV NUMBA_CACHE_DIR=/tmp/numba_cache
ENV NUMBA_DISABLE_JIT=0
ENV NUMBA_DISABLE_CUDA=1
ENV NUMBA_DISABLE_NVVM=1
ENV NUMBA_DISABLE_LLVM=0
# Deshabilitar cache de numba para evitar problemas con vectorbt
ENV NUMBA_DISABLE_CACHE=1
ENV NUMBA_CACHE_DIR=/dev/null

# Instalar dependencias de Python
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Crear directorio de cache de numba
RUN mkdir -p /tmp/numba_cache && chmod 777 /tmp/numba_cache

# Copiar código de la aplicación
COPY . .

# Crear directorios necesarios
RUN mkdir -p /app/logs /app/data /app/cache /app/static && \
    chown -R gridbot:gridbot /app /tmp/numba_cache

# Cambiar al usuario no-root
USER gridbot

# Exponer puerto
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Comando por defecto
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
