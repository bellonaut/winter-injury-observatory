"""Neighborhood corridor routing over risk-weighted adjacency graph."""
from __future__ import annotations

from itertools import combinations
from typing import Any, Dict, List, Tuple

import networkx as nx
from shapely.geometry import shape


class RouteInputError(ValueError):
    """Raised when route inputs cannot be resolved to known neighborhoods."""


def _canonical_name(name: str) -> str:
    return " ".join(str(name or "").strip().lower().split())


def _risk_level(probability: float) -> str:
    if probability < 0.3:
        return "low"
    if probability < 0.6:
        return "medium"
    if probability < 0.8:
        return "high"
    return "critical"


def _extract_neighborhood_rows(
    neighborhood_feature_collection: Dict[str, Any],
) -> List[Dict[str, Any]]:
    features = neighborhood_feature_collection.get("features", [])
    rows: List[Dict[str, Any]] = []

    for feature in features:
        properties = feature.get("properties") or {}
        name = properties.get("neighborhood_name")
        geometry = feature.get("geometry")
        if not name or not geometry:
            continue

        geom = shape(geometry)
        if geom.is_empty:
            continue
        if not geom.is_valid:
            geom = geom.buffer(0)
        if geom.is_empty:
            continue

        probability = float(properties.get("probability", 0.5))
        rows.append(
            {
                "name": str(name),
                "canonical_name": _canonical_name(str(name)),
                "geometry": geom,
                "probability": max(0.0, min(1.0, probability)),
            }
        )
    return rows


def _centroid_distance_km(node_a: Dict[str, Any], node_b: Dict[str, Any]) -> float:
    # Approximate conversion: one degree is ~111km for local planning-scale scoring.
    return float(node_a["geometry"].centroid.distance(node_b["geometry"].centroid) * 111.0)


def _fallback_connect_isolates(graph: nx.Graph, nodes: List[Dict[str, Any]]) -> None:
    if graph.number_of_nodes() <= 1:
        return

    index = {node["name"]: node for node in nodes}
    isolates = [name for name, degree in graph.degree() if degree == 0]
    for isolated_name in isolates:
        isolated_node = index[isolated_name]
        candidates = [node for node in nodes if node["name"] != isolated_name]
        if not candidates:
            continue
        closest = min(candidates, key=lambda node: _centroid_distance_km(isolated_node, node))
        distance_km = _centroid_distance_km(isolated_node, closest)
        traversal_penalty = 0.16 + min(1.2, distance_km * 0.08)
        graph.add_edge(isolated_name, closest["name"], traversal_penalty=traversal_penalty)


def build_neighborhood_graph(neighborhood_feature_collection: Dict[str, Any]) -> nx.Graph:
    """Build adjacency graph from neighborhood polygons."""
    nodes = _extract_neighborhood_rows(neighborhood_feature_collection)
    if not nodes:
        raise RouteInputError("No neighborhood geometries available for routing.")

    graph = nx.Graph()
    for node in nodes:
        graph.add_node(
            node["name"],
            canonical_name=node["canonical_name"],
            probability=node["probability"],
        )

    for left, right in combinations(nodes, 2):
        touches_or_intersects = left["geometry"].touches(right["geometry"]) or left[
            "geometry"
        ].intersects(right["geometry"])
        if not touches_or_intersects:
            continue

        distance_km = _centroid_distance_km(left, right)
        traversal_penalty = 0.08 + min(0.9, distance_km * 0.06)
        graph.add_edge(left["name"], right["name"], traversal_penalty=traversal_penalty)

    _fallback_connect_isolates(graph, nodes)
    return graph


def _resolve_graph_node(graph: nx.Graph, neighborhood_name: str) -> str:
    canonical = _canonical_name(neighborhood_name)
    for node_name, attrs in graph.nodes(data=True):
        if attrs.get("canonical_name") == canonical:
            return str(node_name)
    raise RouteInputError(f"Unknown neighborhood: {neighborhood_name}")


def _apply_edge_weights(graph: nx.Graph) -> None:
    for left, right, edge_data in graph.edges(data=True):
        left_risk = float(graph.nodes[left].get("probability", 0.5))
        right_risk = float(graph.nodes[right].get("probability", 0.5))
        average_risk = (left_risk + right_risk) / 2.0
        traversal_penalty = float(edge_data.get("traversal_penalty", 0.1))
        # Weighted shortest path: risk dominates, traversal penalty breaks ties.
        edge_data["weight"] = traversal_penalty + (0.72 * average_risk)


def _build_guidance(path: List[str], path_probabilities: List[float], aggregate_risk: float) -> str:
    worst = max(path_probabilities) if path_probabilities else aggregate_risk
    level = _risk_level(aggregate_risk)
    if level in {"critical", "high"}:
        return (
            f"{level.upper()} corridor with peak segment risk {(worst * 100):.1f}%. "
            "Prioritize mitigation and active travel advisories along this path."
        )
    if level == "medium":
        return (
            f"MEDIUM corridor risk (aggregate {(aggregate_risk * 100):.1f}%). "
            "Maintain routine controls and re-check if weather intensity rises."
        )
    return (
        f"LOW corridor risk (aggregate {(aggregate_risk * 100):.1f}%) across {len(path)} neighborhoods. "
        "Current conditions are comparatively stable."
    )


def compute_neighborhood_corridor(
    neighborhood_feature_collection: Dict[str, Any],
    from_neighborhood: str,
    to_neighborhood: str,
) -> Dict[str, Any]:
    """Compute lowest-risk neighborhood corridor between two neighborhoods."""
    graph = build_neighborhood_graph(neighborhood_feature_collection)
    _apply_edge_weights(graph)

    from_node = _resolve_graph_node(graph, from_neighborhood)
    to_node = _resolve_graph_node(graph, to_neighborhood)

    if from_node == to_node:
        probability = float(graph.nodes[from_node].get("probability", 0.0))
        return {
            "from_neighborhood": from_node,
            "to_neighborhood": to_node,
            "ordered_neighborhoods": [from_node],
            "per_hop_risk_scores": [
                {
                    "hop": 1,
                    "neighborhood": from_node,
                    "probability": probability,
                    "risk_level": _risk_level(probability),
                    "step_weight": 0.0,
                }
            ],
            "aggregate_corridor_risk": probability,
            "narrative_guidance": _build_guidance([from_node], [probability], probability),
        }

    try:
        path = nx.shortest_path(graph, source=from_node, target=to_node, weight="weight")
    except nx.NetworkXNoPath as exc:
        raise RouteInputError(
            f"No route available between '{from_neighborhood}' and '{to_neighborhood}'."
        ) from exc

    hop_scores: List[Dict[str, Any]] = []
    path_probabilities: List[float] = []
    path_weights: List[float] = []

    for index, node_name in enumerate(path):
        probability = float(graph.nodes[node_name].get("probability", 0.0))
        path_probabilities.append(probability)
        if index == 0:
            step_weight = 0.0
        else:
            edge = graph[path[index - 1]][node_name]
            step_weight = float(edge.get("weight", 0.0))
            path_weights.append(step_weight)

        hop_scores.append(
            {
                "hop": index + 1,
                "neighborhood": node_name,
                "probability": probability,
                "risk_level": _risk_level(probability),
                "step_weight": round(step_weight, 4),
            }
        )

    average_risk = sum(path_probabilities) / len(path_probabilities)
    max_risk = max(path_probabilities)
    aggregate_corridor_risk = (0.6 * average_risk) + (0.4 * max_risk)

    return {
        "from_neighborhood": from_node,
        "to_neighborhood": to_node,
        "ordered_neighborhoods": path,
        "per_hop_risk_scores": hop_scores,
        "aggregate_corridor_risk": round(float(aggregate_corridor_risk), 6),
        "corridor_cost": round(float(sum(path_weights)), 6),
        "narrative_guidance": _build_guidance(path, path_probabilities, aggregate_corridor_risk),
    }
