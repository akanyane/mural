from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="WEB_", extra="ignore")

    # Onde a posts-api está rodando.
    api_url: str = "http://localhost:8000"
    # Em produção (HTTPS) deixe True para o cookie de sessão só trafegar criptografado.
    cookie_secure: bool = False
    # Validade do cookie no navegador. Quem decide se a sessão ainda vale é a API
    # (expiração por inatividade e limite absoluto); isto só evita que o cookie
    # suma ao fechar o navegador.
    session_cookie_days: int = 90


settings = Settings()
