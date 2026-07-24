from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ─── LLM ──────────────────────────────────────────────────────────
    llm_provider: str = Field(default="openai", alias="LLM_PROVIDER")  # openai | bedrock
    model: str = Field(default="gpt-4o-mini", alias="MODEL")
    model_temperature: float = Field(default=0.0, alias="MODEL_TEMPERATURE")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")

    aws_region: str = Field(default="us-east-1", alias="AWS_REGION")
    aws_access_key_id: str = Field(default="", alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str = Field(default="", alias="AWS_SECRET_ACCESS_KEY")

    embeddings_provider: str = Field(default="openai", alias="EMBEDDINGS_PROVIDER")  # openai | bedrock
    embeddings_model: str = Field(default="text-embedding-3-small", alias="EMBEDDINGS_MODEL")
    collection_name: str = Field(default="query_categories", alias="COLLECTION_NAME")

    # ─── Persistence ──────────────────────────────────────────────────
    db_uri: str = Field(default="", alias="DB_URI")
    db_name: str = Field(default="sacramento", alias="DB_NAME")
    db_table_name: str = Field(default="sacramento", alias="DB_TABLE_NAME")

    # ─── Observability ────────────────────────────────────────────────
    log_file: str = Field(default="app.log", alias="LOG_FILE")
    log_level: str = Field(default="info", alias="LOG_LEVEL")

    # ─── Twilio (SMS webhook) ─────────────────────────────────────────
    twilio_account_sid: str = Field(default="", alias="TWILIO_ACCOUNT_SID")
    twilio_auth_token: str = Field(default="", alias="TWILIO_AUTH_TOKEN")
    # API Key (SK…) + Secret — REQUIRED to sign browser Voice access tokens.
    twilio_api_key_sid: str = Field(default="", alias="TWILIO_API_KEY_SID")
    twilio_api_key_secret: str = Field(default="", alias="TWILIO_API_KEY_SECRET")
    twilio_phone_number: str = Field(default="", alias="TWILIO_PHONE_NUMBER")    # TwiML App SID (AP...) — required for browser Voice SDK calling.
    twilio_twiml_app_sid: str = Field(default="", alias="TWILIO_TWIML_APP_SID")
    # Publicly reachable URL of this backend.
    # Accepts either base URL (https://host) or full webhook URL
    # (https://host/api/kiosk/call/twiml).
    # Twilio calls /api/kiosk/call/twiml on this URL to get dial instructions.
    twilio_public_url: str = Field(default="", alias="TWILIO_PUBLIC_URL")
    # ─── HTTP / CORS ──────────────────────────────────────────────────
    cors_origins: str = Field(default="*", alias="CORS_ORIGINS")

    # ─── Auth ─────────────────────────────────────────────────────────
    jwt_secret: str = Field(default="change-me-in-production", alias="JWT_SECRET")
    cookie_secure: bool = Field(default=True, alias="COOKIE_SECURE")
    # SameSite policy for the auth cookie. Use "none" (requires Secure) when the
    # frontend and backend are served from different origins (e.g. Vercel SPA
    # calling the Fly backend); "lax" for same-origin deployments.
    cookie_samesite: str = Field(default="lax", alias="COOKIE_SAMESITE")
    frontend_url: str = Field(default="http://localhost:8084", alias="FRONTEND_URL")
    disable_auth: bool = Field(default=False, alias="DISABLE_AUTH")

    admin_email: str = Field(default="admin@example.com", alias="ADMIN_EMAIL")
    admin_password: str = Field(default="changeme", alias="ADMIN_PASSWORD")
    admin_name: str = Field(default="Admin", alias="ADMIN_NAME")
    admin_company: str = Field(default="", alias="ADMIN_COMPANY")

    # ─── Kiosk ────────────────────────────────────────────────────────
    # When true, the /api/kiosk/query endpoint returns curated sample
    # resources instead of hitting the OpenAI + pgvector pipeline. Lets the
    # kiosk demo run on a laptop or Raspberry Pi with no API key or seeded DB.
    kiosk_mock_query: bool = Field(default=False, alias="KIOSK_MOCK_QUERY")
    # Inactivity timeout (seconds) before the kiosk auto-resets to the idle menu.
    kiosk_idle_reset_seconds: int = Field(default=60, alias="KIOSK_IDLE_RESET_SECONDS")
    # Seconds of no keypad activity during a live call before the kiosk asks
    # "are you still there?" (two warnings ~45s apart, then auto-hangup).
    kiosk_call_idle_warn_seconds: int = Field(
        default=300, alias="KIOSK_CALL_IDLE_WARN_SECONDS"
    )
    # Seconds of no activity before the idle screen dims (burn-in protection).
    # Any key wakes it instantly.
    kiosk_screen_dim_seconds: int = Field(
        default=1800, alias="KIOSK_SCREEN_DIM_SECONDS"
    )

    # ─── Kiosk calling (Twilio Voice) ─────────────────────────────────
    # Master switch for real outbound calls. Even when enabled, the backend
    # only dials numbers found in the agencies database (allowlist).
    kiosk_calling_enabled: bool = Field(default=False, alias="KIOSK_CALLING_ENABLED")
    # Comma-separated list of E.164 numbers allowed outside the DB allowlist.
    # Example: +19165551234,+17075559876
    # On Twilio trial accounts, only verified numbers can be called.
    kiosk_test_call_numbers: str = Field(default="", alias="KIOSK_TEST_CALL_NUMBERS")

    # ─── Kiosk speech-to-text ─────────────────────────────────────────
    kiosk_stt_enabled: bool = Field(default=True, alias="KIOSK_STT_ENABLED")
    kiosk_stt_provider: str = Field(default="local", alias="KIOSK_STT_PROVIDER")  # local | openai | auto
    kiosk_stt_model_path: str = Field(
        default="/models/ggml-tiny.en-q5_1.bin",
        alias="KIOSK_STT_MODEL_PATH",
    )
    kiosk_stt_whisper_bin: str = Field(
        default="/usr/local/bin/whisper-cli",
        alias="KIOSK_STT_WHISPER_BIN",
    )
    kiosk_stt_max_seconds: int = Field(default=6, alias="KIOSK_STT_MAX_SECONDS")
    kiosk_stt_language: str = Field(default="en", alias="KIOSK_STT_LANGUAGE")
    kiosk_stt_openai_model: str = Field(
        default="gpt-4o-mini-transcribe",
        alias="KIOSK_STT_OPENAI_MODEL",
    )
    kiosk_stt_min_chars: int = Field(default=3, alias="KIOSK_STT_MIN_CHARS")
    kiosk_stt_max_upload_bytes: int = Field(
        default=8 * 1024 * 1024,
        alias="KIOSK_STT_MAX_UPLOAD_BYTES",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
