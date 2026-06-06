import os

from pydantic_settings import BaseSettings, SettingsConfigDict  # pyright: ignore[reportMissingImports]

_IS_VERCEL = bool(os.getenv("VERCEL"))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"
    closing_heading_default: str = "A manner of closing"
    upload_dir: str = "/tmp/uploads" if _IS_VERCEL else "uploads"
    output_dir: str = "/tmp/output" if _IS_VERCEL else "output"


settings = Settings()
