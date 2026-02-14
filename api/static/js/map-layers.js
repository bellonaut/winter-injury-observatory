export const MAP_STYLE_URL = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json";

export const SOURCE_IDS = {
  neighborhoodRisk: "neighborhood-risk-source",
  sidewalks: "sidewalks-source",
  winterRoutes: "winter-routes-source",
  trailClosures: "trail-closures-source",
  elevationSpots: "elevation-spots-source",
  corridorLine: "corridor-line-source",
  corridorStops: "corridor-stops-source",
};

export const LAYER_IDS = {
  neighborhoodFill: "neighborhood-risk-fill",
  neighborhoodLine: "neighborhood-risk-line",
  selectedNeighborhood: "neighborhood-selected-line",
  sidewalks: "sidewalks-layer",
  winterRoutes: "winter-routes-layer",
  trailClosures: "trail-closures-layer",
  elevationSpots: "elevation-spots-layer",
  corridorLine: "corridor-line-layer",
  corridorStops: "corridor-stops-layer",
  corridorLabels: "corridor-labels-layer",
};

export const OVERLAYS = {
  sidewalks: {
    endpoint: "/map/layers/sidewalks",
    sourceId: SOURCE_IDS.sidewalks,
    layerId: LAYER_IDS.sidewalks,
  },
  winterRoutes: {
    endpoint: "/map/layers/winter-routes",
    sourceId: SOURCE_IDS.winterRoutes,
    layerId: LAYER_IDS.winterRoutes,
  },
  trailClosures: {
    endpoint: "/map/layers/trail-closures",
    sourceId: SOURCE_IDS.trailClosures,
    layerId: LAYER_IDS.trailClosures,
  },
  elevationSpots: {
    endpoint: "/map/layers/elevation-spots",
    sourceId: SOURCE_IDS.elevationSpots,
    layerId: LAYER_IDS.elevationSpots,
  },
};

function emptyFeatureCollection() {
  return { type: "FeatureCollection", features: [] };
}

function riskColorExpression() {
  return [
    "match",
    ["downcase", ["coalesce", ["get", "risk_level"], ""]],
    "critical",
    "#a32638",
    "high",
    "#d15b1f",
    "medium",
    "#cc9731",
    "low",
    "#3f8f4f",
    "#8a99ad",
  ];
}

export function ensureSources(map) {
  const sourceIds = Object.values(SOURCE_IDS);
  for (const sourceId of sourceIds) {
    if (!map.getSource(sourceId)) {
      map.addSource(sourceId, {
        type: "geojson",
        data: emptyFeatureCollection(),
      });
    }
  }
}

export function ensureLayers(map) {
  if (!map.getLayer(LAYER_IDS.neighborhoodFill)) {
    map.addLayer({
      id: LAYER_IDS.neighborhoodFill,
      type: "fill",
      source: SOURCE_IDS.neighborhoodRisk,
      paint: {
        "fill-color": riskColorExpression(),
        "fill-opacity": 0.62,
      },
    });
  }

  if (!map.getLayer(LAYER_IDS.neighborhoodLine)) {
    map.addLayer({
      id: LAYER_IDS.neighborhoodLine,
      type: "line",
      source: SOURCE_IDS.neighborhoodRisk,
      paint: {
        "line-color": "#2a3d5a",
        "line-width": 1,
        "line-opacity": 0.6,
      },
    });
  }

  if (!map.getLayer(LAYER_IDS.selectedNeighborhood)) {
    map.addLayer({
      id: LAYER_IDS.selectedNeighborhood,
      type: "line",
      source: SOURCE_IDS.neighborhoodRisk,
      paint: {
        "line-color": "#091f3e",
        "line-width": 3,
      },
      filter: ["==", ["get", "neighborhood_name"], ""],
    });
  }

  if (!map.getLayer(LAYER_IDS.sidewalks)) {
    map.addLayer({
      id: LAYER_IDS.sidewalks,
      type: "line",
      source: SOURCE_IDS.sidewalks,
      layout: { visibility: "none" },
      paint: {
        "line-color": "#336699",
        "line-width": 1,
        "line-opacity": 0.72,
      },
    });
  }

  if (!map.getLayer(LAYER_IDS.winterRoutes)) {
    map.addLayer({
      id: LAYER_IDS.winterRoutes,
      type: "line",
      source: SOURCE_IDS.winterRoutes,
      layout: { visibility: "none" },
      paint: {
        "line-color": "#1e9a7f",
        "line-width": 2,
        "line-opacity": 0.85,
      },
    });
  }

  if (!map.getLayer(LAYER_IDS.trailClosures)) {
    map.addLayer({
      id: LAYER_IDS.trailClosures,
      type: "circle",
      source: SOURCE_IDS.trailClosures,
      layout: { visibility: "none" },
      paint: {
        "circle-color": "#9e3344",
        "circle-stroke-color": "#fff",
        "circle-stroke-width": 1,
        "circle-radius": 4,
      },
    });
  }

  if (!map.getLayer(LAYER_IDS.elevationSpots)) {
    map.addLayer({
      id: LAYER_IDS.elevationSpots,
      type: "circle",
      source: SOURCE_IDS.elevationSpots,
      layout: { visibility: "none" },
      paint: {
        "circle-color": [
          "interpolate",
          ["linear"],
          ["to-number", ["coalesce", ["get", "elevation"], 200]],
          150,
          "#4a90e2",
          250,
          "#cc9731",
          350,
          "#8d3f2c",
        ],
        "circle-radius": [
          "interpolate",
          ["linear"],
          ["to-number", ["coalesce", ["get", "elevation"], 200]],
          100,
          2,
          350,
          6,
        ],
        "circle-opacity": 0.78,
      },
    });
  }

  if (!map.getLayer(LAYER_IDS.corridorLine)) {
    map.addLayer({
      id: LAYER_IDS.corridorLine,
      type: "line",
      source: SOURCE_IDS.corridorLine,
      layout: { visibility: "none" },
      paint: {
        "line-color": "#163a6a",
        "line-width": 4,
        "line-opacity": 0.88,
      },
    });
  }

  if (!map.getLayer(LAYER_IDS.corridorStops)) {
    map.addLayer({
      id: LAYER_IDS.corridorStops,
      type: "circle",
      source: SOURCE_IDS.corridorStops,
      layout: { visibility: "none" },
      paint: {
        "circle-radius": 6,
        "circle-color": "#163a6a",
        "circle-stroke-width": 2,
        "circle-stroke-color": "#fff",
      },
    });
  }

  if (!map.getLayer(LAYER_IDS.corridorLabels)) {
    map.addLayer({
      id: LAYER_IDS.corridorLabels,
      type: "symbol",
      source: SOURCE_IDS.corridorStops,
      layout: {
        visibility: "none",
        "text-field": ["concat", "#", ["to-string", ["get", "rank"]]],
        "text-offset": [0, 1.3],
        "text-size": 11,
      },
      paint: {
        "text-color": "#0b2140",
      },
    });
  }
}

export function setGeoJson(map, sourceId, featureCollection) {
  const source = map.getSource(sourceId);
  if (!source) {
    return;
  }
  source.setData(featureCollection || emptyFeatureCollection());
}

export function setLayerVisibility(map, layerId, visible) {
  const layer = map.getLayer(layerId);
  if (!layer) {
    return;
  }
  map.setLayoutProperty(layerId, "visibility", visible ? "visible" : "none");
}

export function setSelectedNeighborhoodFilter(map, neighborhoodName) {
  if (!map.getLayer(LAYER_IDS.selectedNeighborhood)) {
    return;
  }
  map.setFilter(LAYER_IDS.selectedNeighborhood, [
    "==",
    ["coalesce", ["get", "neighborhood_name"], ""],
    neighborhoodName || "",
  ]);
}

export function setCorridorVisibility(map, visible) {
  setLayerVisibility(map, LAYER_IDS.corridorLine, visible);
  setLayerVisibility(map, LAYER_IDS.corridorStops, visible);
  setLayerVisibility(map, LAYER_IDS.corridorLabels, visible);
}

export function buildNeighborhoodPopupHtml(feature) {
  const props = feature?.properties || {};
  const probability = Number(props.probability || 0);
  const rawProbability = Number(props.raw_probability || 0);
  const calibrationDelta = Number(props.calibration_delta || 0);

  return [
    `<h4>${props.neighborhood_name || "Unknown"}</h4>`,
    `<div class="popup-line"><strong>Risk:</strong> ${(props.risk_level || "unknown").toUpperCase()}</div>`,
    `<div class="popup-line"><strong>Adjusted:</strong> ${(probability * 100).toFixed(1)}%</div>`,
    `<div class="popup-line"><strong>Raw:</strong> ${(rawProbability * 100).toFixed(1)}%</div>`,
    `<div class="popup-line"><strong>Calibration Delta:</strong> ${(calibrationDelta * 100).toFixed(1)} pts</div>`,
  ].join("");
}
