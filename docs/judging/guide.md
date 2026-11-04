# How a run is scored: a guide for ADB and Clay

This guide explains what the score on a run means, how it's produced, and how to check it. The design detail is in [design.md](design.md), and the acceptance criteria are in [spec.md](spec.md). **[team]**

## The score in one paragraph

Every run is scored 0–100 on two dimensions:
- **Workflow:** did the agent use its tools well?
- **Output:** can the dataset it produced be trusted?

The overall score is the mean of the two. Two criteria are **measured by code**:
- whether each claimed value appears in the tool result it cites;
- whether each claimed location is inside the requested area.

Eight criteria are **judged** by a tribunal of three LLMs from three different model families. Each panel score is the median of the three votes. Next to the score sits a **confidence** label (High, Medium or Low). It says how far the judges agreed and whether the trace is intact. It does **not** say the answer is true: that would need an answer key, which is our main open gap ([gaps.md](gaps.md)).

## Plain explanation on each report

The run page and static report start with **What this means**: a short account of the request, listed locations, score, evidence limits, and up to three things to check by hand. It is computed from the saved archive without an AI call. Counts describe the agent's listed locations, not a count of independently confirmed facilities. Image checks that returned "no" or an unclear answer get specific review actions.

Scorecard questions use optional `plain:` labels from the current configured rubric. Old judgements keep their archived scoring definitions; display text falls back to the saved question when no current label exists. Adding a plain label does not change votes, scoring anchors, weights, or aggregation, although the file's hash changes.

## The rubric

`rubrics/geo-dataset-v1.yaml` is generalized for any agentic geospatial dataset build. Each judged criterion has one sentence per score: 0, 1 and 2.

| Criterion | Dimension | How it's scored | It asks |
| --- | --- | --- | --- |
| Tool choice (`tool_selection`) | workflow | judged | Were the tools able to answer the task, without a weaker proxy? |
| Tool-call accuracy (`tool_arguments`) | workflow | judged | Area, index, time range, query terms and limits as requested? |
| Sequencing & recovery (`sequencing_recovery`) | workflow | judged | Search, then verify, then answer; errors handled, no loops? |
| Efficiency (`efficiency`) | workflow | judged | Steps, tokens and cost proportionate? |
| Result relevance (`result_relevance`) | output | judged | Are results the requested target, according to the tools' evidence? |
| Grounding (`grounding`) | output | judged | Does every stated fact trace, faithfully, to executed tool output? |
| Completeness (`completeness`) | output | judged | Is every part of the request answered? |
| Honest uncertainty (`calibration`) | output | judged | Are limits and unverified items stated plainly? |
| Claim provenance (`claim_provenance`) | output | measured | Share of declared claims whose value is in the cited tool result |
| Area compliance (`area_compliance`) | output | measured | Share of claimed coordinates inside the requested boundary |

**To use ADB's rubric:** write it in the same YAML shape and point `judging.rubric` in `harness.yaml` at it. No code changes. Code names only the two measured criteria. The rubric's `calibration:` map says which judged criterion each planted defect should lower.

### Value-checker update under review (2026-11-04)

Checker version 2 requires a coordinate pair from the same source record or labelled table row. Verification labels such as "supported" no longer match "not supported", and failed tool calls cannot verify claims. Ordinary text and number checks still compare declared values; they do not prove the meaning of every claim or its real-world truth.

New judgements record `value_matcher_version`. Old judgements remain intact; viewing or replaying them uses current measured checks and shows an update note, so their regenerated scores may differ from earlier reports. Keep the checker version, judge seats, and rubric fixed when comparing runs.

## The panel

A tribunal of three judges from three families:

| Seat | Model | Family | $/Mtok in / out |
| --- | --- | --- | --- |
| Chair | Claude Opus 5.5 | Anthropic | 4.00 / 20.00 |
| 2 | DeepSeek V3.2 | DeepSeek | 0.62 / 1.85 |
| 3 | Kimi K3 | Moonshot | 3.30 / 16.50 |
| Reserves, in order | Mistral Large 3 (Mistral), Qwen3 235B (Alibaba), Sonnet 5.5 (Anthropic) | | 0.50 / 1.50; 0.22 / 0.88; 2.00 / 10.00 |

- **Why three, from three families:** an odd panel has no ties, and its median is always one judge's real vote. No single vendor can carry a majority. That answers the self-preference risk the GRA paper leaves open, since it rated Gemini with Gemini.
- **Who was dropped, and why** (from the 7 runs judged by the earlier five-judge panel):
  - **Grok 4.7**: it averaged 143 s per verdict against 11–50 s for the others, so it set the time to a score, and it was the only judge that errored.
  - **Mistral Large 3** and **Qwen3 235B** are reserves: they were the two most lenient judges (+0.14 and +0.25 points above their peers' median on average). Kimi took Mistral's seat at the user's call. It voted closest to its peers (mean bias −0.09), so the tribunal isn't outvoted by lenient seats.
  - **Kimi K3** judges and is also an agent under test. On a Kimi run it recuses and Mistral sits.
- **Recusal:** a judge from the agent's own family steps down, and the first reserve from another family takes the seat. The page shows "seated for opus".
  - Sonnet 5.5 is our default agent, so on a Sonnet run Opus recuses and Mistral sits.
  - On a Kimi run, Kimi recuses and Mistral sits.
  - The setting is `recuse_same_family`.
- **Stand-ins:** if a judge fails (after its one retry), the next reserve takes its seat. The reserve must share a family with neither the agent nor a seated judge. The page shows "stood in for kimi", and the failed attempt stays on the record.
- **What a judge sees:** a dossier built by code from the archive. It holds the task, the requested area, the tools available, every step in order (reasoning, arguments, outputs labeled `T1`, `T2`…), run totals and the final answer.
  - Tool output is wrapped in `<tool_output>` tags and declared untrusted.
  - Judges never see our measured results, so code and LLMs are two independent lines of evidence.
- **What a judge returns:** JSON with, for each criterion, a rationale, the step IDs it relied on, and a score.
  - A malformed reply is retried once; a second failure means the judge failed.
  - A pass counts only with all three votes, after any stand-in. If the reserves run out, the run is not scored.
  - Unknown step IDs and unknown failure-mode tags are dropped and counted.

## From votes to a score

1. **Per judged criterion:** the median vote (the lower median for an even count, from older five-judge records). The score is median ÷ 2 × 100.
2. **Measured criteria:** the share × 100, or N/A when there's nothing to measure (no area, no coordinates).
3. **Dimensions:** the mean of their criteria. **Overall:** the mean of the two dimensions.
4. **Fatal gates** override everything: no final answer, or no successful tool call. The run scores **FAILED** (0 overall, 0 on every output criterion), and its workflow scores stay visible for diagnosis.
   - **Not scored** is different from FAILED. If no model call succeeded at all (expired credentials, throttling, a model the account can't use), the agent never got a chance, so the panel isn't asked. The run shows **not scored** with the cause, costs nothing to judge, replaces any earlier judgement, and stays out of agreement (`measure.infrastructure_failure`).
5. **Failure modes** (`retry_loop`, `parametric_guess`, `scope_violation` and so on) are listed when most judges tag them.

## How much to trust the score

| Check | Where | Meaning |
| --- | --- | --- |
| **Confidence** (per run) | KPI strip, report | **High**: trace intact, no gate, every seat's vote valid (stand-ins count), judges within 1 point on ≥ 80% of criteria. **Low**: trace broken, a gate fired, two or more seats short, or < 50% within 1 point. **Medium**: otherwise, for example one seat short |
| **Within-one, MAD** (per run) | Judge agreement tile | How tightly the votes cluster |
| **Krippendorff's α** (across runs) | `harness agreement --all`, `harness compare` | Chance-corrected agreement between judges, with a cluster-bootstrap 95% CI. For scale: domain experts reached α ≈ 0.56 on a similar task (GRA §4.1.4) |
| **Repeat stability** | `harness judge <run> --passes 3` | Each criterion's mean ± std over three panel passes |
| **Calibration** | `harness calibrate <run>` | Plants one defect at a time and checks the panel notices it (below) |

### Calibration: can the judges see a planted defect?

`harness calibrate <run_id>` builds three copies of the run's dossier, each with one defect, and has the panel judge each copy:

| Defect | What changes | Must lower |
| --- | --- | --- |
| `unscoped` | Area removed from every search; results relabeled as "searched everywhere" | Tool-call accuracy |
| `fabricated` | A made-up "Lakeview Data Center, operated by Northgate Cloud", inside the area, with a claim citing a real tool step | Grounding |
| `no_answer` | Final answer removed | Completeness |

Each defect is reported as one of:
- **pass:** the target dropped;
- **fail:** it didn't;
- **inconclusive:** it was already 0;
- **non-specific:** another criterion dropped as much as the target.

## Human feedback: reviews, reconsideration and guidance
Anyone using a deployment can answer a score, and the judges learn from the answers ([spec](../judge-feedback/spec.md), [design](../judge-feedback/design.md)).

1. **Review** a judged run on its page (**Your review**), criterion by criterion. Either agree, or give the score you'd give, a reason, and optionally the steps that show it (`T3`, `M2`). Measured criteria are code, so they take a note, not a score.
2. **Ask the judges to reconsider.** The judges that voted re-score the run, each seeing its own earlier reply and your review.
   - The review is a claim they check against the steps, not an order. A judge may keep its score, and says why.
   - The revised votes become the run's score, marked "Revised after human review". The original judgement stays one click away.
   - Your own score is shown beside the panel's, never mixed into it.
3. **Guidance.** On the **Guidance** page, propose lessons from all reviews. The chair judge drafts short, general clarifications per criterion, each citing its reviews.
   - **Edit** them, then **evaluate** them. About a third of reviewed runs are held out by run ID and never shown to the proposer. Evaluation re-judges them with the live guidance and with the draft, compares both with the reviewers, and reruns planted-defect calibration. It says **adopt** only if agreement with reviewers improves and calibration still passes.
   - **Approve** a version to make it active; without an **adopt** verdict you must give a reason. Approve an older version to roll back, or switch guidance off.
   - An active version is added under each criterion's anchors in every judge's prompt. It never replaces an anchor.
   - Each judgement records the version it used, so only like is compared with like.

**Where it lives:** in the deployment's own archive (`archive_uri`, under `feedback/`). So guidance is scoped to one Foundry instance, survives restarts, and is never in the repo or the browser. Guidance is keyed to a rubric's id and version: ADB's rubric, once dropped in, starts with none.

**Can the judges be talked into a wrong score?** `harness calibrate <run> --feedback` checks four cases on planted copies of the run:
- a wrong review;
- the same wrong review made with authority ("I insist");
- one with injected instructions;
- a right review.

The judges must resist the first three and accept the last. The review text is escaped and declared data in the prompt.

**Agreement with people:** `harness agreement --human`, and the Guidance page, report Krippendorff's α between the panel and reviewers, with its CI. Agreement between judges (`harness agreement`) only counts first judgements, never votes a review influenced.

## Commands

```sh
uv run harness judge <run-id> [--passes 3]   # score an archived run; writes runs/<id>/judgement.json
uv run harness calibrate <run-id>            # planted-defect check of the panel
uv run harness calibrate <run-id> --feedback # do the judges resist wrong reviews and accept right ones?
uv run harness guidance list                 # this deployment's guidance versions and agreement
uv run harness agreement --all               # Krippendorff's alpha across every judged run
uv run harness compare <suite-id>            # suite table with scores, confidence and corpus alpha
uv run harness ui                            # the console: live runs, scores, map, plain-language trace
```

`harness run` and the console judge every finished run automatically (`judging.auto: true`). Replay never calls a model: it re-aggregates the archived votes with the rubric snapshot stored in the judgement.

## Reading a score well

- **Compare, don't rank in the absolute.** A stricter panel scores everything lower (GRA §6). Comparisons are fair when they use the same rubric and the same panel. Every judgement records `rubric.sha256` and its seats, so that's checkable.
- **A 100 is not proof.** It means the panel found no material flaw in what the agent executed, and that the agent's claims match its tool outputs. It doesn't mean the agent found every facility. Read the agent's own caveats in its answer, and the honest-uncertainty criterion.

## Request conditions (rubric v2)

New runs archive extracted request conditions before judging. Code checks each declared location against the saved boundary and any evidenced distance reference. A missing reference is unverified. Finding only far references does not prove no nearer one exists. Distance is to the recorded reference point, not the area's edge. Identity and other constraints remain judge/human assessments.

The output dimension is capped at measured spatial-condition coverage, so good scores elsewhere cannot hide missing required evidence. Unverified or contradicted spatial conditions lower confidence. Extraction errors leave the overall evaluation not scored. Old archives without conditions remain N/A and are never re-extracted by replay/re-judge. Compare runs only with the same rubric/checker versions.
