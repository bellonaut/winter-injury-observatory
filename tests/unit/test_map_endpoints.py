"""Unit tests for public map endpoint contracts."""
import os
from typing import Any, Dict, List, Tuple

import pandas as pd
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("MODEL_BACKEND", "local")
os.environ.setdefault("MODEL_ARTIFACT_PATH", "artifacts/demo_model.joblib")
os.environ.setdefault("DEMO_API_TOKEN", "test-token")
os.environ.setdefault("API_SECRET_KEY", "test-token")

import api.main as main_module  # noqa: E402
from api import map_routes  # noqa: E402
from api.main import app  # noqa: E402
from api.map_data import MapDataUnavailableError  # noqa: E402


def _risk_level(probability: float) -> str:
    if probability < 0.3:
        return "low"
    if probability < 0.6:
        return "medium"
    if probability < 0.8:
        return "high"
    return "critical"


class FakeModelService:
    """Small deterministic scorer used for map endpoint tests."""

    model = object()

    def batch_predict(self, frame: pd.DataFrame) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for _, row in frame.iterrows():
            raw = (
                0.16
                + 0.06 * float(row["precipitation"])
                + 0.004 * float(row["snow_depth"])
                + (0.10 if int(row["hour"]) in {7, 8, 9, 16, 17, 18} else 0.0)
                + 0.10 * max(0.0, 0.55 - float(row["infrastructure_quality"]))
            )
            raw_probability = max(0.02, min(0.98, raw))
            adjusted = max(0.02, min(0.98, raw_probability * 0.93))
            rows.append(
                {
                    "prediction": int(adjusted >= 0.5),
                    "probability": adjusted,
                    "risk_level": _risk_level(adjusted),
                    "raw_prediction": int(raw_probability >= 0.5),
                    "raw_probability": raw_probability,
                }
            )
        return rows


class FakeMapDataService:
    """Static map layer provider with optional per-layer failure."""

    def __init__(self, fail_layers: List[str] | None = None):
        self.fail_layers = set(fail_layers or [])
        self.calls: List[Tuple[str, bool]] = []

    def config(self) -> Dict[str, Any]:
        return {
            "layers": {
                "neighborhoods": {"dataset_id": "xu6q-xcmj", "geometry_types": ["Polygon"]},
                "sidewalks": {"dataset_id": "4feb-tv8p", "geometry_types": ["LineString"]},
                "winter_routes": {"dataset_id": "8pdx-hfxi", "geometry_types": ["LineString"]},
                "trail_closures": {"dataset_id": "k4mi-dkvi", "geometry_types": ["Point"]},
                "elevation_spots": {"dataset_id": "tarx-cg5m", "geometry_types": ["Point"]},
            },
            "cache": {"ttl_seconds": 3600, "stats": {"hits": 0, "misses": 0}},
        }

    def get_layer(self, layer_key: str, force_refresh: bool = False) -> Dict[str, Any]:
        self.calls.append((layer_key, force_refresh))
        if layer_key in self.fail_layers:
            raise MapDataUnavailableError(f"{layer_key} unavailable")

        by_key = {
            "neighborhoods": {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[-113.6, 53.54], [-113.59, 53.54], [-113.59, 53.55], [-113.6, 53.55], [-113.6, 53.54]]],
                        },
                        "properties": {"neighborhood_name": "Downtown", "neighborhood_number": 101},
                    },
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[-113.62, 53.55], [-113.61, 53.55], [-113.61, 53.56], [-113.62, 53.56], [-113.62, 53.55]]],
                        },
                        "properties": {"neighborhood_name": "Glenora", "neighborhood_number": 102},
                    },
                ],
            },
            "sidewalks": {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [[-113.6, 53.54], [-113.59, 53.55]],
                        },
                        "properties": {"segment_id": "s-1"},
                    }
                ],
            },
            "winter_routes": {
                "type": "FeatureCollection",
                "features": [],
            },
            "trail_closures": {
                "type": "FeatureCollection",
                "features": [],
            },
            "elevation_spots": {
                "type": "FeatureCollection",
                "features": [],
            },
        }

        return {
            "layer": layer_key,
            "data": by_key[layer_key],
            "meta": {
                "source": "cache",
                "stale": False,
                "age_seconds": 0.0,
                "fetched_at": 1_739_528_000.0,
                "ttl_seconds": 3600,
                "duration_ms": 1.2,
            },
            "errors": [],
        }


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    fake_model = FakeModelService()
    fake_map = FakeMapDataService()
    with TestClient(app) as test_client:
        monkeypatch.setattr(main_module, "model_service", fake_model, raising=False)
        monkeypatch.setattr(map_routes, "_map_data_service", fake_map, raising=True)
        yield test_client, fake_map


def test_map_config_returns_expected_keys(client):
    test_client, _ = client
    response = test_client.get("/map/config")
    assert response.status_code == 200
    body = response.json()
    assert "layers" in body
    assert "cache" in body
    assert "endpoints" in body
    assert body["endpoints"]["neighborhood_risk"] == "/map/layers/neighborhood-risk"


def test_map_layer_endpoint_passes_through_geojson(client):
    test_client, _ = client
    response = test_client.get("/map/layers/sidewalks")
    assert response.status_code == 200
    body = response.json()
    assert body["layer"] == "sidewalks"
    assert body["data"]["type"] == "FeatureCollection"
    assert body["meta"]["source"] in {"cache", "live"}


def test_neighborhood_risk_includes_adjusted_and_raw_probabilities(client):
    test_client, _ = client
    response = test_client.get(
        "/map/layers/neighborhood-risk",
        params={"hour_offset": 2, "precipitation": 2.5, "snow_depth": 20},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["layer"] == "neighborhood-risk"
    assert body["meta"]["hour_offset"] == 2
    assert body["meta"]["feature_count"] == 2
    assert len(body["meta"]["top_risk_neighborhoods"]) >= 1

    first = body["data"]["features"][0]["properties"]
    assert "probability" in first
    assert "raw_probability" in first
    assert "calibration_delta" in first
    assert first["raw_probability"] >= first["probability"]


def test_neighborhood_risk_rejects_out_of_range_hour_offset(client):
    test_client, _ = client
    response = test_client.get("/map/layers/neighborhood-risk", params={"hour_offset": 24})
    assert response.status_code == 422


def test_layer_failure_isolated_to_requested_layer(monkeypatch: pytest.MonkeyPatch):
    fake_model = FakeModelService()
    failing_map = FakeMapDataService(fail_layers=["trail_closures"])
    with TestClient(app) as test_client:
        monkeypatch.setattr(main_module, "model_service", fake_model, raising=False)
        monkeypatch.setattr(map_routes, "_map_data_service", failing_map, raising=True)

        sidewalks = test_client.get("/map/layers/sidewalks")
        assert sidewalks.status_code == 200

        trail = test_client.get("/map/layers/trail-closures")
        assert trail.status_code == 503
