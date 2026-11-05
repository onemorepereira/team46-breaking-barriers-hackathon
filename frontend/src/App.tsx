import { useEffect, useRef, useState } from "react";
import { Text, Stat } from "./UI";
import Evaluation from "./Evaluation";
import Guidance from "./Guidance";
import RunSummary, { DetailedSummary } from "./RunSummary";
import { Accessibility, Dialog, Disclosure } from "./Controls";
import {
  readAccessibility,
  buildPrompt,
  hasTemplateBlanks,
  writePreference,
} from "./preferences";
import { Icon } from "./Icon";
import EvidenceMap from "./Map";
import {
  request,
  endpoint,
  candidatesOf,
  formatScore,
  money,
  localTime,
  reviewPayload,
  type View,
  type Row,
} from "./api";
import "./index.css";
import "./workspace.css";
const examples = [
  {
    label: "Solar farms",
    place: "Jodhpur, India",
    prompt:
      "Find the solar parks in Jodhpur district, Rajasthan, India, and give each one's location exactly as the tool returned it.",
  },
  {
    label: "Warehouses",
    place: "Nagoya, Japan",
    prompt:
      "Find warehouses in Nagoya, Japan, and give each one's location exactly as the tool returned it. Explain evidence and limitations.",
  },
  {
    label: "Data centers",
    place: "Richardson, Texas",
    prompt:
      "Find data centers within the city limits of Richardson, TX. Give each one's location exactly as the tool returned it.",
  },
];
function Empty({
  title,
  children,
}: {
  title: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="empty-state">
      <Icon name="search" size={26} />
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
function DataTable({ rows }: { rows: any[] }) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Claim / value</th>
            <th>Source</th>
            <th>Check</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((c, i) => (
            <tr key={i}>
              <td>
                <strong>{c.claim}</strong>
                <span>{c.value}</span>
              </td>
              <td>{c.ref || "No reference"}</td>
              <td>
                <span
                  className={`status-tag ${c.status === "matched" ? "supported" : "unverified"}`}
                >
                  {c.status}
                </span>
                {c.inside === false && <small>Outside requested area</small>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
function Reviewer({
  view,
  onSaved,
  onReconsider,
  busy,
}: {
  view: View;
  onSaved: () => void;
  onReconsider: (id: string) => void;
  busy: boolean;
}) {
  const judged =
    view.scorecard?.criteria?.filter(
      (c: any) => c.kind === "judged" && c.score !== null,
    ) || [];
  const [name, setName] = useState(""),
    [criterion, setCriterion] = useState(""),
    [decision, setDecision] = useState("agree"),
    [score, setScore] = useState("1"),
    [notes, setNotes] = useState(""),
    [refs, setRefs] = useState(""),
    [saved, setSaved] = useState(""),
    [error, setError] = useState(""),
    [sending, setSending] = useState(false),
    [basket, setBasket] = useState<Record<string, any>>({}),
    [measuredNote, setMeasuredNote] = useState("");
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSaved("");
    setSending(true);
    try {
      const payload = criterion
        ? reviewPayload(name, criterion, decision, score, notes, refs)
        : {
            reviewer: name.trim(),
            criteria: {},
            note: notes,
            measured_note: "",
          };
      if (!name.trim()) throw new Error("Enter your name.");
      payload.criteria = { ...basket, ...payload.criteria };
      payload.measured_note = measuredNote;
      if (!Object.keys(payload.criteria).length)
        throw new Error("Choose at least one rubric question.");
      await request(`/api/runs/${view.run.id}/reviews`, payload);
      setSaved(
        "Review saved to the run archive. The automated score has not been changed.",
      );
      setNotes("");
      setBasket({});
      setCriterion("");
      setMeasuredNote("");
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSending(false);
    }
  }
  return (
    <section className="review-card">
      <div className="section-kicker">Human review</div>
      <h3>What would you check or change?</h3>
      <p>
        Your assessment is kept separately from the automated score. It can
        inform a later judge reconsideration.
      </p>
      <form onSubmit={submit}>
        {Object.keys(basket).length > 0 && (
          <div className="review-basket">
            <b>Criteria ready to save</b>
            {Object.entries(basket).map(([id, item]: [string, any]) => (
              <div key={id}>
                <span>
                  {judged.find((c: any) => c.id === id)?.plain || id}:{" "}
                  {item.agree ? "Agree" : `Suggested rating ${item.score}`}
                </span>
                <button
                  type="button"
                  onClick={() =>
                    setBasket((old) =>
                      Object.fromEntries(
                        Object.entries(old).filter(([key]) => key !== id),
                      ),
                    )
                  }
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
        )}
        <label>
          Your name
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            maxLength={80}
          />
        </label>
        <label>
          What are you reviewing?
          <select
            value={criterion}
            onChange={(e) => {
              setCriterion(e.target.value);
              setDecision("agree");
            }}
          >
            <option value="">Choose a rubric question</option>
            {judged.map((c: any) => (
              <option key={c.id} value={c.id}>
                {c.plain || c.question}
              </option>
            ))}
          </select>
        </label>
        {criterion && (
          <div className="review-pair">
            <label>
              Assessment
              <select
                value={decision}
                onChange={(e) => setDecision(e.target.value)}
              >
                <option value="agree">Agree with panel</option>
                <option value="disagree">Suggest a different score</option>
              </select>
            </label>
            {decision === "disagree" && (
              <label>
                Suggested score
                <select
                  value={score}
                  onChange={(e) => setScore(e.target.value)}
                >
                  {Object.keys(
                    view.scorecard.anchors?.[criterion] || {
                      0: "",
                      1: "",
                      2: "",
                    },
                  ).map((s) => (
                    <option key={s}>{s}</option>
                  ))}
                </select>
              </label>
            )}
          </div>
        )}
        {criterion && (
          <p className="fine-print">
            Current panel score:{" "}
            {formatScore(judged.find((c: any) => c.id === criterion)?.score)}
            /100.{" "}
            {decision === "disagree" &&
              `Your selected rubric anchor: ${view.scorecard.anchors?.[criterion]?.[score] || "No anchor recorded"}`}
          </p>
        )}
        <label>
          Notes
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            maxLength={2000}
            placeholder="What supports your assessment? What remains uncertain?"
          />
        </label>
        {decision === "disagree" && (
          <label>
            Evidence step IDs
            <input
              value={refs}
              onChange={(e) => setRefs(e.target.value)}
              placeholder="For example: T2, T4"
            />
          </label>
        )}
        <label>
          Note on measured checks (kept out of judge prompts)
          <textarea
            value={measuredNote}
            onChange={(e) => setMeasuredNote(e.target.value)}
            maxLength={4000}
          />
        </label>
        <button
          className="secondary"
          type="button"
          disabled={busy || sending || !criterion}
          onClick={() => {
            try {
              const part = reviewPayload(
                name,
                criterion,
                decision,
                score,
                notes,
                refs,
              );
              setBasket((old) => ({ ...old, ...part.criteria }));
              setCriterion("");
              setNotes("");
              setRefs("");
              setError("");
            } catch (e) {
              setError((e as Error).message);
            }
          }}
        >
          Add criterion to review
        </button>
        <button
          className="primary"
          disabled={
            busy ||
            sending ||
            (!criterion && !Object.keys(basket).length) ||
            !view.scorecard ||
            view.kpis.score === null
          }
        >
          {sending ? "Saving…" : "Save human review"}
        </button>
        {!view.scorecard && (
          <small>Judge this run before submitting a review.</small>
        )}
      </form>
      {saved && (
        <p role="status" className="success-message">
          {saved}
        </p>
      )}
      {error && (
        <p role="alert" className="error-message">
          {error}
        </p>
      )}
      <div className="saved-reviews">
        {view.scorecard?.reviews?.map((r: any, i: number) => (
          <details key={r.id || i}>
            <summary>
              {r.reviewer} · {localTime(r.created_at)}
              {r.current === false ? " · earlier judgement" : ""}
            </summary>
            <p>{r.note || "Criterion review saved."}</p>
            {r.measured_note && <p>Measured-check note: {r.measured_note}</p>}
            <pre>{JSON.stringify(r.criteria, null, 2)}</pre>
            {r.current &&
              !r.reconsidered &&
              view.scorecard.reconsider_enabled && (
                <button
                  className="secondary"
                  disabled={busy}
                  onClick={() => onReconsider(r.id)}
                >
                  Ask judges to reconsider
                </button>
              )}
            {r.reconsidered && (
              <small>Reconsidered {localTime(r.reconsidered)}</small>
            )}
          </details>
        ))}
      </div>
    </section>
  );
}
export default function App() {
  const [view, setView] = useState<View | null>(null),
    [prompt, setPrompt] = useState(""),
    [models, setModels] = useState<string[]>([]),
    [model, setModel] = useState(""),
    [tab, setTab] = useState("findings"),
    [selected, setSelected] = useState<number | null>(null),
    [busy, setBusy] = useState(false),
    [phase, setPhase] = useState("Ready to explore"),
    [error, setError] = useState(""),
    [events, setEvents] = useState<any[]>([]),
    [history, setHistory] = useState<Row[] | null>(null),
    [historyNext, setHistoryNext] = useState<string | null>(null),
    [loading, setLoading] = useState(false),
    [modal, setModal] = useState(false),
    [settingsOpen, setSettingsOpen] = useState(false),
    [preferences, setPreferences] = useState(readAccessibility),
    [page, setPage] = useState(() =>
      new URLSearchParams(window.location.search).get("page") === "guidance"
        ? "guidance"
        : "workspace",
    ),
    [selectedChip, setSelectedChip] = useState<number | null>(null),
    [focusBounds, setFocusBounds] = useState<number[] | null>(null),
    [previous, setPrevious] = useState<any>(null),
    [filterModel, setFilterModel] = useState(""),
    [filterVerdict, setFilterVerdict] = useState(""),
    [asset, setAsset] = useState(""),
    [area, setArea] = useState(""),
    [focusedRef, setFocusedRef] = useState<string | null>(null);
  const stream = useRef<{ close: () => void } | null>(null),
    active = useRef(""),
    busyRef = useRef(false),
    requestId = useRef(0);
  const sites = candidatesOf(view),
    chips = view?.map.chips?.features || [];
  const running = busy || loading;
  const promptBox = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    const root = document.documentElement;
    root.dataset.reading = String(preferences.reading);
    root.dataset.colour = preferences.colour;
    root.dataset.contrast = String(preferences.contrast);
    root.dataset.largeText = String(preferences.largeText);
    root.dataset.reducedMotion = String(preferences.reducedMotion);
  }, [preferences]);
  function navigate(next: string) {
    setPage(next);
    const url = new URL(window.location.href);
    if (next === "guidance") url.searchParams.set("page", "guidance");
    else url.searchParams.delete("page");
    if (
      url.pathname + url.search !==
      window.location.pathname + window.location.search
    )
      window.history.pushState({}, "", url.pathname + url.search);
  }
  function showSummary() {
    setPage("workspace");
    setHistory(null);
    setTab("summary");
  }
  function inspectStep(ref: string) {
    setFocusedRef(ref);
    setTab("trace");
    setPage("workspace");
  }
  async function openPrevious(at: string) {
    if (!view) return;
    try {
      setPrevious(
        await request(
          `/api/runs/${view.run.id}/judgements/${encodeURIComponent(at)}`,
        ),
      );
    } catch (e) {
      setError((e as Error).message);
    }
  }
  function useTemplate() {
    const text = buildPrompt(asset, area);
    setPrompt(text);
    requestAnimationFrame(() => {
      promptBox.current?.focus();
      const start = text.indexOf("[");
      if (start >= 0)
        promptBox.current?.setSelectionRange(
          start,
          text.indexOf("]", start) + 1,
        );
    });
  }
  async function load(id: string, updateUrl = true) {
    if (
      updateUrl ||
      new URLSearchParams(window.location.search).get("page") !== "guidance"
    )
      setPage("workspace");
    setSelectedChip(null);
    setFocusBounds(null);
    const ticket = ++requestId.current;
    setError("");
    setLoading(true);
    try {
      let data: View;
      try {
        data = await request<View>(`/api/runs/${encodeURIComponent(id)}`);
      } catch (e) {
        // Not archived yet: a run that started moments ago (refresh, back/forward, shared link).
        const live = await request<{ done: boolean }>(
          `/api/runs/${encodeURIComponent(id)}/progress`,
        ).catch(() => null);
        if (ticket !== requestId.current) return;
        if (!live) throw e;
        resume(id, updateUrl);
        return;
      }
      if (ticket !== requestId.current) return;
      stream.current?.close();
      if (data.run.status === "running") {
        setView(data);
        resume(id, updateUrl);
        return;
      }
      setBusy(false);
      setView(data);
      setPrompt(data.run.prompt);
      active.current = id;
      setSelected(null);
      setEvents([]);
      setPhase(data.kpis.verdict || "Run loaded");
      setHistory(null);
      if (updateUrl)
        window.history.pushState(
          {},
          "",
          `${window.location.pathname}?run=${encodeURIComponent(id)}`,
        );
    } catch (e) {
      if (ticket === requestId.current) setError((e as Error).message);
    } finally {
      if (ticket === requestId.current) setLoading(false);
    }
  }
  useEffect(() => {
    request<{ models: string[] }>("/api/models")
      .then((d) => {
        setModels(d.models);
        setModel(d.models[0] || "");
      })
      .catch((e) => setError(e.message));
    const id = new URLSearchParams(window.location.search).get("run");
    if (id) void load(id, false);
    const pop = () => {
      if (
        new URLSearchParams(window.location.search).get("page") === "guidance"
      ) {
        setPage("guidance");
        return;
      }
      setPage("workspace");
      const id = new URLSearchParams(window.location.search).get("run");
      if (id) void load(id, false);
      else reset(false);
    };
    window.addEventListener("popstate", pop);
    return () => {
      stream.current?.close();
      window.removeEventListener("popstate", pop);
    };
  }, []);
  useEffect(() => {
    busyRef.current = busy;
    const warn = (e: BeforeUnloadEvent) => {
      if (busyRef.current) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [busy]);
  function reset(updateUrl = true) {
    setPage("workspace");
    setSelectedChip(null);
    setFocusBounds(null);
    requestId.current++;
    stream.current?.close();
    setView(null);
    active.current = "";
    setPrompt("");
    setSelected(null);
    setHistory(null);
    setEvents([]);
    setTab("findings");
    setBusy(false);
    setLoading(false);
    setError("");
    setPhase("Ready to explore");
    if (updateUrl) window.history.pushState({}, "", window.location.pathname);
  }
  function resume(id: string, updateUrl: boolean) {
    active.current = id;
    setBusy(true);
    setSelected(null);
    setEvents([]);
    setPhase("Following a run in progress");
    if (updateUrl)
      window.history.pushState(
        {},
        "",
        `${window.location.pathname}?run=${encodeURIComponent(id)}`,
      );
    follow(id);
  }
  function follow(id: string) {
    stream.current?.close();
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    let failures = 0;
    let cursor = "";
    // Short requests survive workshop/CloudFront buffering; the backend reads the same
    // archived/live events as SSE. Polling does not trigger inference.
    stream.current = {
      close: () => {
        stopped = true;
        clearTimeout(timer);
      },
    };
    async function poll() {
      if (stopped || active.current !== id) return;
      try {
        const snapshot = await request<{
          events: any[];
          done: boolean;
          cursor: string;
        }>(
          `/api/runs/${encodeURIComponent(id)}/progress${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ""}`,
        );
        if (stopped || active.current !== id) return;
        failures = 0;
        setError("");
        cursor = snapshot.cursor || cursor; // each poll returns only events since the last one
        if (snapshot.events.length)
          setEvents((prev) => [...prev, ...snapshot.events]);
        for (const ev of snapshot.events) {
          if (ev.type === "area")
            setPhase(
              ev.label ? `Searching ${ev.label}` : "Resolving search area",
            );
          if (ev.type === "step")
            setPhase(
              ev.entry?.kind === "end"
                ? "Agent finished; preparing summary and evaluation"
                : ev.entry?.title || "Gathering evidence",
            );
          if (ev.type === "judging")
            setPhase("Independent judge panel is reviewing the evidence");
          if (ev.type === "judge")
            setPhase(
              `${ev.key}: ${ev.status === "ok" ? "judgement received" : "judge unavailable"}`,
            );
          if (ev.type === "judge_error")
            setError(ev.error || "A judging service was unavailable.");
          if (ev.type === "done") {
            stopped = true;
            setBusy(false);
            setPhase(
              ev.error
                ? "Run ended with an error"
                : ev.view?.kpis?.verdict || "Complete",
            );
            if (ev.error) setError(ev.error);
            if (ev.view) {
              setView(ev.view);
              setPrompt(ev.view.run.prompt);
              setTab("evaluation");
            } else
              request<View>(`/api/runs/${id}`)
                .then((fresh) =>
                  setView((old) =>
                    old?.run.id === fresh.run.id ? fresh : old,
                  ),
                )
                .catch((e) => setError(e.message));
          }
        }
      } catch (e) {
        if (stopped || active.current !== id) return;
        failures++;
        setError(
          `Progress connection interrupted; retrying. ${(e as Error).message}`,
        );
        if (failures >= 5) {
          stopped = true;
          setBusy(false);
          setError(
            "Progress is unavailable. The server may still be working; reopen this run from Previous runs.",
          );
        }
      }
      if (!stopped) timer = setTimeout(poll, 2000);
    }
    void poll();
  }
  async function start() {
    if (!prompt.trim() || busy) return;
    if (hasTemplateBlanks(prompt)) {
      setError("Fill in [asset type] and [area] before starting.");
      promptBox.current?.focus();
      return;
    }
    const ticket = ++requestId.current; // a load still in flight must not overwrite this run
    stream.current?.close();
    setError("");
    setBusy(true);
    setView(null);
    setSelected(null);
    setEvents([]);
    setPhase("Starting research");
    try {
      const data = await request<{ run_id: string }>("/api/runs", {
        prompt: prompt.trim(),
        model: model || undefined,
      });
      if (ticket !== requestId.current) return;
      active.current = data.run_id;
      window.history.pushState(
        {},
        "",
        `${window.location.pathname}?run=${data.run_id}`,
      );
      follow(data.run_id);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
      setPhase("Could not start run");
    }
  }
  async function rejudge() {
    if (!view || busy) return;
    setError("");
    setBusy(true);
    setEvents([]);
    setPhase("Re-judging saved evidence");
    try {
      await request(`/api/runs/${view.run.id}/judge`, {});
      active.current = view.run.id;
      follow(view.run.id);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }
  async function reconsider(reviewId: string) {
    if (!view || busy) return;
    setError("");
    setBusy(true);
    setEvents([]);
    setPhase("Judges are considering the saved human review");
    try {
      await request(
        `/api/runs/${view.run.id}/reviews/${reviewId}/reconsider`,
        {},
      );
      active.current = view.run.id;
      follow(view.run.id);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }
  async function runs(
    more = false,
    filters = { model: filterModel, verdict: filterVerdict },
  ) {
    navigate("workspace");
    setError("");
    try {
      const data = await request<{ runs: Row[]; next: string | null }>(
        `/api/runs?limit=30${filters.model ? `&model=${encodeURIComponent(filters.model)}` : ""}${filters.verdict ? `&verdict=${encodeURIComponent(filters.verdict)}` : ""}${more && historyNext ? `&before=${encodeURIComponent(historyNext)}` : ""}`,
      );
      setHistory((old) => (more ? [...(old || []), ...data.runs] : data.runs));
      setHistoryNext(data.next);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  const timeline =
    view?.timeline ||
    events.filter((e) => e.type === "step").map((e) => e.entry);
  const judgedEvents = events.filter((e) => e.type === "judge");
  function exportJson() {
    if (!view) return;
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(view, null, 2)], { type: "application/json" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = `foundry-${view.run.id}.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return (
    <div className="app-shell live-workspace">
      <header className="app-header">
        <button
          className="brand"
          onClick={() => !busy && reset()}
          aria-label="Team Foundry home"
        >
          <span className="brand-mark" aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
          <span className="brand-name">Team Foundry</span>
          <span className="brand-context">Evidence workspace</span>
        </button>
        <nav className="main-nav" aria-label="Main navigation">
          <button
            className={`nav-item ${page === "workspace" && history === null ? "active" : ""}`}
            onClick={() => {
              setHistory(null);
              navigate("workspace");
            }}
          >
            Workspace
          </button>
          <button
            className={`nav-item ${history !== null ? "active" : ""}`}
            onClick={() => void runs()}
            disabled={busy}
          >
            <Icon name="clock" size={16} /> Previous runs
          </button>
          <button
            className={`nav-item ${page === "guidance" ? "active" : ""}`}
            onClick={() => navigate("guidance")}
          >
            Judge guidance
          </button>
        </nav>
        <div className="header-actions">
          <div
            className={`run-status ${busy ? "running" : view ? "completed" : "before"}`}
            role="status"
          >
            <span />
            {busy ? "Working" : view ? view.kpis.verdict : "Ready"}
          </div>
          <button
            className="evaluation-button"
            onClick={() => {
              setTab("evaluation");
              navigate("workspace");
              setHistory(null);
            }}
            disabled={!view}
          >
            <Icon name="panel" size={16} /> Evaluation
          </button>
          <button
            className="icon-button accessibility-trigger"
            aria-label="Accessibility and reading settings"
            onClick={() => setSettingsOpen(true)}
          >
            <span aria-hidden="true">Aa</span>
          </button>
        </div>
      </header>
      {error && (
        <div className="error-banner" role="alert">
          <Icon name="info" />
          <span>{error}</span>
          <button onClick={() => setError("")} aria-label="Dismiss error">
            <Icon name="x" />
          </button>
        </div>
      )}
      {page === "guidance" ? (
        <Guidance onRun={(id) => void load(id)} />
      ) : history !== null ? (
        <main className="history-page">
          <div className="page-heading">
            <div>
              <span className="section-kicker">Your evidence archive</span>
              <h1>Previous runs</h1>
              <p>
                Reopen a result, follow its evidence, or review its evaluation.
              </p>
            </div>
            <button className="primary" onClick={() => reset()}>
              New research <Icon name="plus" />
            </button>
          </div>
          <div className="run-filters">
            <label>
              Agent model
              <select
                value={filterModel}
                onChange={(e) => {
                  setFilterModel(e.target.value);
                  void runs(false, {
                    model: e.target.value,
                    verdict: filterVerdict,
                  });
                }}
              >
                <option value="">All models</option>
                {models.map((m) => (
                  <option key={m}>{m}</option>
                ))}
              </select>
            </label>
            <label>
              Result
              <select
                value={filterVerdict}
                onChange={(e) => {
                  setFilterVerdict(e.target.value);
                  void runs(false, {
                    model: filterModel,
                    verdict: e.target.value,
                  });
                }}
              >
                {["", "scored", "FAILED", "not scored", "not judged"].map(
                  (v) => (
                    <option key={v} value={v}>
                      {v || "All results"}
                    </option>
                  ),
                )}
              </select>
            </label>
          </div>
          {!history.length ? (
            <Empty title="No archived runs yet">
              Start a research request to build your first evidence record.
            </Empty>
          ) : (
            <div className="run-grid">
              {history.map((row) => (
                <button
                  className="run-card"
                  key={row.id}
                  onClick={() => void load(row.id)}
                >
                  <span className="run-card-top">
                    <span className="status-tag">{row.verdict}</span>
                    <span>
                      {formatScore(row.score)}
                      <small> /100</small>
                    </span>
                  </span>
                  <h3>{row.prompt}</h3>
                  <p>{row.area || "Area not recorded"}</p>
                  <footer>
                    <span>{row.model_key}</span>
                    <span>{localTime(row.started_at)}</span>
                    <Icon name="arrow" />
                  </footer>
                </button>
              ))}
            </div>
          )}
          {historyNext && (
            <button className="secondary" onClick={() => void runs(true)}>
              Load more runs
            </button>
          )}
        </main>
      ) : (
        <main className="workspace">
          <div className="map-column">
            <section
              className={`map-stage ${!view && !busy ? "welcome-stage" : ""}`}
              aria-label="Geographic evidence map"
            >
              <EvidenceMap
                view={view}
                selected={selected}
                selectedChip={selectedChip}
                preferences={preferences}
                focusBounds={focusBounds}
                onSelectChip={(i) => {
                  setSelectedChip(i);
                  setSelected(null);
                }}
                onClose={() => {
                  setSelected(null);
                  setSelectedChip(null);
                }}
                onTrace={inspectStep}
                onSelect={(i) => {
                  setSelectedChip(null);
                  setSelected(i);
                  setTab("findings");
                }}
              />
              {!view && !busy && !loading ? (
                <div className="welcome-card">
                  <div className="eyebrow">
                    <Icon name="spark" size={15} /> Geographic research, with
                    evidence
                  </div>
                  <h1>
                    From a question
                    <br />
                    to a result you can check.
                  </h1>
                  <p>
                    Search Earth data. See what the agent did.
                    <br />
                    Understand what to trust and what to review.
                  </p>
                  <form
                    className="prompt-composer"
                    onSubmit={(e) => {
                      e.preventDefault();
                      void start();
                    }}
                  >
                    <textarea
                      ref={promptBox}
                      aria-label="Geographic research question"
                      value={prompt}
                      onChange={(e) => setPrompt(e.target.value)}
                      onKeyDown={(e) => {
                        if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                          e.preventDefault();
                          void start();
                        }
                      }}
                      placeholder="Find [asset type] in [area]. Return locations, cite evidence, and explain uncertainty."
                    />
                    <div className="composer-footer">
                      <label className="model-select">
                        <span className="sr-only">Agent model</span>
                        <select
                          aria-label="Agent model"
                          value={model}
                          onChange={(e) => setModel(e.target.value)}
                        >
                          {models.map((m) => (
                            <option key={m} value={m}>
                              {m}
                            </option>
                          ))}
                        </select>
                      </label>
                      <span className="keyboard-hint">⌘ / Ctrl ↵</span>
                      <button
                        className="run-button"
                        disabled={
                          !prompt.trim() ||
                          !models.length ||
                          hasTemplateBlanks(prompt)
                        }
                      >
                        Run research <Icon name="arrow" size={16} />
                      </button>
                    </div>
                  </form>
                  <div className="template-builder">
                    <label>
                      Asset type
                      <input
                        value={asset}
                        onChange={(e) => setAsset(e.target.value)}
                        placeholder="e.g. solar parks"
                      />
                    </label>
                    <label>
                      Area
                      <input
                        value={area}
                        onChange={(e) => setArea(e.target.value)}
                        placeholder="e.g. Jodhpur, India"
                      />
                    </label>
                    <button
                      type="button"
                      className="secondary"
                      onClick={useTemplate}
                    >
                      Use editable template
                    </button>
                  </div>
                  {hasTemplateBlanks(prompt) && (
                    <p className="template-hint">
                      Replace the bracketed fields with your asset and area. The
                      template is editable text.
                    </p>
                  )}
                  <div className="real-examples">
                    <span>START WITH A QUESTION</span>
                    <div>
                      {examples.map((e) => (
                        <button
                          key={e.label}
                          onClick={() => setPrompt(e.prompt)}
                        >
                          <Icon name="target" size={16} />
                          <strong>{e.label}</strong>
                          <small>{e.place}</small>
                          <Icon name="arrow" size={14} />
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="welcome-foot">
                    <i /> Real tool results · Independent model judges · Human
                    review
                  </div>
                </div>
              ) : (
                <div className="compact-prompt">
                  <span className="prompt-icon">
                    <Icon name="search" />
                  </span>
                  <div>
                    <small>
                      {busy
                        ? "Researching this request"
                        : view?.run.area || "Research request"}
                    </small>
                    <strong>{prompt || "Loading saved run…"}</strong>
                  </div>
                  <button
                    className="edit-button"
                    onClick={() => reset()}
                    disabled={running}
                  >
                    <Icon name="plus" size={15} /> New run
                  </button>
                </div>
              )}
              {busy && (
                <div className="research-progress">
                  <div className="progress-head">
                    <span className="activity-pulse" />
                    <div>
                      <strong>{phase}</strong>
                      <span>
                        {timeline.length} recorded steps · {judgedEvents.length}{" "}
                        judge replies
                      </span>
                    </div>
                  </div>
                  <div className="indeterminate" />
                  <p>You can inspect completed steps while the agent works.</p>
                </div>
              )}
              {loading && (
                <div className="loading-overlay" role="status">
                  Loading archived evidence…
                </div>
              )}
              {view && (
                <div className="research-area">
                  <span>
                    <Icon name="target" size={14} /> Saved search area
                  </span>
                  {view.run.area || "No boundary recorded"}
                </div>
              )}
            </section>
            {view && <RunSummary view={view} onExpand={showSummary} />}
          </div>
          {(view || busy) && (
            <aside className="side-panel real-panel">
              <div className="panel-header">
                <div className="panel-tabs">
                  {["findings", "evaluation", "trace", "summary"].map((t) => (
                    <button
                      key={t}
                      onClick={() => {
                        setTab(t);
                        setFocusedRef(null);
                      }}
                      className={tab === t ? "active" : ""}
                    >
                      {t === "findings"
                        ? `Findings${view ? " · " + sites.length : ""}`
                        : t === "trace"
                          ? "Actions"
                          : t === "summary"
                            ? "Summary"
                            : "Evaluation"}
                    </button>
                  ))}
                </div>
              </div>
              <div
                className="panel-content"
                key={`${view?.run.id || "live"}-${tab}`}
              >
                {!view ? (
                  <>
                    <div className="section-kicker live-kicker">
                      <span className="live-dot" aria-hidden="true" />
                      Live research
                    </div>
                    <h2>Building an evidence trail</h2>
                    <p>
                      Results and scores appear when the agent finishes.
                      Activity below comes from the actual run.
                    </p>
                    <div className="live-progress" aria-hidden="true">
                      <span />
                    </div>
                    <Trace entries={timeline} live />
                    <LiveNow events={events} timeline={timeline} />
                  </>
                ) : tab === "findings" ? (
                  <>
                    <div className="section-kicker">
                      Findings from saved evidence
                    </div>
                    <h2>
                      {sites.length
                        ? `${sites.length} reported ${sites.length === 1 ? "location" : "locations"}`
                        : "The agent’s answer"}
                    </h2>
                    <p className="fine-print">
                      Reported locations are candidates for review. Matching a
                      tool result does not independently confirm the asset.
                    </p>
                    <div className="mini-stats">
                      <Stat
                        label="Source values matched"
                        value={`${view.kpis.claims_matched}/${view.kpis.claims_total}`}
                      />
                      <Stat
                        label="Locations in area"
                        value={
                          view.kpis.claims_located
                            ? `${view.kpis.claims_inside}/${view.kpis.claims_located}`
                            : "Not checked"
                        }
                      />
                      <Stat label="Imagery results" value={chips.length} />
                    </div>
                    {sites.length > 0 && (
                      <div className="candidate-list">
                        {sites.map((s, i) => (
                          <button
                            key={s.id}
                            className={`candidate-row ${selected === s.id ? "selected" : ""}`}
                            onClick={() => setSelected(s.id)}
                          >
                            <span className="candidate-index">
                              {String(i + 1).padStart(2, "0")}
                            </span>
                            <span className="candidate-info">
                              <strong>{s.name}</strong>
                              <small>
                                {s.lat.toFixed(5)}, {s.lon.toFixed(5)} ·{" "}
                                {s.ref || "No source ref"}
                              </small>
                            </span>
                            <span
                              className={`location-dot ${s.inside === false ? "outside" : ""}`}
                            />
                          </button>
                        ))}
                      </div>
                    )}
                    {selected !== null && sites[selected] && (
                      <div className="selected-evidence">
                        <h3>Source for location {selected + 1}</h3>
                        <p>{sites[selected].name}</p>
                        <button
                          className="text-button"
                          onClick={() => {
                            setFocusedRef(sites[selected].ref);
                            setTab("trace");
                          }}
                        >
                          Inspect step{" "}
                          {sites[selected].ref || "and source claims"}{" "}
                          <Icon name="arrow" size={14} />
                        </button>
                      </div>
                    )}
                    {chips.length > 0 && (
                      <div
                        className="evidence-strip"
                        aria-label="Tool-returned imagery"
                      >
                        {chips
                          .filter((f: any) => f.properties.tile_url)
                          .slice(0, 24)
                          .map((f: any, i: number) => (
                            <figure key={i}>
                              <button
                                className="chip-open"
                                aria-label={`Open imagery result ${i + 1} on map`}
                                onClick={() => {
                                  setSelected(null);
                                  setSelectedChip(chips.indexOf(f));
                                }}
                              >
                                <img
                                  src={f.properties.tile_url}
                                  alt={`Tool-returned imagery ${f.properties.node || i + 1}`}
                                  loading="lazy"
                                  onError={(e) => {
                                    e.currentTarget.hidden = true;
                                  }}
                                />
                              </button>
                              <figcaption>
                                {f.properties.ref} ·{" "}
                                {f.properties.index || "Imagery"}
                                <small>
                                  {f.properties.observed || "Date not recorded"}
                                </small>
                              </figcaption>
                            </figure>
                          ))}
                      </div>
                    )}
                    <Disclosure id="full-answer" title="Full agent answer">
                      <Text value={view.final_answer} />
                    </Disclosure>
                    <Disclosure
                      id="source-values"
                      title={`Check all ${view.claims.length} declared source values`}
                    >
                      <DataTable rows={view.claims} />
                    </Disclosure>
                    <button
                      className="secondary"
                      onClick={() => setTab("evaluation")}
                    >
                      Review evaluation scores →
                    </button>
                  </>
                ) : tab === "evaluation" ? (
                  <>
                    <Evaluation
                      view={view}
                      busy={busy}
                      onRejudge={() => void rejudge()}
                      onExport={exportJson}
                      onPrevious={(at) => void openPrevious(at)}
                      reviewer={
                        <Reviewer
                          key={view.run.id}
                          view={view}
                          busy={busy}
                          onReconsider={(id) => void reconsider(id)}
                          onSaved={() =>
                            void request<View>(`/api/runs/${view.run.id}`)
                              .then((fresh) =>
                                setView((old) =>
                                  old?.run.id === fresh.run.id ? fresh : old,
                                ),
                              )
                              .catch((e) => setError(e.message))
                          }
                        />
                      }
                    />
                  </>
                ) : tab === "summary" ? (
                  <DetailedSummary view={view} />
                ) : (
                  <>
                    <div className="section-kicker">Reproducible activity</div>
                    <h2>What the agent actually did</h2>
                    <p>
                      Open any step to inspect the saved tool arguments, results
                      or model reply.
                    </p>
                    <Trace
                      entries={timeline}
                      focusedRef={focusedRef}
                      onZoom={(bounds) => {
                        setSelected(null);
                        setSelectedChip(null);
                        setFocusBounds([...bounds]);
                      }}
                    />
                    <details className="source-details">
                      <summary>Run metadata</summary>
                      <pre>{JSON.stringify(view.run, null, 2)}</pre>
                    </details>
                    <Disclosure
                      id="datasets-used"
                      title="Datasets and sources accessed"
                    >
                      <pre>{JSON.stringify(view.datasets || [], null, 2)}</pre>
                    </Disclosure>
                    <button className="secondary" onClick={showSummary}>
                      Read the run summary →
                    </button>
                  </>
                )}
              </div>
            </aside>
          )}
        </main>
      )}
      <footer className="workspace-footer">
        <span>
          <i /> Team Foundry · Clay Earth Dataset Foundry
        </span>
        <span>Evidence first. Human judgement always.</span>
        <button className="footer-link" onClick={() => setModal(true)}>
          About
        </button>
        <a href={endpoint("/api/docs")}>API</a>
        <a href={endpoint("/")}>Classic console</a>
      </footer>
      {modal && (
        <Dialog title="About this workspace" onClose={() => setModal(false)}>
          <p>
            Foundry records what an agent did, its tool evidence, rubric ratings
            and your review. The /100 number evaluates workflow and output; it
            is not confidence or verified accuracy.
          </p>
          <p>
            AWS and LGND credentials stay on the backend. Run records live in
            the configured archive. Display settings are saved only in this
            browser.
          </p>
        </Dialog>
      )}
      {settingsOpen && (
        <Accessibility
          value={preferences}
          onChange={setPreferences}
          onClose={() => setSettingsOpen(false)}
        />
      )}
      {previous && (
        <Dialog title="Earlier judgement" onClose={() => setPrevious(null)}>
          <p>
            Judged {localTime(previous.judged_at)} · Run {previous.run_id}
          </p>
          <p>
            Rubric evaluation score: {formatScore(previous.panel?.overall)}/100
          </p>
          <pre>{JSON.stringify(previous, null, 2)}</pre>
        </Dialog>
      )}
    </div>
  );
}
// What the run is doing right now, while it runs: the agent's next move after its last recorded step,
// then each judge's progress through its passes. Elapsed time ticks from the last thing that happened.
function LiveNow({ events, timeline }: { events: any[]; timeline: any[] }) {
  const [now, setNow] = useState(Date.now());
  const since = useRef(Date.now());
  const count = events.length;
  useEffect(() => {
    since.current = Date.now();
  }, [count]);
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  const elapsed = Math.max(0, Math.round((now - since.current) / 1000));
  const judging = [...events].reverse().find((e) => e.type === "judging");
  const replies = events.filter((e) => e.type === "judge");
  if (judging) {
    const passes = judging.passes || 1;
    return (
      <div className="live-judges" role="status" aria-live="polite">
        <div className="live-now">
          <span className="live-badge" aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
          <span>
            <strong>Independent judges are reviewing the evidence</strong>
            <small>
              {replies.length} of {passes * (judging.seats?.length || 3)} verdicts
              · {elapsed}s since the last
            </small>
          </span>
        </div>
        {(judging.seats || []).map((seat: any) => {
          const mine = replies.filter((r) => r.key === seat.key);
          const done = mine.length >= passes;
          const scores = mine
            .filter((r) => r.status === "ok")
            .map((r) => formatScore(r.score));
          return (
            <div
              key={seat.key}
              className={`live-judge ${done ? "done" : "working"}`}
            >
              <span className="live-judge-dot" aria-hidden="true" />
              <strong>{seat.key}</strong>
              <span className="live-judge-passes" aria-hidden="true">
                {Array.from({ length: passes }, (_, i) => (
                  <i key={i} className={i < mine.length ? "in" : ""} />
                ))}
              </span>
              <span className="live-judge-score">
                {scores.length ? scores.join(" · ") : done ? "Unavailable" : "reading…"}
              </span>
            </div>
          );
        })}
      </div>
    );
  }
  const last = timeline[timeline.length - 1];
  const doing =
    last?.kind === "model"
      ? "Calling a tool"
      : timeline.length
        ? "The agent is thinking"
        : "Starting the agent";
  return (
    <div className="live-now" role="status" aria-live="polite">
      <span className="live-badge" aria-hidden="true">
        <i />
        <i />
        <i />
      </span>
      <span>
        <strong>{doing}</strong>
        <small>
          {elapsed}s since the last step · {timeline.length}{" "}
          {timeline.length === 1 ? "step" : "steps"} so far
        </small>
      </span>
    </div>
  );
}
function Trace({
  entries,
  focusedRef,
  onZoom,
  live = false,
}: {
  onZoom?: (bounds: number[]) => void;
  entries: any[];
  focusedRef?: string | null;
  live?: boolean;
}) {
  useEffect(() => {
    if (focusedRef)
      document
        .getElementById(`step-${focusedRef}`)
        ?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [focusedRef]);
  return (
    <div className="real-timeline">
      {entries.map((e, i) => (
        <details
          key={`${e.ref}-${i}`}
          id={`step-${e.ref}`}
          open={focusedRef === e.ref}
          className={`trace-step ${e.status === "error" ? "trace-error" : ""} ${live ? "trace-live" : ""} ${live && i === entries.length - 1 ? "trace-latest" : ""}`}
        >
          <summary>
            <span className="trace-ref">{e.ref || i + 1}</span>
            <span>
              <strong>
                {e.title || e.sentence || e.tool || "Recorded step"}
              </strong>
              <small>
                {e.kind} {e.ms != null ? `· ${(e.ms / 1000).toFixed(1)}s` : ""}
              </small>
            </span>
            <Icon name="chevron" size={14} />
          </summary>
          {e.bounds?.length === 4 && onZoom && (
            <button className="secondary" onClick={() => onZoom(e.bounds)}>
              Show this step on map
            </button>
          )}
          {e.detail && <p>{e.detail}</p>}
          <pre>{JSON.stringify(e.raw || e, null, 2)}</pre>
        </details>
      ))}
    </div>
  );
}
