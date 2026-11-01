from functools import lru_cache
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = BASE_DIR / "config"

def load_yaml(filepath: Path) -> Dict[str, Any]:
    """Helper to read YAML configuration files safely."""
    if not filepath.exists():
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

class Settings(BaseSettings):
    """
    Application Settings combining:
    - Dedicated YAML configuration files (config/app.yaml, config/ai.yaml, config/prompts.yaml)
    - Sensitive credentials and keys via .env / environment variables
    """
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # ----------------------------------------------------
    # SENSITIVE SECRETS & CORS (from .env)
    # ----------------------------------------------------
    SUPABASE_URL: str = Field(default="https://placeholder.supabase.co")
    SUPABASE_KEY: str = Field(default="placeholder-key")
    OPENROUTER_API_KEY: str = Field(default="placeholder-openrouter-key")
    N8N_API_KEY: str = Field(default="placeholder-n8n-key")
    CORS_ORIGINS: Optional[List[str]] = Field(default=None, alias="CORS_ORIGINS")
    MAGIC_LINK_BASE_URL: Optional[str] = Field(default=None, alias="MAGIC_LINK_BASE_URL")

    # Instant Dispatch & Remote Scheduler Trigger
    INSTANT_DISPATCH: bool = Field(default=False, alias="INSTANT_DISPATCH")
    SCHEDULER_URL: str = Field(default="https://lschedule.xseed.space", alias="SCHEDULER_URL")
    CRON_SECRET: Optional[str] = Field(default=None, alias="CRON_SECRET")
    FRONTEND_BASE_URL: str = Field(default="https://lfront.xseed.space", alias="FRONTEND_BASE_URL")

    # SMTP Configuration (for direct email delivery from backend when INSTANT_DISPATCH=true)
    SMTP_HOST: str = Field(default="smtp.hostinger.com", alias="SMTP_HOST")
    SMTP_PORT: int = Field(default=587, alias="SMTP_PORT")
    SMTP_USER: str = Field(default="education@xseed.space", alias="SMTP_USER")
    SMTP_PASSWORD: str = Field(default="", alias="SMTP_PASSWORD")
    SMTP_FROM_EMAIL: str = Field(default="education@xseed.space", alias="SMTP_FROM_EMAIL")
    SMTP_FROM_NAME: str = Field(default="Deutsch Daily", alias="SMTP_FROM_NAME")
    SMTP_USE_TLS: bool = Field(default=True, alias="SMTP_USE_TLS")
    SMTP_USE_SSL: bool = Field(default=False, alias="SMTP_USE_SSL")
    SMTP_TIMEOUT: int = Field(default=15, alias="SMTP_TIMEOUT")

    @property
    def is_smtp_configured(self) -> bool:
        return bool(self.SMTP_HOST and self.SMTP_USER and self.SMTP_PASSWORD)

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> Optional[List[str]]:
        if v is None:
            return None
        if isinstance(v, list):
            return [str(item).strip() for item in v if str(item).strip()]
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return []
            if s.startswith("[") and s.endswith("]"):
                try:
                    parsed = json.loads(s)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except Exception:
                    pass
            return [item.strip() for item in s.split(",") if item.strip()]
        return None

    # ----------------------------------------------------
    # LOADED FROM YAML CONFIGS
    # ----------------------------------------------------
    app_name: str = "German Exercise Platform"
    app_version: str = "1.0.0"
    app_environment: str = "development"

    server_host: str = "0.0.0.0"
    server_port: int = 8000
    server_reload: bool = True
    server_cors_origins: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]
    server_timeout_seconds: int = 30

    magic_link_timespan_days: int = 7
    magic_link_base_url: str = "http://localhost:5173/lesson"

    default_course_name: str = "German Theory"
    auto_provision_inactive: bool = True

    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "google/gemini-2.5-flash"
    openrouter_timeout_seconds: int = 45
    openrouter_max_retries: int = 3
    openrouter_site_url: str = "https://german-exercises.local"
    openrouter_site_name: str = "German AI Exercises"

    ai_generation_temperature: float = 0.2
    ai_generation_max_tokens: int = 3500

    ai_evaluation_temperature: float = 0.1
    ai_evaluation_max_tokens: int = 800

    # Prompts dictionary loaded from config/prompts.yaml
    prompts: Dict[str, Any] = Field(default_factory=dict)

    def __init__(self, **values):
        super().__init__(**values)
        self._load_yaml_configurations()

    def _load_yaml_configurations(self):
        # 1. Load app.yaml
        app_data = load_yaml(CONFIG_DIR / "app.yaml")
        if "app" in app_data:
            self.app_name = app_data["app"].get("name", self.app_name)
            self.app_version = app_data["app"].get("version", self.app_version)
            self.app_environment = app_data["app"].get("environment", self.app_environment)
        if "server" in app_data:
            self.server_host = app_data["server"].get("host", self.server_host)
            self.server_port = app_data["server"].get("port", self.server_port)
            self.server_reload = app_data["server"].get("reload", self.server_reload)
            yaml_cors = app_data["server"].get("cors_origins", self.server_cors_origins)
            if self.CORS_ORIGINS is not None and len(self.CORS_ORIGINS) > 0:
                self.server_cors_origins = self.CORS_ORIGINS
            else:
                self.server_cors_origins = yaml_cors
            self.server_timeout_seconds = app_data["server"].get("timeout_seconds", self.server_timeout_seconds)
        if "magic_links" in app_data:
            self.magic_link_timespan_days = app_data["magic_links"].get("timespan_days", self.magic_link_timespan_days)
            yaml_magic = app_data["magic_links"].get("base_url", self.magic_link_base_url)
            self.magic_link_base_url = self.MAGIC_LINK_BASE_URL or yaml_magic
        if "courses" in app_data:
            self.default_course_name = app_data["courses"].get("default_course_name", self.default_course_name)
            self.auto_provision_inactive = app_data["courses"].get("auto_provision_inactive", self.auto_provision_inactive)
            if "instant_dispatch" in app_data["courses"]:
                import os
                if "INSTANT_DISPATCH" not in os.environ:
                    self.INSTANT_DISPATCH = bool(app_data["courses"]["instant_dispatch"])

        # 2. Load ai.yaml
        ai_data = load_yaml(CONFIG_DIR / "ai.yaml")
        if "openrouter" in ai_data:
            self.openrouter_base_url = ai_data["openrouter"].get("base_url", self.openrouter_base_url)
            self.openrouter_model = ai_data["openrouter"].get("model", self.openrouter_model)
            self.openrouter_timeout_seconds = ai_data["openrouter"].get("timeout_seconds", self.openrouter_timeout_seconds)
            self.openrouter_max_retries = ai_data["openrouter"].get("max_retries", self.openrouter_max_retries)
            self.openrouter_site_url = ai_data["openrouter"].get("site_url", self.openrouter_site_url)
            self.openrouter_site_name = ai_data["openrouter"].get("site_name", self.openrouter_site_name)
        if "generation" in ai_data:
            self.ai_generation_temperature = ai_data["generation"].get("temperature", self.ai_generation_temperature)
            self.ai_generation_max_tokens = ai_data["generation"].get("max_tokens", self.ai_generation_max_tokens)
        if "evaluation" in ai_data:
            self.ai_evaluation_temperature = ai_data["evaluation"].get("temperature", self.ai_evaluation_temperature)
            self.ai_evaluation_max_tokens = ai_data["evaluation"].get("max_tokens", self.ai_evaluation_max_tokens)

        # 3. Load prompts.yaml
        prompts_data = load_yaml(CONFIG_DIR / "prompts.yaml")
        if "prompts" in prompts_data:
            self.prompts = prompts_data["prompts"]

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
