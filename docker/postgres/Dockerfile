FROM postgres:16-alpine

# Locales musl (evita: "WARNING: no usable system locales were found")
RUN apk add --no-cache musl-locales musl-locales-lang tzdata

# Configurar variables de entorno para locale
ENV LANG=en_US.UTF-8
ENV LANGUAGE=en_US:en
ENV LC_ALL=en_US.UTF-8

# Configurar PostgreSQL para usar UTF-8
# En Alpine/musl usamos C.UTF-8 para el initdb (locales C siempre disponibles)
# mientras que LANG queda en en_US.UTF-8 para mensajes.
ENV POSTGRES_INITDB_ARGS="--encoding=UTF-8 --lc-collate=C.UTF-8 --lc-ctype=C.UTF-8"

# Crear usuario y base de datos para Grafana con permisos completos
COPY 01-create-grafana-db.sql /docker-entrypoint-initdb.d/01-create-grafana-db.sql
COPY 01b-grafana-schema.sql   /docker-entrypoint-initdb.d/01b-grafana-schema.sql

# Copiar script de inicialización de la BD de la aplicación y sus grants
COPY init.sql                 /docker-entrypoint-initdb.d/02-init-gridbot.sql
COPY 02b-gridbot-grants.sql   /docker-entrypoint-initdb.d/02b-gridbot-grants.sql
