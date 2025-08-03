FROM postgres:16-alpine

# Instalar locales y configurar UTF-8
RUN apk add --no-cache locales && \
    locale-gen en_US.UTF-8

# Configurar variables de entorno para locale
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8

# Configurar PostgreSQL para usar UTF-8
ENV POSTGRES_INITDB_ARGS "--encoding=UTF-8 --lc-collate=en_US.UTF-8 --lc-ctype=en_US.UTF-8"

# Crear usuario y base de datos para Grafana
RUN echo "CREATE DATABASE grafana;" > /docker-entrypoint-initdb.d/01-create-grafana-db.sql && \
    echo "CREATE USER grafana WITH PASSWORD 'grafana_pass';" >> /docker-entrypoint-initdb.d/01-create-grafana-db.sql && \
    echo "GRANT ALL PRIVILEGES ON DATABASE grafana TO grafana;" >> /docker-entrypoint-initdb.d/01-create-grafana-db.sql

# Copiar script de inicialización personalizado
COPY init.sql /docker-entrypoint-initdb.d/02-init-gridbot.sql 