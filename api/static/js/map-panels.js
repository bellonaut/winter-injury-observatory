function selectById(id) {
  return document.getElementById(id);
}

function riskLevelClass(level) {
  const normalized = String(level || "").toLowerCase();
  if (["low", "medium", "high", "critical"].includes(normalized)) {
    return normalized;
  }
  return "low";
}

export function populateRouteSelectors(neighborhoods) {
  const fromSelect = selectById("route-from-neighborhood");
  const toSelect = selectById("route-to-neighborhood");
  if (!fromSelect || !toSelect) {
    return;
  }

  const unique = Array.from(new Set((neighborhoods || []).filter(Boolean))).sort();
  if (unique.length === 0) {
    return;
  }

  const previousFrom = fromSelect.value;
  const previousTo = toSelect.value;

  fromSelect.innerHTML = "";
  toSelect.innerHTML = "";

  unique.forEach((name) => {
    const fromOption = document.createElement("option");
    fromOption.value = name;
    fromOption.textContent = name;

    const toOption = document.createElement("option");
    toOption.value = name;
    toOption.textContent = name;

    fromSelect.appendChild(fromOption);
    toSelect.appendChild(toOption);
  });

  fromSelect.value = unique.includes(previousFrom) ? previousFrom : unique[0];
  toSelect.value = unique.includes(previousTo)
    ? previousTo
    : unique[Math.min(1, unique.length - 1)];
}

export function readRouteFormValues() {
  return {
    fromNeighborhood: String(selectById("route-from-neighborhood")?.value || "").trim(),
    toNeighborhood: String(selectById("route-to-neighborhood")?.value || "").trim(),
    compareHourOffset: Number(selectById("compare-hour-offset")?.value || 0),
  };
}

export function setCorridorRaw(payload) {
  const raw = selectById("corridor-raw-output");
  if (!raw) {
    return;
  }
  raw.textContent = JSON.stringify(payload, null, 2);
}

export function renderCorridorResult(payload) {
  const summary = selectById("corridor-summary");
  const list = selectById("corridor-hops");
  if (!summary || !list) {
    return;
  }

  const aggregate = Number(payload?.aggregate_corridor_risk || 0);
  const ordered = payload?.ordered_neighborhoods || [];
  const guidance = payload?.narrative_guidance || "No guidance available.";

  summary.textContent = `Corridor ${ordered.join(" -> ")} | aggregate risk ${(aggregate * 100).toFixed(1)}%`;

  list.innerHTML = "";
  (payload?.per_hop_risk_scores || []).forEach((hop) => {
    const item = document.createElement("li");
    const level = riskLevelClass(hop.risk_level);
    item.innerHTML = `<span class="pill ${level}">${level}</span> <strong>#${hop.hop} ${hop.neighborhood}</strong> ${(Number(hop.probability || 0) * 100).toFixed(1)}%`;
    list.appendChild(item);
  });

  const guidanceItem = document.createElement("li");
  guidanceItem.textContent = guidance;
  list.appendChild(guidanceItem);
}

export function renderCorridorComparison(baseResult, compareResult, compareHourOffset) {
  const target = selectById("corridor-compare-summary");
  if (!target) {
    return;
  }

  const baseRisk = Number(baseResult?.aggregate_corridor_risk || 0);
  const compareRisk = Number(compareResult?.aggregate_corridor_risk || 0);
  const delta = compareRisk - baseRisk;
  const trendWord = delta > 0.02 ? "higher" : delta < -0.02 ? "lower" : "similar";

  target.textContent = `Compare +${compareHourOffset}h: ${(compareRisk * 100).toFixed(1)}% vs current ${(baseRisk * 100).toFixed(1)}% (${trendWord} by ${(Math.abs(delta) * 100).toFixed(1)} pts).`;
}

export function setCorridorStatus(message, isError = false) {
  const element = selectById("corridor-status");
  if (!element) {
    return;
  }
  element.textContent = message;
  element.classList.toggle("error", isError);
}
