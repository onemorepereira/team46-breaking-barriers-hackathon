import { useEffect, useRef, useState } from "react";
import { candidatesOf, chipFor, endpoint, type View } from "./api";
const CYAN = "#01bdda",
  ORANGE = "#e97800",
  POPUP_ROOM = 150; // px the focused point sits below centre, so the popup above it stays in frame
function node(tag: string, cls: string, text?: string): HTMLElement {
  const n = document.createElement(tag);
  n.className = cls;
  if (text) n.textContent = text;
  return n;
}
// Popup body built from DOM nodes (never innerHTML): tool output is untrusted text.
function popupBody(title: string, p: any): HTMLElement {
  const box = node("div", "chip-popup");
  if (p?.tile_url) {
    const img = document.createElement("img");
    img.src = p.tile_url;
    img.alt = `Imagery under ${p.node || title}`;
    img.onerror = () => img.replaceWith(node("div", "chip-popup-missing", "Tile unavailable"));
    box.append(img);
  } else box.append(node("div", "chip-popup-missing", "No imagery tile for this location"));
  box.append(node("strong", "chip-popup-title", title));
  const facts = [
    p?.index ? String(p.index).toUpperCase() : null,
    p?.observed ? `observed ${p.observed}` : null,
    Number.isFinite(Number(p?.similarity)) && p?.similarity !== null
      ? `similarity ${Number(p.similarity).toFixed(2)}`
      : null,
  ].filter(Boolean);
  if (facts.length) box.append(node("span", "chip-popup-meta", facts.join(" · ")));
  if (Number.isFinite(Number(p?.lat)) && Number.isFinite(Number(p?.lon)))
    box.append(
      node("span", "chip-popup-meta", `${Number(p.lat).toFixed(4)}, ${Number(p.lon).toFixed(4)}`),
    );
  const badges = node("div", "chip-popup-badges");
  const inside = p?.inside === true || p?.inside === "true",
    outside = p?.inside === false || p?.inside === "false";
  badges.append(
    node(
      "span",
      `chip-popup-badge ${outside ? "out" : inside ? "in" : ""}`,
      outside ? "Outside the requested area" : inside ? "Inside the requested area" : "No area to check",
    ),
  );
  if (p?.ref) badges.append(node("span", "chip-popup-badge ref", `from ${p.ref}`));
  box.append(badges);
  if (p?.tile_source) box.append(node("span", "chip-popup-source", p.tile_source));
  return box;
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
    popup = useRef<any>(null),
    viewRef = useRef<View | null>(view);
  viewRef.current = view;
  function showPopup(lngLat: [number, number], title: string, p: any) {
    const lib = (window as any).maplibregl;
    if (!map.current || !lib) return;
    popup.current?.remove();
    popup.current = new lib.Popup({ anchor: "bottom", offset: 18, maxWidth: "260px", focusAfterOpen: false })
      .setLngLat(lngLat)
      .setDOMContent(popupBody(title, p))
      .addTo(map.current);
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
      popup.current?.remove();
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
    popup.current?.remove();
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
          m.easeTo({ center: at, offset: [0, POPUP_ROOM], duration: 500 });
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
      offset: [0, POPUP_ROOM],
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
      offset: [0, POPUP_ROOM],
      duration: 650,
    });
    showPopup(at, f.properties.node || "Imagery result", f.properties);
  }, [focusChip]);
  return (
    <div className="evidence-map">
      <div ref={host} className="map-canvas" />
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
      <div className="map-key">
        <span>
          <i /> Requested area
        </span>
        <span>
          <b /> Reported locations
        </span>
        <span className="map-key-caption">
          Map context is not independent verification
        </span>
      </div>
    </div>
  );
}
