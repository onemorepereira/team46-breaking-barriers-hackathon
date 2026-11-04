import { useMemo } from "react";
import { type View } from "./api";
import { Disclosure } from "./Controls";
import { Text } from "./UI";
import { summarise } from "./summary";
export default function RunSummary({
  view,
  onExpand,
}: {
  view: View;
  onExpand: () => void;
}) {
  const s = useMemo(() => summarise(view), [view]);
  return (
    <section
      className="live-summary structured-summary"
      aria-label="High-level run summary"
    >
      <div className="summary-top">
        <span className="section-kicker">Summary · at a glance</span>
        <button
          className="secondary small"
          onClick={onExpand}
          aria-label="Expand summary in the right panel"
        >
          Expand summary →
        </button>
      </div>
      <h2>{s.takeaway}</h2>
      <div className="summary-glance">
        <p>
          <b>Found</b> {s.found}
        </p>
        <p>
          <b>Needs review</b> {s.shortGap}
        </p>
      </div>
    </section>
  );
}
export function DetailedSummary({ view }: { view: View }) {
  const s = useMemo(() => summarise(view), [view]);
  return (
    <div className="detailed-summary">
      <span className="section-kicker">
        Summary · evidence, not just a score
      </span>
      <h2>{s.takeaway}</h2>
      <section>
        <h3>What it found</h3>
        <p>{s.found}</p>
      </section>
      <section>
        <h3>What’s missing or uncertain</h3>
        <p>{s.missing}</p>
      </section>
      <section>
        <h3>How it searched</h3>
        <p>{s.method}</p>
      </section>
      <section>
        <h3>What to check next</h3>
        <ol>
          {s.next.map((text: string) => (
            <li key={text}>{text}</li>
          ))}
        </ol>
      </section>
      <Disclosure id="summary-detail" title="More detail from the saved run">
        <p>Original request: {view.run.prompt}</p>
        {view.narrative ? (
          <Text value={view.narrative} />
        ) : (
          <p>
            No additional generated narrative is saved. Actions contains the
            recorded steps.
          </p>
        )}
      </Disclosure>
    </div>
  );
}
