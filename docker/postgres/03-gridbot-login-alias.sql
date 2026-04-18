-- Rol de login `gridbot` (misma contraseña que POSTGRES_PASSWORD en compose) para
-- clientes que confunden el nombre de la base de datos con el usuario PostgreSQL
-- (p. ej. postgresql://gridbot:...@host/gridbot fallaba antes de este rol).

\connect gridbot

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'gridbot') THEN
    CREATE ROLE gridbot WITH LOGIN PASSWORD 'gridpass' INHERIT;
  END IF;
END
$$;

-- Mismos privilegios efectivos que griduser (herencia de rol)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_auth_members am
    JOIN pg_roles r ON r.oid = am.roleid
    JOIN pg_roles m ON m.oid = am.member
    WHERE r.rolname = 'griduser' AND m.rolname = 'gridbot'
  ) THEN
    GRANT griduser TO gridbot;
  END IF;
END
$$;
