from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
from app.core.config import settings

load_dotenv()

# Usar SIEMPRE la configuración centralizada, no el archivo .env
DATABASE_URL = settings.database_url

# Convertir URL asíncrona a síncrona si es necesario
if DATABASE_URL and "+asyncpg" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("+asyncpg", "")

# Configurar engine para PostgreSQL
engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Exporto para uso externo
from app.models.base import Base 