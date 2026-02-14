"""Unit tests for neighborhood corridor routing utilities."""

import pytest

from api.routing import RouteInputError, build_neighborhood_graph, compute_neighborhood_corridor


FEATURE_COLLECTION = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]]],
            },
            "properties": {"neighborhood_name": "Alpha", "probability": 0.22},
        },
        {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[1.0, 0.0], [2.0, 0.0], [2.0, 1.0], [1.0, 1.0], [1.0, 0.0]]],
            },
            "properties": {"neighborhood_name": "Beta", "probability": 0.41},
        },
        {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[2.0, 0.0], [3.0, 0.0], [3.0, 1.0], [2.0, 1.0], [2.0, 0.0]]],
            },
            "properties": {"neighborhood_name": "Gamma", "probability": 0.58},
        },
    ],
}


def test_build_neighborhood_graph_detects_polygon_adjacency():
    graph = build_neighborhood_graph(FEATURE_COLLECTION)
    assert graph.number_of_nodes() == 3
    assert graph.has_edge("Alpha", "Beta")
    assert graph.has_edge("Beta", "Gamma")


def test_compute_neighborhood_corridor_returns_ordered_path_and_scores():
    result = compute_neighborhood_corridor(
        neighborhood_feature_collection=FEATURE_COLLECTION,
        from_neighborhood="Alpha",
        to_neighborhood="Gamma",
    )
    assert result["from_neighborhood"] == "Alpha"
    assert result["to_neighborhood"] == "Gamma"
    assert result["ordered_neighborhoods"] == ["Alpha", "Beta", "Gamma"]
    assert len(result["per_hop_risk_scores"]) == 3
    assert 0.0 <= result["aggregate_corridor_risk"] <= 1.0
    assert "corridor" in result["narrative_guidance"].lower()


def test_compute_neighborhood_corridor_same_origin_destination():
    result = compute_neighborhood_corridor(
        neighborhood_feature_collection=FEATURE_COLLECTION,
        from_neighborhood="Beta",
        to_neighborhood="Beta",
    )
    assert result["ordered_neighborhoods"] == ["Beta"]
    assert result["per_hop_risk_scores"][0]["step_weight"] == 0.0


def test_compute_neighborhood_corridor_unknown_neighborhood_raises():
    with pytest.raises(RouteInputError):
        compute_neighborhood_corridor(
            neighborhood_feature_collection=FEATURE_COLLECTION,
            from_neighborhood="Alpha",
            to_neighborhood="Does Not Exist",
        )
