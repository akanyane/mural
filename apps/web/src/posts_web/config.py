from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="WEB_", extra="ignore")

    # Onde a posts-api está rodando.
    api_url: str = "http://localhost:8000"
    # Em produção (HTTPS) deixe True para o cookie de sessão só trafegar criptografado.
    cookie_secure: bool = False


settings = Settings()
