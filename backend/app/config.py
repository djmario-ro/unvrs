from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://guesthouse:guesthouse@db:5432/guesthouse"
    secret_key: str = "change-me-in-production-please"
    debug: bool = False

    # Token validity in hours
    access_token_expire_hours: int = 12

    # Frontend origin for CORS
    frontend_origin: str = "http://localhost:5173"

    # Cookie settings
    cookie_secure: bool = False  # True in production (HTTPS)
    cookie_samesite: str = "lax"


settings = Settings()
