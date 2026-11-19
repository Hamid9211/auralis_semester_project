"""End-to-end tests of the lab report API (FR-RA-01..05, NFR-03, NFR-06).

These use the real SQLite repository, the real PyMuPDF extractor and the
real background workers; only the LLM is replaced.
"""

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from report_fakes import FakeGenerator

from app.core.config import Settings
from app.main import create_app

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_PDF = (FIXTURES / "sample_lab_report.pdf").read_bytes()
POLL_SECONDS = 10


def _client(generator=None, max_upload_mb=5) -> TestClient:
    settings = Settings(database_url="sqlite://", groq_api_key=None,
                        max_upload_bytes=max_upload_mb * 1024 * 1024)
    app = create_app(settings, explanation_generator=generator)
    return TestClient(app, raise_server_exceptions=False)


def _upload(client, data=SAMPLE_PDF, name="lab.pdf", content_type="application/pdf"):
    return client.post("/api/reports", files={"file": (name, data, content_type)})


def _wait_until_finished(client, report_id) -> dict:
    deadline = time.monotonic() + POLL_SECONDS
    while time.monotonic() < deadline:
        body = client.get(f"/api/reports/{report_id}").json()
        if body["status"] in ("done", "failed"):
            return body
        time.sleep(0.05)
    pytest.fail(f"report {report_id} did not finish within {POLL_SECONDS} s")


@pytest.fixture(name="client")
def fixture_client():
    with _client() as client:
        yield client


def test_upload_is_accepted_immediately_as_pending_or_later(client):
    response = _upload(client)
    assert response.status_code == 202
    body = response.json()
    assert body["filename"] == "lab.pdf"
    assert body["status"] in ("pending", "processing", "done")


def test_uploaded_report_is_processed_in_the_background(client):
    report_id = _upload(client).json()["id"]
    body = _wait_until_finished(client, report_id)
    assert body["status"] == "done"
    values = {v["test_name"]: v for v in body["values"]}
    assert set(values) == {"hba1c", "fasting_glucose", "ldl_cholesterol", "creatinine"}
    assert values["hba1c"]["value"] == 6.8
    assert values["hba1c"]["is_normal"] is False
    assert values["creatinine"]["is_normal"] is True
    assert values["hba1c"]["normal_range"] == "4-5.6 %"
    assert body["explanation_source"] == "template"
    assert "HbA1c" in body["explanation"]


def test_llm_failure_still_gives_values_and_template_explanation():
    with _client(generator=FakeGenerator("llm", fail=True)) as client:
        body = _wait_until_finished(client, _upload(client).json()["id"])
    assert body["status"] == "done"
    assert body["explanation_source"] == "template"
    assert len(body["values"]) == 4


def test_working_llm_explanation_is_used():
    with _client(generator=FakeGenerator("llm")) as client:
        body = _wait_until_finished(client, _upload(client).json()["id"])
    assert body["explanation_source"] == "llm"


def test_corrupt_pdf_is_marked_failed(client):
    response = _upload(client, data=b"%PDF-1.4\nbroken content")
    body = _wait_until_finished(client, response.json()["id"])
    assert body["status"] == "failed"
    assert body["error_message"]


def test_duplicate_upload_returns_409(client):
    _upload(client)
    response = _upload(client, name="again.pdf")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "duplicate_report"


def test_non_pdf_upload_returns_400(client):
    response = _upload(client, data=b"hello", name="notes.txt", content_type="text/plain")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_file"


def test_oversized_upload_returns_400():
    with _client(max_upload_mb=1) as client:
        response = _upload(client, data=b"%PDF-" + b"0" * (1024 * 1024))
    assert response.status_code == 400
    assert "larger than 1 MB" in response.json()["error"]["message"]


def test_missing_file_field_returns_422_with_field_name(client):
    response = client.post("/api/reports")
    assert response.status_code == 422
    assert response.json()["error"]["fields"][0]["field"] == "file"


def test_list_reports_shows_all_reports_newest_first(client):
    first = _upload(client, name="a.pdf").json()["id"]
    second = _upload(client, data=SAMPLE_PDF + b"\n%second", name="b.pdf").json()["id"]
    ids = [r["id"] for r in client.get("/api/reports").json()]
    assert ids == [second, first]


def test_unknown_report_returns_404(client):
    response = client.get("/api/reports/999")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_report_id_must_be_positive(client):
    assert client.get("/api/reports/0").status_code == 422
