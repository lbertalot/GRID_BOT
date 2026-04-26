#!/usr/bin/env python3
"""
Script para asegurar que la tabla alembic_version tenga el tamaño correcto.
Se ejecuta automáticamente antes de las migraciones en Heroku.
"""

import os
import sys
from sqlalchemy import create_engine, text, inspect


def fix_alembic_version_table():
    """Asegura que alembic_version tenga VARCHAR(255) en lugar de VARCHAR(32)"""
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        print("❌ DATABASE_URL no está configurada")
        sys.exit(1)

    # Convertir formato postgres:// a postgresql:// (Heroku)
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    try:
        engine = create_engine(db_url)
        inspector = inspect(engine)

        # Verificar si la tabla existe
        if "alembic_version" in inspector.get_table_names():
            # Verificar el tamaño actual de la columna
            with engine.connect() as conn:
                result = conn.execute(
                    text("""
                    SELECT character_maximum_length
                    FROM information_schema.columns
                    WHERE table_name = 'alembic_version'
                    AND column_name = 'version_num'
                """)
                )
                row = result.fetchone()

                if row and row[0] and row[0] < 255:
                    # Redimensionar la columna
                    print(
                        f"📝 Redimensionando version_num de {row[0]} a 255 caracteres..."
                    )
                    with engine.begin() as trans:
                        trans.execute(
                            text(
                                "ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(255)"
                            )
                        )
                    print("✅ Columna version_num redimensionada correctamente")
                else:
                    print("✅ Columna version_num ya tiene tamaño suficiente")
        else:
            # Crear la tabla si no existe
            print("📝 Creando tabla alembic_version con VARCHAR(255)...")
            with engine.begin() as conn:
                conn.execute(
                    text("""
                    CREATE TABLE alembic_version (
                        version_num VARCHAR(255) NOT NULL,
                        CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
                    )
                """)
                )
            print("✅ Tabla alembic_version creada correctamente")

        return True

    except Exception as e:
        print(f"❌ Error arreglando tabla alembic_version: {e}")
        return False


if __name__ == "__main__":
    success = fix_alembic_version_table()
    sys.exit(0 if success else 1)
