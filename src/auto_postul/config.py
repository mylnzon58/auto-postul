"""Configuración de la aplicación, validada y cargada desde el entorno."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from platformdirs import user_data_dir
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Configuración local. Los secretos se leen del entorno, nunca del repo."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_host: str = "127.0.0.1"
    app_port: int = 8765
    app_env: str = "local"
    app_password: str = ""
    session_secret: str = "dev-only-change-me"
    app_data_dir: Path | None = None

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"
    gemini_cv_extraction: bool = True
    gemini_job_extraction: bool = False

    linkedin_mcp_version: str = "4.28.0"
    linkedin_headless: bool = True
    linkedin_tool_timeout: int = 300

    apply_headless: bool = False
    apply_dry_run: bool = True
    apply_live_submit: bool = False
    apply_max_steps: int = 8
    apply_action_delay_ms: int = 700
    apply_action_delay_jitter_ms: int = 500
    apply_human_typing: bool = True
    remote_only: bool = True

    daily_scan_limit: int = 1
    daily_job_detail_limit: int = 25
    daily_apply_limit: int = 5
    mcp_calls_per_minute: int = 8

    @field_validator("app_data_dir", mode="before")
    @classmethod
    def empty_path_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def data_dir(self) -> Path:
        """Directorio de datos fuera del repo, salvo que se indique otro."""
        base = self.app_data_dir or Path(user_data_dir("AutoPostul", "mylnzon58"))
        base.mkdir(parents=True, exist_ok=True)
        return base

    @property
    def artifacts_dir(self) -> Path:
        path = self.data_dir / "artifacts"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def documents_dir(self) -> Path:
        path = self.data_dir / "documents"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def database_path(self) -> Path:
        return self.data_dir / "auto_postul.sqlite"

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.database_path}"

    @property
    def linkedin_profile_dir(self) -> Path:
        # El MCP rota el perfil y su padre. Este directorio solo contiene LinkedIn.
        path = self.data_dir / "linkedin" / "profile"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def linkedin_parent_dir(self) -> Path:
        return self.linkedin_profile_dir.parent

    @property
    def cv_input_dir(self) -> Path:
        return PROJECT_ROOT

    @property
    def gemini_enabled(self) -> bool:
        return bool(self.gemini_api_key.strip())

    @property
    def live_submit_enabled(self) -> bool:
        return self.apply_live_submit and not self.apply_dry_run


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Devuelve la configuración una sola vez por proceso."""
    return Settings()
