"""The app factory wires settings, database, CORS and routes."""

from app.infrastructure.db.init_db import DEFAULT_PATIENT_ID
from app.infrastructure.db.models import PatientRow


def test_health_reports_api_and_database_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_factory_uses_the_given_settings(app, settings):
    assert app.state.settings is settings


def test_factory_initialises_the_database(db_session):
    assert db_session.get(PatientRow, DEFAULT_PATIENT_ID) is not None


def test_frontend_origin_is_allowed(client):
    response = client.options(
        "/api/health",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_unknown_route_returns_404(client):
    assert client.get("/api/does-not-exist").status_code == 404
