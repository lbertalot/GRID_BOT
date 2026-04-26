from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    # Configuración de base de datos
    postgres_user: str = "griduser"
    postgres_password: str = "gridpass"
    postgres_db: str = "gridbot"
    postgres_host: str = "localhost"  # Cambiado a localhost por defecto
    postgres_port: int = 5432

    # URL de base de datos - se configurará dinámicamente
    database_url: str = ""

    # Configuración adicional
    redis_url: str = "redis://localhost:6379/0"  # Cambiado a localhost
    secret_key: str = os.getenv("SECRET_KEY", "")
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    binance_api_key: str = ""
    binance_api_secret: str = ""
    binance_testnet: bool = False
    paper_trading: bool = False
    api_key: str = ""

    class Config:
        env_file = ".env"
        extra = "allow"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Priorizar DATABASE_URL del entorno si está disponible (Heroku, etc.)
        env_database_url = os.getenv("DATABASE_URL")
        if env_database_url:
            # Heroku proporciona DATABASE_URL en formato postgres://, convertir a postgresql://
            if env_database_url.startswith("postgres://"):
                self.database_url = env_database_url.replace(
                    "postgres://", "postgresql://", 1
                )
            else:
                self.database_url = env_database_url
        else:
            # Detectar si estamos en Docker o ejecutándose localmente
            is_docker = os.getenv("DOCKER_ENV") == "true" or os.path.exists(
                "/.dockerenv"
            )

            if is_docker:
                # Configuración para Docker
                self.postgres_host = "db"
                self.redis_url = "redis://redis:6379/0"
                self.database_url = f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            else:
                # Configuración para desarrollo local
                self.postgres_host = "localhost"
                self.redis_url = "redis://localhost:6379/0"
                self.database_url = f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

        # Priorizar REDIS_URL del entorno si está disponible (Heroku, etc.)
        env_redis_url = os.getenv("REDIS_URL")
        if env_redis_url:
            self.redis_url = env_redis_url

        # Flags de trading
        self.paper_trading = bool(os.getenv("PAPER_TRADING", "false").lower() == "true")
        self.binance_testnet = bool(
            os.getenv("BINANCE_TESTNET", "false").lower() == "true"
        )

        # Validaciones de seguridad para producción
        if os.getenv("ENV", "development").lower() == "production":
            if not self.secret_key:
                raise ValueError("SECRET_KEY es obligatorio en producción")
            if self.debug:
                raise ValueError("DEBUG debe ser false en producción")


settings = Settings()
