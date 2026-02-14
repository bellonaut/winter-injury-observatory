"""Public map endpoints for geospatial layers and neighborhood risk surfaces."""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from api.map_data import MapDataService, MapDataUnavailableError
from synthetic_data.generate_data import WinterInjuryDataGenerator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/map", tags=["map"])

_map_data_service = MapDataService(ttl_seconds=3600)
_model_service_getter: Optional[Callable[[], Any]] = None

DEFAULT_SCENARIO: Dict[str, float | int] = {
    "temperature": -12.0,
    "wind_speed": 20.0,
    "wind_chill": -22.0,
    "precipitation": 1.0,
    "snow_depth": 18.0,
    "hour": 8,
    "day_of_week": 1,
    "month": 1,
}

NEIGHBORHOOD_CONTEXT = WinterInjuryDataGenerator.NEIGHBORHOODS
NEIGHBORHOOD_ALIASES = {
    "castle downs": "Castle Downs",
    "castledowns": "Castle Downs",
    "northgate": "North Edmonton",
    "jasper place": "West Edmonton",
    "alberta avenue": "North Edmonton",
    "glenora": "West Edmonton",
    "mactaggart": "Terwillegar",
}


def configure_map_services(
    model_service_getter: Callable[[], Any],
    map_data_service: Optional[MapDataService] = None,
) -> None:
    """Inject dependencies from app startup context."""
    global _model_service_getter, _map_data_service
    _model_service_getter = model_service_getter
    if map_data_service is not None:
        _map_data_service = map_data_service


def _canonical_neighborhood_key(name: str) -> str:
    return " ".join(name.strip().lower().split())


def _resolve_neighborhood_context(name: str) -> Dict[str, float]:
    key = _canonical_neighborhood_key(name)
    mapped_name = NEIGHBORHOOD_ALIASES.get(key, name)

    if mapped_name in NEIGHBORHOOD_CONTEXT:
        return NEIGHBORHOOD_CONTEXT[mapped_name]

    canonical = _canonical_neighborhood_key(mapped_name)
    for known_name, values in NEIGHBORHOOD_CONTEXT.items():
        if _canonical_neighborhood_key(known_name) == canonical:
            return values

    # fallback baseline if neighborhood is outside current synthetic lookup table
    return {"ses_index": 0.5, "infrastructure_quality": 0.65, "pop_density": 0.6}


def _get_model_service():
    if _model_service_getter is None:
        return None
    return _model_service_getter()


def _apply_hour_offset(hour: int, day_of_week: int, hour_offset: int) -> tuple[int, int]:
    total_hours = hour + hour_offset
    adjusted_hour = total_hours % 24
    adjusted_day = (day_of_week + (total_hours // 24)) % 7
    return adjusted_hour, adjusted_day


def _layer_or_503(layer_key: str, force_refresh: bool = False) -> Dict[str, Any]:
    try:
        return _map_data_service.get_layer(layer_key, force_refresh=force_refresh)
    except MapDataUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/config")
async def map_config():
    """Return map layer configuration and cache telemetry."""
    config = _map_data_service.config()
    config["endpoints"] = {
        "neighborhood_risk": "/map/layers/neighborhood-risk",
        "sidewalks": "/map/layers/sidewalks",
        "winter_routes": "/map/layers/winter-routes",
        "trail_closures": "/map/layers/trail-closures",
        "elevation_spots": "/map/layers/elevation-spots",
    }
    return config


@router.get("/layers/sidewalks")
async def sidewalks_layer(force_refresh: bool = False):
    """Return normalized sidewalks/curb lines GeoJSON."""
    return _layer_or_503("sidewalks", force_refresh=force_refresh)


@router.get("/layers/winter-routes")
async def winter_routes_layer(force_refresh: bool = False):
    """Return normalized snow/ice route status GeoJSON."""
    return _layer_or_503("winter_routes", force_refresh=force_refresh)


@router.get("/layers/trail-closures")
async def trail_closures_layer(force_refresh: bool = False):
    """Return normalized trail closure GeoJSON."""
    return _layer_or_503("trail_closures", force_refresh=force_refresh)


@router.get("/layers/elevation-spots")
async def elevation_spots_layer(force_refresh: bool = False):
    """Return normalized elevation spot GeoJSON."""
    return _layer_or_503("elevation_spots", force_refresh=force_refresh)


@router.get("/layers/neighborhood-risk")
async def neighborhood_risk_layer(
    hour_offset: int = Query(0, ge=0, le=23),
    temperature: Optional[float] = Query(None),
    wind_speed: Optional[float] = Query(None),
    wind_chill: Optional[float] = Query(None),
    precipitation: Optional[float] = Query(None),
    snow_depth: Optional[float] = Query(None),
    hour: Optional[int] = Query(None, ge=0, le=23),
    day_of_week: Optional[int] = Query(None, ge=0, le=6),
    month: Optional[int] = Query(None, ge=1, le=12),
    force_refresh: bool = False,
):
    """
    Return neighborhood polygons enriched with adjusted + raw risk scores.
    """
    model_service = _get_model_service()
    if model_service is None or model_service.model is None:
        raise HTTPException(status_code=503, detail="Model service unavailable")

    layer = _layer_or_503("neighborhoods", force_refresh=force_refresh)
    features = layer["data"].get("features", [])
    if not features:
        raise HTTPException(status_code=503, detail="No neighborhood features available")

    scenario = dict(DEFAULT_SCENARIO)
    if temperature is not None:
        scenario["temperature"] = temperature
    if wind_speed is not None:
        scenario["wind_speed"] = wind_speed
    if wind_chill is not None:
        scenario["wind_chill"] = wind_chill
    if precipitation is not None:
        scenario["precipitation"] = precipitation
    if snow_depth is not None:
        scenario["snow_depth"] = snow_depth
    if hour is not None:
        scenario["hour"] = hour
    if day_of_week is not None:
        scenario["day_of_week"] = day_of_week
    if month is not None:
        scenario["month"] = month

    adj_hour, adj_day = _apply_hour_offset(
        int(scenario["hour"]), int(scenario["day_of_week"]), hour_offset
    )
    scenario["hour"] = adj_hour
    scenario["day_of_week"] = adj_day

    frame_rows = []
    feature_names = []
    for feature in features:
        props = feature.get("properties", {})
        neighborhood_name = props.get("neighborhood_name") or "Unknown"
        context = _resolve_neighborhood_context(neighborhood_name)
        frame_rows.append(
            {
                "temperature": float(scenario["temperature"]),
                "wind_speed": float(scenario["wind_speed"]),
                "wind_chill": float(scenario["wind_chill"]),
                "precipitation": float(scenario["precipitation"]),
                "snow_depth": float(scenario["snow_depth"]),
                "hour": int(scenario["hour"]),
                "day_of_week": int(scenario["day_of_week"]),
                "month": int(scenario["month"]),
                "neighborhood": neighborhood_name,
                "ses_index": float(context["ses_index"]),
                "infrastructure_quality": float(context["infrastructure_quality"]),
            }
        )
        feature_names.append(neighborhood_name)

    df = pd.DataFrame(frame_rows)
    try:
        predictions = model_service.batch_predict(df)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Unable to score neighborhood risk: {exc}"
        ) from exc

    enriched_features = []
    ranking = []
    for feature, prediction, neighborhood_name in zip(features, predictions, feature_names):
        adjusted_probability = float(prediction["probability"])
        raw_probability = float(prediction.get("raw_probability", adjusted_probability))
        calibration_delta = adjusted_probability - raw_probability

        props = dict(feature.get("properties", {}))
        props.update(
            {
                "prediction": int(prediction["prediction"]),
                "raw_prediction": int(prediction.get("raw_prediction", prediction["prediction"])),
                "probability": adjusted_probability,
                "raw_probability": raw_probability,
                "risk_level": prediction["risk_level"],
                "calibration_delta": calibration_delta,
            }
        )

        enriched_features.append(
            {
                "type": "Feature",
                "geometry": feature.get("geometry"),
                "properties": props,
            }
        )
        ranking.append(
            {
                "neighborhood": neighborhood_name,
                "probability": adjusted_probability,
                "risk_level": prediction["risk_level"],
            }
        )

    top_three = sorted(ranking, key=lambda item: item["probability"], reverse=True)[:3]

    return {
        "layer": "neighborhood-risk",
        "data": {"type": "FeatureCollection", "features": enriched_features},
        "meta": {
            **layer["meta"],
            "hour_offset": hour_offset,
            "feature_count": len(enriched_features),
            "scenario": scenario,
            "top_risk_neighborhoods": top_three,
        },
        "errors": layer.get("errors", []),
    }
