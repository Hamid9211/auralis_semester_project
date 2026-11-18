"""Settings are read from the environment with safe defaults."""

import dataclasses

import pytest

from app.core.config import Settings

ENV_VARS = ("DATABASE_URL", "GROQ_API_KEY", "GROQ_MODEL", "LLM_TIMEOUT_SECONDS",
            "MAX_UPLOAD_MB", "CORS_ORIGINS")


@pytest.fixture(name="clean_env")
def fixture_clean_env(monkeypatch):
    """Remove Auralis variables and stop a local .env file from leaking in."""
    for var in ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr("app.core.config.load_dotenv", lambda: None)
    return monkeypatch


def test_defaults_when_environment_is_empty(clean_env):  # pylint: disable=unused-argument
    settings = Settings.from_env()
    assert settings.database_url == "sqlite:///./auralis.db"
    assert settings.max_upload_bytes == 5 * 1024 * 1024
    assert settings.groq_api_key is None
    assert settings.llm_enabled is False


def test_values_are_read_from_environment(clean_env):
    clean_env.setenv("DATABASE_URL", "sqlite:///./other.db")
    clean_env.setenv("GROQ_API_KEY", "test-key")
    clean_env.setenv("MAX_UPLOAD_MB", "2")
    clean_env.setenv("CORS_ORIGINS", "http://a.test, http://b.test")
    settings = Settings.from_env()
    assert settings.database_url == "sqlite:///./other.db"
    assert settings.llm_enabled is True
    assert settings.max_upload_bytes == 2 * 1024 * 1024
    assert settings.cors_origins == ("http://a.test", "http://b.test")


def test_empty_api_key_means_llm_disabled(clean_env):
    clean_env.setenv("GROQ_API_KEY", "")
    assert Settings.from_env().llm_enabled is False


def test_settings_are_immutable():
    with pytest.raises(dataclasses.FrozenInstanceError):
        Settings().database_url = "changed"  # type: ignore[misc]
