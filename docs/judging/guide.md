# How a run is scored: a guide for ADB and Clay

This guide explains what the score on a run means, how it's produced, and how to check it. The design detail is in [design.md](design.md), and the acceptance criteria are in [spec.md](spec.md). **[team]**

## The score in one paragraph

Every run is scored 0–100 on two dimensions:
- **Workflow:** did the agent use its tools well?
- **Output:** can the dataset it produced be trusted?

The overall score is the mean of the two. Two criteria are **measured by code**:
- whether each claimed value appears in the tool result it cites;
- whether each claimed location is inside the requested area.

Eight criteria are **judged** by a panel of five LLMs from five different model families. Each panel score is the median of the five votes. Next to the score sits a **confidence** label (High, Medium or Low). It says how far the judges agreed and whether the trace is intact. It does **not** say the answer is true: that would need an answer key, which is our main open gap ([gaps.md](gaps.md)).

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

## The panel

| Seat | Model | Family | $/Mtok in / out |
| --- | --- | --- | --- |
| Chair | Claude Opus 5.5 | Anthropic | 4.00 / 20.00 |
| 2 | Grok 4.7 | xAI | 2.20 / 6.60 |
| 3 | Kimi K3 | Moonshot | 3.30 / 16.50 |
| 4 | DeepSeek V3.2 | DeepSeek | 0.62 / 1.85 |
| 5 | Mistral Large 3 | Mistral | 0.50 / 1.50 |
| Reserves | Qwen3 235B (Alibaba), then Sonnet 5.5 (Anthropic) | | 0.22 / 0.88; 2.00 / 10.00 |

- **Why five, from five families:** an odd panel has no ties, and its median is always one judge's real vote. No single vendor can carry a majority. That answers the self-preference risk the GRA paper leaves open, since it rated Gemini with Gemini.
- **Recusal:** a judge from the agent's own family steps down, and the first reserve from another family takes the seat. The page shows "seated for opus".
  - Sonnet 5.5 is our default agent, so on a Sonnet run Opus recuses and Qwen sits.
  - On a Kimi run, Kimi recuses and Qwen sits.
  - The setting is `recuse_same_family`.
- **What a judge sees:** a dossier built by code from the archive. It holds the task, the requested area, the tools available, every step in order (reasoning, arguments, outputs labeled `T1`, `T2`…), run totals and the final answer.
  - Tool output is wrapped in `<tool_output>` tags and declared untrusted.
  - Judges never see our measured results, so code and LLMs are two independent lines of evidence.
- **What a judge returns:** JSON with, for each criterion, a rationale, the step IDs it relied on, and a score.
  - A malformed reply is retried once; a second failure means the judge failed.
  - A run is scored only if at least three judges are valid.
  - Unknown step IDs and unknown failure-mode tags are dropped and counted.

## From votes to a score

1. **Per judged criterion:** the median vote, or the lower median if only 3–4 judges are valid. The score is median ÷ 2 × 100.
2. **Measured criteria:** the share × 100, or N/A when there's nothing to measure (no area, no coordinates).
3. **Dimensions:** the mean of their criteria. **Overall:** the mean of the two dimensions.
4. **Fatal gates** override everything: no final answer, or no successful tool call. The run scores **FAILED** (0 overall, 0 on every output criterion), and its workflow scores stay visible for diagnosis.
   - **Not scored** is different from FAILED. If no model call succeeded at all (expired credentials, throttling, a model the account can't use), the agent never got a chance, so the panel isn't asked. The run shows **not scored** with the cause, costs nothing to judge, replaces any earlier judgement, and stays out of agreement (`measure.infrastructure_failure`).
5. **Failure modes** (`retry_loop`, `parametric_guess`, `scope_violation` and so on) are listed when most judges tag them.

## How much to trust the score

| Check | Where | Meaning |
| --- | --- | --- |
| **Confidence** (per run) | KPI strip, report | **High**: trace intact, no gate, 5 valid judges, judges within 1 point on ≥ 80% of criteria. **Low**: trace broken, a gate fired, < 4 valid judges, or < 50% within 1 point. **Medium**: otherwise |
| **Within-one, MAD** (per run) | Judge agreement tile | How tightly the five votes cluster |
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

## Commands

```sh
uv run harness judge <run-id> [--passes 3]   # score an archived run; writes runs/<id>/judgement.json
uv run harness calibrate <run-id>            # planted-defect check of the panel
uv run harness agreement --all               # Krippendorff's alpha across every judged run
uv run harness compare <suite-id>            # suite table with scores, confidence and corpus alpha
uv run harness ui                            # the console: live runs, scores, map, plain-language trace
```

`harness run` and the console judge every finished run automatically (`judging.auto: true`). Replay never calls a model: it re-aggregates the archived votes with the rubric snapshot stored in the judgement.

## Reading a score well

- **Compare, don't rank in the absolute.** A stricter panel scores everything lower (GRA §6). Comparisons are fair when they use the same rubric and the same panel. Every judgement records `rubric.sha256` and its seats, so that's checkable.
- **A 100 is not proof.** It means the panel found no material flaw in what the agent executed, and that the agent's claims match its tool outputs. It doesn't mean the agent found every facility. Read the agent's own caveats in its answer, and the honest-uncertainty criterion.
