import { useEffect, useRef, useState } from "react";
import {
  candidatesOf,
  imageForCandidate,
  endpoint,
  fitCoordinates,
  VISUAL_MARK,
  VISUAL_SOURCE,
  visualCaption,
  type Candidate,
  type View,
} from "./api";
import { Icon } from "./Icon";
import type { Preferences } from "./preferences";
let loading: Promise<any> | null = null;
function library(): Promise<any> {
  if ((window as any).maplibregl)
    return Promise.resolve((window as any).maplibregl);
  if (!loading)
    loading = new Promise((resolve, reject) => {
      const css = document.createElement("link");
      css.rel = "stylesheet";
      css.href = endpoint("/static/vendor/maplibre/maplibre-gl.css");
      document.head.append(css);
      const s = document.createElement("script");
      s.src = endpoint("/static/vendor/maplibre/maplibre-gl.js");
      s.onload = () => resolve((window as any).maplibregl);
      s.onerror = () => {
        loading = null;
        reject(new Error("Map library could not load"));
      };
      document.head.append(s);
    });
  return loading;
}
export default function EvidenceMap({
  view,
  selected,
  selectedChip,
  onSelect,
  onSelectChip,
  onClose,
  onTrace,
  preferences,
  focusBounds,
}: {
  view: View | null;
  selected: number | null;
  selectedChip: number | null;
  onSelect: (n: number) => void;
  onSelectChip: (n: number) => void;
  onClose: () => void;
  onTrace: (ref: string) => void;
  preferences: Preferences;
  focusBounds: number[] | null;
}) {
  const host = useRef<HTMLDivElement>(null),
    map = useRef<any>(null),
    markers = useRef<any[]>([]),
    fit = useRef<(animate?: boolean) => void>(() => {}),
    lastInspection = useRef({ open: false, runId: "" }),
    onSelectRef = useRef(onSelect),
    onSelectChipRef = useRef(onSelectChip),
    viewRef = useRef(view),
    tileFocus = useRef<HTMLButtonElement>(null),
    tileBody = useRef<HTMLDivElement>(null);
  onSelectRef.current = onSelect;
  onSelectChipRef.current = onSelectChip;
  viewRef.current = view;
  const [ready, setReady] = useState(false),
    [error, setError] = useState(""),
    [layer, setLayer] = useState("s2"),
    [imageError, setImageError] = useState(false),
    [imageAttempt, setImageAttempt] = useState(0),
    // The URL whose image finished loading: "loaded" belongs to one image, so a cached image that loads
    // before the reset effect runs can't leave the frame stuck on "Fetching" (a thumbnail's URL is cached).
    [loadedSrc, setLoadedSrc] = useState<string | null>(null),
    [imageMode, setImageMode] = useState<"checked" | "agent">("checked"),
    [overlays, setOverlays] = useState({
      area: true,
      chips: true,
      reference: true,
    });
  const chipIndex = selectedChip ?? imageForCandidate(view, selected),
    chip = chipIndex === null ? null : view?.map.chips?.features?.[chipIndex],
    candidate = selected === null ? null : candidatesOf(view)[selected];
  const inspecting = selected !== null || selectedChip !== null;
  // A reported site opens on the image it was visually checked against (docs/visual-check).
  const visual = selectedChip === null ? candidate?.visual || null : null,
    checkedUrl =
      visual?.image_url && imageMode === "checked" ? visual.image_url : null,
    shownUrl: string | undefined = checkedUrl || chip?.properties?.tile_url,
    caption = visualCaption(view?.map.visual);
  const imgSrc =
    shownUrl && imageAttempt
      ? `${shownUrl}${shownUrl.includes("?") ? "&" : "?"}retry=${imageAttempt}`
      : shownUrl;
  const imageLoaded = !!imgSrc && loadedSrc === imgSrc;
  const reduced =
    preferences.reducedMotion ||
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const duration = reduced ? 0 : 550;
  useEffect(() => {
    let cancelled = false;
    let resize: ResizeObserver | undefined;
    library()
      .then((lib) => {
        if (cancelled || !host.current) return;
        try {
          const m = new lib.Map({
            container: host.current,
            center: [78, 23],
            zoom: 2.3,
            // Added below as compact: by default MapLibre only compacts the credit on maps up to 640px
            // wide, so on a desktop it sat fully expanded under the legend.
            attributionControl: false,
            style: {
              version: 8,
              sources: {
                base: {
                  type: "raster",
                  tiles: [endpoint("/tiles/base/s2/{z}/{x}/{y}.jpg")],
                  tileSize: 256,
                  attribution:
                    "Sentinel-2 cloudless 2023 by EOX · modified Copernicus Sentinel data",
                },
              },
              layers: [{ id: "base", type: "raster", source: "base" }],
            },
          });
          map.current = m;
          m.addControl(new lib.NavigationControl(), "bottom-right");
          m.addControl(
            new lib.AttributionControl({ compact: true }),
            "bottom-right",
          );
          // Evidence overlays must load even if a context basemap tile is unavailable.
          m.on("style.load", () => setReady(true));
          // MapLibre's compact attribution starts expanded and only folds after the first drag, so it
          // sat over the legend. Start it folded behind its (i) button; a click still expands it.
          m.once("load", () =>
            m
              .getContainer()
              .querySelector(".maplibregl-ctrl-attrib.maplibregl-compact")
              ?.classList.remove("maplibregl-compact-show"),
          );
          m.on("error", () =>
            setError(
              "Some map imagery is unavailable. The saved evidence and coordinates remain accessible.",
            ),
          );
          resize = new ResizeObserver(() => m.resize());
          resize.observe(host.current);
        } catch {
          setError(
            "Map unavailable in this browser. Use the saved coordinates and evidence below.",
          );
        }
      })
      .catch((e) => setError(e.message));
    return () => {
      cancelled = true;
      resize?.disconnect();
      map.current?.remove();
      map.current = null;
    };
  }, []);
  useEffect(() => {
    setImageError(false);
    setImageAttempt(0);
    // A new tile starts at its title, even when it was picked from thumbnails further down.
    tileBody.current?.scrollTo({ top: 0 });
  }, [chipIndex, selected, imageMode, view?.run.id]);
  useEffect(() => setImageMode("checked"), [selected, view?.run.id]);
  useEffect(() => {
    if (!ready || !map.current) return;
    const sources: Record<
      string,
      { tiles: string; credit: string; max: number }
    > = {
      s2: {
        tiles: endpoint("/tiles/base/s2/{z}/{x}/{y}.jpg"),
        credit:
          "Sentinel-2 cloudless 2023 by EOX · modified Copernicus Sentinel data",
        max: 15,
      },
      usgs: {
        tiles: endpoint("/tiles/base/usgs/{z}/{x}/{y}.jpg"),
        credit: "USGS The National Map · imagery coverage varies",
        max: 16,
      },
      naip: {
        tiles: endpoint("/tiles/base/naip/{z}/{x}/{y}.jpg"),
        credit: "USGS The National Map · NAIP (US coverage)",
        max: 19,
      },
      streets: {
        tiles: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        credit: "© OpenStreetMap contributors",
        max: 19,
      },
    };
    const source = sources[layer];
    const m = map.current;
    if (m.getLayer("base")) m.removeLayer("base");
    if (m.getSource("base")) m.removeSource("base");
    m.addSource("base", {
      type: "raster",
      tiles: [source.tiles],
      tileSize: 256,
      maxzoom: source.max,
      attribution: source.credit,
    });
    const first = m.getStyle().layers?.[0]?.id;
    m.addLayer({ id: "base", type: "raster", source: "base" }, first);
    setError("");
  }, [layer, ready]);
  useEffect(() => {
    if (!ready || !map.current) return;
    const m = map.current,
      lib = (window as any).maplibregl,
      empty = { type: "FeatureCollection", features: [] };
    const area = view?.map.area
      ? { type: "FeatureCollection", features: [view.map.area] }
      : empty;
    function source(id: string, data: any) {
      if (m.getSource(id)) m.getSource(id).setData(data);
      else m.addSource(id, { type: "geojson", data });
    }
    source("area", area);
    source("chips", view?.map.chips || empty);
    // A dot per imagery result: its ~150 m footprint is invisible until zoomed in (PR #14).
    source("chip-dots", {
      type: "FeatureCollection",
      features: (view?.map.chips?.features || []).flatMap(
        (f: any, i: number) => {
          const lon = Number(f?.properties?.lon),
            lat = Number(f?.properties?.lat);
          return Number.isFinite(lon) && Number.isFinite(lat)
            ? [
                {
                  type: "Feature",
                  geometry: { type: "Point", coordinates: [lon, lat] },
                  properties: { i, inside: f.properties.inside },
                },
              ]
            : [];
        },
      ),
    });
    source("reference", view?.reference?.features || empty);
    source("false-alarms", {
      type: "FeatureCollection",
      features: (view?.reference?.false_alarm_cells || []).map(
        (geometry: any) => ({ type: "Feature", geometry, properties: {} }),
      ),
    });
    const blue = preferences.colour === "colour-safe" ? "#0072b2" : "#01bdda",
      orange = preferences.colour === "colour-safe" ? "#e69f00" : "#e97800";
    if (!m.getLayer("area-fill")) {
      m.addLayer({
        id: "area-fill",
        type: "fill",
        source: "area",
        paint: { "fill-color": blue, "fill-opacity": 0.07 },
      });
      m.addLayer({
        id: "area-line",
        type: "line",
        source: "area",
        paint: {
          "line-color": blue,
          "line-width": 2,
          "line-dasharray": [3, 2],
        },
      });
      m.addLayer({
        id: "chips-fill",
        type: "fill",
        source: "chips",
        paint: {
          "fill-color": [
            "case",
            ["==", ["get", "inside"], false],
            orange,
            blue,
          ],
          "fill-opacity": 0.2,
        },
      });
      m.addLayer({
        id: "chips-line",
        type: "line",
        source: "chips",
        paint: { "line-color": blue, "line-width": 1 },
      });
      m.addLayer({
        id: "chip-dots",
        type: "circle",
        source: "chip-dots",
        maxzoom: 14,
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 4, 3, 13, 6],
          "circle-color": [
            "case",
            ["==", ["get", "inside"], false],
            orange,
            blue,
          ],
          "circle-stroke-width": 1.5,
          "circle-stroke-color": "#ffffff",
        },
      });
      // Clicking an imagery result opens it in the inspector (dot when zoomed out, footprint up close).
      m.on("click", (e: any) => {
        const dot = m.queryRenderedFeatures(e.point, {
          layers: ["chip-dots"],
        })[0];
        if (dot) return onSelectChipRef.current(Number(dot.properties.i));
        const hit = m.queryRenderedFeatures(e.point, {
          layers: ["chips-fill"],
        })[0];
        if (!hit) return;
        const chips = viewRef.current?.map.chips?.features || [];
        const i = chips.findIndex(
          (f: any) =>
            f?.properties?.node && f.properties.node === hit.properties.node,
        );
        if (i >= 0) onSelectChipRef.current(i);
      });
      for (const id of ["chip-dots", "chips-fill"]) {
        m.on("mouseenter", id, () => (m.getCanvas().style.cursor = "pointer"));
        m.on("mouseleave", id, () => (m.getCanvas().style.cursor = ""));
      }
      const colour = ["case", ["get", "found"], blue, orange];
      m.addLayer({
        id: "ref-fill",
        type: "fill",
        source: "reference",
        filter: ["!=", ["geometry-type"], "Point"],
        paint: { "fill-color": colour, "fill-opacity": 0.35 },
      });
      m.addLayer({
        id: "ref-line",
        type: "line",
        source: "reference",
        paint: { "line-color": colour, "line-width": 2 },
      });
      m.addLayer({
        id: "ref-points",
        type: "circle",
        source: "reference",
        filter: ["==", ["geometry-type"], "Point"],
        paint: {
          "circle-color": colour,
          "circle-radius": 5,
          "circle-stroke-color": "white",
          "circle-stroke-width": 1,
        },
      });
      m.addLayer({
        id: "false-line",
        type: "line",
        source: "false-alarms",
        paint: {
          "line-color": orange,
          "line-width": 2,
          "line-dasharray": [2, 2],
        },
      });
    }
    m.setPaintProperty("area-line", "line-color", blue);
    m.setPaintProperty("area-fill", "fill-color", blue);
    m.setPaintProperty("chips-fill", "fill-color", [
      "case",
      ["==", ["get", "inside"], false],
      orange,
      blue,
    ]);
    m.setPaintProperty("chips-line", "line-color", blue);
    m.setPaintProperty("chip-dots", "circle-color", [
      "case",
      ["==", ["get", "inside"], false],
      orange,
      blue,
    ]);
    for (const [id, prop] of [
      ["ref-fill", "fill-color"],
      ["ref-line", "line-color"],
      ["ref-points", "circle-color"],
    ])
      m.setPaintProperty(id, prop, ["case", ["get", "found"], blue, orange]);
    m.setPaintProperty("false-line", "line-color", orange);
    markers.current.forEach((x) => x.remove());
    markers.current = [];
    candidatesOf(view).forEach((c) => {
      const el = document.createElement("button");
      const verdict = c.visual?.verdict || "";
      el.className = `evidence-marker ${c.inside === false ? "outside" : ""}`;
      el.textContent = String(c.id + 1);
      if (VISUAL_MARK[verdict]) {
        const badge = document.createElement("span");
        badge.className = `visual-badge v-${verdict}`;
        badge.textContent = VISUAL_MARK[verdict];
        badge.setAttribute("aria-hidden", "true");
        el.appendChild(badge);
      }
      const seen =
        verdict === "present"
          ? ", seen in the checked image"
          : verdict === "absent"
            ? ", not seen in the checked image"
            : verdict === "unclear"
              ? ", can't tell from the checked image"
              : "";
      el.setAttribute(
        "aria-label",
        `Open location ${c.id + 1}: ${c.name}${seen}`,
      );
      el.onclick = () => onSelectRef.current(c.id);
      markers.current.push(
        new lib.Marker({ element: el }).setLngLat(c.coordinates).addTo(m),
      );
    });
    const bounds = new lib.LngLatBounds();
    // The area's main polygon plus the evidence, not every outlying island (docs/map-fit).
    fitCoordinates(view).forEach((c) => bounds.extend(c));
    fit.current = (animate = true) => {
      m.setPadding({ top: 40, bottom: 50, left: 40, right: 40 });
      if (!bounds.isEmpty())
        m.fitBounds(bounds, {
          padding: 60,
          maxZoom: 14,
          duration: animate ? duration : 0,
        });
    };
    if (!inspecting) fit.current(false);
  }, [view, ready, preferences.colour]);
  useEffect(() => {
    if (!ready || !map.current) return;
    for (const id of ["area-fill", "area-line"])
      map.current.setLayoutProperty(
        id,
        "visibility",
        overlays.area ? "visible" : "none",
      );
    for (const id of ["chips-fill", "chips-line", "chip-dots"])
      map.current.setLayoutProperty(
        id,
        "visibility",
        overlays.chips ? "visible" : "none",
      );
    for (const id of ["ref-fill", "ref-line", "ref-points", "false-line"])
      map.current.setLayoutProperty(
        id,
        "visibility",
        overlays.reference ? "visible" : "none",
      );
  }, [overlays, ready, view]);
  useEffect(() => {
    if (!ready || !map.current) return;
    markers.current.forEach((m, i) =>
      m.getElement().classList.toggle("selected", i === selected),
    );
    const m = map.current;
    if (inspecting) {
      const narrow = host.current!.clientWidth < 650;
      const padding = narrow
        ? { top: 100, left: 30, right: 30, bottom: 285 }
        : { top: 100, left: 40, right: 365, bottom: 70 };
      let center = candidate?.coordinates;
      if (!center && chip) {
        const box = chip.properties?.bbox;
        const ring = chip.geometry?.coordinates?.[0];
        if (box?.length === 4)
          center = [(box[0] + box[2]) / 2, (box[1] + box[3]) / 2];
        else if (ring?.length) center = ring[0];
      }
      if (center) m.easeTo({ center, padding, duration });
    } else if (
      lastInspection.current.open &&
      lastInspection.current.runId === view?.run.id
    )
      m.easeTo({
        padding: { top: 40, left: 40, right: 40, bottom: 50 },
        duration,
      });
    lastInspection.current = { open: inspecting, runId: view?.run.id || "" };
  }, [selected, selectedChip, ready, view]);
  useEffect(() => {
    if (
      ready &&
      focusBounds?.length === 4 &&
      focusBounds.every(Number.isFinite)
    ) {
      map.current?.fitBounds(
        [
          [focusBounds[0], focusBounds[1]],
          [focusBounds[2], focusBounds[3]],
        ],
        { padding: 60, duration },
      );
    }
  }, [focusBounds, ready]);
  useEffect(() => {
    if (!inspecting) return;
    const close = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
        markers.current[selected ?? -1]?.getElement().focus();
      }
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [inspecting, onClose, selected]);
  return (
    <div className={`evidence-map ${inspecting ? "has-inspector" : ""}`}>
      <div ref={host} className="map-canvas" />
      <div className="map-tools">
        <label>
          <span className="sr-only">Map layer</span>
          <select
            aria-label="Map layer"
            value={layer}
            onChange={(e) => setLayer(e.target.value)}
          >
            <option value="s2">Sentinel-2 satellite</option>
            <option value="usgs">USGS imagery</option>
            <option value="naip">NAIP imagery (US)</option>
            <option value="streets">Street map</option>
          </select>
        </label>
        <button
          onClick={() => {
            onClose();
            fit.current();
          }}
        >
          Fit all evidence
        </button>
        <details>
          <summary>Map overlays</summary>
          {Object.entries(overlays).map(([key, value]) => (
            <label key={key}>
              <input
                type="checkbox"
                checked={value}
                onChange={(e) =>
                  setOverlays((old) => ({ ...old, [key]: e.target.checked }))
                }
              />
              {key === "area"
                ? "Requested boundary"
                : key === "chips"
                  ? "Tool image footprints"
                  : "Reference assets / false alarms"}
            </label>
          ))}
        </details>
      </div>
      {error && (
        <div className="map-warning" role="status">
          {error}
        </div>
      )}
      <div className="map-key">
        <span>
          <i /> Requested area
        </span>
        <span>
          <b /> Numbered reported sites
        </span>
        {view?.reference && (
          <span>Reference: blue = found · orange = missed / false alarm</span>
        )}
        {view?.map.visual?.sites ? (
          <span
            className="map-key-visual"
            title="Each site was looked at in the sharpest open image of it (docs/visual-check)"
          >
            <em className="visual-badge v-present" aria-hidden="true">
              ✓
            </em>
            seen
            <em className="visual-badge v-absent" aria-hidden="true">
              ✕
            </em>
            not seen
            <em className="visual-badge v-unclear" aria-hidden="true">
              ?
            </em>
            can’t tell
          </span>
        ) : null}
        <span
          className="map-key-caption"
          title={
            view?.map.visual &&
            (view.map.visual.unclear || view.map.visual.no_image)
              ? `${view.map.visual.unclear} couldn’t be told, ${view.map.visual.no_image} had no open image`
              : undefined
          }
        >
          {caption || "Context map is not independent verification"}
        </span>
      </div>
      {inspecting && (
        <aside className="tile-inspector" aria-label="Map imagery inspector">
          <button
            ref={tileFocus}
            className="icon-button tile-inspector-close"
            aria-label="Close imagery inspector"
            onClick={onClose}
          >
            <Icon name="x" />
          </button>
          {visual?.image_url && (
            <div
              className="image-switch"
              role="group"
              aria-label="Which image to show"
            >
              <button
                aria-pressed={imageMode === "checked"}
                onClick={() => setImageMode("checked")}
              >
                <span className="long">Checked image</span>
                <span className="short">Checked</span>
              </button>
              <button
                aria-pressed={imageMode === "agent"}
                onClick={() => setImageMode("agent")}
              >
                <span className="long">Agent’s image</span>
                <span className="short">Agent’s</span>
              </button>
            </div>
          )}
          <div
            className={`tile-frame ${imageLoaded ? "loaded" : imageError ? "failed" : "loading"}`}
          >
            {shownUrl && !imageError && (
              <img
                key={`${imageMode}-${imageAttempt}`}
                className="inspected-image"
                src={imgSrc}
                alt={
                  checkedUrl
                    ? `Checked image of location ${(candidate?.id ?? 0) + 1}`
                    : `Saved tool imagery ${chip?.properties?.node || ""}`
                }
                onLoad={(e) =>
                  setLoadedSrc(e.currentTarget.getAttribute("src"))
                }
                onError={() =>
                  // A cold imagery provider can be slow; retry once on our own before giving up.
                  imageAttempt === 0 ? setImageAttempt(1) : setImageError(true)
                }
              />
            )}
            {imageLoaded &&
              (checkedUrl && visual?.source ? (
                <span className="image-pill">
                  {VISUAL_SOURCE[visual.source] || visual.source}{" "}
                  {visual.gsd_m != null && `${formatGsd(visual.gsd_m)} m`}
                  {visual.date ? ` · ${visual.date}` : ""}
                </span>
              ) : (
                !checkedUrl &&
                chip?.properties && (
                  <span className="image-pill">
                    {chipPill(chip.properties)}
                  </span>
                )
              ))}
            {!shownUrl ? (
              <p className="tile-frame-note">
                No imagery was saved for this location’s cited tool result.
              </p>
            ) : imageError ? (
              <p className="tile-frame-note">
                {checkedUrl
                  ? "The checked image couldn’t be loaded."
                  : "The imagery provider didn’t answer in time."}
                <button
                  className="secondary small"
                  onClick={() => {
                    setImageError(false);
                    setImageAttempt((n) => n + 1);
                  }}
                >
                  Try again
                </button>
              </p>
            ) : (
              !imageLoaded && (
                <p className="tile-frame-note">
                  {checkedUrl ? (
                    "Loading the checked image…"
                  ) : (
                    <>
                      Fetching imagery from{" "}
                      {chip?.properties?.index === "naip"
                        ? "USGS"
                        : "the provider"}
                      …
                      <small>
                        An image not viewed before can take up to 15 s.
                      </small>
                    </>
                  )}
                </p>
              )
            )}
          </div>
          <div className="tile-inspector-body" ref={tileBody}>
            {visual && <VisualVerdict visual={visual} />}
            <h3>
              {candidate ? `Location ${candidate.id + 1}` : "Tool imagery"}
            </h3>
            <p className="tile-name">
              {candidate?.name || chip?.properties?.node}
            </p>
            <dl className="tile-facts">
              <div>
                <dt>Location</dt>
                <dd>
                  {candidate
                    ? `${candidate.lat.toFixed(4)}, ${candidate.lon.toFixed(4)}`
                    : chip?.properties?.lat != null
                      ? `${Number(chip.properties.lat).toFixed(4)}, ${Number(chip.properties.lon).toFixed(4)}`
                      : "—"}
                </dd>
              </div>
              <div>
                <dt>Observed</dt>
                <dd>{chip?.properties?.observed || "—"}</dd>
              </div>
              <div>
                <dt>Source</dt>
                <dd>
                  {String(chip?.properties?.index || "—").toUpperCase()} ·{" "}
                  {chip?.properties?.ref || candidate?.ref || "—"}
                </dd>
              </div>
              <div>
                <dt title="Retrieval rank, not confidence">Similarity</dt>
                <dd>
                  {chip?.properties?.similarity != null
                    ? Number(chip.properties.similarity).toFixed(2)
                    : "—"}
                </dd>
              </div>
            </dl>
            {(chip?.properties?.ref || candidate?.ref) && (
              <button
                className="secondary small tile-step"
                onClick={() =>
                  onTrace(chip?.properties?.ref || candidate?.ref!)
                }
              >
                Inspect step {chip?.properties?.ref || candidate?.ref} →
              </button>
            )}
            <p className="fine-print tile-caveat">
              {selectedChip === null
                ? "Nearest imagery in the cited result. "
                : ""}
              Similarity is a retrieval rank, not confidence. Imagery alone
              doesn’t establish what the asset is or its status.
            </p>
            {checkedUrl && visual ? (
              <p className="tile-credit">
                Checked by {visual.model || "a vision model"} ·{" "}
                {visual.credit || VISUAL_SOURCE[visual.source || ""]}
                {visual.licence ? ` (${visual.licence})` : ""}
              </p>
            ) : (
              chip?.properties?.tile_source && (
                <p className="tile-credit">{chip.properties.tile_source}</p>
              )
            )}
            <div className="tile-thumbs">
              {(view?.map.chips?.features || []).map((f: any, i: number) =>
                f.properties?.tile_url ? (
                  <button
                    key={i}
                    aria-label={`Inspect tool image ${i + 1}`}
                    aria-pressed={chipIndex === i}
                    onClick={() => onSelectChip(i)}
                  >
                    <img src={f.properties.tile_url} alt="" loading="lazy" />
                  </button>
                ) : null,
              )}
            </div>
          </div>
        </aside>
      )}
    </div>
  );
}

function formatGsd(m: number): string {
  return m >= 2
    ? String(Math.round(m))
    : m >= 0.1
      ? m.toFixed(1)
      : m.toFixed(2);
}

const VERDICT_TEXT: Record<string, string> = {
  present: "Seen",
  absent: "Not seen",
  unclear: "Can’t tell",
};

function VisualVerdict({
  visual,
}: {
  visual: NonNullable<Candidate["visual"]>;
}) {
  if (visual.verdict === "no_image")
    return (
      <p className="visual-verdict v-none">
        No open image of this site to check.
      </p>
    );
  if (!VERDICT_TEXT[visual.verdict])
    return (
      <p className="visual-verdict v-none">
        Not checked{visual.reason ? `: ${visual.reason}` : "."}
      </p>
    );
  return (
    <div className={`visual-verdict v-${visual.verdict}`}>
      <p>
        <b>
          <span aria-hidden="true">{VISUAL_MARK[visual.verdict]}</span>{" "}
          {VERDICT_TEXT[visual.verdict]}
        </b>
        {visual.reason ? `: ${visual.reason}` : ""}
      </p>
      {visual.gsd_m != null && visual.gsd_m > 2 && (
        <p className="fine-print">
          {Math.round(visual.gsd_m)} m image: only large assets are visible.
        </p>
      )}
    </div>
  );
}

// The agent's LGND image: its index, resolution and observed date (the scene shown), or the mosaic it falls
// back to when no date was recorded. NAIP is 1 m before 2018 and 0.6 m in most states since, so no single figure.
function chipPill(p: any): string {
  const name = p.index === "naip" ? "NAIP 0.6–1 m" : "Sentinel-2 10 m";
  return p.observed ? `${name} · ${p.observed}` : `${name} · mosaic`;
}
