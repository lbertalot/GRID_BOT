-- Script 02b: Permisos explícitos en la BD `gridbot`
-- Postgres 15+ endurece el schema `public` (no CREATE por defecto para no-owner).
-- Aunque `griduser` es owner vía POSTGRES_USER, forzamos los GRANT para que
-- Alembic pueda crear su tabla `alembic_version` y cualquier objeto en `public`
-- sin chocar con "permission denied for schema public".

\connect gridbot

-- Garantizar ownership y permisos de la BD y del esquema public
ALTER DATABASE gridbot OWNER TO griduser;
GRANT ALL PRIVILEGES ON DATABASE gridbot TO griduser;

ALTER SCHEMA public OWNER TO griduser;
GRANT ALL ON SCHEMA public TO griduser;
GRANT CREATE ON SCHEMA public TO griduser;
GRANT USAGE ON SCHEMA public TO griduser;

-- Permisos también sobre el esquema de aplicación
GRANT ALL ON SCHEMA gridbot TO griduser;

-- Objetos existentes (idempotente)
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO griduser;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO griduser;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO griduser;

-- Defaults para objetos futuros creados por griduser (único superusuario en esta imagen;
-- no existe el rol `postgres` del Docker oficial, evitar ALTER DEFAULT PRIVILEGES FOR ROLE postgres).
ALTER DEFAULT PRIVILEGES FOR ROLE griduser IN SCHEMA public
    GRANT ALL ON TABLES TO griduser;
ALTER DEFAULT PRIVILEGES FOR ROLE griduser IN SCHEMA public
    GRANT ALL ON SEQUENCES TO griduser;
