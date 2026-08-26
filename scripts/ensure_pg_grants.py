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
import time

try:
    import psycopg2  # type: ignore
except Exception as e:  # pragma: no cover
    print(f"❌ psycopg2 no disponible: {e}", file=sys.stderr)
    sys.exit(1)


def _normalize_dsn(dsn: str) -> str:
    if dsn.startswith("postgresql+psycopg2://"):
        return dsn.replace("postgresql+psycopg2://", "postgresql://", 1)
    if dsn.startswith("postgresql+asyncpg://"):
        return dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    return dsn


def wait_for_postgres_ready(
    dsn: str,
    *,
    max_wait_sec: float,
    interval_sec: float,
) -> None:
    """
    Espera hasta que Postgres acepte TCP y responda a SELECT 1.

    Tras el primer arranque con volumen vacío, el entrypoint de Docker puede
    apagar el servidor temporal al terminar initdb.d; el healthcheck puede
    marcar healthy demasiado pronto y ensure_pg_grants vería Connection refused.
    """
    deadline = time.monotonic() + max_wait_sec
    attempt = 0
    last_err: Exception | None = None
    while time.monotonic() < deadline:
        attempt += 1
        try:
            conn = psycopg2.connect(dsn, connect_timeout=5)
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            conn.close()
            if attempt > 1:
                print(f"✅ Postgres listo tras {attempt} intento(s)")
            return
        except Exception as e:
            last_err = e
            if attempt == 1 or attempt % 10 == 0:
                print(
                    f"⏳ Postgres aún no acepta conexiones: {e!s} (intento {attempt})"
                )
            time.sleep(interval_sec)

    print(
        f"❌ Timeout ({max_wait_sec:g}s) esperando Postgres: {last_err!s}",
        file=sys.stderr,
    )
    sys.exit(1)


def main() -> int:
    dsn = os.environ.get("DATABASE_URL", "")
    if not dsn:
        print("❌ DATABASE_URL no definida", file=sys.stderr)
        return 1

    dsn = _normalize_dsn(dsn)

    max_wait = float(os.environ.get("OPS_PG_WAIT_MAX_SEC", "120"))
    interval = float(os.environ.get("OPS_PG_WAIT_INTERVAL_SEC", "2"))
    print("⏳ Esperando a que Postgres acepte conexiones (post-init / reinicio)…")
    wait_for_postgres_ready(dsn, max_wait_sec=max_wait, interval_sec=interval)

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
        conn = psycopg2.connect(dsn, connect_timeout=30)
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

            try:
                cur.execute("CREATE EXTENSION IF NOT EXISTS pg_stat_statements")
                print("✅ pg_stat_statements disponible (E-OBS-PG-SRE)")
            except Exception as e:
                print(
                    "⚠️  pg_stat_statements: "
                    f"{e} — requiere shared_preload_libraries y restart de db"
                )

        conn.close()
    except Exception as e:
        print(f"❌ Error conectando a Postgres: {e}", file=sys.stderr)
        return 1

    print("✅ Permisos verificados en schema public")
    return 0


if __name__ == "__main__":
    sys.exit(main())
