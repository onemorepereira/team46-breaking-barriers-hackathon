import { candidatesOf, type View } from "./api.ts";
export function summarise(view: View) {
  const k = view.kpis,
    sites = candidatesOf(view),
    spatial = view.conditions;
  const unsupported =
    spatial?.rows
      ?.flatMap((r: any) => r.cells || [])
      .filter((c: any) => c.status !== "supported").length || 0;
  const tools = [
    ...new Set(
      view.timeline
        .filter((s: any) => s.kind === "tool")
        .map((s: any) => s.title || s.tool || "recorded tool"),
    ),
  ] as string[];
  const notScored = k.verdict === "not scored",
    failed = k.verdict === "FAILED";
  const place = view.run.area ? ` in ${view.run.area}` : "";
  const found = sites.length
    ? `The agent reported ${sites.length} distinct location${sites.length === 1 ? "" : "s"}${place}. ${k.claims_matched ?? 0}/${k.claims_total ?? 0} declared values matched their cited tool results.`
    : `No distinct coordinate locations were listed${place}. ${view.final_answer ? "An answer was saved; inspect Findings for its conclusions." : "No usable final answer was saved."}`;
  const gaps: string[] = [];
  if (notScored)
    gaps.push(
      k.not_scored_cause || "The evaluation could not produce a score.",
    );
  if (failed) gaps.push("A fatal gate prevented a usable answer.");
  if (unsupported)
    gaps.push(
      `${unsupported} request-condition checks still need review or have contradictory evidence.`,
    );
  if (k.claims_total > k.claims_matched)
    gaps.push(
      `${k.claims_total - k.claims_matched} declared values could not be matched to their cited sources.`,
    );
  if (k.claims_located > k.claims_inside)
    gaps.push(
      `${k.claims_located - k.claims_inside} location ${k.claims_located - k.claims_inside === 1 ? "entry is" : "entries are"} outside the requested area.`,
    );
  if (!view.reference || view.reference.error)
    gaps.push(
      "No independent reference set is attached, so accuracy and completeness are not established.",
    );
  if (view.licences?.presentable === false)
    gaps.push("Some source licences need review before sharing.");
  const method = tools.length
    ? `${k.tool_calls ?? tools.length} tool ${k.tool_calls === 1 ? "call" : "calls"} and ${k.model_calls ?? 0} model ${k.model_calls === 1 ? "call" : "calls"} were recorded${k.runtime_s != null ? ` over ${Math.round(k.runtime_s)} seconds` : ""}. Tools: ${tools.slice(0, 3).join("; ")}${tools.length > 3 ? "; more in Actions" : ""}.`
    : "No completed tool calls are recorded. See Actions for errors or partial work.";
  const next = (
    view.explanation?.check_by_hand?.length
      ? view.explanation.check_by_hand
      : [
          "Check the evidence and a sample of sites against an independent source.",
        ]
  ).slice(0, 3);
  const takeaway = notScored
    ? "This run could not be fully evaluated."
    : failed
      ? "This run did not deliver a usable result."
      : sites.length
        ? `${sites.length} candidate location${sites.length === 1 ? "" : "s"} found${place}; review the evidence before using them.`
        : "The agent returned an answer to review; no coordinate sites were identified.";
  return {
    takeaway,
    found,
    shortGap:
      gaps[0] ||
      "No automatic gap was flagged; independently verify before using the result.",
    missing:
      gaps.slice(0, 3).join(" ") ||
      "No automatic gap was flagged. Tool-text matches and judge ratings still do not independently verify the result.",
    method,
    next,
  };
}
