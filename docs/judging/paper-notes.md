# Paper review: the Geospatial Research Agent (GRA)

**Source:** arXiv [2610.15750v1](https://arxiv.org/html/2610.15750v1), Google. A hackathon partner shared it, passing it on from Clay. We read it on 2026-11-04 to design our judge panel. Section numbers below are the paper's own. **[ext]**

## What the paper does

GRA is an agent that plans and runs geospatial analyses: it calls tools, loads skills and writes code over Earth-observation data. The paper evaluates it on several benchmarks, including expert-written queries with golden workflows (GeoExpertQueries) and value-level tasks (GeoKTools, CBGB). The parts that matter to us are how it scores agent runs and how it shows that the scorer can be trusted.

## What we took, and where it lives

| Paper finding | Our design |
| --- | --- |
| **Only executed work counts.** The autorater credits what the agent actually did, not its plan. Plan-only responses and answers with no analysis on tool-retrieved data score 0 (§3, A.3.1). | The dossier contains only executed steps and their outputs. The judge prompt says facts that appear in no tool output are not evidence. The fatal gates `no_answer` and `no_tool_data` fail the run (spec AC3, AC6). |
| **Anchored, coarse scales.** GeoExpertQueries is scored 0–2 against anchored definitions. Deviations are weighed "by their impact on the answer rather than by their number" (A.3.1). | Every judged criterion is scored 0, 1 or 2, with an anchor sentence for each level (`rubrics/geo-dataset-v1.yaml`). The impact rule is quoted in `prompts/judge/system.md`. |
| **The reference is a reference, not a checklist.** Alternative approaches count when an expert would accept them (A.3.1). | The rubric is task-agnostic: it asks whether the tools could answer, whether the arguments matched the request, and whether the results match the target. It doesn't ask whether the run followed a fixed recipe. |
| **A deterministic layer for value accuracy.** GeoKTools/CBGB score values against an authoritative reference, with rules such as invalidating values that depend on a wrong upstream entity (A.3.2). | Measured criteria are computed by code, with no LLM: claim provenance (each claim's value found in the tool result it cites) and area compliance (coordinates inside the requested boundary). |
| **Autorater validation.** The autorater was validated against domain experts rating the same traces: Krippendorff's α was 0.56 among experts and 0.57 with the autorater, and Spearman's ρ was 0.72 (§4.1.4). | Krippendorff's ordinal α across judges and runs (`harness agreement`, `harness compare`), with a cluster-bootstrap CI. The paper's expert α (≈0.56) is a realistic bar for humans on this kind of task. |
| **Run-to-run variance.** Three runs per configuration, reported as mean ± std. A 1.6-point gap is called "within run-to-run variation" (§4.2). | `harness judge --passes N` reports each criterion's mean ± std across passes (AC8), and suites run several prompts and models. |
| **Judge strictness shifts absolute scores.** "A stricter autorater would likely assign lower scores across the board", so conclusions rest on comparisons between configurations (§6). | Our docs and UI say confidence measures agreement, not ground truth. We recommend reading scores comparatively (model vs model, prompt vs prompt), and we prove sensitivity with calibration (planted defects must lower their target). |
| **Failure modes.** Execution failures (29% on UnivEARTH), benchmarks a plain LLM answers from memory (saturation), data drift in reference values, and bookkeeping calls inflating raw tool counts (§5). | Failure-mode tags in the rubric: `parametric_guess` (memory presented as findings), `budget_abort`, `retry_loop`, `premature_fallback`, `proxy_substitution`, `overconfidence`, `scope_violation`, `hallucinated_value`, `wrong_tool`, `incomplete_answer`. They are reported when a majority of judges agree. |
| **Self-preference and single-family risk.** Only Gemini models were tested, as both agent and rater (§6, limitations). | Three judges from three model families. A judge from the agent's own family recuses itself, and a reserve from another family takes its seat. |

## What we chose differently, and why

- **A panel, not one autorater.** The paper validates one autorater against experts. We have no experts at the event, so we use three judges from different families. Disagreement between them is the signal we can measure (within-one, MAD, α). The median of three is always an actual vote, so ties can't happen **[team]**.
- **Calibration by planted defects.** The paper's validation is correlational, comparing autorater scores with expert scores. We add a causal check: `harness calibrate` plants a known defect (unscoped searches, a fabricated site, a missing answer) and requires the panel to lower the targeted criterion **[team]**.
- **Measured results are hidden from the judges.** The paper's value rubric gives the judge the golden answer. Our judges never see our own code's verdicts, so code and LLMs are two independent lines of evidence, and a perturbation can't contradict a stale measured block **[team]**.

## Open caveats from the paper that still apply to us

- **Process alignment is not outcome correctness** (§6). A run that scores 100 can still have missed facilities that a ground-truth list (OSM, operator lists) would reveal. An answer key for the Dallas task is a follow-up (spike S6: both Overpass mirrors were unavailable).
- **A judge's strictness is a free parameter.** Absolute scores depend on the panel. Keep the panel fixed within a comparison, which the judgement's `seats` and `rubric.sha256` make checkable.
