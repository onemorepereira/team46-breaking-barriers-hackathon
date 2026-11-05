// Reference check and data licences on the run page (docs/adb-alignment AC4, AC6, AC7).
(() => {
  "use strict";
  const F = window.FOUNDRY;
  if (!F) return;
  const { el, icon } = F;
  const $ = (id) => document.getElementById(id);
  const fmt = (v) => (v === null || v === undefined ? "n/a" : String(v));

  function metric(label, value, hint) {
    return el("div", { class: "col-6 col-md-3" }, el("div", { class: "text-secondary small", title: hint }, label),
      el("div", { class: "h2 m-0", text: fmt(value) }));
  }

  function renderReference(ref) {
    const col = $("reference-col");
    if (!ref) { col.hidden = true; clearMap(); return; }
    col.hidden = false;
    const body = $("reference-body");
    if (ref.error) {
      $("reference-sub").textContent = ref.id || "";
      body.replaceChildren(el("div", { class: "text-danger small" }, icon("alert-triangle", "me-1"), ref.error));
      clearMap();
      return;
    }
    $("reference-sub").textContent = `${ref.id} · ${ref.completeness}`;
    const cell = Math.round(ref.cell_m);
    body.replaceChildren(...[  // replaceChildren prints null as text: drop empty slots
      el("div", { class: "small text-secondary mb-2" },
        `${(ref.concept || "").replace(/_/g, " ")} in ${ref.place} · ${ref.source?.name || ""} ${ref.source?.version || ""} · licence ${ref.licence?.name || ""}`),
      ref.stale ? el("div", { class: "small text-warning mb-2" }, icon("alert-triangle", "me-1"), "The repo's copy of this reference has changed since the run was tied.") : null,
      el("div", { class: "row g-2 mb-2" },
        metric("Site recall", ref.site_recall, "Share of reference assets a claimed site's cell touches"),
        metric("Cell precision", ref.cell_precision, "Share of claimed cells that touch a reference asset"),
        metric("Count ratio", ref.count_ratio, "Distinct claimed sites ÷ reference assets"),
        metric("Lift", ref.lift, "Cell precision ÷ the share of the area's cells that touch an asset")),
      el("div", { class: "small" }, `${ref.found.length}/${ref.assets} assets found · ${ref.sites} claimed sites in ${ref.flagged_cells} ${cell} m cells · ${ref.outside_area} outside the reference area`),
      ...(ref.notes || []).map((n) => el("div", { class: "small text-secondary" }, icon("info-circle", "me-1"), n)),
      ref.missed?.length ? el("div", { class: "small mt-1" }, el("span", { class: "text-secondary", text: "Missed: " }), ref.missed.join(", ")) : null,
      ...rankingRows(ref.ranking),
      el("div", { class: "small text-secondary mt-2" }, "On the map: reference assets green (found) or red (missed); claimed cells with no asset outlined orange.")].filter(Boolean));
    drawMap(ref);
  }

  // Ranking metrics over the run's ranked candidates (docs/ranking-metrics).
  function effortText(e, random) {
    if (!e) return "n/a";
    return e.cells != null ? `${e.cells.toLocaleString("en-US")} cells (random ≈ ${random != null ? random.toLocaleString("en-US") : "—"})` : `not reached (${Math.round(e.reached * 100)}% after ${e.after} cells)`;
  }
  function rankingRows(rk) {
    if (!rk) return [];
    const eff = rk.effort || {};
    return [
      el("div", { class: "small fw-semibold mt-3 mb-1", text: "Ranking" }),
      el("div", { class: "row g-2 mb-1" },
        metric(`Recall@k (k = ${rk.k})`, rk.recall_at_k, "Share of reference assets touched by this run's top-k ranked cells"),
        metric("AUROC", rk.auroc, "How often an asset cell ranks above an empty one (0.5 = random)"),
        metric("AP", rk.ap, "Average precision down this run's ranking")),
      el("div", { class: "small" }, `Review effort to find 50% / 80% / 90% of the assets: ${["50", "80", "90"].map((p) => effortText(eff[p], rk.random_effort?.[p])).join(" · ")}`),
      el("div", { class: "small text-secondary" }, `${rk.candidates} ranked cells: the answer's sites first, then each LGND search's results by similarity, searches interleaved.`),
      ...(rk.notes || []).map((n) => el("div", { class: "small text-secondary" }, icon("info-circle", "me-1"), n)),
    ];
  }

  function clearMap() {
    const map = F.map();
    if (!map) return;
    for (const id of ["ref-assets-fill", "ref-assets-line", "ref-false"]) if (map.getLayer(id)) map.removeLayer(id);
    for (const id of ["ref-assets", "ref-false"]) if (map.getSource(id)) map.removeSource(id);
  }

  function drawMap(ref, tries = 0) {
    const map = F.map();
    if (!map) { if (tries < 40) setTimeout(() => drawMap(ref, tries + 1), 250); return; }
    clearMap();
    const falseCells = { type: "FeatureCollection", features: (ref.false_alarm_cells || []).map((g) => ({ type: "Feature", geometry: g, properties: {} })) };
    map.addSource("ref-assets", { type: "geojson", data: ref.features });
    map.addSource("ref-false", { type: "geojson", data: falseCells });
    const colour = ["case", ["get", "found"], "#2fb344", "#d63939"];
    map.addLayer({ id: "ref-assets-fill", type: "fill", source: "ref-assets", filter: ["!=", ["geometry-type"], "Point"], paint: { "fill-color": colour, "fill-opacity": 0.35 } });
    map.addLayer({ id: "ref-assets-line", type: "line", source: "ref-assets", paint: { "line-color": colour, "line-width": 2 } });
    map.addLayer({ id: "ref-false", type: "line", source: "ref-false", paint: { "line-color": "#f76707", "line-width": 1.5 } });
  }

  function renderLicences(lic, kpis) {
    const badge = $("licences-badge");
    const ok = lic && lic.presentable;
    const tag = (cls, ic, text, title) => el("span", { class: `badge bg-${cls}-lt`, title }, icon(ic, "me-1"), text);
    badge.replaceChildren(lic ? (ok ? tag("success", "circle-check", "Presentable", "Every source allows sharing with third parties")
      : tag("warning", "alert-triangle", "Check before sharing", (lic.blockers || []).join("; "))) : "");
    const k = $("k-presentable");
    if (k) k.replaceChildren(lic ? (ok ? tag("success", "license", "Presentable", "")
      : tag("warning", "license", `Check before sharing: ${(kpis?.licence_blockers || lic.blockers || []).length} sources`, (lic.blockers || []).join("; "))) : "");
    const body = $("licences-body");
    if (!lic || !lic.items.length) { body.replaceChildren(el("tr", {}, el("td", { colspan: 4, class: "text-secondary small", text: "No sources recorded." }))); return; }
    body.replaceChildren(...lic.items.map((i) => el("tr", {},
      el("td", {}, el("div", { text: i.name }), el("div", { class: "small text-secondary", text: i.provider })),
      el("td", { class: "small" }, `${i.role}: ${i.used_as}`),
      el("td", { class: "small" }, i.url ? el("a", { href: i.url, target: "_blank", rel: "noopener", text: i.licence }) : i.licence,
        i.attribution ? el("div", { class: "text-secondary", text: i.attribution }) : null),
      el("td", { class: "text-end" }, i.presentable ? icon("circle-check", "text-success") : el("span", { class: "text-warning", title: i.fact_source || "" }, icon("alert-triangle"))))));
  }

  F.onView.push((v) => { renderReference(v.reference); renderLicences(v.licences, v.kpis); });
})();
