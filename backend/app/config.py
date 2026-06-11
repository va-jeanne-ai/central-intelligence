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

    # ------------------------------------------------------------------
    # Integrations master key — used by app/services/secrets.py to encrypt
    # third-party credentials at rest in the `integrations` table. Generate
    # one with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # In debug mode an empty value generates a per-process dev key (data
    # written with it won't survive a restart). In non-debug mode this is
    # required at first use or operations raise.
    # ------------------------------------------------------------------
    integrations_encryption_key: str = ""

    # Public base URL for constructing webhook URLs we hand to third parties
    # (GHL, future Stripe/Calendly, etc.). Local dev uses the default; in
    # prod set to https://api.<domain> so the user can copy a working URL
    # straight into GHL's Custom Webhook action. Defaults to the local
    # uvicorn binding so curl-based verification works out of the box.
    public_api_base_url: str = "http://localhost:8000"

    # ------------------------------------------------------------------
    # Google OAuth (per-user). Each staff member runs through Google's
    # consent flow once; CI stores their encrypted refresh token in
    # `user_integration_credentials` and uses it to read Gmail on their
    # behalf. Set up the OAuth 2.0 Client (Web application type) in
    # Google Cloud Console → APIs & Services → Credentials, then add
    # the authorized redirect URI matching the value below.
    # ------------------------------------------------------------------
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_oauth_redirect_uri: str = (
        "http://localhost:8000/api/v1/integrations/google_workspace/oauth/callback"
    )

    # ------------------------------------------------------------------
    # Voyage AI embeddings (RAG layer). voyage-3 is 1024-d; the embed
    # worker batches up to ``embed_worker_batch_size`` chunks per API
    # call (Voyage's API limit is 128). Each chunk is sized to at most
    # ``embed_worker_max_tokens_per_chunk`` cl100k tokens.
    # ------------------------------------------------------------------
    voyage_api_key: str = ""
    embed_worker_batch_size: int = 32
    embed_worker_max_tokens_per_chunk: int = 1024

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
