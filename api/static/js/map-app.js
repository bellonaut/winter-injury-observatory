import {
  MAP_STYLE_URL,
  SOURCE_IDS,
  LAYER_IDS,
  OVERLAYS,
  ensureSources,
  ensureLayers,
  setGeoJson,
  setLayerVisibility,
  setSelectedNeighborhoodFilter,
  buildNeighborhoodPopupHtml,
} from "./map-layers.js";

import {
  restoreToken,
  saveToken,
  getToken,
  readScenario,
  applyMorningCommuteScenario,
  getHourOffset,
  setHourOffset,
  updateHourOffsetLabel,
  readOverlayToggles,
  setStatus,
  setTopRiskList,
  setSelectedNeighborhoodSummary,
  renderPredictionResult,
  setRawJson,
  setNeighborhoodInput,
  setMapConfigSummary,
} from "./map-controls.js";

const state = {
  map: null,
  popup: null,
  playTimer: null,
  overlayLoaded: {
    sidewalks: false,
    winterRoutes: false,
    trailClosures: false,
    elevationSpots: false,
  },
  latestRiskData: null,
  initialBoundsApplied: false,
};

let riskRefreshTimer = null;

function serializeNeighborhoodRiskParams(scenario, hourOffset) {
  const params = new URLSearchParams();
  params.set("hour_offset", String(hourOffset));

  const keys = [
    "temperature",
    "wind_speed",
    "wind_chill",
    "precipitation",
    "snow_depth",
    "hour",
    "day_of_week",
    "month",
  ];
  for (const key of keys) {
    params.set(key, String(scenario[key]));
  }

  return params;
}

async function fetchJson(url, options = undefined) {
  const response = await fetch(url, options);
  let payload;
  try {
    payload = await response.json();
  } catch (_) {
    payload = { detail: `Non-JSON response from ${url}` };
  }

  if (!response.ok) {
    const detail = payload?.detail || `Request failed (${response.status})`;
    throw new Error(detail);
  }

  return payload;
}

function riskFeatureFromName(name) {
  const features = state.latestRiskData?.data?.features || [];
  return features.find((feature) => feature?.properties?.neighborhood_name === name) || null;
}

function maybeFitBounds(featureCollection) {
  if (state.initialBoundsApplied) {
    return;
  }

  const turf = window.turf;
  if (!turf || !featureCollection || !featureCollection.features?.length) {
    return;
  }

  try {
    const bounds = turf.bbox(featureCollection);
    state.map.fitBounds(
      [
        [bounds[0], bounds[1]],
        [bounds[2], bounds[3]],
      ],
      { padding: 40, duration: 700 }
    );
    state.initialBoundsApplied = true;
  } catch (_) {
    // no-op when bbox cannot be computed from payload
  }
}

async function loadMapConfig() {
  const config = await fetchJson("/map/config");
  setMapConfigSummary(config);
}

async function loadNeighborhoodRisk() {
  const scenario = readScenario();
  const hourOffset = getHourOffset();

  setStatus("Refreshing neighborhood risk surface...");
  const params = serializeNeighborhoodRiskParams(scenario, hourOffset);
  const payload = await fetchJson(`/map/layers/neighborhood-risk?${params.toString()}`);

  state.latestRiskData = payload;
  setGeoJson(state.map, SOURCE_IDS.neighborhoodRisk, payload.data);
  setTopRiskList(payload?.meta?.top_risk_neighborhoods || []);
  setRawJson("map-raw-output", payload);
  maybeFitBounds(payload.data);

  const selectedName = scenario.neighborhood;
  setSelectedNeighborhoodFilter(state.map, selectedName);
  setSelectedNeighborhoodSummary(riskFeatureFromName(selectedName)?.properties || null);

  setStatus(`Map refreshed for +${hourOffset}h offset.`);
}

async function loadOverlay(overlayKey) {
  const overlay = OVERLAYS[overlayKey];
  if (!overlay) {
    return;
  }

  const payload = await fetchJson(overlay.endpoint);
  setGeoJson(state.map, overlay.sourceId, payload.data);
  state.overlayLoaded[overlayKey] = true;
}

async function syncOverlayVisibility() {
  const toggles = readOverlayToggles();
  const jobs = [];

  for (const [overlayKey, overlay] of Object.entries(OVERLAYS)) {
    const enabled = Boolean(toggles[overlayKey]);
    setLayerVisibility(state.map, overlay.layerId, enabled);

    if (enabled && !state.overlayLoaded[overlayKey]) {
      jobs.push(loadOverlay(overlayKey));
    }
  }

  if (jobs.length > 0) {
    setStatus("Loading selected overlays...");
    await Promise.all(jobs);
    setStatus("Overlay layers updated.");
  }
}

function refreshNeighborhoodRiskDebounced(delayMs = 220) {
  if (riskRefreshTimer) {
    window.clearTimeout(riskRefreshTimer);
  }

  riskRefreshTimer = window.setTimeout(async () => {
    try {
      await loadNeighborhoodRisk();
    } catch (error) {
      setStatus(`Map update failed: ${error.message}`, true);
    }
  }, delayMs);
}

function stopTimelinePlayback() {
  if (state.playTimer) {
    window.clearInterval(state.playTimer);
    state.playTimer = null;
  }

  const button = document.getElementById("timeline-play");
  if (button) {
    button.textContent = "Play 24h";
  }
}

async function toggleTimelinePlayback() {
  const button = document.getElementById("timeline-play");
  if (state.playTimer) {
    stopTimelinePlayback();
    return;
  }

  if (button) {
    button.textContent = "Pause";
  }

  state.playTimer = window.setInterval(async () => {
    const nextOffset = (getHourOffset() + 1) % 24;
    setHourOffset(nextOffset);
    try {
      await loadNeighborhoodRisk();
    } catch (error) {
      stopTimelinePlayback();
      setStatus(`Timeline stopped: ${error.message}`, true);
    }
  }, 1300);
}

function wireMapInteractions() {
  state.popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 12 });

  state.map.on("mousemove", LAYER_IDS.neighborhoodFill, (event) => {
    const feature = event.features?.[0];
    if (!feature) {
      return;
    }

    state.map.getCanvas().style.cursor = "pointer";
    state.popup
      .setLngLat(event.lngLat)
      .setHTML(buildNeighborhoodPopupHtml(feature))
      .addTo(state.map);
  });

  state.map.on("mouseleave", LAYER_IDS.neighborhoodFill, () => {
    state.map.getCanvas().style.cursor = "";
    if (state.popup) {
      state.popup.remove();
    }
  });

  state.map.on("click", LAYER_IDS.neighborhoodFill, (event) => {
    const feature = event.features?.[0];
    if (!feature) {
      return;
    }

    const name = feature?.properties?.neighborhood_name;
    if (!name) {
      return;
    }

    setNeighborhoodInput(name);
    setSelectedNeighborhoodFilter(state.map, name);
    setSelectedNeighborhoodSummary(feature.properties || null);
    setStatus(`Selected neighborhood: ${name}`);
  });
}

async function runPrediction() {
  const token = getToken();
  if (!token) {
    setStatus("Demo token required for /predict.", true);
    return;
  }

  const payload = readScenario();
  setStatus("Calling /predict...");

  const response = await fetchJson("/predict", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });

  saveToken(token);
  renderPredictionResult(payload, response);
  setRawJson("raw-output", response);
  setStatus("Prediction complete.");
}

function wireControls() {
  const slider = document.getElementById("hour-offset");
  const playButton = document.getElementById("timeline-play");
  const refreshButton = document.getElementById("update-map");
  const commuteButton = document.getElementById("load-commute-scenario");
  const predictButton = document.getElementById("run-predict");

  updateHourOffsetLabel(getHourOffset());

  slider?.addEventListener("input", () => {
    updateHourOffsetLabel(getHourOffset());
    refreshNeighborhoodRiskDebounced(160);
  });

  playButton?.addEventListener("click", async () => {
    await toggleTimelinePlayback();
  });

  refreshButton?.addEventListener("click", async () => {
    stopTimelinePlayback();
    try {
      await loadNeighborhoodRisk();
      await syncOverlayVisibility();
    } catch (error) {
      setStatus(`Map refresh failed: ${error.message}`, true);
    }
  });

  commuteButton?.addEventListener("click", async () => {
    stopTimelinePlayback();
    applyMorningCommuteScenario();
    try {
      await loadNeighborhoodRisk();
    } catch (error) {
      setStatus(`Scenario load failed: ${error.message}`, true);
    }
  });

  predictButton?.addEventListener("click", async () => {
    try {
      await runPrediction();
    } catch (error) {
      setStatus(`Prediction failed: ${error.message}`, true);
    }
  });

  const overlayInputs = [
    "toggle-sidewalks",
    "toggle-winter-routes",
    "toggle-trail-closures",
    "toggle-elevation-spots",
  ];

  overlayInputs.forEach((id) => {
    const element = document.getElementById(id);
    element?.addEventListener("change", async () => {
      try {
        await syncOverlayVisibility();
      } catch (error) {
        setStatus(`Overlay update failed: ${error.message}`, true);
      }
    });
  });
}

async function initialize() {
  restoreToken();
  setStatus("Loading map services...");

  state.map = new maplibregl.Map({
    container: "map",
    style: MAP_STYLE_URL,
    center: [-113.4909, 53.5461],
    zoom: 10.2,
    minZoom: 8.2,
  });

  state.map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "bottom-right");

  state.map.on("load", async () => {
    try {
      ensureSources(state.map);
      ensureLayers(state.map);
      wireMapInteractions();
      wireControls();

      await loadMapConfig();
      await loadNeighborhoodRisk();
      await syncOverlayVisibility();

      setStatus("Map ready.");
    } catch (error) {
      setStatus(`Startup failed: ${error.message}`, true);
    }
  });
}

initialize();
