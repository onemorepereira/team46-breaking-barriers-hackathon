import { useEffect, useRef, useState } from "react";
import { Icon } from "./Icon";
import { request, localTime } from "./api";
export type Reaction = {
  id: string;
  target: string;
  vote: "up" | "down";
  comment: string;
  score: number;
  judged_at: string;
  created_at: string;
  current?: boolean;
};
export function QuickFeedback({
  runId,
  judgedAt,
  target,
  label,
  disabled,
  onSaved,
}: {
  runId: string;
  judgedAt: string;
  target: string;
  label: string;
  disabled: boolean;
  onSaved: (r: Reaction) => void;
}) {
  const [receipt, setReceipt] = useState<Reaction | null>(null),
    [comment, setComment] = useState(""),
    [editing, setEditing] = useState(false),
    [sending, setSending] = useState(false),
    [error, setError] = useState("");
  const mounted = useRef(true),
    input = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  useEffect(() => {
    setReceipt(null);
    setComment("");
    setEditing(false);
    setError("");
  }, [runId, judgedAt]);
  useEffect(() => {
    if (editing) input.current?.focus();
  }, [editing]);
  async function vote(value: "up" | "down") {
    if (receipt?.vote === value) {
      if (value === "down") setEditing(true);
      return;
    }
    setSending(true);
    setError("");
    try {
      const r = await request<Reaction>(`/api/runs/${runId}/reactions`, {
        judged_at: judgedAt,
        target,
        vote: value,
      });
      if (!mounted.current) return;
      setReceipt(r);
      setComment("");
      setEditing(value === "down");
      onSaved(r);
    } catch (e) {
      if (mounted.current) setError((e as Error).message);
    } finally {
      if (mounted.current) setSending(false);
    }
  }
  async function saveComment(e: React.FormEvent) {
    e.preventDefault();
    if (!receipt) return;
    setSending(true);
    setError("");
    try {
      const r = await request<Reaction>(
        `/api/runs/${runId}/reactions/${receipt.id}`,
        { comment },
        undefined,
        "PUT",
      );
      if (!mounted.current) return;
      setReceipt(r);
      setEditing(false);
      onSaved(r);
    } catch (e) {
      if (mounted.current) setError((e as Error).message);
    } finally {
      if (mounted.current) setSending(false);
    }
  }
  return (
    <div
      className={`quick-feedback ${target === "overall" ? "overall-feedback" : ""}`}
    >
      <div className="quick-feedback-row">
        <span>
          {target === "overall" ? "Does this score seem fair?" : "Review score"}
        </span>
        <div
          className="thumb-buttons"
          role="group"
          aria-label={`Human feedback on ${label}`}
        >
          {(["up", "down"] as const).map((v) => (
            <button
              type="button"
              key={v}
              aria-label={`${v === "up" ? "Thumbs up" : "Thumbs down"} on ${label}`}
              aria-pressed={receipt?.vote === v}
              title={
                v === "up"
                  ? "Agree with this score"
                  : "Disagree with this score"
              }
              disabled={disabled || sending}
              onClick={() => void vote(v)}
            >
              <Icon name={v === "up" ? "thumb-up" : "thumb-down"} size={17} />
            </button>
          ))}
        </div>
      </div>
      {receipt && (
        <small className="feedback-saved" role="status">
          {sending ? "Saving…" : "Response recorded. Score unchanged."}
        </small>
      )}
      {editing && (
        <form className="feedback-comment" onSubmit={saveComment}>
          <label>
            What could the evaluation do better? (optional)
            <textarea
              ref={input}
              maxLength={2000}
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="For example: the score missed evidence in step T3."
            />
          </label>
          <div>
            <button className="secondary small" disabled={sending || disabled}>
              Save comment
            </button>
            <button
              className="text-button"
              type="button"
              disabled={sending}
              onClick={() => setEditing(false)}
            >
              Skip comment
            </button>
          </div>
          <small>
            Your thumbs down is already recorded. Comments do not automatically
            change the score.
          </small>
        </form>
      )}
      {error && (
        <small role="alert" className="error-message">
          {error}
        </small>
      )}
    </div>
  );
}
export function FeedbackHistory({ records }: { records: Reaction[] }) {
  return records.length ? (
    <div className="feedback-history">
      {records.map((r) => (
        <div key={r.id}>
          <strong>
            {r.vote === "up" ? "Thumbs up" : "Thumbs down"} ·{" "}
            {r.target.replace(/_/g, " ")} · {r.score}/100
          </strong>
          <small>
            {localTime(r.created_at)}
            {r.current === false ? " · earlier judgement" : ""} · anonymous
            quick response
          </small>
          {r.comment && <p>{r.comment}</p>}
        </div>
      ))}
    </div>
  ) : (
    <p>
      No quick feedback recorded yet. These responses are stored separately from
      detailed rubric reviews.
    </p>
  );
}
