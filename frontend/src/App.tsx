import { useEffect, useRef, useState } from "react";
import MarkdownIt from "markdown-it";
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
const markdown = new MarkdownIt({ html: false, linkify: false }).enable(
  "table",
);
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
function Text({ value }: { value: unknown }) {
  return (
    <div
      className="markdown"
      dangerouslySetInnerHTML={{
        __html: markdown.render(typeof value === "string" ? value : ""),
      }}
    />
  );
}
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
function Stat({
  label,
  value,
  sub,
}: {
  label: string;
  value: React.ReactNode;
  sub?: string;
}) {
  return (
    <div className="stat">
      <span>{label}</span>
      <strong>{value}</strong>
      {sub && <small>{sub}</small>}
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
function Reviewer({ view, onSaved }: { view: View; onSaved: () => void }) {
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
    [sending, setSending] = useState(false);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSaved("");
    setSending(true);
    try {
      const payload = reviewPayload(
        name,
        criterion,
        decision,
        score,
        notes,
        refs,
      );
      await request(`/api/runs/${view.run.id}/reviews`, payload);
      setSaved(
        "Review saved to the run archive. The automated score has not been changed.",
      );
      setNotes("");
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
        <label>
          Your name
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            maxLength={100}
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
        <button
          className="primary"
          disabled={
            sending || !criterion || !view.scorecard || view.kpis.score === null
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
            <pre>{JSON.stringify(r.criteria, null, 2)}</pre>
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
    [focusedRef, setFocusedRef] = useState<string | null>(null);
  const stream = useRef<EventSource | null>(null),
    active = useRef(""),
    busyRef = useRef(false),
    requestId = useRef(0);
  const sites = candidatesOf(view),
    chips = view?.map.chips?.features || [];
  const running = busy || loading;
  async function load(id: string, updateUrl = true) {
    const ticket = ++requestId.current;
    setError("");
    setLoading(true);
    try {
      const data = await request<View>(`/api/runs/${encodeURIComponent(id)}`);
      if (ticket !== requestId.current) return;
      stream.current?.close();
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
  function follow(id: string) {
    stream.current?.close();
    const source = new EventSource(
      endpoint(`/api/runs/${encodeURIComponent(id)}/events`),
    );
    stream.current = source;
    source.onmessage = (e) => {
      if (active.current !== id) return;
      let ev: any;
      try {
        ev = JSON.parse(e.data);
      } catch {
        return;
      }
      setEvents((old) => [...old, ev]);
      if (ev.type === "area")
        setPhase(ev.label ? `Searching ${ev.label}` : "Resolving search area");
      if (ev.type === "step") setPhase(ev.entry?.title || "Gathering evidence");
      if (ev.type === "judging")
        setPhase("Independent judge panel is reviewing the evidence");
      if (ev.type === "judge")
        setPhase(
          `${ev.key}: ${ev.status === "ok" ? "judgement received" : "judge unavailable"}`,
        );
      if (ev.type === "judge_error" || ev.type === "guidance_unavailable")
        setError(ev.error || "A judging service was unavailable.");
      if (ev.type === "done") {
        source.close();
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
        } else {
          request<View>(`/api/runs/${id}`)
            .then(setView)
            .catch((e) => setError(e.message));
        }
      }
    };
    source.onerror = () => {
      if (active.current !== id) return;
      setError(
        "Live connection interrupted. Reconnecting… You can also reopen this run from Previous runs.",
      );
      if (source.readyState === EventSource.CLOSED) setBusy(false);
    };
    source.onopen = () => setError("");
  }
  async function start() {
    if (!prompt.trim() || busy) return;
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
  async function runs(more = false) {
    setError("");
    try {
      const data = await request<{ runs: Row[]; next: string | null }>(
        `/api/runs?limit=30${more && historyNext ? `&before=${encodeURIComponent(historyNext)}` : ""}`,
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
            className={`nav-item ${history === null ? "active" : ""}`}
            onClick={() => setHistory(null)}
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
          <a className="nav-item" href={endpoint("/guidance")}>
            Judge guidance
          </a>
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
              setHistory(null);
            }}
            disabled={!view}
          >
            <Icon name="panel" size={16} /> Evaluation
          </button>
          <button
            className="avatar"
            aria-label="About this workspace"
            onClick={() => setModal(true)}
          >
            <Icon name="info" />
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
      {history !== null ? (
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
                onSelect={(i) => {
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
                      aria-label="Geographic research question"
                      value={prompt}
                      onChange={(e) => setPrompt(e.target.value)}
                      onKeyDown={(e) => {
                        if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                          e.preventDefault();
                          void start();
                        }
                      }}
                      placeholder="Find solar parks in Jodhpur, India, and show their locations…"
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
                        disabled={!prompt.trim() || !models.length}
                      >
                        Run research <Icon name="arrow" size={16} />
                      </button>
                    </div>
                  </form>
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
            {view && (
              <section className="live-summary">
                <div className="summary-label">
                  <Icon name="check" size={18} />
                  <span>What this result means</span>
                </div>
                <h2>
                  {view.explanation?.headline ||
                    "Review this run before using its findings."}
                </h2>
                <p>{view.explanation?.summary}</p>
                <div className="summary-actions">
                  {view.explanation?.check_by_hand?.map((t: string) => (
                    <span key={t}>
                      <Icon name="arrow" size={13} />
                      {t}
                    </span>
                  ))}
                </div>
              </section>
            )}
          </div>
          {(view || busy) && (
            <aside className="side-panel real-panel">
              <div className="panel-header">
                <div className="panel-tabs">
                  {["findings", "evaluation", "trace"].map((t) => (
                    <button
                      key={t}
                      onClick={() => setTab(t)}
                      className={tab === t ? "active" : ""}
                    >
                      {t === "findings"
                        ? `Findings${view ? " · " + sites.length : ""}`
                        : t === "trace"
                          ? "Activity"
                          : "Evaluation"}
                    </button>
                  ))}
                </div>
              </div>
              <div className="panel-content">
                {!view ? (
                  <>
                    <div className="section-kicker">Live research</div>
                    <h2>Building an evidence trail</h2>
                    <p>
                      Results and scores appear when the agent finishes.
                      Activity below comes from the actual run.
                    </p>
                    {timeline.length === 0 && (
                      <Empty title="Connecting to the research tools">
                        Resolving the request and preparing the agent.
                      </Empty>
                    )}
                    <Trace entries={timeline} />
                    {judgedEvents.map((j, i) => (
                      <div key={i} className="judge-line">
                        <strong>{j.key}</strong>
                        <span>
                          {j.status === "ok"
                            ? `${formatScore(j.score)}/100`
                            : j.error || "Unavailable"}
                        </span>
                      </div>
                    ))}
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
                              <img
                                src={f.properties.tile_url}
                                alt={`Tool-returned imagery ${f.properties.node || i + 1}`}
                                loading="lazy"
                                onError={(e) => {
                                  e.currentTarget.hidden = true;
                                }}
                              />
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
                    <section className="answer-section">
                      <h3>Final answer</h3>
                      <Text value={view.final_answer} />
                    </section>
                    <details className="source-details">
                      <summary>
                        Check all {view.claims.length} declared source values
                      </summary>
                      <DataTable rows={view.claims} />
                    </details>
                    <Reviewer
                      key={view.run.id}
                      view={view}
                      onSaved={() =>
                        void request<View>(`/api/runs/${view.run.id}`)
                          .then(setView)
                          .catch((e) => setError(e.message))
                      }
                    />
                  </>
                ) : tab === "evaluation" ? (
                  <>
                    <div className="section-kicker">Quality and trust</div>
                    <div className="evaluation-heading">
                      <h2>Evaluate the result</h2>
                      <button
                        className="secondary small"
                        disabled={busy}
                        onClick={() => void rejudge()}
                      >
                        Re-judge
                      </button>
                    </div>
                    <div className="score-hero">
                      <strong>
                        {formatScore(view.kpis.score)}
                        <small>/100</small>
                      </strong>
                      <div>
                        <span>{view.kpis.verdict}</span>
                        <p>
                          {view.kpis.confidence
                            ? `${view.kpis.confidence} evidence agreement`
                            : "Not judged"}
                        </p>
                      </div>
                    </div>
                    <p className="fine-print">
                      Agreement measures how closely the judges agree on the
                      evidence. It is not a probability that the answer is
                      correct.
                    </p>
                    <div className="mini-stats">
                      <Stat
                        label="Workflow"
                        value={formatScore(view.kpis.workflow)}
                      />
                      <Stat
                        label="Output"
                        value={formatScore(view.kpis.output)}
                      />
                      <Stat
                        label="Trace integrity"
                        value={
                          view.kpis.trace_integrity ? "Intact" : "Needs review"
                        }
                      />
                    </div>
                    {view.source_check_note && (
                      <p className="notice">{view.source_check_note}</p>
                    )}
                    {view.kpis.not_scored_cause && (
                      <p className="notice">{view.kpis.not_scored_cause}</p>
                    )}
                    <h3 className="section-title">Rubric scorecard</h3>
                    {view.scorecard?.criteria?.map((c: any) => (
                      <details key={c.id} className="criterion">
                        <summary>
                          <span>
                            {c.plain || c.question}
                            <small>
                              {c.kind === "measured"
                                ? "Measured by code"
                                : c.dimension}
                            </small>
                          </span>
                          <strong>
                            {formatScore(c.score)}
                            {c.score !== null && <small>/100</small>}
                          </strong>
                        </summary>
                        <p>{c.question}</p>
                        {c.value && <p>Measured: {c.value}</p>}
                        <div className="score-bar">
                          <span style={{ width: `${c.score || 0}%` }} />
                        </div>
                        {Object.entries(
                          view.scorecard.anchors?.[c.id] || {},
                        ).map(([s, t]) => (
                          <p key={s} className="anchor">
                            <b>{s}</b> {String(t)}
                          </p>
                        ))}
                        {view.scorecard.judges?.map((j: any) => {
                          const jc = j.criteria?.find(
                            (x: any) => x.id === c.id,
                          );
                          return jc ? (
                            <div key={j.key} className="judge-reason">
                              <strong>
                                {j.key} · {jc.score}
                              </strong>
                              <p>{jc.rationale}</p>
                              <small>{jc.refs?.join(" · ")}</small>
                            </div>
                          ) : null;
                        })}
                      </details>
                    ))}
                    <h3 className="section-title">
                      Every condition in your request
                    </h3>
                    {view.conditions ? (
                      <>
                        <p>
                          {view.conditions.supported}/{view.conditions.total}{" "}
                          code-checked cells supported. Target identity and
                          other conditions may still need judge or human review.
                        </p>
                        {view.conditions.error && (
                          <p className="error-message">
                            {view.conditions.error}
                          </p>
                        )}
                        {view.conditions.rows?.map((row: any, i: number) => (
                          <div className="condition-row" key={i}>
                            <strong>{row.claim}</strong>
                            {row.cells.map((cell: any) => {
                              const condition = view.conditions.conditions.find(
                                (c: any) => c.id === cell.condition_id,
                              );
                              return (
                                <div key={cell.condition_id}>
                                  <span className={`status-tag ${cell.status}`}>
                                    {cell.status}
                                  </span>
                                  <b>{condition?.text || cell.condition_id}</b>
                                  <p>{cell.reason}</p>
                                  <small>{cell.refs?.join(" · ")}</small>
                                </div>
                              );
                            })}
                          </div>
                        ))}
                      </>
                    ) : (
                      <p className="notice">
                        No request-condition matrix is stored for this run. It
                        is not treated as fully compliant.
                      </p>
                    )}
                    <h3 className="section-title">Independent judge panel</h3>
                    {view.scorecard?.judges?.map((j: any) => (
                      <div key={j.key} className="judge-line">
                        <div>
                          <strong>{j.key}</strong>
                          <small>
                            {j.family}
                            {j.stood_in_for
                              ? ` · replacing ${j.stood_in_for}`
                              : ""}
                          </small>
                        </div>
                        <span>
                          {j.status === "ok"
                            ? `${formatScore(j.score)}/100`
                            : "Unavailable"}
                        </span>
                      </div>
                    ))}
                    <h3 className="section-title">Cost and review effort</h3>
                    <div className="mini-stats">
                      <Stat
                        label="Agent estimate"
                        value={money(view.kpis.agent_cost_usd)}
                      />
                      <Stat
                        label="Judge estimate"
                        value={money(view.kpis.judging_cost_usd)}
                      />
                      <Stat
                        label="Elapsed"
                        value={
                          view.kpis.runtime_s != null
                            ? `${Math.round(view.kpis.runtime_s)}s`
                            : "—"
                        }
                      />
                    </div>
                    <p className="fine-print">
                      Token-based estimates, not a full AWS bill. Imagery
                      procurement and analyst time are not included unless
                      explicitly recorded.
                    </p>
                    <details className="source-details">
                      <summary>Reference benchmark</summary>
                      {view.reference ? (
                        <>
                          <p>
                            {view.reference.error ||
                              "Metrics are tied to the archived reference and matching rule."}
                          </p>
                          <pre>
                            {JSON.stringify(
                              Object.fromEntries(
                                Object.entries(view.reference).filter(
                                  ([k]) =>
                                    !["features", "found", "missed"].includes(
                                      k,
                                    ),
                                ),
                              ),
                              null,
                              2,
                            )}
                          </pre>
                        </>
                      ) : (
                        <p>
                          No independent reference set is tied to this run.
                          Recall, precision and transfer performance are not
                          established.
                        </p>
                      )}
                    </details>
                    <details className="source-details">
                      <summary>
                        Sources, licences and presentation limits
                      </summary>
                      <p>
                        Presentation status:{" "}
                        <b>
                          {view.licences?.presentable === true
                            ? "No recorded blockers"
                            : view.licences?.presentable === false
                              ? "Needs licence review"
                              : "Not recorded"}
                        </b>
                      </p>
                      <div className="licence-list">
                        {view.licences?.items?.map((item: any, i: number) => (
                          <div key={i}>
                            <strong>{item.name}</strong>
                            <span
                              className={`status-tag ${item.presentable === true ? "supported" : "unverified"}`}
                            >
                              {item.presentable === true
                                ? "Recorded as presentable"
                                : "Check terms"}
                            </span>
                            <p>{item.licence || "Licence not recorded"}</p>
                          </div>
                        ))}
                      </div>
                      <details>
                        <summary>Full licence record</summary>
                        <pre>{JSON.stringify(view.licences, null, 2)}</pre>
                      </details>
                    </details>
                    <div className="export-actions">
                      <a
                        className="secondary"
                        href={endpoint(`/reports/${view.run.id}`)}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Open static report <Icon name="external" size={14} />
                      </a>
                      <button className="secondary" onClick={exportJson}>
                        Export evidence JSON
                      </button>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="section-kicker">Reproducible activity</div>
                    <h2>What the agent actually did</h2>
                    <p>
                      Open any step to inspect the saved tool arguments, results
                      or model reply.
                    </p>
                    <Trace entries={timeline} focusedRef={focusedRef} />
                    <details className="source-details">
                      <summary>Run metadata</summary>
                      <pre>{JSON.stringify(view.run, null, 2)}</pre>
                    </details>
                    {view.narrative && (
                      <>
                        <h3 className="section-title">Run summary</h3>
                        <Text value={view.narrative} />
                      </>
                    )}
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
        <a href={endpoint("/api/docs")}>API</a>
        <a href={endpoint("/")}>Classic console</a>
      </footer>
      {modal && (
        <div className="modal-backdrop" onClick={() => setModal(false)}>
          <section
            className="about-modal"
            role="dialog"
            aria-modal="true"
            aria-label="About this workspace"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              className="close-panel"
              aria-label="Close about"
              onClick={() => setModal(false)}
              autoFocus
            >
              <Icon name="x" />
            </button>
            <span className="section-kicker">Built for the analyst</span>
            <h2>Research you can inspect.</h2>
            <p>
              Foundry connects a tool-using agent, its evidence, independent
              model judges and your review in one workspace.
            </p>
            <p>
              Start a request, inspect the returned imagery and claims, then use
              Evaluation to see what was supported and what needs checking.
              Reference accuracy is reported only when a suitable reference set
              is attached.
            </p>
            <p>
              Your AWS and LGND credentials remain on the backend. Run history
              and reviews are saved in the configured deployment archive.
            </p>
            <button className="primary" onClick={() => setModal(false)}>
              Back to workspace
            </button>
          </section>
        </div>
      )}
    </div>
  );
}
function Trace({
  entries,
  focusedRef,
}: {
  entries: any[];
  focusedRef?: string | null;
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
          className={`trace-step ${e.status === "error" ? "trace-error" : ""}`}
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
          {e.detail && <p>{e.detail}</p>}
          <pre>{JSON.stringify(e.raw || e, null, 2)}</pre>
        </details>
      ))}
    </div>
  );
}
