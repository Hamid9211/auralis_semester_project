"""End-to-end tests of the foods and meals API on a real SQLite database."""

from datetime import datetime, timedelta, timezone

import pytest


def _at(hours_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()


def _food_id(client, name: str) -> int:
    return client.get("/api/foods", params={"q": name}).json()[0]["id"]


def _post_meal(client, items, hours_ago=1.0, meal_type="lunch"):
    return client.post("/api/meals", json={"meal_type": meal_type, "eaten_at": _at(hours_ago),
                                           "items": items})


# --- FR-ML-01 ----------------------------------------------------------------------------

def test_food_search_returns_suggestions(client):
    response = client.get("/api/foods", params={"q": "rice"})
    assert response.status_code == 200
    assert [f["name"] for f in response.json()] == ["Brown rice, cooked", "Rice, white, cooked"]


def test_empty_food_search_returns_422(client):
    response = client.get("/api/foods", params={"q": " "})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_meal"


# --- FR-ML-02 / FR-ML-03 ---------------------------------------------------------------------

def test_post_meal_returns_items_and_totals(client):
    rice, daal = _food_id(client, "Rice, white"), _food_id(client, "Daal")
    response = _post_meal(client, [{"food_id": rice, "portion": 1.0},
                                   {"food_id": daal, "portion": 0.5}])
    assert response.status_code == 201
    body = response.json()
    assert body["total_carbs_g"] == 65.0
    assert body["total_calories_kcal"] == 320.0
    assert [i["carbs_g"] for i in body["items"]] == [45.0, 20.0]


@pytest.mark.parametrize("portion", [0.4, 3.1])
def test_portion_outside_range_returns_422_on_that_field(client, portion):
    response = _post_meal(client, [{"food_id": _food_id(client, "Roti"), "portion": portion}])
    assert response.status_code == 422
    assert response.json()["error"]["fields"][0]["field"] == "items.0.portion"


def test_meal_without_items_returns_422(client):
    assert _post_meal(client, []).status_code == 422


def test_unknown_food_returns_422(client):
    response = _post_meal(client, [{"food_id": 9999, "portion": 1.0}])
    assert response.status_code == 422
    assert "9999" in response.json()["error"]["message"]


def test_unknown_meal_type_returns_422(client):
    response = _post_meal(client, [{"food_id": _food_id(client, "Roti"), "portion": 1}],
                          meal_type="brunch")
    assert response.status_code == 422


def test_future_meal_returns_422(client):
    response = _post_meal(client, [{"food_id": _food_id(client, "Roti"), "portion": 1}],
                          hours_ago=-1)
    assert response.status_code == 422


def test_list_meals_newest_first(client):
    roti = _food_id(client, "Roti")
    older = _post_meal(client, [{"food_id": roti, "portion": 1}], hours_ago=5).json()["id"]
    newer = _post_meal(client, [{"food_id": roti, "portion": 1}], hours_ago=1).json()["id"]
    assert [m["id"] for m in client.get("/api/meals").json()] == [newer, older]


# --- FR-ML-04 / FR-ML-05 -----------------------------------------------------------------------

def test_daily_totals_for_7_days(client):
    _post_meal(client, [{"food_id": _food_id(client, "Roti"), "portion": 2}], hours_ago=0.1)
    totals = client.get("/api/meals/daily-totals").json()
    assert len(totals) == 7
    assert sum(t["carbs_g"] for t in totals) == 36.0


def test_daily_totals_period_is_validated(client):
    assert client.get("/api/meals/daily-totals", params={"days": 31}).status_code == 422


def test_meal_followed_by_high_after_meal_reading_is_flagged(client):
    rice = _food_id(client, "Rice, white")
    meal_id = _post_meal(client, [{"food_id": rice, "portion": 2}], hours_ago=3).json()["id"]
    client.post("/api/glucose", json={"value_mg_dl": 230, "measured_at": _at(2),
                                      "context": "after_meal"})
    impact = client.get("/api/meals/impact").json()
    assert impact[0]["meal"]["id"] == meal_id
    assert impact[0]["reading"]["value_mg_dl"] == 230
    assert impact[0]["is_high"] is True
