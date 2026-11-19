"""Domain errors are mapped to HTTP responses with one consistent body shape."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from app.api.error_handlers import register_error_handlers, status_for
from app.core.exceptions import (
    AuralisError,
    ExplanationError,
    ExtractionError,
    InvalidFileError,
    InvalidReadingError,
    NotFoundError,
)

ERROR_CASES = [
    (InvalidReadingError, 422, "invalid_reading"),
    (NotFoundError, 404, "not_found"),
    (InvalidFileError, 400, "invalid_file"),
    (ExtractionError, 422, "extraction_failed"),
    (ExplanationError, 502, "explanation_failed"),
]


class _Reading(BaseModel):
    value_mg_dl: float = Field(ge=20, le=600)


class _DuplicateFileError(InvalidFileError):
    """A module-specific subclass should inherit the parent's status."""


def _build_client() -> TestClient:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/raise/{index}")
    def raise_error(index: int):
        error_cls = ERROR_CASES[index][0]
        raise error_cls("something went wrong")

    @app.get("/crash")
    def crash():
        raise RuntimeError("secret internal detail")

    @app.post("/readings")
    def create_reading(reading: _Reading):
        return reading

    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(name="client")
def fixture_client() -> TestClient:
    return _build_client()


@pytest.mark.parametrize("index", range(len(ERROR_CASES)))
def test_domain_error_maps_to_status_and_body(client, index):
    _, expected_status, expected_code = ERROR_CASES[index]
    response = client.get(f"/raise/{index}")
    assert response.status_code == expected_status
    assert response.json() == {
        "error": {"code": expected_code, "message": "something went wrong"}
    }


def test_subclass_inherits_parent_status():
    assert status_for(_DuplicateFileError("dup")) == 400


def test_base_error_without_mapping_is_500():
    assert status_for(AuralisError("generic")) == 500


def test_unexpected_error_returns_500_without_leaking_details(client):
    response = client.get("/crash")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "secret" not in response.text


def test_schema_error_lists_the_failing_field(client):
    response = client.post("/readings", json={"value_mg_dl": 601})
    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "validation_error"
    assert body["fields"][0]["field"] == "value_mg_dl"
