from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_secret_key: str = "dev-secret-change-me"
    app_env: str = "development"
    app_base_url: str = "http://localhost:8000"

    database_url: str = "postgresql+asyncpg://gitpulse:gitpulse_dev@db:5432/gitpulse"

    github_client_id: str = ""
    github_client_secret: str = ""

    # ── AI provider chain ──────────────────────────────────────────────────
    # Comma-separated list of  "<provider>:<api_key>"
    # Supported providers: openai, anthropic, groq, openrouter
    # System tries them in order; moves to next on any error.
    # Example:
    #   AI_PROVIDERS=openai:sk-abc...,groq:gsk_xyz...,anthropic:sk-ant-...
    ai_providers: str = ""

    # Legacy single-key support (auto-converted to ai_providers if set)
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    resend_api_key: str = ""
    resend_from_email: str = "noreply@gitpulse.io"

    lemonsqueezy_api_key: str = ""
    lemonsqueezy_webhook_secret: str = ""
    lemonsqueezy_store_id: str = ""
    lemonsqueezy_starter_variant_id: str = ""
    lemonsqueezy_pro_variant_id: str = ""

    free_changelog_limit: int = 3
    starter_changelog_limit: int = 20

    @property
    def is_dev(self) -> bool:
        return self.app_env == "development"

    def get_ai_providers_string(self) -> str:
        """
        Return ai_providers string, falling back to legacy single keys
        so existing .env files keep working without changes.
        """
        if self.ai_providers.strip():
            return self.ai_providers.strip()
        # Build from legacy keys
        parts = []
        if self.openai_api_key:
            parts.append(f"openai:{self.openai_api_key}")
        if self.anthropic_api_key:
            parts.append(f"anthropic:{self.anthropic_api_key}")
        return ",".join(parts)


settings = Settings()
# Patch ai_providers to include legacy keys so ai.py only needs to read one field
if not settings.ai_providers.strip():
    settings.ai_providers = settings.get_ai_providers_string()
