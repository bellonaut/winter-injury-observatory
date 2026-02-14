"""Smoke tests for map endpoints."""
import os

import pandas as pd
from fastapi.testclient import TestClient

os.environ.setdefault("MODEL_BACKEND", "local")
os.environ.setdefault("MODEL_ARTIFACT_PATH", "artifacts/demo_model.joblib")
os.environ.setdefault("DEMO_API_TOKEN", "test-token")
os.environ.setdefault("API_SECRET_KEY", "test-token")

import api.main as main_module  # noqa: E402
from api import map_routes  # noqa: E402
from api.main import app  # noqa: E402


class _SmokeModel:
    model = object()

    def batch_predict(self, frame: pd.DataFrame):
        rows = []
        for _ in range(len(frame)):
            rows.append(
                {
                    "prediction": 1,
                    "probability": 0.61,
                    "risk_level": "high",
                    "raw_prediction": 1,
                    "raw_probability": 0.67,
                }
            )
        return rows


class _SmokeMapService:
    def config(self):
        return {"layers": {"neighborhoods": {"dataset_id": "xu6q-xcmj"}}, "cache": {"ttl_seconds": 3600, "stats": {}}}

    def get_layer(self, layer_key: str, force_refresh: bool = False):
        del force_refresh
        if layer_key == "neighborhoods":
            data = {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[-113.6, 53.54], [-113.59, 53.54], [-113.59, 53.55], [-113.6, 53.55], [-113.6, 53.54]]],
                        },
                        "properties": {"neighborhood_name": "Downtown"},
                    }
                ],
            }
        else:
            data = {"type": "FeatureCollection", "features": []}
        return {
            "layer": layer_key,
            "data": data,
            "meta": {"source": "cache", "stale": False, "age_seconds": 0.0, "fetched_at": 1_739_528_000.0, "ttl_seconds": 3600, "duration_ms": 1.0},
            "errors": [],
        }


def test_smoke_map_endpoints(monkeypatch):
    with TestClient(app) as client:
        monkeypatch.setattr(main_module, "model_service", _SmokeModel(), raising=False)
        monkeypatch.setattr(map_routes, "_map_data_service", _SmokeMapService(), raising=True)

        config = client.get("/map/config")
        assert config.status_code == 200

        layer = client.get("/map/layers/sidewalks")
        assert layer.status_code == 200

        risk = client.get("/map/layers/neighborhood-risk", params={"hour_offset": 1})
        assert risk.status_code == 200
        body = risk.json()
        assert body["layer"] == "neighborhood-risk"
        assert body["data"]["type"] == "FeatureCollection"
