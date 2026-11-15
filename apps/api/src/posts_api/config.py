from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Qualquer URL do SQLAlchemy funciona; o padrão é um arquivo SQLite local.
    database_url: str = "sqlite:///./posts.db"

    # Sessões no servidor (validadas no banco a cada requisição):
    # expiram após `session_idle_days` sem uso, e nunca duram mais que `session_max_age_days`.
    session_idle_days: int = 30
    session_max_age_days: int = 90
    # O "último uso" é gravado no máximo a cada N minutos, para não escrever no banco
    # a cada requisição.
    session_touch_minutes: int = 5


settings = Settings()
