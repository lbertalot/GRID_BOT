#!/usr/bin/env python3
"""
Asegura idempotentemente los permisos en el schema `public` para `griduser`.

Se ejecuta antes de `alembic upgrade head` en el servicio `migrate`.
Razón: Postgres 15+ endurece `public` y, si el volumen `pgdata` ya existe,
los scripts de `/docker-entrypoint-initdb.d/` NO se re-ejecutan; por eso
este paso en runtime es necesario para entornos que ya tenían la BD.

Idempotente: cada GRANT/ALTER es seguro de repetir.
"""
from __future__ import annotations

import os
import sys

try:
    import psycopg2  # type: ignore
except Exception as e:  # pragma: no cover
    print(f"❌ psycopg2 no disponible: {e}", file=sys.stderr)
    sys.exit(1)


def main() -> int:
    dsn = os.environ.get("DATABASE_URL", "")
    if not dsn:
        print("❌ DATABASE_URL no definida", file=sys.stderr)
        return 1

    # SQLAlchemy-style -> libpq-style
    if dsn.startswith("postgresql+psycopg2://"):
        dsn = dsn.replace("postgresql+psycopg2://", "postgresql://", 1)
    elif dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)

    print("🔐 Asegurando permisos en schema public para griduser…")

    pg_pass = os.environ.get("POSTGRES_PASSWORD", "gridpass")

    stmts = [
        "ALTER SCHEMA public OWNER TO griduser",
        "GRANT ALL ON SCHEMA public TO griduser",
        "GRANT CREATE ON SCHEMA public TO griduser",
        "GRANT USAGE ON SCHEMA public TO griduser",
        "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO griduser",
        "GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO griduser",
        "GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO griduser",
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO griduser",
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO griduser",
    ]

    try:
        conn = psycopg2.connect(dsn)
        conn.autocommit = True
        with conn.cursor() as cur:
            for stmt in stmts:
                try:
                    cur.execute(stmt)
                except Exception as e:
                    # No abortamos: lo normal es que algunos ya existan o
                    # requieran privilegios superiores (ignorables en dev).
                    print(f"⚠️  {stmt}: {e}")

            # Rol de login `gridbot` (alias) — idempotente; griduser es superuser en Docker
            try:
                cur.execute("SELECT 1 FROM pg_roles WHERE rolname = 'gridbot'")
                if cur.fetchone() is None:
                    cur.execute(
                        "CREATE ROLE gridbot WITH LOGIN PASSWORD %s INHERIT",
                        (pg_pass,),
                    )
                    print("✅ Rol gridbot creado (alias de permisos vía griduser)")
            except Exception as e:
                print(f"⚠️  Rol gridbot: {e}")

            try:
                cur.execute(
                    """
                    SELECT 1 FROM pg_auth_members am
                    JOIN pg_roles r ON r.oid = am.roleid
                    JOIN pg_roles m ON m.oid = am.member
                    WHERE r.rolname = 'griduser' AND m.rolname = 'gridbot'
                    """
                )
                if cur.fetchone() is None:
                    cur.execute("GRANT griduser TO gridbot")
                    print("✅ GRANT griduser TO gridbot aplicado")
            except Exception as e:
                print(f"⚠️  GRANT griduser TO gridbot: {e}")

        conn.close()
    except Exception as e:
        print(f"❌ Error conectando a Postgres: {e}", file=sys.stderr)
        return 1

    print("✅ Permisos verificados en schema public")
    return 0


if __name__ == "__main__":
    sys.exit(main())
