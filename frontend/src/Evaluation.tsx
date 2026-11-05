import { useEffect, useState, type ReactNode } from "react";
import { Disclosure } from "./Controls";
import { QuickFeedback, FeedbackHistory, type Reaction } from "./QuickFeedback";
import { Stat } from "./UI";
import {
  endpoint,
  formatScore,
  sectionIssues,
  weakCriterion,
  money,
  localTime,
  request,
  type View,
} from "./api";
import { readPreference, scoreLabel, writePreference } from "./preferences";
export default function Evaluation({
  view,
  busy,
  onRejudge,
  onExport,
  onPrevious,
  reviewer,
}: {
  view: View;
  busy: boolean;
  onRejudge: () => void;
  onExport: () => void;
  onPrevious: (at: string) => void;
  reviewer: ReactNode;
}) {
  const card = view.scorecard,
    k = view.kpis,
    reference = view.reference;
  // Issue badges and the "only sections with issues" filter (docs/evaluation-issues).
  const issues = sectionIssues(view),
    totalIssues = Object.values(issues).reduce((a, b) => a + b, 0);
  const [issuesOnly, setIssuesOnly] = useState<boolean>(
    () => readPreference<boolean>("evaluation.issuesOnly", false) === true,
  );
  const filtering = issuesOnly && totalIssues > 0;
  const show = (id: string) => !filtering || (issues[id] || 0) > 0;
  const [reactions, setReactions] = useState<Reaction[]>([]),
    [reactionError, setReactionError] = useState("");
  useEffect(() => {
    let current = true;
    setReactions([]);
    setReactionError("");
    request<{ reactions: Reaction[] }>(`/api/runs/${view.run.id}/reactions`)
      .then((data) => {
        if (current) setReactions(data.reactions);
      })
      .catch((e) => {
        if (current) setReactionError(e.message);
      });
    return () => {
      current = false;
    };
  }, [view.run.id, card?.judged_at]);
  function quick(target: string, label: string, score: unknown) {
    return (
      <QuickFeedback
        key={`${view.run.id}-${card?.judged_at}-${target}`}
        runId={view.run.id}
        judgedAt={card?.judged_at}
        target={target}
        label={label}
        disabled={
          busy ||
          typeof score !== "number" ||
          typeof k.score !== "number" ||
          !card?.judged_at
        }
        onSaved={(r) =>
          setReactions((old) => [
            { ...r, current: r.judged_at === card?.judged_at },
            ...old.filter((x) => x.id !== r.id),
          ])
        }
      />
    );
  }
  const pct = (v: any) =>
    typeof v === "number" ? `${Math.round(v * 100)}%` : "Not defined";
  return (
    <>
      <div className="section-kicker">Evaluation</div>
      <div className="evaluation-heading">
        <h2>Evaluate the result</h2>
        <button className="secondary small" disabled={busy} onClick={onRejudge}>
          Re-judge
        </button>
      </div>
      <div className="score-hero">
        <strong>
          {formatScore(k.score)}
          {typeof k.score === "number" && <small>/100</small>}
        </strong>
        <div>
          <span>{scoreLabel(k.score)}</span>
          <p>{k.verdict}</p>
          {card?.pass_count > 0 && (
            <p>
              {card.pass_count} {card.pass_count === 1 ? "pass" : "passes"} ·{" "}
              {votesPerQuestion(card)} votes per question
              {card.overall_se > 0 && ` · ±${formatScore(card.overall_se)}`}
            </p>
          )}
          {card?.pass_count > 1 && card.overall_range && (
            <p>
              Single passes scored {formatScore(card.overall_range[0])}–
              {formatScore(card.overall_range[1])}
            </p>
          )}
        </div>
      </div>
      {quick("overall", "overall evaluation score", k.score)}
      <p className="fine-print">
        Assesses how the agent worked and answered your request. This is not a
        probability of correctness or a detection-accuracy measurement.
      </p>
      {busy && (
        <p role="status" className="notice">
          Judging is in progress. The previous result remains visible until the
          new judgement is saved.
        </p>
      )}
      {view.licences?.presentable === false && (
        <p className="notice">
          Source licences need review before sharing. See Sources and licences
          below.
        </p>
      )}
      {k.not_scored_cause && (
        <p role="alert" className="notice">
          {k.not_scored_cause}
        </p>
      )}
      <label className={`issue-filter ${totalIssues ? "" : "is-clean"}`}>
        <input
          type="checkbox"
          checked={filtering}
          disabled={!totalIssues}
          onChange={(e) => {
            setIssuesOnly(e.target.checked);
            writePreference("evaluation.issuesOnly", e.target.checked);
          }}
        />
        {totalIssues
          ? `Show only sections with issues (${totalIssues})`
          : "Nothing needs attention"}
      </label>
      <Disclosure
        id="detailed-human-review"
        hidden={!show("detailed-human-review")}
        badge={issues["detailed-human-review"] || undefined}
        title="Detailed human review and reconsideration"
      >
        {reviewer}
      </Disclosure>
      <Disclosure
        id="score-method"
        hidden={!show("score-method")}
        badge={issues["score-method"] || undefined}
        title="What this score means"
      >
        <p>
          Each judged question averages every judge’s rubric rating across all
          passes (three per judging), normalised to 100. Judging the same
          evidence again adds votes, so the score settles rather than flips.
          Workflow and output are the averages of their applicable questions and
          measured checks; the overall result averages those two dimensions.
          Required spatial conditions can cap the output dimension. Fatal gates
          force zero; missing valid judgements or required extraction can leave
          it not scored.
        </p>
        <p>
          Judge agreement and trace reliability are reported separately below.
          Matching source text alone does not prove an asset exists.
        </p>
        <p>
          Rubric: {card?.rubric_title || card?.rubric?.id || "Not recorded"} v
          {card?.rubric?.version ?? "—"} · Judged {localTime(card?.judged_at)}
        </p>
      </Disclosure>
      <Disclosure
        id="score-breakdown"
        hidden={!show("score-breakdown")}
        badge={issues["score-breakdown"] || undefined}
        title="Workflow and output breakdown"
      >
        <div className="mini-stats">
          <div>
            <Stat label="Workflow" value={formatScore(k.workflow)} />
            {quick("workflow", "workflow score", k.workflow)}
          </div>
          <div>
            <Stat label="Output" value={formatScore(k.output)} />
            {quick("output", "output score", k.output)}
          </div>
          <Stat
            label="Trace integrity"
            value={k.trace_integrity ? "Intact" : "Needs review"}
          />
        </div>
        {view.source_check_note && (
          <p className="notice">{view.source_check_note}</p>
        )}
      </Disclosure>
      <Disclosure
        id="rubric"
        hidden={!show("rubric")}
        badge={issues["rubric"] || undefined}
        title="Rubric scorecard"
      >
        {card?.criteria?.map((c: any) => (
          <Disclosure
            key={c.id}
            id={`criterion-${c.id}`}
            hidden={filtering && !weakCriterion(c)}
            badge={weakCriterion(c) ? "dot" : undefined}
            title={`${c.plain || c.question} · ${formatScore(c.score)}${c.score !== null ? "/100" : ""}`}
            accessory={quick(c.id, c.plain || c.question, c.score)}
          >
            <p>{c.question}</p>
            <p>
              {c.kind === "measured"
                ? "Measured by code"
                : `Judged · ${c.dimension}`}
              {c.value ? ` · ${c.value}` : ""}
            </p>
            {c.gated && (
              <p className="notice">
                A fatal gate set this output score to zero.
              </p>
            )}
            <div className="score-bar">
              <span style={{ width: `${c.score ?? 0}%` }} />
            </div>
            {c.kind === "judged" && <Votes votes={card.votes_all?.[c.id]} />}
            {c.original_median != null && (
              <p>Original panel rating: {c.original_median}</p>
            )}
            {c.human != null && (
              <p>
                Human reviewer rating: {c.human} ·{" "}
                {c.human_reviewers?.join(", ")}
              </p>
            )}
            {Object.entries(card.anchors?.[c.id] || {}).map(([s, t]) => (
              <p className="anchor" key={s}>
                <b>{s}</b> {String(t)}
              </p>
            ))}
            {card.judges?.map((j: any) => {
              const jc = j.criteria?.find((x: any) => x.id === c.id);
              return jc ? (
                <div className="judge-reason" key={j.key}>
                  <strong>
                    {j.key} · rubric rating {jc.score}
                    {card.pass_count > 1 ? " (pass 1)" : ""}
                  </strong>
                  <p>{jc.rationale}</p>
                  <small>
                    Evidence: {jc.refs?.join(" · ") || "No references cited"}
                  </small>
                  {jc.response && <p>{jc.response}</p>}
                </div>
              ) : null;
            })}
          </Disclosure>
        ))}
      </Disclosure>
      <Disclosure
        id="conditions"
        hidden={!show("conditions")}
        badge={issues["conditions"] || undefined}
        title="Every condition in your request"
      >
        {view.conditions ? (
          <>
            <p>
              {view.conditions.supported}/{view.conditions.total} code-checked
              cells supported. Other conditions still require judge or human
              review.
            </p>
            {view.conditions.status === "not_checked" && (
              <p className="notice">
                Request conditions were not checked for this run.
              </p>
            )}
            {view.conditions.error && (
              <p className="error-message">{view.conditions.error}</p>
            )}
            {view.conditions.rows?.map((row: any, i: number) => (
              <div className="condition-row" key={i}>
                <strong>{row.claim}</strong>
                {row.cells.map((cell: any) => (
                  <div key={cell.condition_id}>
                    <span className={`status-tag ${cell.status}`}>
                      {cell.status === "supported"
                        ? "✓ supported"
                        : cell.status === "contradicted"
                          ? "× contradicted"
                          : "? unverified"}
                    </span>
                    <b>
                      {view.conditions.conditions.find(
                        (c: any) => c.id === cell.condition_id,
                      )?.text || cell.condition_id}
                    </b>
                    <p>{cell.reason}</p>
                    <small>{cell.refs?.join(" · ")}</small>
                  </div>
                ))}
              </div>
            ))}
          </>
        ) : (
          <p>
            No request-condition matrix was saved. Compliance is not
            established.
          </p>
        )}
      </Disclosure>
      <Disclosure
        id="judges"
        hidden={!show("judges")}
        badge={issues["judges"] || undefined}
        title="Judge panel, agreement and evaluation reliability"
      >
        <div className="mini-stats">
          <Stat label="Within-one-point agreement" value={pct(k.within_one)} />
          <Stat
            label="Mean absolute difference"
            value={k.mad ?? "Not recorded"}
          />
          <Stat
            label="Evaluation reliability"
            value={k.confidence || "Not judged"}
          />
        </div>
        <p>
          Agreement compares the judges’ rubric ratings. Reliability also
          considers trace integrity, missing judges, fatal gates and missing
          condition evidence. Neither establishes real-world accuracy.
        </p>
        <ul>
          {k.confidence_reasons?.map((r: string) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
        {card?.passes_dropped > 0 && (
          <p className="fine-print">
            {card.passes_dropped} slow{" "}
            {card.passes_dropped === 1 ? "pass was" : "passes were"} left out so
            the score didn’t wait on it.
          </p>
        )}
        {card?.judges?.map((j: any) => (
          <Disclosure
            id={`judge-${j.key}`}
            title={`${j.key} · ${j.family} · ${j.status === "ok" ? formatScore(judgeMean(card, j.key) ?? j.score) + "/100" : "Unavailable"}`}
            key={j.key}
          >
            <p>{j.model_id}</p>
            <p>
              {j.recused_for ? `Recused for ${j.recused_for}. ` : ""}
              {j.stood_in_for ? `Replacing ${j.stood_in_for}. ` : ""}
            </p>
            <p>
              Cost: {money(j.cost_usd)} · Time: {j.latency_s ?? "—"} seconds
              {card.pass_count > 1 ? " (pass 1)" : ""}
            </p>
            {j.temperature === null && (
              <p>
                This model rejects temperature 0 on Bedrock, so it judged with
                its default sampling.
              </p>
            )}
            <p>{j.verdict}</p>
            {j.error && <p className="error-message">{j.error}</p>}
          </Disclosure>
        ))}
      </Disclosure>
      <Disclosure
        id="failures"
        hidden={!show("failures")}
        badge={issues["failures"] || undefined}
        title="Failures, retries and evidence gaps"
      >
        <div className="mini-stats">
          <Stat label="Tool errors" value={k.errors ?? 0} />
          <Stat label="Retries" value={k.retries ?? 0} />
          <Stat label="Repeated calls" value={k.repeats ?? 0} />
        </div>
        {card?.gates?.map((g: any) => (
          <p className="notice" key={g.id}>
            {g.reason}
          </p>
        ))}
        {card?.failure_modes?.length ? (
          card.failure_modes.map((f: any) => (
            <p key={f.id}>
              <b>{f.id.replaceAll("_", " ")}</b>: {f.meaning} ({f.votes}/{f.of}{" "}
              judges)
            </p>
          ))
        ) : (
          <p>
            No failure mode was flagged by the panel majority. This is not a
            guarantee of correctness.
          </p>
        )}
        {view.trouble_spots?.map((t: any, i: number) => (
          <pre key={i}>
            {typeof t === "string" ? t : JSON.stringify(t, null, 2)}
          </pre>
        ))}
      </Disclosure>
      <Disclosure
        id="cost"
        hidden={!show("cost")}
        badge={issues["cost"] || undefined}
        title="Cost, usage and review effort"
      >
        <div className="mini-stats">
          <Stat label="Agent estimate" value={money(k.agent_cost_usd)} />
          <Stat label="Judge estimate" value={money(k.judging_cost_usd)} />
          <Stat
            label="Agent runtime"
            value={k.runtime_s != null ? `${Math.round(k.runtime_s)}s` : "—"}
          />
          <Stat
            label="Input tokens"
            value={k.tokens_in?.toLocaleString() ?? "—"}
          />
          <Stat
            label="Output tokens"
            value={k.tokens_out?.toLocaleString() ?? "—"}
          />
          <Stat
            label="Model / tool calls"
            value={`${k.model_calls ?? 0} / ${k.tool_calls ?? 0}`}
          />
        </div>
        <p>
          Token-based estimates, not a full AWS bill. Analyst time and imagery
          procurement are not measured unless explicitly recorded.
        </p>
      </Disclosure>
      <Disclosure
        id="reference"
        hidden={!show("reference")}
        badge={issues["reference"] || undefined}
        title="Independent reference benchmark"
      >
        {reference && !reference.error ? (
          <>
            <p>
              {reference.concept} · {reference.place}
            </p>
            <div className="mini-stats">
              <Stat label="Site recall" value={pct(reference.site_recall)} />
              <Stat
                label="Cell precision"
                value={pct(reference.cell_precision)}
              />
              <Stat
                label="Count ratio"
                value={reference.count_ratio ?? "Not defined"}
              />
              <Stat label="Lift" value={reference.lift ?? "Not defined"} />
              <Stat
                label="Found / reference assets"
                value={`${reference.found?.length ?? 0}/${reference.assets ?? "—"}`}
              />
              <Stat
                label="Distinct predicted sites"
                value={reference.sites ?? "—"}
              />
            </div>
            {reference.ranking && <Ranking rk={reference.ranking} />}
            <p>
              {reference.completeness} reference · {reference.cell_m} m cells ·
              any-touch matching. Incomplete references cannot establish recall.
            </p>
            {reference.stale && (
              <p className="notice">
                The repository reference changed after this run. Metrics use the
                archived snapshot.
              </p>
            )}
            <p>
              Source: {reference.source?.name || "See full record"} · Licence:{" "}
              {reference.licence?.name || "See full record"}
            </p>
            {reference.notes?.map((n: string) => (
              <p key={n}>{n}</p>
            ))}
            {reference.missed?.length > 0 && (
              <p>Missed reference IDs: {reference.missed.join(", ")}</p>
            )}
            <p>
              Reference assets and false-alarm cells are available in Map
              overlays.
            </p>
            <Disclosure
              id="reference-record"
              title="Full reference and matching record"
            >
              <pre>
                {JSON.stringify(
                  Object.fromEntries(
                    Object.entries(reference).filter(
                      ([k]) => !["features", "found", "missed"].includes(k),
                    ),
                  ),
                  null,
                  2,
                )}
              </pre>
            </Disclosure>
          </>
        ) : (
          <p>
            {reference?.error ||
              "No independent reference is tied to this run. Precision, recall and transfer performance are not established."}
          </p>
        )}
      </Disclosure>
      <Disclosure
        id="licences"
        hidden={!show("licences")}
        badge={issues["licences"] || undefined}
        title="Sources, licences and presentation limits"
      >
        <p>
          {view.licences?.presentable === true
            ? "No recorded licence blockers"
            : view.licences?.presentable === false
              ? "Check the following sources before sharing"
              : "Licence status not recorded"}
        </p>
        {view.licences?.items?.map((s: any, i: number) => (
          <div className="licence-list" key={i}>
            <strong>{s.name}</strong>
            <p>
              {s.provider} · {s.role}: {s.used_as}
            </p>
            <p>{s.licence}</p>
            <p>{s.attribution}</p>
            <p>
              {s.presentable === true
                ? "✓ Recorded as presentable"
                : "? Check terms before sharing"}
            </p>
            {/^https?:\/\//.test(s.url || "") && (
              <a target="_blank" rel="noreferrer" href={s.url}>
                Read source and terms
              </a>
            )}
            <small>{s.fact_source}</small>
          </div>
        ))}
      </Disclosure>
      <Disclosure
        id="revisions"
        hidden={!show("revisions")}
        badge={issues["revisions"] || undefined}
        title="Human revisions and earlier judgement"
      >
        {card?.revision ? (
          <>
            <p>
              Revised after review by {card.revision.reviewer} ·{" "}
              {localTime(card.revision.at)}
            </p>
            <button
              className="secondary"
              onClick={() => onPrevious(card.revision.previous)}
            >
              View original judgement
            </button>
          </>
        ) : (
          <p>
            No human-review revision is recorded for this judgement. Re-judging
            also keeps earlier judgements in the archive.
          </p>
        )}
        {card?.guidance_error && (
          <p className="notice">Guidance unavailable: {card.guidance_error}</p>
        )}
        <p>
          Guidance used:{" "}
          {card?.guidance ? `Version ${card.guidance.version}` : "None"}
        </p>
        {card?.guidance?.lessons?.map((l: any, i: number) => (
          <p key={i}>
            {l.criterion}: {l.text}
          </p>
        ))}
      </Disclosure>
      <Disclosure
        id="quick-feedback-records"
        hidden={!show("quick-feedback-records")}
        badge={issues["quick-feedback-records"] || undefined}
        title={`Recorded score feedback${reactions.length ? ` · ${reactions.length}` : ""}`}
      >
        {reactionError ? (
          <p role="alert" className="error-message">
            {reactionError}
          </p>
        ) : (
          <FeedbackHistory records={reactions} />
        )}
        <p className="fine-print">
          Quick responses do not set human rubric scores, feed guidance training
          or request a re-judge. Use detailed human review to suggest a scored
          correction.
        </p>
      </Disclosure>
      <Disclosure
        id="exports"
        hidden={!show("exports")}
        badge={issues["exports"] || undefined}
        title="Reports and evidence exports"
      >
        <div className="export-actions">
          <a
            className="secondary"
            href={endpoint(`/reports/${view.run.id}`)}
            target="_blank"
            rel="noreferrer"
          >
            Open static report
          </a>
          <button className="secondary" onClick={onExport}>
            Export evidence JSON
          </button>
        </div>
      </Disclosure>
    </>
  );
}

// Every judge's vote on a question across all passes (docs/judging-stability).
function Votes({ votes }: { votes?: Record<string, number[]> }) {
  if (!votes) return null;
  return (
    <div className="votes" aria-label="Judge ratings, every pass">
      {Object.entries(votes).map(([judge, vs]) => (
        <span key={judge} className="vote-group">
          <span className="vote-judge">{judge}</span>
          {vs.map((v, i) => (
            <i key={i} className={`vote v${v}`} title={`${judge}: ${v}`} />
          ))}
          <span className="sr-only">{vs.join(", ")}</span>
        </span>
      ))}
    </div>
  );
}
function votesPerQuestion(card: any): number {
  const first = Object.values(card?.votes_all || {})[0] as
    | Record<string, number[]>
    | undefined;
  return first ? Object.values(first).flat().length : 0;
}
function judgeMean(card: any, key: string): number | null {
  const all = Object.values(card?.votes_all || {}).flatMap(
    (v: any) => v[key] || [],
  ) as number[];
  return all.length
    ? (all.reduce((a, b) => a + b, 0) / all.length / 2) * 100
    : null;
}

// Ranking metrics over the run's ranked candidates (docs/ranking-metrics).
function effortText(e: any, random: number | undefined): string {
  if (!e) return "Not defined";
  return e.cells != null
    ? `${e.cells.toLocaleString("en-US")} cells (random ≈ ${random != null ? random.toLocaleString("en-US") : "—"})`
    : `Not reached (${Math.round((e.reached ?? 0) * 100)}% after ${e.after} cells)`;
}
function Ranking({ rk }: { rk: any }) {
  const num = (v: any) => (typeof v === "number" ? String(v) : "Not defined");
  return (
    <>
      <p>
        <b>Ranking</b> · {rk.candidates} ranked cells: the answer's sites first,
        then each LGND search's results by similarity, searches interleaved.
      </p>
      <div className="mini-stats">
        <Stat label={`Recall@k (k = ${rk.k})`} value={num(rk.recall_at_k)} />
        <Stat label="AUROC" value={num(rk.auroc)} />
        <Stat label="AP" value={num(rk.ap)} />
        {["50", "80", "90"].map((p) => (
          <Stat
            key={p}
            label={`Cells to ${p}% of assets`}
            value={effortText(rk.effort?.[p], rk.random_effort?.[p])}
          />
        ))}
      </div>
      {rk.notes?.map((n: string) => (
        <p key={n} className="fine-print">
          {n}
        </p>
      ))}
    </>
  );
}
