from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_secret_key: str = "dev-secret-change-me"
    app_env: str = "development"
    app_base_url: str = "http://localhost:8000"

    database_url: str = "postgresql+asyncpg://gitpulse:gitpulse_dev@db:5432/gitpulse"

    github_client_id: str = ""
    github_client_secret: str = ""

    # AI provider chain
    ai_providers: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # Email
    resend_api_key: str = ""
    resend_from_email: str = "noreply@gitpulse.io"

    # Polar.sh payments
    polar_access_token: str = ""
    polar_webhook_secret: str = ""
    polar_starter_product_id: str = ""
    polar_pro_product_id: str = ""
    polar_env: str = "sandbox"  # "sandbox" or "production"

    free_changelog_limit: int = 3
    starter_changelog_limit: int = 20

    @property
    def is_dev(self) -> bool:
        return self.app_env == "development"

    @property
    def polar_server(self) -> str:
        return "sandbox" if self.polar_env == "sandbox" else "production"

    def get_ai_providers_string(self) -> str:
        if self.ai_providers.strip():
            return self.ai_providers.strip()
        parts = []
        if self.openai_api_key:
            parts.append(f"openai:{self.openai_api_key}")
        if self.anthropic_api_key:
            parts.append(f"anthropic:{self.anthropic_api_key}")
        return ",".join(parts)


settings = Settings()
if not settings.ai_providers.strip():
    settings.ai_providers = settings.get_ai_providers_string()
