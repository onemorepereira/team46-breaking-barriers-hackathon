// Same-origin requests keep AWS and LGND credentials exclusively on the server.
export type Row = {
  id: string;
  prompt: string;
  model_key?: string;
  score: number | null;
  verdict: string;
  started_at?: string;
  area?: string;
};
export type View = {
  run: Record<string, any>;
  kpis: Record<string, any>;
  map: Record<string, any>;
  claims: any[];
  timeline: any[];
  scorecard: any;
  conditions: any;
  explanation: any;
  final_answer: string;
  narrative: any;
  reference: any;
  licences: any;
  source_check_note?: string;
  trouble_spots?: any[];
  datasets?: any[];
};
export function basePath(path = window.location.pathname): string {
  // The last `/workspace` segment is the app's own mount; anything before it is the deploy prefix.
  const mount = path.match(/^(.*)\/workspace(?:\/|$)/);
  if (mount) return mount[1];
  return path.match(/^\/proxy\/\d+/)?.[0] || "";
}
export function endpoint(path: string): string {
  return `${basePath()}${path}`;
}
export async function request<T>(
  path: string,
  body?: unknown,
  signal?: AbortSignal,
  method?: "PUT" | "POST",
): Promise<T> {
  const response = await fetch(endpoint(path), {
    credentials: "same-origin",
    signal,
    ...(body !== undefined
      ? {
          method: method || "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      : {}),
  });
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json"))
    throw new Error(
      "The server returned a sign-in page or an unavailable service. Refresh your workshop login and try again.",
    );
  const data = await response.json();
  if (!response.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : data.error || `Request failed (${response.status})`,
    );
  return data;
}
// One reported site's visual check (docs/visual-check): the sharpest open image and a model's verdict.
export type Visual = {
  n?: number;
  verdict:
    | "present"
    | "absent"
    | "unclear"
    | "no_image"
    | "error"
    | "not_checked";
  reason?: string | null;
  source?: "vantor" | "oam" | "naip" | "s2" | null;
  gsd_m?: number | null;
  date?: string | null;
  licence?: string | null;
  credit?: string | null;
  model?: string | null;
  image_url?: string;
};
export const VISUAL_SOURCE: Record<string, string> = {
  vantor: "Vantor",
  oam: "OpenAerialMap",
  naip: "NAIP",
  s2: "Sentinel-2",
};
export const VISUAL_MARK: Record<string, string> = {
  present: "✓",
  absent: "✕",
  unclear: "?",
};
export function visualCaption(summary: any): string | null {
  if (!summary) return null;
  if (
    summary.status === "error" ||
    (summary.status === "not_checked" && !summary.checked)
  )
    return `Visual check not run${summary.reason ? `: ${summary.reason}` : ""}`;
  if (!summary.sites)
    return "Visual check: the answer listed no locations to check";
  if (!summary.checked)
    return "Visual check: no site could be confirmed or ruled out";
  return `Visually checked: ${summary.seen} of ${summary.checked} sites seen`;
}
export type Candidate = {
  id: number;
  lat: number;
  lon: number;
  name: string;
  ref: string | null;
  inside: boolean | null;
  coordinates: [number, number];
  visual: Visual | null;
};
export function candidatesOf(view: View | null): Candidate[] {
  const seen = new Set<string>();
  return (view?.map.claims?.features || [])
    .filter((f: any) => {
      const c = f.geometry?.coordinates;
      if (!Array.isArray(c) || c.length < 2 || !c.every(Number.isFinite))
        return false;
      const key = c.join(",");
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .map((f: any, i: number) => ({
      id: i,
      lat: f.geometry.coordinates[1],
      lon: f.geometry.coordinates[0],
      name:
        f.properties.claim ||
        f.properties.label ||
        `Reported location ${i + 1}`,
      ref: f.properties.ref,
      inside: f.properties.inside,
      coordinates: f.geometry.coordinates,
      visual: f.properties.visual || null,
    }));
}
export function formatScore(value: unknown): string {
  return typeof value === "number" && Number.isFinite(value)
    ? `${Number(value.toFixed(1))}`
    : "—";
}
export function money(value: unknown): string {
  return typeof value === "number" ? `$${value.toFixed(2)}` : "Not recorded";
}
export function localTime(value?: string): string {
  return value ? new Date(value).toLocaleString() : "Time not recorded";
}
export type Draft = {
  decision: "agree" | "disagree";
  score: string;
  reason: string;
  refs: string;
};
// One review covering every question the reviewer assessed (docs/judge-feedback): agreeing needs nothing
// else; suggesting a score needs a whole-number score and a reason.
export function draftPayload(
  reviewer: string,
  drafts: Record<string, Draft>,
  note = "",
) {
  if (!reviewer.trim())
    throw new Error("Enter your name so the review has an author.");
  const entries = Object.entries(drafts);
  if (!entries.length)
    throw new Error("Agree or disagree with at least one question first.");
  const criteria: Record<string, unknown> = {};
  for (const [id, d] of entries) {
    if (d.decision === "agree") {
      criteria[id] = { agree: true };
      continue;
    }
    const value = d.score.trim() === "" ? NaN : Number(d.score);
    if (!Number.isInteger(value))
      throw new Error("Choose the score you would give.");
    if (!d.reason.trim()) throw new Error("Explain your suggested score.");
    criteria[id] = {
      agree: false,
      score: value,
      reason: d.reason.trim(),
      refs: d.refs.split(/[\s,]+/).filter(Boolean),
    };
  }
  return {
    reviewer: reviewer.trim(),
    criteria,
    note: note.trim(),
    measured_note: "",
  };
}
export function reviewPayload(
  reviewer: string,
  criterion: string,
  decision: string,
  score: string,
  note: string,
  refText: string,
) {
  if (!criterion || (decision !== "agree" && decision !== "disagree"))
    throw new Error(
      "Choose a rubric question and an assessment before saving.",
    );
  if (decision === "disagree" && !note.trim())
    throw new Error("Explain your suggested score.");
  return {
    ...draftPayload(
      reviewer,
      { [criterion]: { decision, score, reason: note, refs: refText } },
      note,
    ),
  };
}

// Select imagery only from the cited tool result, nearest to the reported point.
export function imageForCandidate(
  view: View | null,
  index: number | null,
): number | null {
  if (index === null) return null;
  const candidate = candidatesOf(view)[index];
  if (!candidate) return null;
  const chips = view?.map.chips?.features || [];
  let best: number | null = null,
    distance = Infinity;
  chips.forEach((chip: any, i: number) => {
    if (!chip.properties?.tile_url || chip.properties.ref !== candidate.ref)
      return;
    const coords = chip.geometry?.coordinates?.[0];
    if (!Array.isArray(coords)) return;
    const points = coords.filter(
      (c: any) => Array.isArray(c) && c.every(Number.isFinite),
    );
    if (!points.length) return;
    const lon =
      (Math.min(...points.map((c: any) => c[0])) +
        Math.max(...points.map((c: any) => c[0]))) /
      2;
    const lat =
      (Math.min(...points.map((c: any) => c[1])) +
        Math.max(...points.map((c: any) => c[1]))) /
      2;
    const d = (lon - candidate.lon) ** 2 + (lat - candidate.lat) ** 2;
    if (d < distance) {
      distance = d;
      best = i;
    }
  });
  return best;
}
// The imagery result behind a reported location: the chip the claim names ("chip naip/obs:123"),
// else the chip at the same coordinates, else the nearest chip within ~300 m. -1 when none.
export function chipFor(c: Candidate, chips: any[]): number {
  // Claims name their chip as "chip naip/obs:123" or just "(s2/obs:123)".
  const node = c.name.match(/\b([a-z0-9]+\/obs:\d+)\b/i)?.[1];
  const named = node
    ? chips.findIndex((f) => String(f?.properties?.node) === node)
    : -1;
  if (named >= 0) return named;
  let best = -1,
    bestD = Infinity;
  chips.forEach((f, i) => {
    const lat = Number(f?.properties?.lat),
      lon = Number(f?.properties?.lon);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;
    const dy = (lat - c.lat) * 111_320,
      dx = (lon - c.lon) * 111_320 * Math.cos((c.lat * Math.PI) / 180),
      d = Math.hypot(dx, dy);
    if (d < bestD) [best, bestD] = [i, d];
  });
  return bestD <= 300 ? best : -1;
}

// Issues per Evaluation section (docs/evaluation-issues): what a reviewer should look at first.
export function weakCriterion(c: any): boolean {
  return typeof c?.score === "number" && c.score < 100;
}
export function sectionIssues(view: View | null): Record<string, number> {
  const card = view?.scorecard,
    k = view?.kpis || {},
    conditions: any = (view as any)?.conditions,
    reference: any = (view as any)?.reference,
    licences: any = (view as any)?.licences;
  const list = (v: any) => (Array.isArray(v) ? v : []);
  const cells = list(conditions?.rows).flatMap((r: any) => list(r?.cells));
  return {
    rubric: card ? list(card.criteria).filter(weakCriterion).length : 0,
    conditions:
      cells.filter(
        (c: any) => c?.status === "contradicted" || c?.status === "unverified",
      ).length +
      (conditions && (conditions.status === "not_checked" || conditions.error)
        ? 1
        : 0),
    judges: card
      ? list(card.judges).filter((j: any) => j?.status !== "ok").length +
        (k.confidence === "Low" || card.judges_in_doubt ? 1 : 0)
      : 0,
    failures: card
      ? list(card.gates).length +
        list(card.failure_modes).length +
        ((k.errors ?? 0) > 0 ? 1 : 0)
      : 0,
    reference: reference
      ? list(reference.missed).length + (reference.error ? 1 : 0)
      : 0,
    licences:
      licences?.presentable === false
        ? Math.max(1, list(licences.blockers).length)
        : 0,
  };
}
