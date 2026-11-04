import { useEffect, useRef, useState } from "react";
import { request, localTime } from "./api";
import { Disclosure } from "./Controls";
type Lesson = { criterion: string; text: string; sources: string[] };
export default function Guidance({ onRun }: { onRun: (id: string) => void }) {
  const [overview, setOverview] = useState<any>(null),
    [version, setVersion] = useState<any>(null),
    [lessons, setLessons] = useState<Lesson[]>([]),
    [by, setBy] = useState(""),
    [reason, setReason] = useState(""),
    [estimate, setEstimate] = useState<any>(null),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [progress, setProgress] = useState(""),
    [dirty, setDirty] = useState(false);
  const cancel = useRef<(() => void) | null>(null),
    selection = useRef(0);
  useEffect(() => {
    void refresh();
    return () => cancel.current?.();
  }, []);
  async function refresh() {
    try {
      setOverview(await request("/api/guidance"));
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function open(n: number) {
    if (dirty && !window.confirm("Discard unsaved lesson edits?")) return;
    const ticket = ++selection.current;
    setError("");
    setEstimate(null);
    try {
      const v = await request<any>(`/api/guidance/${n}`);
      if (ticket !== selection.current) return;
      setVersion(v);
      setLessons(v.lessons || []);
      setDirty(false);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function action(path: string, body: any, method?: "PUT") {
    if (!by.trim() && method !== "PUT") {
      setError("Enter your name so the change has an author.");
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const v = await request<any>(path, body, undefined, method);
      await refresh();
      if (v?.version) {
        setVersion(v);
        setLessons(v.lessons || []);
        setDirty(false);
        setEstimate(null);
      }
      setNotice("Saved. The change is recorded in guidance history.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function preflight() {
    setBusy(true);
    setError("");
    try {
      setEstimate(
        await request(`/api/guidance/${version.version}/evaluate`, {
          confirm: false,
        }),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function evaluate() {
    setError("");
    setBusy(true);
    try {
      const n = version.version;
      await request(`/api/guidance/${n}/evaluate`, { confirm: true });
      let stopped = false,
        cursor = "";
      let timer: ReturnType<typeof setTimeout>;
      cancel.current = () => {
        stopped = true;
        clearTimeout(timer);
      };
      async function poll() {
        if (stopped) return;
        try {
          const data = await request<any>(
            `/api/guidance/${n}/progress${cursor ? "?cursor=" + encodeURIComponent(cursor) : ""}`,
          );
          if (stopped) return;
          cursor = data.cursor;
          for (const e of data.events || []) {
            if (e.type === "evaluating")
              setProgress(
                `${e.done ?? 0} / ${e.total ?? "?"} runs · ${e.stage || "evaluating"}`,
              );
            if (e.type === "evaluated")
              setProgress(e.verdict || "Evaluation recorded");
            if (e.type === "done") {
              stopped = true;
              setBusy(false);
              setProgress(
                "Evaluation completed. Review the report before approving.",
              );
              if (e.error) setError(e.error);
              await refresh();
              const v = await request<any>(`/api/guidance/${n}`);
              setVersion(v);
            }
          }
          if (!stopped) timer = setTimeout(poll, 2000);
        } catch (e) {
          setError((e as Error).message);
          setBusy(false);
        }
      }
      void poll();
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }
  function edit(i: number, key: keyof Lesson, value: any) {
    setLessons((old) =>
      old.map((l, j) => (j === i ? { ...l, [key]: value } : l)),
    );
    setDirty(true);
    setEstimate(null);
  }
  const canApprove = version && version.status !== "active" && !dirty;
  return (
    <main className="guidance-page">
      <div className="page-heading">
        <div>
          <span className="section-kicker">
            Human feedback → better judging
          </span>
          <h1>Judge guidance</h1>
          <p>
            Turn reviewed disagreements into versioned lessons. Test them before
            changing how future runs are judged.
          </p>
        </div>
        <button
          className="secondary"
          onClick={() => void refresh()}
          disabled={busy}
        >
          Refresh
        </button>
      </div>
      {error && (
        <p role="alert" className="error-message">
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className="success-message">
          {notice}
        </p>
      )}
      {!overview ? (
        <p role="status">Loading guidance…</p>
      ) : (
        <>
          <div className="guidance-summary">
            <div>
              <span className="section-kicker">Active guidance</span>
              <h2>
                {overview.active?.version != null
                  ? `Version ${overview.active.version}`
                  : "No active version"}
              </h2>
              <p>
                {overview.rubric?.title} · {overview.rubric?.id} v
                {overview.rubric?.version}
              </p>
              {overview.enabled === false && (
                <p className="notice">
                  Guidance is disabled in deployment configuration. Approving a
                  version does not override that setting.
                </p>
              )}
            </div>
            <div>
              <b>{overview.reviewed_runs ?? 0} reviewed runs</b>
              <p>
                {overview.reviews ?? 0} reviews · {overview.held_out_runs ?? 0}{" "}
                held out
              </p>
              <p>
                At least {overview.min_held_out ?? 5} held-out runs are required
                for an evidence-backed evaluation.
              </p>
            </div>
          </div>
          <div className="guidance-identity">
            <label>
              Your name
              <input
                value={by}
                onChange={(e) => setBy(e.target.value)}
                placeholder="Name recorded with changes"
                maxLength={100}
              />
            </label>
            <label>
              Reason / approval note
              <input
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                maxLength={2000}
              />
            </label>
          </div>
          <div className="export-actions">
            <button
              className="primary"
              disabled={busy || !by.trim() || dirty}
              onClick={() => void action("/api/guidance", { by: by.trim() })}
            >
              Propose lessons from reviews
            </button>
            <button
              className="secondary"
              disabled={busy || !overview.active || !by.trim()}
              onClick={() =>
                void action("/api/guidance/off", { by: by.trim(), reason })
              }
            >
              Switch guidance off
            </button>
          </div>
          <p className="fine-print">
            Proposing and evaluating call the configured models. Drafts do not
            change judging until approved. Retired versions can be approved to
            roll back.
          </p>
          <section className="guidance-versions">
            <h2>Versions</h2>
            {!overview.versions?.length ? (
              <p>
                No versions yet. Review a run and record a reasoned disagreement
                to begin.
              </p>
            ) : (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Version</th>
                      <th>Status</th>
                      <th>Lessons</th>
                      <th>Evaluation</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {overview.versions.map((v: any) => (
                      <tr key={v.version}>
                        <td>
                          v{v.version}
                          <small>
                            {localTime(v.created_at)} · {v.created_by}
                          </small>
                        </td>
                        <td>{v.status}</td>
                        <td>{v.lessons}</td>
                        <td>
                          {v.latest_evaluation?.verdict || "Not evaluated"}
                          {v.evaluation_current === false ? " · stale" : ""}
                        </td>
                        <td>
                          <button
                            className="secondary"
                            disabled={busy}
                            onClick={() => void open(v.version)}
                          >
                            Open v{v.version}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
          {version && (
            <section className="guidance-editor">
              <div className="evaluation-heading">
                <h2>
                  Version {version.version} · {version.status}
                </h2>
                {dirty && (
                  <span className="status-tag unverified">Unsaved edits</span>
                )}
              </div>
              <p>
                Created {localTime(version.created_at)} by {version.created_by}.{" "}
                {version.status !== "draft"
                  ? "Approved versions are read-only. Propose a new version to change lessons."
                  : ""}
              </p>
              {lessons.map((lesson, i) => (
                <div className="lesson-editor" key={i}>
                  <label>
                    Lesson {i + 1} criterion
                    <select
                      disabled={version.status !== "draft" || busy}
                      value={lesson.criterion}
                      onChange={(e) => edit(i, "criterion", e.target.value)}
                    >
                      {overview.criteria?.map((c: any) => (
                        <option key={c.id} value={c.id}>
                          {c.question || c.id}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Lesson text
                    <textarea
                      maxLength={400}
                      value={lesson.text}
                      disabled={version.status !== "draft" || busy}
                      onChange={(e) => edit(i, "text", e.target.value)}
                    />
                  </label>
                  <small>
                    {lesson.text.length}/400 characters. Write a general lesson,
                    without run or step IDs.
                  </small>
                  <label>
                    Source review IDs
                    <input
                      value={lesson.sources.join(", ")}
                      disabled={version.status !== "draft" || busy}
                      onChange={(e) =>
                        edit(
                          i,
                          "sources",
                          e.target.value.split(/[\s,]+/).filter(Boolean),
                        )
                      }
                    />
                  </label>
                  <div>
                    {lesson.sources.map((s) =>
                      version.source_runs?.[s] ? (
                        <button
                          key={s}
                          className="text-button"
                          onClick={() => onRun(version.source_runs[s])}
                        >
                          Open source {s}
                        </button>
                      ) : (
                        <small key={s}>{s}</small>
                      ),
                    )}
                  </div>
                  {version.status === "draft" && (
                    <button
                      className="secondary"
                      disabled={busy}
                      onClick={() => {
                        setLessons((old) => old.filter((_, j) => i !== j));
                        setDirty(true);
                        setEstimate(null);
                      }}
                    >
                      Remove lesson {i + 1}
                    </button>
                  )}
                </div>
              ))}
              <div className="export-actions">
                {version.status === "draft" && (
                  <>
                    <button
                      className="secondary"
                      disabled={busy}
                      onClick={() => {
                        setLessons((old) => [
                          ...old,
                          {
                            criterion: overview.criteria?.[0]?.id || "",
                            text: "",
                            sources: [],
                          },
                        ]);
                        setDirty(true);
                        setEstimate(null);
                      }}
                    >
                      Add lesson
                    </button>
                    <button
                      className="primary"
                      disabled={busy || !dirty}
                      onClick={() =>
                        void action(
                          `/api/guidance/${version.version}`,
                          { lessons },
                          "PUT",
                        )
                      }
                    >
                      Save draft
                    </button>
                  </>
                )}
                <button
                  className="secondary"
                  disabled={busy || dirty}
                  onClick={() => void preflight()}
                >
                  Estimate evaluation
                </button>
                <button
                  className="primary"
                  disabled={
                    busy ||
                    !canApprove ||
                    !by.trim() ||
                    (!reason.trim() &&
                      !(
                        version.evaluation_current &&
                        version.latest_evaluation?.verdict === "adopt"
                      ))
                  }
                  onClick={() =>
                    void action(`/api/guidance/${version.version}/approve`, {
                      by: by.trim(),
                      reason,
                    })
                  }
                >
                  {version.status === "retired"
                    ? "Roll back to this version"
                    : "Approve for future judging"}
                </button>
              </div>
              {estimate && (
                <div className="notice">
                  <strong>Evaluation estimate — no model calls made yet</strong>
                  <pre>{JSON.stringify(estimate, null, 2)}</pre>
                  <button
                    className="primary"
                    disabled={busy}
                    onClick={() => void evaluate()}
                  >
                    Confirm and run evaluation
                  </button>
                </div>
              )}
              {progress && <p role="status">{progress}</p>}
              <Disclosure id="guidance-evaluations" title="Evaluation reports">
                {version.evaluations?.length ? (
                  version.evaluations.map((e: any, i: number) => (
                    <pre key={i}>{JSON.stringify(e, null, 2)}</pre>
                  ))
                ) : (
                  <p>No evaluation reports yet.</p>
                )}
              </Disclosure>
            </section>
          )}
          <Disclosure
            id="guidance-agreement"
            title="Agreement with human reviewers"
          >
            <p>
              Agreement is measured on reviewed judgements, not on independent
              asset truth. α is Krippendorff’s alpha; MAD is mean absolute
              difference.
            </p>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Guidance</th>
                    <th>α (95% CI)</th>
                    <th>MAD</th>
                    <th>Exact match</th>
                    <th>Runs</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(overview.agreement?.by_guidance || {}).map(
                    ([key, a]: [string, any]) => (
                      <tr key={key}>
                        <td>{key}</td>
                        <td>
                          {a.alpha ?? "—"}{" "}
                          {a.ci95 ? `(${a.ci95.join(" – ")})` : ""}
                        </td>
                        <td>{a.mad ?? "—"}</td>
                        <td>
                          {typeof a.exact === "number"
                            ? `${Math.round(a.exact * 100)}%`
                            : "—"}
                        </td>
                        <td>{a.runs}</td>
                      </tr>
                    ),
                  )}
                </tbody>
              </table>
            </div>
          </Disclosure>
          <Disclosure
            id="guidance-log"
            title="Approval, rollback and switch-off history"
          >
            {overview.log?.length ? (
              overview.log.map((e: any, i: number) => (
                <div className="judge-line" key={i}>
                  <span>
                    {e.action} · v{e.version ?? "none"} · {e.by}
                    <small>{e.reason}</small>
                  </span>
                  <span>{localTime(e.at)}</span>
                </div>
              ))
            ) : (
              <p>No changes recorded.</p>
            )}
          </Disclosure>
        </>
      )}
    </main>
  );
}
