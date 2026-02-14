"""Smoke tests for essential API routes."""
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


def test_smoke_health_docs_predict():
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert "database" in health.json()

        docs = client.get("/docs")
        assert docs.status_code == 200

        map_config = client.get("/map/config")
        assert map_config.status_code == 200
        assert "layers" in map_config.json()

        pred = client.post(
            "/predict",
            json=PAYLOAD,
            headers={"Authorization": "Bearer test-token"},
        )
        assert pred.status_code == 200
        body = pred.json()
        assert "probability" in body
        assert "risk_level" in body
