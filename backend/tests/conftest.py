"""Shared fixtures: every test gets a fresh app on an in-memory database."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture(name="settings")
def fixture_settings() -> Settings:
    return Settings(database_url="sqlite://", groq_api_key=None)


@pytest.fixture(name="app")
def fixture_app(settings):
    return create_app(settings)


@pytest.fixture(name="client")
def fixture_client(app):
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture(name="db_session")
def fixture_db_session(app):
    session = app.state.session_factory()
    try:
        yield session
    finally:
        session.close()
