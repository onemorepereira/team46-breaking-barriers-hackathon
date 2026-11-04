import { useEffect, useRef, useState } from "react";
import { endpoint, type View } from "./api";
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
}: {
  view: View | null;
  selected: number | null;
  onSelect: (n: number) => void;
}) {
  const host = useRef<HTMLDivElement>(null),
    map = useRef<any>(null),
    markers = useRef<any[]>([]);
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
      m.addLayer({
        id: "chips-line",
        type: "line",
        source: "chips",
        paint: { "line-color": "#01bdda", "line-width": 1 },
      });
    }
    m.getSource("chips")?.setData(view?.map.chips || empty);
    const seen = new Set<string>();
    (view?.map.claims?.features || []).forEach((f: any) => {
      const c = f.geometry?.coordinates;
      if (!c || seen.has(c.join(","))) return;
      seen.add(c.join(","));
      const i = seen.size - 1;
      const el = document.createElement("button");
      el.className = `evidence-marker ${f.properties.inside === false ? "outside" : ""}`;
      el.textContent = String(i + 1);
      el.setAttribute(
        "aria-label",
        `Open location ${i + 1}: ${f.properties.claim || "reported site"}`,
      );
      el.onclick = () => onSelect(i);
      markers.current.push(
        new lib.Marker({ element: el }).setLngLat(c).addTo(m),
      );
    });
    const bounds = new lib.LngLatBounds();
    function include(coords: any): void {
      if (
        Array.isArray(coords) &&
        typeof coords[0] === "number" &&
        typeof coords[1] === "number"
      ) {
        bounds.extend(coords as [number, number]);
      } else if (Array.isArray(coords)) coords.forEach(include);
    }
    if (view?.map.area) include(view.map.area.geometry.coordinates);
    [
      ...(view?.map.claims?.features || []),
      ...(view?.map.chips?.features || []),
    ].forEach((f: any) => include(f.geometry.coordinates));
    if (!bounds.isEmpty())
      m.fitBounds(bounds, { padding: 70, maxZoom: 14, duration: 800 });
  }, [view, ready]);
  useEffect(() => {
    markers.current.forEach((marker, i) =>
      marker.getElement().classList.toggle("selected", i === selected),
    );
    if (selected !== null && markers.current[selected])
      map.current?.easeTo({
        center: markers.current[selected].getLngLat(),
        duration: 650,
      });
  }, [selected]);
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
