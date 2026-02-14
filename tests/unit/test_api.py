"""Unit tests for API endpoints."""
import os

from fastapi.testclient import TestClient

os.environ.setdefault("MODEL_BACKEND", "local")
os.environ.setdefault("MODEL_ARTIFACT_PATH", "artifacts/demo_model.joblib")
os.environ.setdefault("DEMO_API_TOKEN", "test-token")
os.environ.setdefault("API_SECRET_KEY", "test-token")

from api.main import app  # noqa: E402


PAYLOAD = {
    "temperature": -15.5,
    "wind_speed": 25.0,
    "wind_chill": -28.0,
    "precipitation": 2.5,
    "snow_depth": 30.0,
    "hour": 8,
    "day_of_week": 1,
    "month": 1,
    "neighborhood": "Unknown-Neighborhood",
    "ses_index": 0.45,
    "infrastructure_quality": 0.70,
}

WARM_PAYLOAD = {
    "temperature": 20.0,
    "wind_speed": 0.0,
    "wind_chill": 5.0,
    "precipitation": 1.0,
    "snow_depth": 5.0,
    "hour": 13,
    "day_of_week": 1,
    "month": 1,
    "neighborhood": "Downtown",
    "ses_index": 0.45,
    "infrastructure_quality": 0.70,
}

OVERNIGHT_DEEP_FREEZE_PAYLOAD = {
    "temperature": -22.0,
    "wind_speed": 30.0,
    "wind_chill": -35.0,
    "precipitation": 0.3,
    "snow_depth": 10.0,
    "hour": 22,
    "day_of_week": 6,
    "month": 2,
    "neighborhood": "Jasper Place",
    "ses_index": 0.33,
    "infrastructure_quality": 0.40,
}


def auth_header(token: str = "test-token") -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_landing_page():
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "Winter Injury Risk" in response.text
        assert "/docs" in response.text
        assert 'id="map"' in response.text
        assert "/static/js/map-app.js" in response.text


def test_api_info():
    with TestClient(app) as client:
        response = client.get("/api/info")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "operational"
        assert data["docs"] == "/docs"


def test_static_assets_served():
    with TestClient(app) as client:
        css = client.get("/static/css/map.css")
        assert css.status_code == 200
        assert "map-frame" in css.text

        js = client.get("/static/js/map-app.js")
        assert js.status_code == 200
        assert "loadNeighborhoodRisk" in js.text


def test_health_check():
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "model_loaded" in data
        assert "database" in data


def test_model_info():
    with TestClient(app) as client:
        response = client.get("/model/info")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data


def test_predict_requires_auth():
    with TestClient(app) as client:
        response = client.post("/predict", json=PAYLOAD)
        assert response.status_code == 401


def test_predict_invalid_token():
    with TestClient(app) as client:
        response = client.post(
            "/predict",
            json=PAYLOAD,
            headers=auth_header("invalid-token"),
        )
        assert response.status_code == 401


def test_predict_success():
    with TestClient(app) as client:
        response = client.post(
            "/predict",
            json=PAYLOAD,
            headers=auth_header(),
        )
        assert response.status_code == 200
        body = response.json()
        assert "prediction" in body
        assert "probability" in body
        assert "risk_level" in body


def test_predict_warm_conditions_not_high_risk():
    with TestClient(app) as client:
        response = client.post(
            "/predict",
            json=WARM_PAYLOAD,
            headers=auth_header(),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["probability"] < 0.5
        assert body["risk_level"] in {"low", "medium"}


def test_predict_overnight_deep_freeze_not_forced_critical():
    with TestClient(app) as client:
        response = client.post(
            "/predict",
            json=OVERNIGHT_DEEP_FREEZE_PAYLOAD,
            headers=auth_header(),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["probability"] <= 0.8
        assert body["risk_level"] in {"medium", "high"}
