"""Tests for configuration."""

import pytest
from app.config import Settings


def test_default_settings():
    """Test default configuration values."""
    settings = Settings()

    assert settings.app_name == "codereview-agent"
    assert settings.environment == "development"
    assert settings.log_level == "INFO"
    assert settings.api_host == "0.0.0.0"
    assert settings.api_port == 8000
    assert settings.default_llm_provider == "anthropic"
    assert settings.model_simple == "claude-3-5-haiku-20241022"
    assert settings.model_complex == "claude-3-5-sonnet-20241022"
    assert settings.max_files_per_pr == 50
    assert settings.max_total_diff_tokens == 50000


def test_settings_from_env(monkeypatch):
    """Test settings loaded from environment variables."""
    monkeypatch.setenv("APP_NAME", "custom-agent")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    monkeypatch.setenv("API_PORT", "9000")
    monkeypatch.setenv("DEFAULT_LLM_PROVIDER", "openai")
    monkeypatch.setenv("MAX_FILES_PER_PR", "100")

    settings = Settings()

    assert settings.app_name == "custom-agent"
    assert settings.environment == "production"
    assert settings.log_level == "WARNING"
    assert settings.api_port == 9000
    assert settings.default_llm_provider == "openai"
    assert settings.max_files_per_pr == 100


def test_settings_secret_handling():
    """Test SecretStr fields."""
    settings = Settings(
        github_token="ghp_test123",
        anthropic_api_key="sk-ant-test456",
    )

    assert settings.github_token.get_secret_value() == "ghp_test123"
    assert settings.anthropic_api_key.get_secret_value() == "sk-ant-test456"

    # Test repr doesn't leak secrets
    assert "ghp_test123" not in repr(settings)
    assert "sk-ant-test456" not in repr(settings)


def test_feature_flags_defaults():
    """Test feature flag defaults."""
    settings = Settings()

    assert settings.enable_security_agent is True
    assert settings.enable_performance_agent is True
    assert settings.enable_style_agent is True
    assert settings.enable_architecture_agent is True
    assert settings.enable_tests_agent is True
    assert settings.enable_learning_loop is False


def test_langsmith_settings():
    """Test LangSmith configuration."""
    settings = Settings(
        langsmith_api_key="lsv2_test",
        langsmith_project="custom-project",
        langsmith_tracing=False,
    )

    assert settings.langsmith_api_key.get_secret_value() == "lsv2_test"
    assert settings.langsmith_project == "custom-project"
    assert settings.langsmith_tracing is False