from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Qualquer URL do SQLAlchemy funciona; o padrão é um arquivo SQLite local.
    database_url: str = "sqlite:///./posts.db"
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30


settings = Settings()
