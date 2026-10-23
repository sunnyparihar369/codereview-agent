"""Configuration management using Pydantic Settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "codereview-agent"
    environment: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # GitHub
    github_app_id: str | None = None
    github_app_private_key: SecretStr | None = None
    github_webhook_secret: SecretStr | None = None
    github_token: SecretStr | None = Field(default=None, description="Personal access token for API access")

    # GitLab (optional)
    gitlab_url: str = "https://gitlab.com"
    gitlab_token: SecretStr | None = None
    gitlab_webhook_secret: SecretStr | None = None

    # LLM Providers
    default_llm_provider: Literal["openai", "anthropic", "gemini"] = "anthropic"
    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None

    # Model selection per task complexity
    model_simple: str = "claude-3-5-haiku-20241022"
    model_complex: str = "claude-3-5-sonnet-20241022"
    model_embedding: str = "text-embedding-3-small"

    # LangSmith
    langsmith_api_key: SecretStr | None = None
    langsmith_project: str = "codereview-agent"
    langsmith_tracing: bool = True

    # Agent Configuration
    max_file_size_kb: int = 100
    max_files_per_pr: int = 50
    max_total_diff_tokens: int = 50000
    review_timeout_seconds: int = 120

    # Specialist Agent Thresholds
    security_severity_threshold: Literal["low", "medium", "high", "critical"] = "medium"
    performance_complexity_threshold: int = 10  # cyclomatic complexity
    style_max_line_length: int = 100

    # Prometheus Metrics
    metrics_enabled: bool = True
    metrics_port: int = 9090

    # Feature Flags
    enable_security_agent: bool = True
    enable_performance_agent: bool = True
    enable_style_agent: bool = True
    enable_architecture_agent: bool = True
    enable_tests_agent: bool = True
    enable_learning_loop: bool = False  # Requires feedback storage


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()