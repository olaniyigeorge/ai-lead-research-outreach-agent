from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    anthropic_api_key: str = ""

    supabase_url: str = ""
    supabase_publishable_key: str = ""

    app_session_ttl_minutes: int = 60

    apify_api_token: str = ""

    lead_count_hard_cap: int = 25

    # After this many rejected objectives (gibberish or failed sanity check)
    # within the cooldown window, further POST /runs attempts are blocked
    # until the window rolls past -- protects against burning sanity-check
    # (and, if someone crafts around the regex, ICP-refinement) tokens on
    # repeated bad-faith submissions.
    vague_objective_max_attempts: int = 3
    vague_objective_cooldown_minutes: int = 30

    # Resend -- used directly by app code only for this one notification
    # (access-granted emails). Auth OTP emails still go through Supabase's
    # own custom-SMTP config, unrelated to this.
    resend_api_key: str = ""
    email_from_address: str = ""
    email_from_name: str = ""
    app_url: str = "http://localhost:3000"

    # Comma-separated list of origins the browser is allowed to call the API
    # from. Defaults cover local dev + the deployed frontend (per README) so
    # prod works out of the box, but this is meant to be overridden via the
    # CORS_ALLOWED_ORIGINS env var on Render, not edited here, since the
    # origin can change (custom domain, new Vercel project) independently of
    # a code deploy.
    cors_allowed_origins: str = "http://localhost:3000,https://ai-lead-research-outreach-agent.vercel.app"

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
