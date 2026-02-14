const TOKEN_STORAGE_KEY = "winter_observatory_demo_token";

function numberValue(id) {
  const element = document.getElementById(id);
  return Number(element?.value || 0);
}

function textValue(id) {
  const element = document.getElementById(id);
  return String(element?.value || "").trim();
}

function selectById(id) {
  return document.getElementById(id);
}

export function restoreToken() {
  const remembered = window.localStorage.getItem(TOKEN_STORAGE_KEY);
  if (remembered) {
    const tokenInput = selectById("token");
    if (tokenInput && !tokenInput.value) {
      tokenInput.value = remembered;
    }
  }
}

export function saveToken(token) {
  if (token) {
    window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
  }
}

export function getToken() {
  return textValue("token");
}

export function readScenario() {
  return {
    temperature: numberValue("temperature"),
    wind_speed: numberValue("wind_speed"),
    wind_chill: numberValue("wind_chill"),
    precipitation: numberValue("precipitation"),
    snow_depth: numberValue("snow_depth"),
    hour: numberValue("hour"),
    day_of_week: numberValue("day_of_week"),
    month: numberValue("month"),
    neighborhood: textValue("neighborhood") || "Downtown",
    ses_index: numberValue("ses_index"),
    infrastructure_quality: numberValue("infrastructure_quality"),
  };
}

export function applyMorningCommuteScenario() {
  const defaults = {
    temperature: -14,
    wind_speed: 26,
    wind_chill: -24,
    precipitation: 2.1,
    snow_depth: 24,
    hour: 8,
    day_of_week: 1,
    month: 1,
    neighborhood: "Downtown",
    ses_index: 0.45,
    infrastructure_quality: 0.65,
  };

  for (const [key, value] of Object.entries(defaults)) {
    const element = selectById(key);
    if (element) {
      element.value = String(value);
    }
  }
}

export function getHourOffset() {
  return Number(selectById("hour-offset")?.value || 0);
}

export function setHourOffset(offset) {
  const slider = selectById("hour-offset");
  if (slider) {
    slider.value = String(offset);
  }
  updateHourOffsetLabel(offset);
}

export function updateHourOffsetLabel(offset) {
  const label = selectById("hour-offset-label");
  if (label) {
    label.textContent = `+${offset}h`;
  }
}

export function readOverlayToggles() {
  return {
    sidewalks: Boolean(selectById("toggle-sidewalks")?.checked),
    winterRoutes: Boolean(selectById("toggle-winter-routes")?.checked),
    trailClosures: Boolean(selectById("toggle-trail-closures")?.checked),
    elevationSpots: Boolean(selectById("toggle-elevation-spots")?.checked),
  };
}

export function setStatus(message, isError = false) {
  const element = selectById("status-text");
  if (!element) {
    return;
  }
  element.textContent = message;
  element.classList.toggle("error", isError);
}

export function setTopRiskList(items) {
  const list = selectById("top-risk-list");
  if (!list) {
    return;
  }
  list.innerHTML = "";

  if (!items || items.length === 0) {
    const empty = document.createElement("li");
    empty.textContent = "No neighborhood scores available yet.";
    list.appendChild(empty);
    return;
  }

  items.forEach((item, index) => {
    const line = document.createElement("li");
    line.textContent = `#${index + 1} ${item.neighborhood}: ${(Number(item.probability || 0) * 100).toFixed(1)}% (${String(item.risk_level || "unknown")})`;
    list.appendChild(line);
  });
}

export function setSelectedNeighborhoodSummary(featureProps) {
  const selectedName = selectById("selected-neighborhood-name");
  const selectedRisk = selectById("selected-neighborhood-risk");
  if (!selectedName || !selectedRisk) {
    return;
  }

  if (!featureProps) {
    selectedName.textContent = "None";
    selectedRisk.textContent = "Hover or click a neighborhood to inspect risk details.";
    return;
  }

  const probability = Number(featureProps.probability || 0);
  const level = String(featureProps.risk_level || "unknown");
  selectedName.textContent = featureProps.neighborhood_name || "Unknown";
  selectedRisk.textContent = `${level.toUpperCase()} (${(probability * 100).toFixed(1)}%) with calibration delta ${(Number(featureProps.calibration_delta || 0) * 100).toFixed(1)} pts.`;
}

function riskClass(level) {
  const normalized = String(level || "").toLowerCase();
  if (["low", "medium", "high", "critical"].includes(normalized)) {
    return normalized;
  }
  return "low";
}

function narrative(payload, probability, level) {
  const notes = [];
  if (payload.temperature <= -15 || payload.wind_chill <= -24) {
    notes.push("deep cold stress and reduced reaction control");
  }
  if (payload.precipitation >= 1.0) {
    notes.push("active precipitation creating unstable walking surfaces");
  }
  if ([7, 8, 9, 16, 17, 18].includes(payload.hour)) {
    notes.push("commute exposure intensity");
  }
  if (payload.infrastructure_quality < 0.6) {
    notes.push("lower infrastructure quality in the selected scenario");
  }

  const pct = (probability * 100).toFixed(1);
  if (notes.length === 0) {
    return `Estimated ${level} risk (${pct}%). Conditions are comparatively stable; monitor for rapid weather change.`;
  }
  return `Estimated ${level} risk (${pct}%) driven by ${notes.join(", ")}.`;
}

function recommendations(level) {
  switch (String(level || "").toLowerCase()) {
    case "critical":
      return [
        "Issue immediate travel risk advisory for exposed corridors.",
        "Deploy rapid salting and clearing to transit-adjacent crossings.",
        "Escalate monitoring in neighborhoods showing repeated spikes.",
      ];
    case "high":
      return [
        "Prioritize maintenance near schools, hubs, and downtown paths.",
        "Push focused public guidance for commute windows.",
        "Track near-miss reports to refine local interventions.",
      ];
    case "medium":
      return [
        "Maintain standard mitigation while monitoring hourly changes.",
        "Re-evaluate if precipitation or wind chill worsens.",
        "Use neighborhood-specific alerts for vulnerable routes.",
      ];
    default:
      return [
        "Maintain baseline winter operations.",
        "Keep passive monitoring active for change detection.",
        "Re-run scenario if conditions shift materially.",
      ];
  }
}

export function renderPredictionResult(payload, responseBody) {
  const probability = Number(responseBody?.probability || 0);
  const level = String(responseBody?.risk_level || "low");
  const prediction = Number(responseBody?.prediction || 0);
  const pct = Math.max(0, Math.min(100, probability * 100));

  const pill = selectById("risk-pill");
  const hero = selectById("result-hero");
  const probabilityLabel = selectById("probability-label");
  const predictionLabel = selectById("prediction-label");
  const narrativeElement = selectById("narrative");
  const recs = selectById("recommendations");
  const meterFill = selectById("meter-fill");

  if (pill) {
    pill.className = `pill ${riskClass(level)}`;
    pill.textContent = `${level} risk`;
  }
  if (hero) {
    hero.textContent = `${String(level).toUpperCase()} RISK`;
  }
  if (probabilityLabel) {
    probabilityLabel.textContent = `Probability: ${pct.toFixed(1)}%`;
  }
  if (predictionLabel) {
    predictionLabel.textContent = `Prediction: ${prediction}`;
  }
  if (narrativeElement) {
    narrativeElement.textContent = narrative(payload, probability, level);
  }
  if (meterFill) {
    meterFill.style.width = `${pct}%`;
  }

  if (recs) {
    recs.innerHTML = "";
    for (const item of recommendations(level)) {
      const li = document.createElement("li");
      li.textContent = item;
      recs.appendChild(li);
    }
  }
}

export function setRawJson(targetId, payload) {
  const element = selectById(targetId);
  if (!element) {
    return;
  }
  element.textContent = JSON.stringify(payload, null, 2);
}

export function setNeighborhoodInput(name) {
  const input = selectById("neighborhood");
  if (input && name) {
    input.value = String(name);
  }
}

export function setMapConfigSummary(config) {
  const element = selectById("map-config-summary");
  if (!element) {
    return;
  }

  const layers = Object.entries(config?.layers || {});
  if (layers.length === 0) {
    element.textContent = "Map config unavailable.";
    return;
  }

  const names = layers.map(([key, layer]) => `${key} (${layer.dataset_id || "unknown"})`);
  element.textContent = names.join(" | ");
}
