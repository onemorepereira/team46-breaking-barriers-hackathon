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
  // tiles.serve: imagery basemaps load through the console's cache (/tiles/base); OSM always loads from OSM.
  const PROXY = document.body.dataset.tileProxy === "1";
  const viaConsole = (b) => (PROXY && b.id !== "osm" ? { ...b, tiles: [`/tiles/base/${b.id}/{z}/{x}/{y}.jpg`] } : b);
  const BASEMAPS = [
    { id: "s2", label: "Sentinel-2", attribution: "Sentinel-2 cloudless 2023 by EOX (contains modified Copernicus Sentinel data)",
      tiles: ["https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2023_3857/default/g/{z}/{y}/{x}.jpg"], maxzoom: 15 },
    { id: "usgs", label: "USGS imagery", attribution: "USGS The National Map",
      tiles: ["https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/tile/{z}/{y}/{x}"], maxzoom: 16 },
    { id: "naip", label: "NAIP (US)", attribution: "USGS The National Map, NAIP",
      tiles: ["https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPImagery/ImageServer/exportImage?bbox={bbox-epsg-3857}&bboxSR=3857&imageSR=3857&size=256,256&format=jpg&f=image"], maxzoom: 19 },
    { id: "osm", label: "Streets", attribution: "© OpenStreetMap contributors",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"], maxzoom: 19 },
  ].map(viaConsole);
  const CYAN = "#01d5f9", ORANGE = "#fd8800";
  const empty = () => ({ type: "FeatureCollection", features: [] });
  const data = { chips: empty(), claims: empty(), area: empty() };
  let map, mapReady = false;
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
      cooperativeGestures: true,  // the wheel scrolls the page; Ctrl/⌘ + wheel (or pinch, or the buttons) zooms
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
      // One handler, one result per click: a claimed location wins over a result dot, which wins over a footprint.
      map.on("click", (e) => {
        for (const layer of ["claims", "chip-dots", "chips-fill"]) {
          const hit = map.queryRenderedFeatures(e.point, { layers: [layer] })[0];
          if (hit) { openDetail(hit.properties, { move: "ease" }); return; }
        }
      });
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
  new ResizeObserver(() => {
    if (map) map.resize();
    if (!detail.hidden) detail.classList.toggle("bottom", phone());  // re-dock on rotation or resize
  }).observe(document.getElementById("map"));

  // ---------- result details: a panel docked inside the map (docs/console-polish) ----------
  // One camera call per action, and never persistent map padding: map clicks ease with a one-off offset,
  // the tile strip fits with per-call padding (pad()), and closing doesn't move the camera.
  const detail = $("detail");
  let detailOpener = null;
  // Bottom-docked on phones, or when the map is too narrow to give up 300 px on its right.
  const phone = () => window.matchMedia("(max-width: 575.98px)").matches || $("map").clientWidth < 600;
  const panelSize = () => (detail.hidden ? 0 : phone() ? detail.offsetHeight : detail.offsetWidth);
  function pad() {
    const p = { top: 40, bottom: 40, left: 40, right: 40 };
    if (!detail.hidden) { if (phone()) p.bottom += panelSize(); else p.right += panelSize(); }
    return p;
  }
  function openDetail(p, { move = "ease" } = {}) {
    const where = p.inside === true || p.inside === "true" ? ["Inside the requested area", "success"]
      : p.inside === false || p.inside === "false" ? ["Outside the requested area", "warning"] : ["No area to check", "secondary"];
    const img = p.tile_url ? el("img", { src: p.tile_url, alt: `Imagery under ${p.node || "this result"}` }) : null;
    if (img) img.addEventListener("error", () => img.replaceWith(el("div", { class: "foundry-detail-missing", text: "Tile unavailable" })));
    $("detail-body").replaceChildren(
      img || el("div", { class: "foundry-detail-missing", text: "No imagery tile" }),
      el("div", { class: "mt-2 fw-bold text-break", text: p.claim || p.label || p.node || "Result" }),
      el("div", { class: "small text-secondary" },
        [p.index ? String(p.index).toUpperCase() : null, p.observed ? `observed ${p.observed}` : null,
         p.similarity && p.similarity !== "null" ? `similarity ${Number(p.similarity).toFixed(2)}` : null].filter(Boolean).join(" · ")),
      el("div", { class: "small" }, `${Number(p.lat).toFixed(4)}, ${Number(p.lon).toFixed(4)}`),
      el("div", { class: "mt-2 d-flex gap-1 flex-wrap" },
        el("span", { class: `badge bg-${where[1]}-lt`, text: where[0] }),
        p.ref ? el("button", { type: "button", class: "badge bg-azure-lt ref-link border-0", text: `from ${p.ref}`, "aria-label": `Show step ${p.ref}`, onclick: (ev) => scrollToStep(p.ref, ev) }) : null),
      p.tile_source ? el("div", { class: "text-secondary mt-2", style: "font-size:.68rem", text: p.tile_source }) : null);
    const wasOpen = !detail.hidden;
    detail.classList.toggle("bottom", phone());
    detail.hidden = false;
    if (!wasOpen) detailOpener = document.activeElement;
    $("detail-close").focus({ preventScroll: true });
    if (move === "ease" && mapReady) {
      const size = panelSize();
      map.easeTo({ center: [Number(p.lon), Number(p.lat)], offset: phone() ? [0, -size / 2] : [-size / 2, 0], duration: 500 });
    }
  }
  function closeDetail() {
    if (detail.hidden) return;
    detail.hidden = true;
    let back = detailOpener;
    if (back && !document.contains(back) && back.dataset && back.dataset.key) {
      back = document.querySelector(`#tiles [data-key="${CSS.escape(back.dataset.key)}"]`);  // re-rendered while streaming
    }
    if (!back || !document.contains(back)) back = mapReady ? map.getCanvas() : null;
    if (back) back.focus({ preventScroll: true });
    detailOpener = null;
  }
  $("detail-close").addEventListener("click", closeDetail);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !detail.hidden) closeDetail(); });

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
    whenMap(() => map.fitBounds([[b[0], b[1]], [b[2], b[3]]], { padding: pad(), maxZoom, duration: 800 }));
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
        "data-key": p.key || p.node || "",
        onclick: () => { openDetail(p, { move: "none" }); fit(p.bbox, 16); } },
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
  // Step links scroll the timeline list, never the page, unless the user asks (docs/console-polish AC4).
  const toast = $("toast");
  let toastTimer = null, toastTarget = null;
  function hideToast() { toast.hidden = true; clearTimeout(toastTimer); toastTarget = null; }
  function armToast() { clearTimeout(toastTimer); toastTimer = setTimeout(hideToast, 8000); }
  toast.addEventListener("mouseenter", () => clearTimeout(toastTimer));
  toast.addEventListener("mouseleave", armToast);
  toast.addEventListener("focusin", () => clearTimeout(toastTimer));
  toast.addEventListener("focusout", armToast);
  $("toast-show").addEventListener("click", () => {
    const n = toastTarget;
    hideToast();
    if (n) { n.scrollIntoView({ block: "nearest", behavior: "smooth" }); flashStep(n); }
  });
  function flashStep(n) { n.classList.remove("flash"); void n.offsetWidth; n.classList.add("flash"); }
  function scrollToStep(ref, ev) {
    const n = $(`step-${ref}`), list = $("timeline");
    if (!n || !list) return;
    // Where will the step land after the list scrolls to center it? Only scroll the list if that's on screen.
    const lr = list.getBoundingClientRect(), nr = n.getBoundingClientRect();
    const want = list.scrollTop + (nr.top - lr.top) - list.clientHeight / 2 + n.offsetHeight / 2;
    const final = Math.min(Math.max(0, want), Math.max(0, list.scrollHeight - list.clientHeight));
    const landing = nr.top - (final - list.scrollTop);
    if (landing >= 0 && landing + n.offsetHeight <= window.innerHeight) {
      list.scrollTo({ top: final, behavior: "smooth" });
      flashStep(n);
      return;
    }
    toastTarget = n;
    $("toast-text").textContent = `Step ${ref} is in the timeline`;
    toast.hidden = false;
    armToast();
    // From the keyboard (a click event with no pointer: detail 0), move focus to Show so it's reachable.
    if (ev && ev.detail === 0) $("toast-show").focus({ preventScroll: true });
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

  // ---------- plain explanation (saved evidence only) ----------
  function renderExplanation(explanation) {
    const card = $("explanation-card");
    card.hidden = !explanation;
    if (!explanation) return;
    setText("explanation-headline", explanation.headline);
    setText("explanation-summary", explanation.summary);
    $("explanation-checks").replaceChildren(...explanation.check_by_hand.map((text) => el("li", { text })));
  }

  function renderConditions(data) {
    show("conditions-card", Boolean(data));
    const box = $("conditions-content");
    box.replaceChildren();
    if (!data) return;
    if (data.error) box.append(el("p", {text:"Request conditions could not be extracted. This request is not fully verified."}));
    const table = el("table", {class:"table table-sm"});
    table.append(el("thead", {}, el("tr", {}, el("th", {text:"Listed location"}),
      ...data.conditions.map(c => el("th", {text:c.text})))));
    const body = el("tbody");
    for (const row of data.rows) body.append(el("tr", {}, el("td", {text:row.value}),
      ...row.cells.map(c => el("td", {title:c.reason}, el("strong", {text:c.status}),
        el("div", {class:"small text-secondary",text:c.reason})))));
    table.append(body); box.append(table);
    if (!data.rows.length) box.append(el("p", {text:"No declared coordinate claims are available to check."}));
  }

  // ---------- scorecard ----------
  function renderScorecard(card) {
    const box = $("scorecard");
    box.replaceChildren();
    if (!card) {
      box.append(el("div", { class: "list-group-item text-secondary small", text: "Not judged yet. Use Re-judge to score this run with the panel." }));
      return;
    }
    setText("rubric-name", `${card.rubric.id} v${card.rubric.version} · ${card.guidance ? `guidance v${card.guidance.version}` : "no guidance"}`);
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
              el("span", { class: `vote vote-${vote} me-1` }, vote), el("strong", { text: key }), " ",
              crit.changed ? el("span", { class: "badge bg-orange-lt me-1", text: "changed" }) : null, crit.rationale || "",
              ...(crit.refs || []).map((r) => el("button", { type: "button", class: "badge bg-azure-lt ms-1 ref-link border-0", text: r, "aria-label": `Show step ${r}`, onclick: (ev) => { ev.stopPropagation(); scrollToStep(r, ev); } })),
              // a judge's reply to a review: inline when its vote changed, else a tooltip (keeps the card short)
              crit.response && crit.changed ? el("div", { class: "text-secondary mt-1" }, icon("message-reply", "me-1"), crit.response) : null,
              crit.response && !crit.changed ? el("span", { class: "ms-1 text-secondary", title: `Kept its vote: ${crit.response}`, "aria-label": `Kept its vote: ${crit.response}` }, icon("message-reply")) : null));
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
          el("div", { class: "small text-secondary mt-1", text: c.plain || c.question }),
          el("div", { class: "progress progress-sm mt-1" }, el("div", { class: `progress-bar bg-${scoreClass(s)}`, style: `width:${s || 0}%` })),
          humanLine(c), rationale));
      }
    }
    const modes = $("modes");
    modes.replaceChildren(el("span", { class: "text-secondary me-2" }, icon("flag", "me-1"), "Failure modes (majority):"),
      ...(card.failure_modes.length  // spread: replaceChildren() would print an array as text
        ? card.failure_modes.map((m) => el("span", { class: "badge bg-orange-lt me-1", title: m.meaning, text: `${m.id.replace(/_/g, " ")} ${m.votes}/${m.of}` }))
        : [el("span", { class: "text-secondary", text: "none" })]));
  }

  // Human review on a judged criterion (docs/judge-feedback): original → revised median, and the reviewers' score.
  function humanLine(c) {
    const moved = c.original_median != null && c.original_median !== c.median;
    if (c.kind !== "judged" || (!moved && c.human == null)) return null;  // nothing worth a line
    const bits = [];
    if (moved) bits.push(`original ${c.original_median} → revised ${c.median}`);
    else bits.push(`panel ${c.median}`);
    if (c.human != null) bits.push(`human ${c.human}${(c.human_reviewers || []).length ? ` (${c.human_reviewers.join(", ")})` : ""}`);
    return el("div", { class: "small text-secondary mt-1" }, icon("user-check", "me-1"), bits.join(" · "));
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
      el("td", {}, c.ref ? el("button", { type: "button", class: "badge bg-azure-lt ref-link border-0", text: c.ref, "aria-label": `Show step ${c.ref}`, onclick: (ev) => scrollToStep(c.ref, ev) }) : "—"),
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
    renderExplanation(v.explanation);
    renderConditions(v.conditions);
    setText("source-check-note", v.source_check_note || "");
    show("source-check-note", Boolean(v.source_check_note));
    renderScorecard(v.scorecard);
    renderJudges(v.scorecard);
    renderClaims(v.claims);
    renderMarkdown($("answer"), v.final_answer || "(no final answer)");
    $("narrative").textContent = v.narrative || "No narrative for this run.";
    $("trouble").replaceChildren(...(v.trouble_spots || []).slice(0, 12).map((t) =>
      el("div", { class: "small" }, icon("alert-triangle", "text-warning me-1"), t.reason)));
    for (const hook of FOUNDRY.onView) hook(v);  // feedback.js: the review card
  }
  // For feedback.js (the review card): re-render after a reconsideration, and update the judge panel live.
  const FOUNDRY = Object.assign(window.FOUNDRY || (window.FOUNDRY = {}), { onView: [], renderView, renderScorecard, judgeRows, judgeResult, el, icon, apiError });

  // ---------- live ----------
  function progress(text, on = true) { show("progress", on); setText("progress-text", text); }
  function follow(runId) {
    const counts = { tools: 0, models: 0, errors: 0, tin: 0, tout: 0 };
    const es = new EventSource(`/api/runs/${runId}/events`);
    es.onmessage = (msg) => {
      const ev = JSON.parse(msg.data);
      if (ev.type === "area") {
        if (ev.geometry) { setArea({ type: "Feature", geometry: ev.geometry, properties: { label: ev.label } }); if (detail.hidden) fitAll(); }
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
          if (detail.hidden) fit(boundsOf([data.area, data.chips]));  // don't pull the view from an open result
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
    if (!res.ok) { $("btn-run").disabled = false; progress("", false); $("error").hidden = false; $("error").textContent = body.error || apiError(body) || "Couldn't start the run."; return; }
    const pv = $("prompt-view"); pv.textContent = prompt; pv.hidden = false; show("run-form", false);
    setText("run-title", `Run ${body.run_id.slice(0, 8)}`); setText("run-pretitle", `${$("model").value} · live`);
    follow(body.run_id);
  }

  async function rejudge() {
    if (!lastView) return;
    const id = lastView.run.id;
    $("btn-rejudge").disabled = true;
    const res = await fetch(`/api/runs/${id}/judge`, { method: "POST" });
    if (!res.ok) { $("btn-rejudge").disabled = false; $("error").hidden = false; $("error").textContent = apiError(await res.json()) || "Couldn't start judging."; return; }
    progress("The judge panel is scoring the run…");
    follow(id);
  }

  // ---------- example cards (static/examples.json): continent tabs over a grid; a click fills the prompt ----------
  function loadExamples() {
    fetch("/static/examples.json").then((r) => r.json()).then(({ continents, examples }) => {
      const tabs = $("example-tabs"), grid = $("example-grid");
      let current = continents.includes("Asia") ? "Asia" : "All";
      const cards = examples.map((x) => {
        const card = el("button", { type: "button", class: "card card-sm foundry-example w-100 text-start", title: x.prompt },
          el("div", { class: "card-body p-2" },
            el("div", { class: "d-flex align-items-center justify-content-between gap-2 mb-1" },
              el("span", { class: "text-uppercase text-secondary fw-semibold foundry-example-region", text: `${x.continent} · ${x.country}` }),
              el("span", { class: "foundry-example-icon", "aria-hidden": "true" }, el("i", { class: `ti ti-${x.icon}` }))),
            el("div", { class: "fw-semibold", text: x.task }),
            el("div", { class: "text-secondary small", text: x.place }),
            el("div", { class: "mt-1" }, el("span", { class: "badge bg-cyan-lt foundry-example-theme", text: x.theme }))));
        card.addEventListener("click", () => {
          $("prompt").value = x.prompt;
          for (const c of cards) c.node.classList.remove("selected");
          card.classList.add("selected");
          $("prompt").focus();
        });
        return { x, node: card, col: el("div", { class: "col-12 col-sm-6 col-lg-4 col-xl-3" }, card) };
      });
      const count = (c) => (c === "All" ? examples.length : examples.filter((x) => x.continent === c).length);
      const show = () => {
        for (const b of tabs.children) {
          const on = b.dataset.continent === current;
          b.classList.toggle("active", on); b.setAttribute("aria-pressed", String(on));
        }
        grid.replaceChildren(...cards.filter((c) => current === "All" || c.x.continent === current).map((c) => c.col));
      };
      for (const c of [...continents.filter((k) => count(k) > 0), "All"]) {
        tabs.append(el("button", { type: "button", class: "btn btn-sm btn-pill foundry-example-tab", "data-continent": c,
          "aria-pressed": "false", onclick: () => { current = c; show(); } }, c, el("span", { class: "ms-1 opacity-75", text: String(count(c)) })));
      }
      show();
      $("examples").hidden = false;
    }).catch(() => { /* examples are a convenience; the form works without them */ });
  }

  // FastAPI errors: {"detail": "text"} (404, 409, 400) or {"detail": [{"msg": …}, …]} (422 validation).
  function apiError(body) {
    const d = body && body.detail;
    return Array.isArray(d) ? d.map((x) => x.msg).join("; ") : d || null;
  }

  // For tests/browser/console_probe.py: resolve when the map has finished moving and rendering.
  window.__foundryIdle = () => new Promise((resolve) => whenMap(() => (map.isMoving() ? map.once("idle", resolve) : resolve())));
  window.__foundryPadding = () => (mapReady ? map.getPadding() : null);

  // ---------- boot ----------
  initMap();
  if (!RUN_ID) {
    $("run-form").addEventListener("submit", startRun);
    loadExamples();
  } else {
    fetch(`/api/runs/${RUN_ID}`).then(async (r) => { const b = await r.json(); if (!r.ok) throw new Error(apiError(b) || r.statusText); return b; }).then(renderView)
      .catch((e) => { $("error").hidden = false; $("error").textContent = `Couldn't load the run: ${e}`; });
  }
  $("btn-rejudge").addEventListener("click", rejudge);
})();
