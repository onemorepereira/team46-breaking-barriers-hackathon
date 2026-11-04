/* Team Foundry console. Renders one run: live (server-sent events) or archived (/api/runs/<id>).
   All text goes in through textContent; nothing from a run is ever parsed as HTML. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const RUN_ID = (window.FOUNDRY || {}).runId;

  // ---------- small helpers ----------
  function el(tag, attrs = {}, ...kids) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") n.className = v;
      else if (k === "text") n.textContent = v;
      else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
      else n.setAttribute(k, v === true ? "" : v);
    }
    for (const kid of kids.flat()) if (kid !== null && kid !== undefined && kid !== false)
      n.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
    return n;
  }
  const icon = (name, cls = "") => el("i", { class: `ti ti-${name} ${cls}`.trim() });
  const usd = (v) => (v === null || v === undefined ? "—" : v < 0.01 ? `$${v.toFixed(4)}` : `$${v.toFixed(2)}`);
  const num = (v) => (v === null || v === undefined ? "—" : Number(v).toLocaleString());
  const secs = (v) => (v === null || v === undefined ? "—" : v >= 90 ? `${Math.floor(v / 60)}m ${Math.round(v % 60)}s` : `${Math.round(v)}s`);
  const pct = (v) => (v === null || v === undefined ? "—" : `${Math.round(v * 100)}%`);
  const ms = (v) => (v === null || v === undefined ? "" : v >= 1000 ? `${(v / 1000).toFixed(1)} s` : `${v} ms`);
  const human = (id) => ({
    tool_selection: "Tool choice", tool_arguments: "Tool-call accuracy", sequencing_recovery: "Sequencing & recovery",
    efficiency: "Efficiency", result_relevance: "Result relevance", grounding: "Grounding",
    completeness: "Completeness", calibration: "Honest uncertainty", claim_provenance: "Claim provenance",
    area_compliance: "Area compliance",
  })[id] || id.replace(/_/g, " ");
  const scoreClass = (s) => (s === null || s === undefined ? "secondary" : s >= 80 ? "success" : s >= 50 ? "warning" : "danger");
  function setText(id, v) { const n = $(id); if (n) n.textContent = v; }
  function show(id, on = true) { const n = $(id); if (n) n.hidden = !on; }

  // ---------- map ----------
  const BASEMAPS = [
    { id: "s2", label: "Sentinel-2", attribution: "Sentinel-2 cloudless 2023 by EOX (contains modified Copernicus Sentinel data)",
      tiles: ["https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2023_3857/default/g/{z}/{y}/{x}.jpg"], maxzoom: 15 },
    { id: "usgs", label: "USGS imagery", attribution: "USGS The National Map",
      tiles: ["https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/tile/{z}/{y}/{x}"], maxzoom: 16 },
    { id: "naip", label: "NAIP (US)", attribution: "USGS The National Map, NAIP",
      tiles: ["https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPImagery/ImageServer/exportImage?bbox={bbox-epsg-3857}&bboxSR=3857&imageSR=3857&size=256,256&format=jpg&f=image"], maxzoom: 19 },
    { id: "osm", label: "Streets", attribution: "© OpenStreetMap contributors",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"], maxzoom: 19 },
  ];
  const CYAN = "#01d5f9", ORANGE = "#fd8800";
  const empty = () => ({ type: "FeatureCollection", features: [] });
  const data = { chips: empty(), claims: empty(), area: empty() };
  let map, popup, mapReady = false;
  const pending = [];

  function initMap() {
    const sources = {}, layers = [];
    for (const b of BASEMAPS) {
      sources[b.id] = { type: "raster", tiles: b.tiles, tileSize: 256, attribution: b.attribution, maxzoom: b.maxzoom };
      layers.push({ id: `base-${b.id}`, type: "raster", source: b.id, layout: { visibility: b.id === "s2" ? "visible" : "none" } });
    }
    map = new maplibregl.Map({
      container: "map", center: [-40, 25], zoom: 1.4, attributionControl: { compact: true },
      style: { version: 8, sources, layers },
    });
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: false }), "top-left");
    map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-right");
    map.on("load", () => {
      map.addSource("area", { type: "geojson", data: data.area });
      map.addSource("chips", { type: "geojson", data: data.chips, promoteId: "key" });
      map.addSource("claims", { type: "geojson", data: data.claims });
      map.addLayer({ id: "area-fill", type: "fill", source: "area", paint: { "fill-color": CYAN, "fill-opacity": 0.06 } });
      map.addLayer({ id: "area-line", type: "line", source: "area", paint: { "line-color": CYAN, "line-width": 2.5, "line-dasharray": [2, 1.5] } });
      const inside = ["==", ["get", "inside"], false];
      map.addLayer({ id: "chips-fill", type: "fill", source: "chips", paint: {
        "fill-color": ["case", inside, ORANGE, CYAN],
        "fill-opacity": ["case", ["boolean", ["feature-state", "hover"], false], 0.6, 0.3] } });
      map.addLayer({ id: "chips-line-in", type: "line", source: "chips", filter: ["!", inside], paint: { "line-color": CYAN, "line-width": 1.6 } });
      map.addLayer({ id: "chips-line-out", type: "line", source: "chips", filter: inside, paint: { "line-color": ORANGE, "line-width": 2, "line-dasharray": [2, 1] } });
      map.addSource("chip-dots", { type: "geojson", data: dotsOf(data.chips) });
      map.addLayer({ id: "chip-dots", type: "circle", source: "chip-dots", maxzoom: 14, paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 4, 2.5, 13, 5],
        "circle-color": ["case", ["==", ["get", "inside"], false], ORANGE, CYAN],
        "circle-stroke-width": 1, "circle-stroke-color": "#0b1220", "circle-opacity": 0.9 } });
      map.addLayer({ id: "claims", type: "circle", source: "claims", paint: {
        "circle-radius": 6, "circle-color": "#ffffff", "circle-stroke-width": 3,
        "circle-stroke-color": ["case", ["==", ["get", "inside"], false], ORANGE, CYAN] } });
      map.on("click", "chip-dots", (e) => openPopup(e.features[0].properties, e.lngLat));
      for (const layer of ["chips-fill", "claims", "chip-dots"]) {
        map.on("mouseenter", layer, () => (map.getCanvas().style.cursor = "pointer"));
        map.on("mouseleave", layer, () => (map.getCanvas().style.cursor = ""));
      }
      let hovered = null;
      map.on("mousemove", "chips-fill", (e) => {
        if (hovered !== null) map.setFeatureState({ source: "chips", id: hovered }, { hover: false });
        hovered = e.features[0].id;
        map.setFeatureState({ source: "chips", id: hovered }, { hover: true });
      });
      map.on("mouseleave", "chips-fill", () => {
        if (hovered !== null) map.setFeatureState({ source: "chips", id: hovered }, { hover: false });
        hovered = null;
      });
      map.on("click", "chips-fill", (e) => openPopup(e.features[0].properties, e.lngLat));
      map.on("click", "claims", (e) => openPopup(e.features[0].properties, e.lngLat));
      mapReady = true;
      map.resize();
      pending.splice(0).forEach((fn) => fn());
    });
    const group = $("basemaps");
    for (const b of BASEMAPS) {
      group.append(el("button", { class: `btn ${b.id === "s2" ? "active" : ""}`, type: "button", "data-id": b.id, text: b.label,
        onclick: (ev) => {
          for (const x of BASEMAPS) map.setLayoutProperty(`base-${x.id}`, "visibility", x.id === b.id ? "visible" : "none");
          group.querySelectorAll("button").forEach((n) => n.classList.toggle("active", n === ev.currentTarget));
        } }));
    }
  }
  const whenMap = (fn) => (mapReady ? fn() : pending.push(fn));
  const dotsOf = (fc) => ({ type: "FeatureCollection", features: fc.features.map((f) => ({ type: "Feature",
    geometry: { type: "Point", coordinates: [Number(f.properties.lon), Number(f.properties.lat)] }, properties: f.properties })) });
  const refreshChips = () => whenMap(() => { map.getSource("chips").setData(data.chips); map.getSource("chip-dots").setData(dotsOf(data.chips)); });
  // The card's width settles after fonts and the grid lay out; keep the canvas matched to it.
  new ResizeObserver(() => map && map.resize()).observe(document.getElementById("map"));

  function openPopup(p, lngLat) {
    const where = p.inside === true || p.inside === "true" ? ["Inside the requested area", "success"]
      : p.inside === false || p.inside === "false" ? ["Outside the requested area", "warning"] : ["No area to check", "secondary"];
    const body = el("div", { class: "foundry-popup" },
      p.tile_url ? el("img", { src: p.tile_url, alt: "imagery tile", loading: "lazy" }) : null,
      el("div", { class: "mt-2 fw-bold", text: p.claim || p.label || p.node || "Result" }),
      el("div", { class: "small text-secondary" },
        [p.index ? String(p.index).toUpperCase() : null, p.observed ? `observed ${p.observed}` : null,
         p.similarity && p.similarity !== "null" ? `similarity ${Number(p.similarity).toFixed(2)}` : null].filter(Boolean).join(" · ")),
      el("div", { class: "small" }, `${Number(p.lat).toFixed(4)}, ${Number(p.lon).toFixed(4)}`),
      el("div", { class: "mt-1 d-flex gap-1 flex-wrap" },
        el("span", { class: `badge bg-${where[1]}-lt`, text: where[0] }),
        p.ref ? el("span", { class: "badge bg-azure-lt ref-link", text: `from ${p.ref}`, onclick: () => scrollToStep(p.ref) }) : null),
      p.tile_source ? el("div", { class: "text-secondary mt-1", style: "font-size:.65rem", text: p.tile_source }) : null);
    if (popup) popup.remove();
    popup = new maplibregl.Popup({ maxWidth: "260px" }).setLngLat(lngLat).setDOMContent(body).addTo(map);
  }

  function bboxPolygon(b) {
    const [w, s, e, n] = b.map(Number);
    return { type: "Polygon", coordinates: [[[w, s], [e, s], [e, n], [w, n], [w, s]]] };
  }
  const seenChips = new Set();
  function addChips(chips) {
    const fresh = [];
    for (const c of chips || []) {
      const key = String(c.node || c.chip_id || `${c.lat},${c.lon}`);
      if (seenChips.has(key) || !c.bbox) continue;
      seenChips.add(key);
      fresh.push({ type: "Feature", geometry: bboxPolygon(c.bbox), properties: { ...c, key } });
    }
    if (!fresh.length) return;
    data.chips.features.push(...fresh);
    refreshChips();
    renderTiles();
  }
  function setChipFeatures(fc) {
    seenChips.clear();
    data.chips = { type: "FeatureCollection", features: fc.features.map((f) => {
      const key = String(f.properties.node || `${f.properties.lat},${f.properties.lon}`);
      seenChips.add(key);
      return { ...f, properties: { ...f.properties, key } };
    }) };
    refreshChips();
    renderTiles();
  }
  function setClaims(fc) { data.claims = fc; whenMap(() => map.getSource("claims").setData(fc)); }
  function setArea(feature) {
    data.area = feature ? { type: "FeatureCollection", features: [feature] } : empty();
    whenMap(() => map.getSource("area").setData(data.area));
  }
  function boundsOf(fcs) {
    let b = null;
    const add = (x, y) => { if (!b) b = [x, y, x, y]; else b = [Math.min(b[0], x), Math.min(b[1], y), Math.max(b[2], x), Math.max(b[3], y)]; };
    const walk = (c) => (typeof c[0] === "number" ? add(c[0], c[1]) : c.forEach(walk));
    for (const fc of fcs) for (const f of fc.features || []) walk(f.geometry.coordinates);
    return b;
  }
  function fit(b, maxZoom = 14) {
    if (!b) return;
    whenMap(() => map.fitBounds([[b[0], b[1]], [b[2], b[3]]], { padding: 40, maxZoom, duration: 800 }));
  }
  function fitAll() { fit(boundsOf([data.area, data.chips, data.claims])); }

  function renderTiles() {
    const box = $("tiles");
    box.replaceChildren();
    const feats = data.chips.features;
    const shown = feats.slice(0, 60);
    for (const f of shown) {
      const p = f.properties;
      const label = p.label || (p.similarity ? `sim ${Number(p.similarity).toFixed(2)}` : p.observed || p.ref || "");
      box.append(el("button", { class: `foundry-tile ${p.inside === false ? "out" : ""}`, type: "button", title: p.node || "",
        onclick: () => { fit(p.bbox, 16); openPopup(p, [Number(p.lon), Number(p.lat)]); } },
        p.tile_url ? el("img", { src: p.tile_url, alt: "", loading: "lazy" }) : null, el("span", { text: `${p.ref || ""} ${label}` })));
    }
    const out = feats.filter((f) => f.properties.inside === false).length;
    setText("tiles-caption", feats.length
      ? `${feats.length} imagery tiles from the tools${feats.length > shown.length ? ` (first ${shown.length} shown)` : ""}${out ? ` · ${out} outside the area` : ""}. Click one to zoom to it.`
      : "Imagery tiles the tools returned appear here.");
  }

  // ---------- timeline ----------
  const STEP_ICON = { model: ["brain", "step-icon-model"], start: ["flag", "step-icon-run"], end: ["flag", "step-icon-run"] };
  function stepIcon(e) {
    if (e.kind === "tool") return e.server === "lgnd" ? ["map-search", "step-icon-lgnd"] : ["database", "step-icon-roda"];
    return STEP_ICON[e.kind] || ["point", "step-icon-run"];
  }
  function renderEntry(e) {
    const [ic, cls] = stepIcon(e);
    const bad = e.status === "error" || e.status === "limit_exceeded";
    const meta = [ms(e.ms), e.tokens_in !== null && e.tokens_in !== undefined ? `${num(e.tokens_in)} in · ${num(e.tokens_out)} out` : "",
      e.attempt ? `retry ${e.attempt}` : "", e.results ? `${e.results} results` : ""].filter(Boolean);
    const raw = el("pre", { hidden: true }, JSON.stringify(e.raw || {}, null, 2));
    const detail = e.detail ? el("div", { class: "step-detail text-secondary mt-1", hidden: true, text: e.detail }) : null;
    const toggles = el("div", { class: "d-flex gap-2 mt-1" },
      detail ? el("a", { href: "#", class: "small", onclick: (ev) => { ev.preventDefault(); ev.stopPropagation(); detail.hidden = !detail.hidden; } }, icon("eye", "me-1"), "reasoning") : null,
      el("a", { href: "#", class: "small", onclick: (ev) => { ev.preventDefault(); ev.stopPropagation(); raw.hidden = !raw.hidden; } }, icon("code", "me-1"), "raw span"));
    const item = el("div", { class: `list-group-item ${e.bounds ? "has-bounds" : ""}`, id: `step-${e.ref}`,
      onclick: () => e.bounds && fit(e.bounds) },
      el("div", { class: "d-flex gap-3" },
        el("span", { class: `avatar avatar-sm ${cls}` }, icon(ic)),
        el("div", { class: "flex-fill min-w-0" },
          el("div", { class: "d-flex align-items-center gap-2 flex-wrap" },
            el("span", { class: "badge bg-secondary-lt step-ref", text: e.ref }),
            el("strong", { text: e.title }),
            bad ? el("span", { class: "badge bg-danger-lt", text: e.status }) : null,
            el("span", { class: "ms-auto small text-secondary", text: meta.join(" · ") })),
          el("div", { class: "mt-1", text: e.sentence }), detail, toggles, raw)));
    return item;
  }
  let timelineStarted = false;
  function appendEntry(e) {
    const box = $("timeline");
    if (!timelineStarted) { box.replaceChildren(); timelineStarted = true; }
    const existing = $(`step-${e.ref}`);
    const node = renderEntry(e);
    if (existing && e.kind !== "tool") existing.replaceWith(node); else box.append(node);
  }
  function scrollToStep(ref) {
    const n = $(`step-${ref}`);
    if (!n) return;
    n.scrollIntoView({ behavior: "smooth", block: "center" });
    n.classList.remove("flash"); void n.offsetWidth; n.classList.add("flash");
  }

  // ---------- KPIs ----------
  function renderKpis(k) {
    const score = $("k-score");
    score.classList.toggle("failed", k.verdict === "FAILED");
    score.textContent = k.verdict === "FAILED" ? "FAILED" : k.score === null || k.score === undefined ? "—" : Math.round(k.score);
    setText("k-verdict", k.verdict === "scored" ? "of 100" : k.verdict === "FAILED" ? "fatal gate" : k.verdict);
    const conf = $("k-confidence");
    conf.replaceChildren(k.confidence ? el("span", { class: `badge bg-${k.confidence === "High" ? "success" : k.confidence === "Medium" ? "warning" : "danger"}-lt`, title: "Confidence = how far the judges agree on this evidence, plus trace integrity. It is not ground truth." }, icon("users-group", "me-1"), `${k.confidence} confidence`) : "");
    setText("k-confidence-why", (k.confidence_reasons || []).join("; "));
    if (k.verdict === "not scored") {
      $("k-verdict").title = k.not_scored_cause || "";
      setText("k-confidence-why", `No model call succeeded, so there was nothing to judge: ${k.not_scored_cause || "unknown cause"}`);
    }
    for (const d of ["workflow", "output"]) {
      const v = k[d];
      $(`k-${d}`).style.width = `${v || 0}%`;
      setText(`k-${d}-v`, v === null || v === undefined ? "—" : Math.round(v));
    }
    setText("k-cost", usd(k.agent_cost_usd));
    setText("k-jcost", usd(k.judging_cost_usd));
    setText("k-jcost-sub", k.valid_judges ? `· ${k.valid_judges.join("/")} judges` : "");
    setText("k-tools", num(k.tool_calls));
    setText("k-tools-sub", `· ${k.model_calls} model · ${k.errors} err · ${k.retries} retry`);
    setText("k-tokens", `${num(k.tokens_in)} / ${num(k.tokens_out)}`);
    setText("k-runtime", secs(k.runtime_s));
    setText("k-claims", k.claims_block_missing ? "no block" : `${k.claims_matched}/${k.claims_total}`);
    setText("k-claims-sub", k.claims_total ? `· ${pct(k.claims_matched / k.claims_total)}` : "");
    setText("k-inarea", k.claims_located ? `${k.claims_inside}/${k.claims_located}` : "n/a");
    setText("k-inarea-sub", k.chips_total ? `· search ${k.chips_inside}/${k.chips_total}` : "");
    setText("k-agree", k.within_one === null || k.within_one === undefined ? "—" : pct(k.within_one));
    setText("k-agree-sub", k.mad !== null && k.mad !== undefined ? `· within 1 pt · MAD ${k.mad.toFixed(2)}` : "· within 1 pt");
    setText("k-trace", k.trace_integrity ? "intact" : `${k.missing_fields} missing`);
  }
  function liveKpis(counts) {
    setText("k-tools", num(counts.tools));
    setText("k-tools-sub", `· ${counts.models} model · ${counts.errors} err`);
    setText("k-tokens", `${num(counts.tin)} / ${num(counts.tout)}`);
  }

  // ---------- scorecard ----------
  function renderScorecard(card) {
    const box = $("scorecard");
    box.replaceChildren();
    if (!card) {
      box.append(el("div", { class: "list-group-item text-secondary small", text: "Not judged yet. Use Re-judge to score this run with the panel." }));
      return;
    }
    setText("rubric-name", `${card.rubric.id} v${card.rubric.version}`);
    const gate = $("gate");
    gate.hidden = !card.gates.length;
    gate.replaceChildren(...card.gates.map((g) => el("div", {}, icon("alert-triangle", "me-1"), el("strong", { text: "FAILED: " }), g.reason)));
    const byId = Object.fromEntries((card.judges || []).map((j) => [j.key, j]));
    for (const dim of ["workflow", "output"]) {
      box.append(el("div", { class: "list-group-item py-2 bg-light-subtle small text-uppercase text-secondary fw-bold d-flex" },
        `${dim} dimension`, el("span", { class: "ms-auto", text: card.dimensions[dim] === null ? "n/a" : Math.round(card.dimensions[dim]) })));
      for (const c of card.criteria.filter((x) => x.dimension === dim)) {
        const s = c.score;
        const rationale = el("div", { hidden: true });
        if (c.kind === "judged") {
          for (const [key, vote] of Object.entries(c.votes || {})) {
            const j = byId[key] || {};
            const crit = (j.criteria || []).find((x) => x.id === c.id) || {};
            rationale.append(el("div", { class: "rationale" },
              el("span", { class: `vote vote-${vote} me-1` }, vote), el("strong", { text: key }), " ", crit.rationale || "",
              ...(crit.refs || []).map((r) => el("span", { class: "badge bg-azure-lt ms-1 ref-link", text: r, onclick: (ev) => { ev.stopPropagation(); scrollToStep(r); } }))));
          }
          const a = (card.anchors || {})[c.id] || {};
          if (Object.keys(a).length) rationale.append(el("div", { class: "small text-secondary mt-2" }, el("strong", { text: "Anchors: " }),
            Object.entries(a).map(([k, v]) => `${k} = ${v}`).join("  ·  ")));
        } else {
          rationale.append(el("div", { class: "rationale", text: `${c.question} Measured by code from the archive: ${c.value || "n/a"}.` }));
        }
        box.append(el("div", { class: "list-group-item criterion", onclick: () => (rationale.hidden = !rationale.hidden) },
          el("div", { class: "d-flex align-items-center gap-2" },
            el("span", { class: "name", text: human(c.id) }),
            c.kind === "measured" ? el("span", { class: "badge bg-secondary-lt", text: "measured" }) : null,
            c.gated ? el("span", { class: "badge bg-danger-lt", text: "gated" }) : null,
            el("span", { class: "ms-auto votes" }, c.kind === "judged"
              ? Object.entries(c.votes || {}).map(([k, v]) => el("span", { class: `vote vote-${v}`, title: `${k}: ${v}` }, v))
              : el("span", { class: "small text-secondary", text: c.value || "" })),
            el("span", { class: `badge bg-${scoreClass(s)}-lt`, style: "min-width:2.6rem", text: s === null ? "n/a" : Math.round(s) })),
          el("div", { class: "progress progress-sm mt-1" }, el("div", { class: `progress-bar bg-${scoreClass(s)}`, style: `width:${s || 0}%` })),
          rationale));
      }
    }
    const modes = $("modes");
    modes.replaceChildren(el("span", { class: "text-secondary me-2" }, icon("flag", "me-1"), "Failure modes (majority):"),
      card.failure_modes.length
        ? card.failure_modes.map((m) => el("span", { class: "badge bg-orange-lt me-1", title: m.meaning, text: `${m.id.replace(/_/g, " ")} ${m.votes}/${m.of}` }))
        : el("span", { class: "text-secondary", text: "none" }));
  }

  // ---------- judges ----------
  function seatRow(s) {
    const note = s.recused_for ? `seated for ${s.recused_for} (same family as the agent)`
      : s.stood_in_for ? `stood in for ${s.stood_in_for}, which failed` : null;
    return el("tr", { id: `judge-${s.key}` },
      el("td", {}, el("strong", { text: s.key }), note ? el("div", { class: "small text-secondary", text: note }) : null),
      el("td", { class: "text-secondary", text: s.family }),
      el("td", { class: "text-end" }, el("span", { class: "spinner-border spinner-border-sm text-secondary" })),
      el("td", { class: "text-end", text: "" }), el("td", { class: "text-end", text: "" }));
  }
  function judgeRows(seats) {
    $("judges").replaceChildren(...seats.map(seatRow));
  }
  function judgeResult(j) {
    let row = $(`judge-${j.key}`);
    if (!row) { row = seatRow(j); $("judges").append(row); }  // a reserve standing in for a failed judge
    const cells = row.children;
    cells[2].replaceChildren(j.status === "ok" ? el("span", { class: `badge bg-${scoreClass(j.score)}-lt`, text: Math.round(j.score) })
      : el("span", { class: "badge bg-danger-lt", title: j.error || "", text: "failed" }));
    cells[3].textContent = usd(j.cost_usd);
    cells[4].textContent = j.latency_s ? `${Math.round(j.latency_s)}s` : "";
  }
  function renderJudges(card) {
    if (!card) return;
    judgeRows(card.seats.map((s) => ({ ...s })));
    for (const j of card.judges) judgeResult(j);
    setText("panel-note", `median of ${card.valid_judges.join("/")} valid · judged ${card.judged_at || ""}`);
  }

  // ---------- claims, answer ----------
  function renderClaims(claims) {
    const body = $("claims");
    if (!claims.length) { body.replaceChildren(el("tr", {}, el("td", { colspan: 5, class: "text-secondary small", text: "No claims block in the answer." }))); return; }
    const badge = { matched: "success", mismatch: "danger", unsourced: "warning" };
    body.replaceChildren(...claims.map((c) => el("tr", {},
      el("td", { class: "small", text: c.claim }), el("td", { class: "small text-break", text: c.value }),
      el("td", {}, c.ref ? el("span", { class: "badge bg-azure-lt ref-link", text: c.ref, onclick: () => scrollToStep(c.ref) }) : "—"),
      el("td", {}, el("span", { class: `badge bg-${badge[c.status] || "secondary"}-lt`, text: c.status })),
      el("td", {}, c.inside === true ? el("span", { class: "badge bg-success-lt", text: "inside" }) : c.inside === false ? el("span", { class: "badge bg-warning-lt", text: "outside" }) : ""))));
  }

  // The agent's answer is Markdown: render it with marked, then sanitize with DOMPurify before it touches the DOM.
  function renderMarkdown(node, text) {
    if (window.marked && window.DOMPurify) {
      node.innerHTML = DOMPurify.sanitize(marked.parse(text, { gfm: true, breaks: false }));
      node.querySelectorAll("table").forEach((t) => t.classList.add("table", "table-sm", "table-bordered"));
      node.classList.remove("foundry-answer-plain");
    } else {
      node.textContent = text;
      node.classList.add("foundry-answer-plain");
    }
  }

  // ---------- whole view ----------
  let lastView = null;
  function renderView(v) {
    lastView = v;
    const r = v.run;
    setText("run-title", `Run ${r.id.slice(0, 8)}`);
    setText("run-pretitle", `${r.model_key || "?"} · ${r.backend || ""} · ${r.status}`);
    setText("run-meta", [r.started_at, r.area ? `area: ${r.area}${r.area_mode ? ` (${r.area_mode})` : ""}` : "no area in the prompt", r.model_id].filter(Boolean).join(" · "));
    const pv = $("prompt-view");
    pv.textContent = r.prompt || r.prompt_file || "";
    pv.hidden = false;
    show("run-form", false);
    show("run-actions", true);
    $("btn-report").href = `/reports/${r.id}`;
    renderKpis(v.kpis);
    $("timeline").replaceChildren(); timelineStarted = true;
    v.timeline.forEach(appendEntry);
    setArea(v.map.area);
    setChipFeatures(v.map.chips);
    setClaims(v.map.claims);
    setText("map-note", v.map.area ? "" : "No area in the prompt: results are shown without a boundary check.");
    fitAll();
    renderScorecard(v.scorecard);
    renderJudges(v.scorecard);
    renderClaims(v.claims);
    renderMarkdown($("answer"), v.final_answer || "(no final answer)");
    $("narrative").textContent = v.narrative || "No narrative for this run.";
    $("trouble").replaceChildren(...(v.trouble_spots || []).slice(0, 12).map((t) =>
      el("div", { class: "small" }, icon("alert-triangle", "text-warning me-1"), t.reason)));
  }

  // ---------- live ----------
  function progress(text, on = true) { show("progress", on); setText("progress-text", text); }
  function follow(runId) {
    const counts = { tools: 0, models: 0, errors: 0, tin: 0, tout: 0 };
    const es = new EventSource(`/api/runs/${runId}/events`);
    es.onmessage = (msg) => {
      const ev = JSON.parse(msg.data);
      if (ev.type === "area") {
        if (ev.geometry) { setArea({ type: "Feature", geometry: ev.geometry, properties: { label: ev.label } }); fitAll(); }
        setText("map-note", ev.label ? `Area: ${ev.label} · ${ev.source || ""} · ${ev.mode || ""}` : ev.note || "");
        progress("Agent is working…");
      } else if (ev.type === "step") {
        const e = ev.entry;
        if (e.kind === "tool") { counts.tools++; if (e.status === "error") counts.errors++; }
        if (e.kind === "model") { counts.models++; counts.tin += e.tokens_in || 0; counts.tout += e.tokens_out || 0; }
        liveKpis(counts);
        if (ev.chips && ev.chips.length) {
          addChips(ev.chips);
          const b = boundsOf([{ features: ev.chips.filter((c) => c.bbox).map((c) => ({ geometry: bboxPolygon(c.bbox) })) }]);
          e.bounds = b;
          fit(boundsOf([data.area, data.chips]));
        }
        appendEntry(e);
        progress(e.kind === "end" ? "Agent finished. Writing the summary and report…" : `Agent is working… ${e.title}`);
      } else if (ev.type === "judging") {
        judgeRows(ev.seats);
        setText("panel-note", `${ev.seats.length} judges deliberating…`);
        progress("The judge panel is scoring the run…");
      } else if (ev.type === "judge") {
        judgeResult(ev);
      } else if (ev.type === "not_scored") {
        setText("panel-note", "Not scored: the agent never got a model reply, so the panel wasn't asked.");
        $("error").hidden = false; $("error").textContent = `Not scored (infrastructure error): ${ev.cause}`;
      } else if (ev.type === "judge_error") {
        $("error").hidden = false; $("error").textContent = `Judging failed: ${ev.error}`;
      } else if (ev.type === "done") {
        es.close();
        progress("", false);
        $("btn-run").disabled = false;
        if (ev.view) { renderView(ev.view); history.replaceState(null, "", `/runs/${runId}`); }
        if (ev.status === "error" || ev.error) { $("error").hidden = false; $("error").textContent = ev.error || "The run failed."; }
      }
    };
    es.onerror = () => { /* EventSource retries on its own; the server ends the stream after "done". */ };
  }

  async function startRun(ev) {
    ev.preventDefault();
    const prompt = $("prompt").value.trim();
    show("error", false);
    if (!prompt) { $("error").hidden = false; $("error").textContent = "Type a prompt first."; return; }
    $("btn-run").disabled = true;
    progress("Reading the area from the prompt…");
    const res = await fetch("/api/runs", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ prompt, model: $("model").value }) });
    const body = await res.json();
    if (!res.ok) { $("btn-run").disabled = false; progress("", false); $("error").hidden = false; $("error").textContent = body.error || "Couldn't start the run."; return; }
    const pv = $("prompt-view"); pv.textContent = prompt; pv.hidden = false; show("run-form", false);
    setText("run-title", `Run ${body.run_id.slice(0, 8)}`); setText("run-pretitle", `${$("model").value} · live`);
    follow(body.run_id);
  }

  async function rejudge() {
    if (!lastView) return;
    const id = lastView.run.id;
    $("btn-rejudge").disabled = true;
    const res = await fetch(`/api/runs/${id}/judge`, { method: "POST" });
    if (!res.ok) { $("btn-rejudge").disabled = false; $("error").hidden = false; $("error").textContent = (await res.json()).detail || "Couldn't start judging."; return; }
    progress("The judge panel is scoring the run…");
    follow(id);
  }

  // ---------- boot ----------
  const EXAMPLES = [
    "Find the data centers within the city limits of Richardson, TX. Give each one's location exactly as the tool returned it.",
    "Find data centers in ZIP code 75080 and give each one's location exactly as the tool returned it.",
    "Map the farmland in Khammouane province, Laos, and give the location of each farmland area you confirm.",
    "Find the large warehouses in Nagoya, Japan, and give each one's location exactly as the tool returned it.",
  ];
  initMap();
  if (!RUN_ID) {
    $("run-form").addEventListener("submit", startRun);
    const ex = $("examples");
    ex.append(el("span", { class: "text-secondary", text: "Try:" }));
    for (const p of EXAMPLES) ex.append(el("a", { href: "#", class: "badge bg-azure-lt text-wrap text-start", text: p.split(/[.,]/)[0],
      onclick: (e) => { e.preventDefault(); $("prompt").value = p; } }));
  } else {
    fetch(`/api/runs/${RUN_ID}`).then((r) => r.json()).then(renderView)
      .catch((e) => { $("error").hidden = false; $("error").textContent = `Couldn't load the run: ${e}`; });
  }
  $("btn-rejudge").addEventListener("click", rejudge);
})();
