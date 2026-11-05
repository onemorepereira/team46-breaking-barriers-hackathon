import { useEffect, useRef, useState } from "react";
import { markdownLibs, renderMarkdown } from "./markdown";
import { Icon } from "./Icon";
import EvidenceMap from "./Map";
import {
  request,
  endpoint,
  candidatesOf,
  formatScore,
  money,
  localTime,
  draftPayload,
  type Draft,
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
function Text({ value }: { value: unknown }) {
  const text = typeof value === "string" ? value : "";
  const [html, setHtml] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    markdownLibs()
      .then((libs) => live && setHtml(renderMarkdown(libs, text)))
      .catch(() => live && setHtml(null)); // plain text below if the renderer can't load
    return () => {
      live = false;
    };
  }, [text]);
  return html === null ? (
    <div className="markdown markdown-plain">{text}</div>
  ) : (
    <div className="markdown" dangerouslySetInnerHTML={{ __html: html }} />
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
const VOTE_WORD = ["No", "Partly", "Yes"];
function Votes({ votes }: { votes: Record<string, number[]> | undefined }) {
  if (!votes) return null;
  return (
    <span className="votes" aria-label="Judge votes, every pass">
      {Object.entries(votes).map(([judge, vs]) => (
        <span key={judge} className="vote-group" title={`${judge}: ${vs.join(", ")}`}>
          <span className="vote-judge">{judge}</span>
          {vs.map((v, i) => (
            <i key={i} className={`vote v${v}`} aria-hidden="true" />
          ))}
          <span className="sr-only">{vs.join(", ")}</span>
        </span>
      ))}
    </span>
  );
}
function CriterionCard({
  c,
  view,
  draft,
  onDraft,
  reviewable,
}: {
  c: any;
  view: View;
  draft: Draft | undefined;
  onDraft: (d: Draft | undefined) => void;
  reviewable: boolean;
}) {
  const card = view.scorecard;
  const anchors: Record<string, string> = card.anchors?.[c.id] || {};
  const judged = c.kind === "judged";
  const set = (patch: Partial<Draft>) =>
    onDraft({
      decision: "agree",
      score: "",
      reason: "",
      refs: "",
      ...draft,
      ...patch,
    });
  return (
    <details className={`criterion ${draft ? "has-draft" : ""}`}>
      <summary>
        <span className="criterion-q">
          {c.plain || c.question}
          <small>
            {judged ? c.dimension : "Measured by code"}
            {c.human != null && (
              <b className="human-tag">
                Reviewer: {formatScore((c.human / 2) * 100)}
              </b>
            )}
            {draft && (
              <b className="draft-tag">
                {draft.decision === "agree" ? "You agree" : `You suggest ${draft.score || "?"}`}
              </b>
            )}
          </small>
        </span>
        {judged && <Votes votes={card.votes_all?.[c.id]} />}
        <strong className="criterion-score">
          {formatScore(c.score)}
          {c.score !== null && <small>/100</small>}
        </strong>
      </summary>
      <div className="criterion-body">
        <p className="criterion-full">{c.question}</p>
        {c.value && <p className="criterion-full">Measured: {c.value}</p>}
        {judged && Object.keys(anchors).length > 0 && (
          <dl className="anchors">
            {Object.entries(anchors).map(([s, t]) => (
              <div key={s}>
                <dt>
                  {s} · {VOTE_WORD[Number(s)] || s}
                </dt>
                <dd>{String(t)}</dd>
              </div>
            ))}
          </dl>
        )}
        {judged &&
          card.judges?.map((j: any) => {
            const jc = j.criteria?.find((x: any) => x.id === c.id);
            return jc ? (
              <div key={j.key} className="judge-reason">
                <strong>
                  {j.key} <span>voted {jc.score}</span>
                </strong>
                <p>{jc.rationale || "No rationale recorded."}</p>
                {jc.refs?.length > 0 && <small>Cites {jc.refs.join(", ")}</small>}
              </div>
            ) : null;
          })}
        {judged && card.pass_count > 1 && (
          <p className="fine-print">
            Rationales are from the first of {card.pass_count} passes; the
            votes above are from every pass.
          </p>
        )}
        {judged && reviewable && (
          <div className="your-call" role="group" aria-label="Your assessment">
            <span className="your-call-label">Your assessment</span>
            <div className="segmented">
              <button
                type="button"
                className={draft?.decision === "agree" ? "on" : ""}
                aria-pressed={draft?.decision === "agree"}
                onClick={() =>
                  draft?.decision === "agree" ? onDraft(undefined) : set({ decision: "agree" })
                }
              >
                Agree with the panel
              </button>
              <button
                type="button"
                className={draft?.decision === "disagree" ? "on" : ""}
                aria-pressed={draft?.decision === "disagree"}
                onClick={() =>
                  draft?.decision === "disagree"
                    ? onDraft(undefined)
                    : set({ decision: "disagree" })
                }
              >
                Suggest a different score
              </button>
            </div>
            {draft?.decision === "disagree" && (
              <>
                <div className="score-pick" role="radiogroup" aria-label="Your score">
                  {(Object.keys(anchors).length ? Object.keys(anchors) : ["0", "1", "2"]).map(
                    (s) => (
                      <button
                        type="button"
                        key={s}
                        role="radio"
                        aria-checked={draft.score === s}
                        className={draft.score === s ? "on" : ""}
                        onClick={() => set({ score: s })}
                      >
                        <b>{s}</b> {VOTE_WORD[Number(s)] || ""}
                      </button>
                    ),
                  )}
                </div>
                <label>
                  Why
                  <textarea
                    value={draft.reason}
                    maxLength={2000}
                    onChange={(e) => set({ reason: e.target.value })}
                    placeholder="What in the evidence supports your score?"
                  />
                </label>
                <label>
                  Steps you relied on <span className="optional">optional</span>
                  <input
                    value={draft.refs}
                    onChange={(e) => set({ refs: e.target.value })}
                    placeholder="T2, T4"
                  />
                </label>
              </>
            )}
          </div>
        )}
      </div>
    </details>
  );
}
function readName(): string {
  try {
    return localStorage.getItem("foundry.reviewer") || "";
  } catch {
    return "";
  }
}
function ReviewBar({
  view,
  drafts,
  onSaved,
}: {
  view: View;
  drafts: Record<string, Draft>;
  onSaved: () => void;
}) {
  const [name, setName] = useState(readName),
    [note, setNote] = useState(""),
    [error, setError] = useState(""),
    [sending, setSending] = useState(false);
  const count = Object.keys(drafts).length;
  if (!count) return null;
  async function save() {
    setError("");
    setSending(true);
    try {
      const payload = draftPayload(name, drafts, note);
      try {
        localStorage.setItem("foundry.reviewer", name.trim());
      } catch {
        /* a per-viewer convenience only */
      }
      await request(`/api/runs/${view.run.id}/reviews`, payload);
      setNote("");
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSending(false);
    }
  }
  return (
    <div className="review-bar" role="region" aria-label="Your review">
      <strong>
        Your review · {count} {count === 1 ? "question" : "questions"}
      </strong>
      <input
        aria-label="Your name"
        placeholder="Your name"
        value={name}
        maxLength={100}
        onChange={(e) => setName(e.target.value)}
      />
      <input
        aria-label="Overall note (optional)"
        placeholder="Overall note (optional)"
        value={note}
        maxLength={2000}
        onChange={(e) => setNote(e.target.value)}
      />
      <button className="primary" disabled={sending} onClick={() => void save()}>
        {sending ? "Saving…" : "Save review"}
      </button>
      {error && (
        <p role="alert" className="error-message">
          {error}
        </p>
      )}
    </div>
  );
}
function SavedReviews({
  view,
  busy,
  onReconsider,
}: {
  view: View;
  busy: boolean;
  onReconsider: (id: string) => void;
}) {
  const card = view.scorecard;
  const reviews = card?.reviews || [];
  if (!reviews.length) return null;
  const name = (id: string) =>
    card.criteria?.find((c: any) => c.id === id)?.plain || id;
  return (
    <section className="saved-reviews">
      <h3 className="section-title">Human reviews</h3>
      {reviews.map((r: any, i: number) => (
        <article key={r.id || i} className="saved-review">
          <header>
            <strong>{r.reviewer}</strong>
            <span>
              {localTime(r.created_at)}
              {r.current === false ? " · about an earlier judgement" : ""}
            </span>
          </header>
          <ul>
            {Object.entries(r.criteria || {}).map(([id, v]: [string, any]) => (
              <li key={id}>
                <b>{name(id)}</b>
                {v.agree ? (
                  <span className="agree">agrees with the panel</span>
                ) : (
                  <span>
                    suggests <em>{v.score}</em>
                    {v.reason ? ` — ${v.reason}` : ""}
                    {v.refs?.length ? ` (${v.refs.join(", ")})` : ""}
                  </span>
                )}
              </li>
            ))}
          </ul>
          {r.note && <p>{r.note}</p>}
          {r.current && !r.reconsidered && card.reconsider_enabled && (
            <button
              className="secondary small"
              disabled={busy}
              onClick={() => onReconsider(r.id)}
            >
              Ask the judges to reconsider with this review
            </button>
          )}
          {r.reconsidered && (
            <small>Judges reconsidered {localTime(r.reconsidered)}</small>
          )}
        </article>
      ))}
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
    [focusedRef, setFocusedRef] = useState<string | null>(null),
    [focusChip, setFocusChip] = useState<{ index: number; nonce: number } | null>(null),
    [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const stream = useRef<{ close: () => void } | null>(null),
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
      setFocusChip(null);
    setDrafts({});
      setDrafts({});
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
    setFocusChip(null);
    setDrafts({});
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
    setFocusChip(null);
    setDrafts({});
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
                .then(setView)
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
    const ticket = ++requestId.current; // a load still in flight must not overwrite this run
    stream.current?.close();
    setError("");
    setBusy(true);
    setView(null);
    setSelected(null);
    setFocusChip(null);
    setDrafts({});
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
          {busy && (
            <div className="run-status running" role="status">
              <span />
              {phase}
            </div>
          )}
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
                focusChip={focusChip}
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
                            onClick={() => {
                              setSelected(s.id);
                              // On a phone the map sits above the list: bring it into view.
                              if (window.matchMedia("(max-width: 800px)").matches)
                                document
                                  .querySelector(".map-stage")
                                  ?.scrollIntoView({ behavior: "smooth", block: "start" });
                            }}
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
                          .map((f: any, index: number) => ({ f, index }))
                          .filter(({ f }: any) => f.properties.tile_url)
                          .slice(0, 24)
                          .map(({ f, index }: any, i: number) => (
                            <figure key={index}>
                              <button
                                type="button"
                                className="evidence-thumb"
                                aria-label={`Show imagery ${f.properties.node || i + 1} on the map`}
                                onClick={() =>
                                  setFocusChip({ index, nonce: Date.now() })
                                }
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
                    {view.scorecard && (
                      <button
                        className="review-cta"
                        onClick={() => setTab("evaluation")}
                      >
                        <span>
                          <strong>Do you agree with the judges?</strong>
                          Review each rubric question in Evaluation. Your
                          review is kept beside the score and can teach the
                          judges.
                        </span>
                        <Icon name="arrow" size={16} />
                      </button>
                    )}
                  </>
                ) : tab === "evaluation" ? (
                  <>
                    <div className="evaluation-heading">
                      <div>
                        <div className="section-kicker">Quality and trust</div>
                        <h2>Evaluation</h2>
                      </div>
                      <button
                        className="secondary small"
                        disabled={busy}
                        onClick={() => void rejudge()}
                        title="Asks the panel again. Unchanged evidence adds votes to the ones already recorded."
                      >
                        Judge again
                      </button>
                    </div>
                    <div className="score-hero">
                      <strong>
                        {formatScore(view.kpis.score)}
                        {view.kpis.score !== null && <small>/100</small>}
                      </strong>
                      <div>
                        <span>
                          {view.kpis.verdict === "scored"
                            ? `${view.kpis.confidence || "Unknown"} agreement`
                            : view.kpis.verdict}
                        </span>
                        {view.scorecard && (
                          <p>
                            {view.scorecard.pass_count}{" "}
                            {view.scorecard.pass_count === 1 ? "pass" : "passes"}{" "}
                            ·{" "}
                            {
                              Object.values(
                                (Object.values(view.scorecard.votes_all || {})[0] ||
                                  {}) as Record<string, number[]>,
                              ).flat().length
                            }{" "}
                            votes per question
                            {view.scorecard.overall_se > 0 &&
                              ` · ±${formatScore(view.scorecard.overall_se)}`}
                          </p>
                        )}
                        {view.scorecard?.overall_range &&
                          view.scorecard.pass_count > 1 && (
                            <p>
                              Single passes scored{" "}
                              {formatScore(view.scorecard.overall_range[0])}–
                              {formatScore(view.scorecard.overall_range[1])}
                            </p>
                          )}
                      </div>
                    </div>
                    <p className="fine-print">
                      Agreement is how closely the judges agree on the evidence,
                      not a probability that the answer is correct. Judging
                      unchanged evidence again adds votes, so the score settles
                      rather than flips.
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
                        label="Trace"
                        value={
                          view.kpis.trace_integrity ? "Intact" : "Needs review"
                        }
                      />
                    </div>
                    {view.licences?.presentable === false && (
                      <p className="notice">
                        Some source licences need review before sharing these
                        results. See Sources and licences below.
                      </p>
                    )}
                    {view.source_check_note && (
                      <p className="notice">{view.source_check_note}</p>
                    )}
                    {view.kpis.not_scored_cause && (
                      <p className="notice">{view.kpis.not_scored_cause}</p>
                    )}
                    <div className="scorecard-head">
                      <h3 className="section-title">Rubric scorecard</h3>
                      <span className="vote-key" aria-hidden="true">
                        <i className="vote v2" /> yes <i className="vote v1" />{" "}
                        partly <i className="vote v0" /> no
                      </span>
                    </div>
                    {view.scorecard && view.kpis.score !== null && (
                      <p className="fine-print">
                        Open a question to read the judges’ reasons and give
                        your own assessment.
                      </p>
                    )}
                    {view.scorecard?.criteria?.map((c: any) => (
                      <CriterionCard
                        key={c.id}
                        c={c}
                        view={view}
                        draft={drafts[c.id]}
                        reviewable={!!view.scorecard && view.kpis.score !== null}
                        onDraft={(d) =>
                          setDrafts((old) => {
                            const next = { ...old };
                            if (d) next[c.id] = d;
                            else delete next[c.id];
                            return next;
                          })
                        }
                      />
                    ))}
                    <ReviewBar
                      view={view}
                      drafts={drafts}
                      onSaved={() => {
                        setDrafts({});
                        void request<View>(`/api/runs/${view.run.id}`)
                          .then(setView)
                          .catch((e) => setError(e.message));
                      }}
                    />
                    <SavedReviews
                      view={view}
                      busy={busy}
                      onReconsider={(id) => void reconsider(id)}
                    />
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
                    {view.scorecard?.judges?.map((j: any) => {
                      const all = Object.values(
                        view.scorecard.votes_all || {},
                      ).flatMap((v: any) => v[j.key] || []) as number[];
                      const mean = all.length
                        ? (all.reduce((a, b) => a + b, 0) / all.length / 2) * 100
                        : null;
                      return (
                        <div key={j.key} className="judge-line">
                          <div>
                            <strong>{j.key}</strong>
                            <small>
                              {j.family}
                              {j.recused_for ? ` · sitting for ${j.recused_for}` : ""}
                              {j.stood_in_for ? ` · replacing ${j.stood_in_for}` : ""}
                              {j.temperature === null ? " · model’s default sampling" : ""}
                            </small>
                          </div>
                          <span>
                            {j.status === "ok" && mean !== null
                              ? `${formatScore(mean)}/100`
                              : "Unavailable"}
                          </span>
                        </div>
                      );
                    })}
                    {view.scorecard?.passes_dropped > 0 && (
                      <p className="fine-print">
                        {view.scorecard.passes_dropped} slow{" "}
                        {view.scorecard.passes_dropped === 1 ? "pass was" : "passes were"}{" "}
                        left out so the score didn’t wait on it.
                      </p>
                    )}
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
                    <section className="reference-card">
                      <h3 className="section-title">
                        Independent reference check
                      </h3>
                      {view.reference && !view.reference.error ? (
                        <>
                          <p>
                            {view.reference.concept} · {view.reference.place}
                          </p>
                          <div className="mini-stats">
                            <Stat
                              label="Known assets found"
                              value={
                                typeof view.reference.site_recall === "number"
                                  ? `${Math.round(view.reference.site_recall * 100)}%`
                                  : "Not defined"
                              }
                            />
                            <Stat
                              label="Cell precision"
                              value={
                                typeof view.reference.cell_precision ===
                                "number"
                                  ? `${Math.round(view.reference.cell_precision * 100)}%`
                                  : "Not defined"
                              }
                            />
                            <Stat
                              label="Reference assets"
                              value={view.reference.assets ?? "—"}
                            />
                          </div>
                          <p className="fine-print">
                            Reference completeness:{" "}
                            {view.reference.completeness}. Matching uses{" "}
                            {view.reference.cell_m} m cells and the archived
                            any-touch rule; this is separate from the model
                            judges’ score.
                          </p>
                          {view.reference.notes?.map((note: string) => (
                            <p key={note} className="fine-print">
                              {note}
                            </p>
                          ))}
                          <details className="source-details">
                            <summary>Reference source and full metrics</summary>
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
                          </details>
                        </>
                      ) : (
                        <p className="notice">
                          {view.reference?.error ||
                            "No independent reference set is tied to this run. Recall, precision and transfer performance are not established."}
                        </p>
                      )}
                    </section>
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
        <button className="footer-link" onClick={() => setModal(true)}>
          About
        </button>
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
