"""Application settings, read once from environment variables."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

_DEFAULT_DATABASE_URL = "sqlite:///./auralis.db"
_DEFAULT_GROQ_MODEL = "llama-3.1-8b-instant"
_DEFAULT_LLM_TIMEOUT_SECONDS = 15.0
_DEFAULT_MAX_UPLOAD_MB = 5
_DEFAULT_CORS_ORIGINS = "http://localhost:5173"


@dataclass(frozen=True)
class Settings:
    """Immutable configuration passed to the app factory.

    Frozen so no module can change configuration at runtime; tests build
    their own Settings instead of patching globals.
    """

    database_url: str = _DEFAULT_DATABASE_URL
    groq_api_key: str | None = None
    groq_model: str = _DEFAULT_GROQ_MODEL
    llm_timeout_seconds: float = _DEFAULT_LLM_TIMEOUT_SECONDS
    max_upload_bytes: int = _DEFAULT_MAX_UPLOAD_MB * 1024 * 1024
    cors_origins: tuple[str, ...] = (_DEFAULT_CORS_ORIGINS,)

    @property
    def llm_enabled(self) -> bool:
        """True when a Groq API key is configured."""
        return bool(self.groq_api_key)

    @classmethod
    def from_env(cls) -> "Settings":
        """Build settings from environment variables (and a .env file if present)."""
        load_dotenv()
        origins = os.getenv("CORS_ORIGINS", _DEFAULT_CORS_ORIGINS)
        return cls(
            database_url=os.getenv("DATABASE_URL", _DEFAULT_DATABASE_URL),
            groq_api_key=os.getenv("GROQ_API_KEY") or None,
            groq_model=os.getenv("GROQ_MODEL", _DEFAULT_GROQ_MODEL),
            llm_timeout_seconds=float(
                os.getenv("LLM_TIMEOUT_SECONDS", str(_DEFAULT_LLM_TIMEOUT_SECONDS))
            ),
            max_upload_bytes=int(os.getenv("MAX_UPLOAD_MB", str(_DEFAULT_MAX_UPLOAD_MB)))
            * 1024
            * 1024,
            cors_origins=tuple(o.strip() for o in origins.split(",") if o.strip()),
        )
