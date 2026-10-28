from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://guesthouse:guesthouse@db:5432/guesthouse"
    secret_key: str = "change-me-in-production-please"
    # Allows placeholder secrets (local development only).
    debug: bool = False
    # Log every SQL statement. Kept separate from debug because statements
    # include guest PINs; never enable in production.
    sql_echo: bool = False

    # Shown as the sender name in guest PIN messages
    guesthouse_name: str = "Guesthouse"

    # Seed admin account, created on first startup if no users exist
    admin_username: str = "admin"
    admin_password: str = "admin"

    # Token validity in hours
    access_token_expire_hours: int = 12

    # Frontend origin for CORS
    frontend_origin: str = "http://localhost:5173"

    # Cookie settings
    cookie_secure: bool = False  # True in production (HTTPS)
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"

    # Networks of the reverse proxies in front of the backend, as a comma
    # separated list of CIDRs and/or the groups "private" (RFC 1918, loopback,
    # link-local: nginx, Traefik) and "cloudflare". Rate limiting walks
    # X-Forwarded-For from the right, skipping these, to find the client IP.
    trusted_proxies: str = "private"

    # Default country code (no +) used to turn locally-formatted numbers such
    # as "0743..." into international "40743..." before sending
    default_country_code: str = "40"

    # IANA timezone the guesthouse operates in; used to display stay dates in
    # guest messages. Stored timestamps remain UTC.
    timezone: str = "Europe/Bucharest"

    # WhatsApp sidecar (Baileys) — leave empty to fall back to a console mock
    whatsapp_service_url: str = ""
    # Shared secret sent as a Bearer token to the sidecar (must match its API_TOKEN)
    whatsapp_api_token: str = ""

    # SMS gateway (sms-gate.app) — leave URL empty to fall back to a console mock
    sms_gateway_url: str = ""
    sms_gateway_username: str = ""
    sms_gateway_password: str = ""


settings = Settings()
