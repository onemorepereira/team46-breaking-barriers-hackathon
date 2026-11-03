# Track 1 Evaluation Harness — Handoff (Design stage)

**What shipped:** A design (`design.md`, revision 5) for the Track 1 evaluation harness, built from `spec.md`. No code yet; Build starts at slice 1 of the implementation plan. Branch: `design/eval-harness`.

**Verification**
- [ ] AC1–AC11: not built yet. Every AC maps to a component and a planned test in `design.md` under Traceability.

**Exercised live** (sandbox account 892605951158, us-west-2, read-only checks except four small `converse` calls):
- Claude is available only through inference profiles, e.g. `us.anthropic.claude-haiku-5-5` and `us.anthropic.claude-sonnet-5-5`.
- `thinking.type=enabled` is rejected. `adaptive` with `display: summarized` returns summarized reasoning text on Haiku 5.5.
- The model can't see Bedrock's `toolUseId`, but it cites a `[ref T1]` label printed in the tool result. That led to the reference-label design for AC6.
- AgentCore: no runtimes exist yet. Transaction Search isn't enabled (`Destination: XRay`).

**Gate history:** Design gate, subagent review:
- **Pass 1:** 18 blocking issues, covering span-processor mutability, ADOT's extra spans, the boto3 timeout and retries, claim citation, Phoenix TLS, and contracts. All fixed in revision 2.
- **Pass 2:** 7 blocking issues (full model input and output, tool latency and retries, a flush before return, cooperative cancel, the payload contract, the AC4 comparison rule, truncation). All fixed in revision 3.
- **Pass 3:** 5 blocking issues (sampler, trouble-spot rule, suite format, model params, S2 bar). That was the skill's limit, so they were brought to the user, who chose to apply the fixes and run one more pass. The user also **dropped Phoenix and the live swap demo**, and AC4 became a CI exporter-swap test (revision 4).
- **Pass 4:** 4 blocking issues (span links for unsourced claims, how claim values are classed, raw vs prefixed tool results, conversation trimming). All fixed in revision 5, **not re-reviewed**.

**Specialists consulted:** ML/AI Engineer, AI Safety, QA Automation, Infrastructure, DevOps, SRE, FinOps and Data Engineer. Their questions were appended to every review pass.

**Decisions and deviations:**
- **Spec changes made during Design:**
  - AC4 is now an exporter-swap CI test that counts agent spans only.
  - AC6 cites reference labels like `T3`.
  - The AC6 matching wording was aligned with the design.
  - Phoenix was removed.
- **Choices settled by convention during pass 4:**
  - Analysis is the only parser of claims.
  - Local runs call the same `handle()` function in a subprocess.
  - `out/index.json` maps runs to their archive.

**Follow-ups:**
- Run spikes S1 and S6 first (Tuesday 1:00–3:00 pm), and S2 at the start of slice 3.
- Before running anything that calls a model, fill `prices_per_mtok` from the Bedrock pricing page.
- Enabling Transaction Search is account-wide: confirm with the user first.

**Risks to watch:**
- Strands hook payloads and the conversation manager (S1).
- ADOT provider behavior inside the runtime, and the 13-minute synchronous call (S2).
- LGND headless auth (S3).
- Coverage of the OSM answer key (S6).
