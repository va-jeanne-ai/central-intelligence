from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://localhost:5432/centralintelligence"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: list[str] = ["http://localhost:3000"]
    debug: bool = False
    app_name: str = "Central Intelligence API"
    mock_mode: bool = True  # Set to False when ANTHROPIC_API_KEY is configured

    # ------------------------------------------------------------------
    # Supabase — leave empty to run auth in mock mode (no live project
    # required).  Populate all three to activate real Supabase auth.
    # ------------------------------------------------------------------
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_jwt_secret: str = ""

    # ------------------------------------------------------------------
    # Mailchimp — F28 connector for email stats. When mailchimp_api_key is
    # empty, the email_stats Celery task falls back to its seed data so
    # local/dev environments still produce a populated dashboard.
    # mailchimp_server_prefix is auto-derived from the dc suffix of the
    # API key (e.g. "abc123-us21" → "us21") when left empty.
    # ------------------------------------------------------------------
    mailchimp_api_key: str = ""
    mailchimp_server_prefix: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
