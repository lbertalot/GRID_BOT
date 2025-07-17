from pydantic import BaseSettings

class Settings(BaseSettings):
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "db"
    postgres_port: int = 5432
    database_url: str

    class Config:
        env_file = ".env"

settings = Settings() 