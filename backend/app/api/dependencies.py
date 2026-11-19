"""Shared FastAPI dependencies (Dependency Inversion: routers receive what they need)."""

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.config import Settings


def get_settings(request: Request) -> Settings:
    """Settings the app was created with."""
    return request.app.state.settings


def get_db(request: Request) -> Iterator[Session]:
    """Open one Session per request and always close it."""
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()
