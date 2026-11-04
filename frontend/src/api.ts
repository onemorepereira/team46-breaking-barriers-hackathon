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
): Promise<T> {
  const response = await fetch(endpoint(path), {
    credentials: "same-origin",
    signal,
    ...(body !== undefined
      ? {
          method: "POST",
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
export type Candidate = {
  id: number;
  lat: number;
  lon: number;
  name: string;
  ref: string | null;
  inside: boolean | null;
  coordinates: [number, number];
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
    }));
}
export function formatScore(value: unknown): string {
  return typeof value === "number" && Number.isFinite(value)
    ? `${Math.round(value)}`
    : "—";
}
export function money(value: unknown): string {
  return typeof value === "number" ? `$${value.toFixed(2)}` : "Not recorded";
}
export function localTime(value?: string): string {
  return value ? new Date(value).toLocaleString() : "Time not recorded";
}
export function reviewPayload(
  reviewer: string,
  criterion: string,
  decision: string,
  score: string,
  note: string,
  refText: string,
) {
  if (!criterion || decision === "note")
    throw new Error(
      "Choose a rubric question and an assessment before saving.",
    );
  if (!reviewer.trim())
    throw new Error("Enter your name so the review has an author.");
  if (decision === "disagree" && !note.trim())
    throw new Error("Explain your suggested score.");
  const value = score.trim() === "" ? NaN : Number(score);
  if (decision === "disagree" && !Number.isInteger(value))
    throw new Error("Choose the score you would give.");
  const criteria: Record<string, unknown> = {
    [criterion]:
      decision === "agree"
        ? { agree: true }
        : {
            agree: false,
            score: value,
            reason: note.trim(),
            refs: refText.split(/[\s,]+/).filter(Boolean),
          },
  };
  return {
    reviewer: reviewer.trim(),
    criteria,
    note: note.trim(),
    measured_note: "",
  };
}
