import { useEffect, useRef, useState } from "react";
import { candidatesOf, chipFor, endpoint, type View } from "./api";
const CYAN = "#01bdda",
  ORANGE = "#e97800";
type Detail = { title: string; p: any; at: [number, number] };
const DRAWER_W = 340; // px; the panel docked inside the map's right edge
// Where the focused point should sit: left of centre beside the side panel, or above a phone's bottom sheet.
function focusOffset(host: HTMLElement | null): [number, number] {
  const w = host?.clientWidth || 0;
  return w >= 700 ? [-DRAWER_W / 2, 0] : [0, -(host?.clientHeight || 0) / 4];
}
function DetailPanel({ d, onClose }: { d: Detail; onClose: () => void }) {
  const p = d.p || {};
  const [broken, setBroken] = useState(false);
  useEffect(() => setBroken(false), [p.tile_url]);
  const inside = p.inside === true || p.inside === "true",
    outside = p.inside === false || p.inside === "false";
  const facts = [
    p.index ? String(p.index).toUpperCase() : null,
    p.observed ? `Observed ${p.observed}` : null,
    p.similarity != null && Number.isFinite(Number(p.similarity))
      ? `Similarity ${Number(p.similarity).toFixed(2)}`
      : null,
  ].filter(Boolean);
  return (
    <aside className="map-drawer" aria-label="Selected result">
      <button className="map-drawer-close" onClick={onClose} aria-label="Close details">
        ×
      </button>
      {p.tile_url && !broken ? (
        <img
          src={p.tile_url}
          alt={`Imagery under ${p.node || d.title}`}
          onError={() => setBroken(true)}
        />
      ) : (
        <div className="map-drawer-missing">
          {p.tile_url ? "Tile unavailable" : "No imagery tile for this location"}
        </div>
      )}
      <div className="map-drawer-body">
        <h3>{d.title}</h3>
        {p.node && !d.title.includes(p.node) && <code>{p.node}</code>}
        <dl>
          {facts.length > 0 && (
            <div>
              <dt>Imagery</dt>
              <dd>{facts.join(" · ")}</dd>
            </div>
          )}
          {Number.isFinite(Number(p.lat)) && Number.isFinite(Number(p.lon)) && (
            <div>
              <dt>Location</dt>
              <dd>
                {Number(p.lat).toFixed(4)}, {Number(p.lon).toFixed(4)}
              </dd>
            </div>
          )}
          <div>
            <dt>Requested area</dt>
            <dd className={outside ? "out" : inside ? "in" : ""}>
              {outside ? "Outside" : inside ? "Inside" : "Not checked"}
            </dd>
          </div>
          {p.ref && (
            <div>
              <dt>Returned by</dt>
              <dd>Step {p.ref}</dd>
            </div>
          )}
        </dl>
        {p.tile_source && <small>{String(p.tile_source)}</small>}
      </div>
    </aside>
  );
}
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
      const script = document.createElement("script");
      script.src = endpoint("/static/vendor/maplibre/maplibre-gl.js");
      script.onload = () => resolve((window as any).maplibregl);
      script.onerror = () => {
        loading = null;
        reject(new Error("Map library could not load"));
      };
      document.head.append(script);
    });
  return loading;
}
export default function EvidenceMap({
  view,
  selected,
  onSelect,
  focusChip,
}: {
  view: View | null;
  selected: number | null;
  onSelect: (n: number) => void;
  focusChip?: { index: number; nonce: number } | null;
}) {
  const host = useRef<HTMLDivElement>(null),
    map = useRef<any>(null),
    markers = useRef<any[]>([]),
    [detail, setDetail] = useState<Detail | null>(null),
    viewRef = useRef<View | null>(view);
  viewRef.current = view;
  useEffect(() => {
    if (!detail) return;
    const close = (e: KeyboardEvent) => e.key === "Escape" && setDetail(null);
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [detail]);
  function showPopup(at: [number, number], title: string, p: any) {
    setDetail({ title, p, at });
  }
  function chipCenter(f: any): [number, number] | null {
    const lon = Number(f?.properties?.lon),
      lat = Number(f?.properties?.lat);
    return Number.isFinite(lon) && Number.isFinite(lat) ? [lon, lat] : null;
  }
  const [ready, setReady] = useState(false),
    [error, setError] = useState(""),
    [layer, setLayer] = useState("satellite");
  useEffect(() => {
    let cancelled = false;
    library()
      .then((lib) => {
        if (cancelled || !host.current) return;
        try {
          map.current = new lib.Map({
            container: host.current,
            center: [78, 23],
            zoom: 2.3,
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
          map.current.addControl(new lib.NavigationControl(), "bottom-right");
          map.current.on("load", () => setReady(true));
          map.current.on("error", () =>
            setError(
              "Some basemap imagery is unavailable. Evidence markers remain available.",
            ),
          );
        } catch {
          setError(
            "Interactive map is unavailable in this browser. Coordinates and evidence remain in the results panel.",
          );
        }
      })
      .catch((e) => setError(e.message));
    return () => {
      cancelled = true;
      map.current?.remove();
      map.current = null;
      setReady(false);
    };
  }, []);
  useEffect(() => {
    if (!ready || !map.current) return;
    map.current
      .getSource("base")
      ?.setTiles([
        layer === "satellite"
          ? endpoint("/tiles/base/s2/{z}/{x}/{y}.jpg")
          : "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
      ]);
    const attribution = document.querySelector(".maplibregl-ctrl-attrib-inner");
    if (attribution)
      attribution.textContent =
        layer === "satellite"
          ? "Sentinel-2 cloudless 2023 by EOX · modified Copernicus Sentinel data"
          : "© OpenStreetMap contributors";
  }, [layer, ready]);
  useEffect(() => {
    if (!ready || !map.current) return;
    const m = map.current,
      lib = (window as any).maplibregl;
    markers.current.forEach((x) => x.remove());
    markers.current = [];
    setDetail(null);
    const empty = { type: "FeatureCollection", features: [] };
    const area = view?.map.area
      ? { type: "FeatureCollection", features: [view.map.area] }
      : empty;
    if (m.getSource("area")) m.getSource("area").setData(area);
    else {
      m.addSource("area", { type: "geojson", data: area });
      m.addLayer({
        id: "area-fill",
        type: "fill",
        source: "area",
        paint: { "fill-color": "#01bdda", "fill-opacity": 0.08 },
      });
      m.addLayer({
        id: "area-line",
        type: "line",
        source: "area",
        paint: {
          "line-color": "#01bdda",
          "line-width": 2,
          "line-dasharray": [3, 2],
        },
      });
      m.addSource("chips", { type: "geojson", data: empty });
      m.addLayer({
        id: "chips-fill",
        type: "fill",
        source: "chips",
        paint: {
          "fill-color": [
            "case",
            ["==", ["get", "inside"], false],
            "#e97800",
            "#01bdda",
          ],
          "fill-opacity": 0.2,
        },
      });
      const outside = ["==", ["get", "inside"], false];
      m.addLayer({
        id: "chips-line",
        type: "line",
        source: "chips",
        paint: {
          "line-color": ["case", outside, ORANGE, CYAN],
          "line-width": 1.6,
        },
      });
      // Footprints are ~150 m across, invisible at county zoom: a dot per result stands in until close up.
      m.addSource("chip-dots", { type: "geojson", data: empty });
      m.addLayer({
        id: "chip-dots",
        type: "circle",
        source: "chip-dots",
        maxzoom: 14,
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 4, 3, 13, 6],
          "circle-color": ["case", outside, ORANGE, CYAN],
          "circle-stroke-width": 1.5,
          "circle-stroke-color": "#ffffff",
        },
      });
      m.on("click", (e: any) => {
        for (const id of ["chip-dots", "chips-fill"]) {
          const hit = m.queryRenderedFeatures(e.point, { layers: [id] })[0];
          if (!hit) continue;
          const p = hit.properties;
          const at: [number, number] =
            Number.isFinite(Number(p.lon)) && Number.isFinite(Number(p.lat))
              ? [Number(p.lon), Number(p.lat)]
              : [e.lngLat.lng, e.lngLat.lat];
          showPopup(at, p.node || p.claim || "Imagery result", p);
          m.easeTo({ center: at, offset: focusOffset(host.current), duration: 500 });
          return;
        }
      });
      for (const id of ["chip-dots", "chips-fill"]) {
        m.on("mouseenter", id, () => (m.getCanvas().style.cursor = "pointer"));
        m.on("mouseleave", id, () => (m.getCanvas().style.cursor = ""));
      }
    }
    m.getSource("chips")?.setData(view?.map.chips || empty);
    m.getSource("chip-dots")?.setData({
      type: "FeatureCollection",
      features: (view?.map.chips?.features || []).flatMap((f: any) => {
        const at = chipCenter(f);
        return at
          ? [{ type: "Feature", geometry: { type: "Point", coordinates: at }, properties: f.properties }]
          : [];
      }),
    });
    // One list for markers and the location panel, so marker i is always candidate i (same
    // dedup and finite-coordinate filter).
    candidatesOf(view).forEach((c) => {
      const el = document.createElement("button");
      el.className = `evidence-marker ${c.inside === false ? "outside" : ""}`;
      el.textContent = String(c.id + 1);
      el.setAttribute("aria-label", `Open location ${c.id + 1}: ${c.name}`);
      el.onclick = () => onSelect(c.id);
      markers.current.push(
        new lib.Marker({ element: el }).setLngLat(c.coordinates).addTo(m),
      );
    });
    const bounds = new lib.LngLatBounds();
    function include(coords: any): void {
      if (
        Array.isArray(coords) &&
        Number.isFinite(coords[0]) &&
        Number.isFinite(coords[1])
      ) {
        bounds.extend(coords as [number, number]);
      } else if (Array.isArray(coords)) coords.forEach(include);
    }
    include(view?.map.area?.geometry?.coordinates);
    [
      ...(view?.map.claims?.features || []),
      ...(view?.map.chips?.features || []),
    ].forEach((f: any) => include(f?.geometry?.coordinates));
    if (!bounds.isEmpty())
      m.fitBounds(bounds, { padding: 70, maxZoom: 14, duration: 800 });
  }, [view, ready]);
  useEffect(() => {
    markers.current.forEach((marker, i) =>
      marker.getElement().classList.toggle("selected", i === selected),
    );
    const site = selected !== null ? candidatesOf(viewRef.current)[selected] : null;
    if (!site || !map.current || !markers.current[selected!]) return;
    // Close enough to separate stacked markers and see the footprint.
    map.current.easeTo({
      center: site.coordinates,
      zoom: Math.max(map.current.getZoom(), 14),
      offset: focusOffset(host.current),
      duration: 650,
    });
    const chips = viewRef.current?.map.chips?.features || [];
    const chip = chips[chipFor(site, chips)];
    showPopup(site.coordinates, `${selected! + 1}. ${site.name}`, {
      ...(chip?.properties || {}),
      lat: site.lat,
      lon: site.lon,
      inside: site.inside,
      ref: site.ref || chip?.properties?.ref,
    });
  }, [selected, ready]);
  useEffect(() => {
    if (!focusChip || !map.current) return;
    const f = viewRef.current?.map.chips?.features?.[focusChip.index];
    const at = chipCenter(f);
    if (!at) return;
    map.current.easeTo({
      center: at,
      zoom: Math.max(map.current.getZoom(), 15),
      offset: focusOffset(host.current),
      duration: 650,
    });
    showPopup(at, f.properties.node || "Imagery result", f.properties);
  }, [focusChip]);
  return (
    <div className={`evidence-map ${detail ? "has-drawer" : ""}`}>
      <div ref={host} className="map-canvas" />
      {detail && <DetailPanel d={detail} onClose={() => setDetail(null)} />}
      <div className="map-style">
        <button
          className={layer === "satellite" ? "active" : ""}
          onClick={() => setLayer("satellite")}
        >
          Satellite
        </button>
        <button
          className={layer === "streets" ? "active" : ""}
          onClick={() => setLayer("streets")}
        >
          Streets
        </button>
      </div>
      {error && <div className="map-warning">{error}</div>}
      <div className="map-key" aria-label="Map legend">
        <span>
          <i className="key-area" /> Requested area
        </span>
        <span>
          <i className="key-location">1</i> Reported location
        </span>
        <span>
          <i className="key-imagery" /> Imagery result
        </span>
        <span>
          <i className="key-outside" /> Outside the area
        </span>
      </div>
    </div>
  );
}
