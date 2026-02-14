"""Map data service: fetch, normalize, cache, and return Edmonton geospatial layers."""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Any, Callable, DefaultDict, Dict, List, Optional, Set

from api.cache import LayerCache
from data_connectors.open_data_edmonton import OpenDataEdmontonClient

logger = logging.getLogger(__name__)


class MapDataUnavailableError(RuntimeError):
    """Raised when a layer cannot be fetched and no stale cache exists."""


class MapDataService:
    """Fetches and normalizes Edmonton map layers with TTL cache and stale fallback."""

    LAYER_CONFIG: Dict[str, Dict[str, Any]] = {
        "neighborhoods": {
            "dataset_id": OpenDataEdmontonClient.NEIGHBORHOOD_BOUNDARIES_DATASET,
            "geometry_types": {"Polygon", "MultiPolygon"},
        },
        "sidewalks": {
            "dataset_id": OpenDataEdmontonClient.CURB_SIDEWALK_DATASET,
            "geometry_types": {"LineString", "MultiLineString"},
        },
        "winter_routes": {
            "dataset_id": OpenDataEdmontonClient.WINTER_ROUTE_STATUS_DATASET,
            "geometry_types": {"LineString", "MultiLineString"},
        },
        "trail_closures": {
            "dataset_id": OpenDataEdmontonClient.TRAIL_CLOSURES_DATASET,
            "geometry_types": {"Point", "LineString", "MultiLineString"},
        },
        "elevation_spots": {
            "dataset_id": OpenDataEdmontonClient.ELEVATION_SPOT_DATASET,
            "geometry_types": {"Point"},
        },
    }

    def __init__(
        self,
        ttl_seconds: int = 3600,
        client_factory: Callable[[], OpenDataEdmontonClient] = OpenDataEdmontonClient,
    ):
        self.cache = LayerCache(ttl_seconds=ttl_seconds)
        self.client_factory = client_factory
        self.layer_error_count: DefaultDict[str, int] = defaultdict(int)

    def _normalize_collection(
        self,
        raw_geojson: Dict[str, Any],
        allowed_geometry_types: Set[str],
        props_transform: Callable[[Dict[str, Any]], Dict[str, Any]],
    ) -> Dict[str, Any]:
        if raw_geojson.get("type") != "FeatureCollection":
            raise ValueError("Upstream payload is not a FeatureCollection")

        normalized: List[Dict[str, Any]] = []
        for feature in raw_geojson.get("features", []):
            geometry = feature.get("geometry") or {}
            geom_type = geometry.get("type")
            if geom_type not in allowed_geometry_types:
                continue
            properties = feature.get("properties") or {}
            normalized_props = props_transform(properties)
            normalized.append(
                {
                    "type": "Feature",
                    "geometry": geometry,
                    "properties": normalized_props,
                }
            )

        return {"type": "FeatureCollection", "features": normalized}

    @staticmethod
    def _normalize_neighborhood_properties(props: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "neighborhood_name": props.get("descriptiv"),
            "neighborhood_number": props.get("neighbourh"),
            "description": props.get("descriptio"),
        }

    @staticmethod
    def _normalize_sidewalk_properties(props: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "feature": props.get("feature"),
            "segment_id": props.get("id"),
            "type": props.get("type"),
        }

    @staticmethod
    def _normalize_winter_route_properties(props: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "route_id": props.get("route_id"),
            "route_number": props.get("route"),
            "priority": props.get("priority"),
            "route_status": props.get("route_stat"),
            "segment_status": props.get("seg_stat"),
            "district": props.get("district"),
            "road_on": props.get("road_on"),
            "road_from": props.get("road_from"),
            "road_to": props.get("road_to"),
            "last_updated": props.get("last_updat"),
            "serv_achieved": props.get("serv_ach"),
        }

    @staticmethod
    def _normalize_trail_closure_properties(props: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id_number": props.get("id_number"),
            "location_name": props.get("location_name"),
            "closure_type": props.get("type_of_closure"),
            "activity_type": props.get("activity_type"),
            "duration": props.get("duration"),
            "start_date": props.get("start_date"),
            "end_date": props.get("end_date"),
            "details": props.get("details"),
            "link": props.get("link"),
            "date_updated": props.get("date_updated"),
        }

    @staticmethod
    def _normalize_elevation_properties(props: Dict[str, Any]) -> Dict[str, Any]:
        elevation = props.get("elevation")
        try:
            elevation = float(elevation) if elevation is not None else None
        except (TypeError, ValueError):
            elevation = None
        return {"elevation": elevation}

    def _normalize_layer(self, layer_key: str, raw_geojson: Dict[str, Any]) -> Dict[str, Any]:
        config = self.LAYER_CONFIG[layer_key]
        allowed = config["geometry_types"]
        transform_map: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
            "neighborhoods": self._normalize_neighborhood_properties,
            "sidewalks": self._normalize_sidewalk_properties,
            "winter_routes": self._normalize_winter_route_properties,
            "trail_closures": self._normalize_trail_closure_properties,
            "elevation_spots": self._normalize_elevation_properties,
        }
        return self._normalize_collection(raw_geojson, allowed, transform_map[layer_key])

    def _fetch_live_layer(self, layer_key: str) -> Dict[str, Any]:
        config = self.LAYER_CONFIG.get(layer_key)
        if config is None:
            raise KeyError(f"Unknown layer key: {layer_key}")

        dataset_id = config["dataset_id"]
        with self.client_factory() as client:
            geojson = client.get_dataset_geojson(dataset_id=dataset_id, limit=50000)
        normalized = self._normalize_layer(layer_key, geojson)
        if not normalized.get("features"):
            raise ValueError(f"Layer '{layer_key}' returned no features after normalization")
        return normalized

    def get_layer(self, layer_key: str, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get layer as GeoJSON with metadata.

        Returns:
            {
              "layer": "sidewalks",
              "data": <FeatureCollection>,
              "meta": {...},
              "errors": [...]
            }
        """
        cache_key = f"layer::{layer_key}"
        start = time.perf_counter()
        cached = None if force_refresh else self.cache.get(cache_key, allow_stale=True)

        if cached and cached["fresh"]:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.info(
                "map_layer layer=%s source=cache cache_event=hit stale=false duration_ms=%.2f",
                layer_key,
                duration_ms,
            )
            return {
                "layer": layer_key,
                "data": cached["value"],
                "meta": {
                    "source": "cache",
                    "cache_event": "hit",
                    "stale": False,
                    "age_seconds": cached["age_seconds"],
                    "fetched_at": cached["fetched_at"],
                    "ttl_seconds": self.cache.ttl_seconds,
                    "duration_ms": duration_ms,
                },
                "errors": [],
            }

        stale_cache = cached if cached else self.cache.get(cache_key, allow_stale=True)
        try:
            live_value = self._fetch_live_layer(layer_key)
            live = self.cache.set(cache_key, live_value)
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.info(
                "map_layer layer=%s source=live cache_event=miss_refresh stale=false duration_ms=%.2f",
                layer_key,
                duration_ms,
            )
            return {
                "layer": layer_key,
                "data": live["value"],
                "meta": {
                    "source": "live",
                    "cache_event": "miss_refresh",
                    "stale": False,
                    "age_seconds": live["age_seconds"],
                    "fetched_at": live["fetched_at"],
                    "ttl_seconds": self.cache.ttl_seconds,
                    "duration_ms": duration_ms,
                },
                "errors": [],
            }
        except Exception as exc:
            self.cache.mark_refresh_failure()
            self.layer_error_count[layer_key] += 1
            logger.warning("Layer refresh failed for %s: %s", layer_key, exc)
            if stale_cache:
                duration_ms = round((time.perf_counter() - start) * 1000, 2)
                logger.warning(
                    "map_layer layer=%s source=cache cache_event=stale_served stale=true duration_ms=%.2f",
                    layer_key,
                    duration_ms,
                )
                return {
                    "layer": layer_key,
                    "data": stale_cache["value"],
                    "meta": {
                        "source": "cache",
                        "cache_event": "stale_served",
                        "stale": True,
                        "age_seconds": stale_cache["age_seconds"],
                        "fetched_at": stale_cache["fetched_at"],
                        "ttl_seconds": self.cache.ttl_seconds,
                        "duration_ms": duration_ms,
                    },
                    "errors": [f"served stale cache because refresh failed: {exc}"],
                }
            raise MapDataUnavailableError(
                f"Unable to fetch layer '{layer_key}' and no stale cache available"
            ) from exc

    def config(self) -> Dict[str, Any]:
        """Return map layer config and cache telemetry."""
        return {
            "layers": {
                layer_key: {
                    "dataset_id": cfg["dataset_id"],
                    "geometry_types": sorted(cfg["geometry_types"]),
                }
                for layer_key, cfg in self.LAYER_CONFIG.items()
            },
            "cache": {
                "ttl_seconds": self.cache.ttl_seconds,
                "stats": self.cache.stats(),
            },
            "ops": {
                "layer_error_count": dict(self.layer_error_count),
            },
        }
