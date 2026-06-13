"""
config.py — Backend configuration and environment variables
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str

    # Clerk
    clerk_secret_key: str

    # Cloudflare R2
    r2_access_key_id: str
    r2_secret_access_key: str
    r2_endpoint: str
    r2_bucket_name: str
    r2_public_url: str = ""

    # AI APIs (passed through to agent)
    anthropic_api_key: str
    elevenlabs_api_key: str
    pexels_api_key: str

    # Redis (for Celery)
    redis_url: str = "redis://localhost:6379/0"

    # App
    app_env: str = "development"
    frontend_url: str = "http://localhost:3000"

    # Encryption key for storing OAuth tokens
    encryption_key: str = ""

    # Google OAuth for YouTube
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "https://youtube-agent-production-9eee.up.railway.app/auth/youtube/callback"

    class Config:
        env_file = "../.env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
