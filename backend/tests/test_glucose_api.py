"""End-to-end tests of the glucose and trends API on a real SQLite database."""

from datetime import datetime, timedelta, timezone

import pytest

from app.domain.glucose import MAX_GLUCOSE_MG_DL

HOUR = timedelta(hours=1)


def _at(hours_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()


def _post(client, value=110, hours_ago=1.0, context="fasting"):
    return client.post("/api/glucose", json={"value_mg_dl": value,
                                             "measured_at": _at(hours_ago),
                                             "context": context})


# --- Glucose readings ------------------------------------------------------------------------

def test_post_valid_reading_returns_201_and_the_reading(client):
    response = _post(client, value=145, context="after_meal")
    assert response.status_code == 201
    body = response.json()
    assert body["value_mg_dl"] == 145
    assert body["context"] == "after_meal"
    assert body["id"] > 0


@pytest.mark.parametrize("value", [19, MAX_GLUCOSE_MG_DL + 1])
def test_out_of_range_value_returns_422_on_that_field(client, value):
    response = _post(client, value=value)
    assert response.status_code == 422
    assert response.json()["error"]["fields"][0]["field"] == "value_mg_dl"


def test_future_reading_returns_422_invalid_reading(client):
    response = _post(client, hours_ago=-1)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_reading"


def test_unknown_context_returns_422_on_that_field(client):
    response = _post(client, context="lunchtime")
    assert response.status_code == 422
    assert response.json()["error"]["fields"][0]["field"] == "context"


def test_missing_value_returns_422(client):
    response = client.post("/api/glucose", json={"measured_at": _at(1), "context": "fasting"})
    assert response.status_code == 422


def test_list_is_newest_first(client):
    older = _post(client, hours_ago=5).json()["id"]
    newer = _post(client, hours_ago=1).json()["id"]
    assert [r["id"] for r in client.get("/api/glucose").json()] == [newer, older]


def test_list_filters_by_date_range(client):
    _post(client, hours_ago=50)
    inside = _post(client, hours_ago=5).json()["id"]
    response = client.get("/api/glucose", params={"start": _at(24), "end": _at(0)})
    assert [r["id"] for r in response.json()] == [inside]


def test_start_after_end_returns_422(client):
    response = client.get("/api/glucose", params={"start": _at(0), "end": _at(24)})
    assert response.status_code == 422


def test_delete_then_delete_again(client):
    reading_id = _post(client).json()["id"]
    assert client.delete(f"/api/glucose/{reading_id}").status_code == 204
    second = client.delete(f"/api/glucose/{reading_id}")
    assert second.status_code == 404
    assert second.json()["error"]["code"] == "not_found"


# --- Trends -----------------------------------------------------------------------------------

def test_trends_report_counts_percentage_and_points(client):
    for value in (65, 100, 150, 200):
        _post(client, value=value, hours_ago=2)
    body = client.get("/api/trends", params={"days": 7}).json()
    assert (body["total"], body["low"], body["in_range"], body["high"]) == (4, 1, 2, 1)
    assert body["time_in_range_percent"] == 50.0
    assert {p["level"] for p in body["points"]} == {"low", "in_range", "high"}


def test_trends_reports_post_meal_highs_with_guidance(client):
    for hours_ago in (2, 26, 50):
        _post(client, value=220, hours_ago=hours_ago, context="after_meal")
    findings = client.get("/api/trends").json()["findings"]
    assert [f["code"] for f in findings] == ["post_meal_highs"]
    assert "180 mg/dL" in findings[0]["message"]


def test_trends_with_no_readings(client):
    body = client.get("/api/trends").json()
    assert body["total"] == 0
    assert body["time_in_range_percent"] is None
    assert body["findings"] == []


def test_trends_period_must_be_7_14_or_30(client):
    response = client.get("/api/trends", params={"days": 10})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_reading"
