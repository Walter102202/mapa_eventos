from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # MySQL
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_database: str = "baches_rm"

    # OpenAI
    openai_api_key: str = ""

    # App
    debug: bool = False
    # Orígenes CORS permitidos, separados por coma. Vacío = sin CORS (frontend servido por el mismo FastAPI).
    cors_origins: str = ""
    # Rate limit por IP para endpoints que llaman a OpenAI. Formato de `limits`: "5/minute", "100/hour".
    rate_limit_enabled: bool = True
    rate_limit_ia: str = "5/minute"
    # Token para operaciones administrativas (ej: ?refresh=true). Vacío = operación deshabilitada.
    admin_token: str = ""

    @property
    def database_url(self) -> str:
        return f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
