# Q&A Prep

Short answers, each sourced to the repo. Say the first sentence; use the rest only if asked to go deeper.

**1. Aren't AI judges biased, or just guessing?**
Three judges from three companies, so no single vendor carries a majority, and the median vote counts. A judge never grades an agent from its own family: on a Kimi run, Kimi steps down and a reserve sits. And the facts code can check, provenance and area, are never left to the judges. (`docs/judging/guide.md`)

**2. How do you know the evaluator itself is right?**
We plant known defects and check that the right criterion drops. All three did, live. That's calibration, and it once caught a bug in our own evidence builder. We're also clear that confidence measures agreement, not ground truth. (`docs/judging/handoff.md:45–65`)

**3. What does α 0.50 mean?**
Krippendorff's α measures how far judges agree beyond chance: 1 is perfect, 0 is chance. Ours is 0.50 across 7 real runs. Human experts reached about 0.56 in the GRA paper Clay shared. Our interval is wide (0.12–0.67), because 7 runs is few. (`docs/judging/handoff.md:116`, `docs/judging/paper-notes.md:17`)

**4. Why three judges, not one, or five?**
An odd number means no ties, and the median is always a real vote. We started with five. We dropped the slowest (it averaged 143 s and was the only one to error), and moved two to reserve. Three is faster and cheaper with no loss of independence. (`docs/judging/handoff.md`, "Tribunal of three")

**5. What does a run cost?**
About $0.30–0.80 for the agent in our runs, and $0.10–0.31 to judge it. (`docs/presentation/claims.md`)

**6. What is verified, and what is judged?**
Verified by code: every claimed value appears in the tool result it cites, and every site is inside the requested area. Judged: tool choice, arguments, sequencing, efficiency, relevance, grounding, completeness, and honest uncertainty. (`rubrics/geo-dataset-v1.yaml`)

**7. Does it know whether a site is really a data center?**
Not yet. It checks the agent against its own evidence, not against the world. That needs an answer key, e.g. a public registry of solar sites, and it's our top next step. (`docs/judging/gaps.md`)

**8. What happens when tools or the area lookup fail?**
The trace shows it, and the verdict says which kind of failure it was. If no model call succeeded at all (e.g. expired credentials), the run is **not scored**: it's an infrastructure failure, not the agent's. If the agent ran but gave no answer, or no tool call succeeded, it's **FAILED**, like the Texas parks run in the demo. A place with no official boundary runs without an area check, and the page says so. These cases were found and fixed from real runs. (`docs/developer-guide.md`, Troubleshooting)

**9. Could ADB use its own rubric?**
Yes: it's one YAML file, with no code changes. The judges read whatever criteria it defines, and calibration says which criterion each planted defect should lower. (`docs/judging/guide.md`, "To use ADB's rubric")

**10. Why AWS Bedrock and AgentCore?**
One place for the agent runtime, the models and the judges, with OpenTelemetry tracing built in. And every part is swappable: the models and judges by config, the tracing backend by config (proved in CI). (`README.md`, "Decisions")

**11. Can I trust a run whose judges disagree?**
That's what confidence is for: wide disagreement lowers it to Medium or Low, so you know to look closer. The demo run is a good example: one judge scored it well below the other two, and the page shows why, vote by vote.

**12. Can a person overrule the judges?**
Not overrule: correct. An expert reviews a run criterion by criterion, and the judges reconsider against the trace. They keep their vote when the review isn't supported, and say why. We tested that with a deliberately wrong review, and Opus corrected us from the steps. The expert's own score sits beside the panel's and is never mixed in. (`docs/judging/guide.md`, "Human feedback"; `docs/judge-feedback/handoff.md`)

**13. Doesn't that make the judges sycophantic?**
That's the risk we test for. `harness calibrate --feedback` sends a wrong review, the same one with "I insist", and one with injected instructions, and checks against a control that none of them moves the scores. Live, all three were resisted. (`docs/judge-feedback/handoff.md`, AC7)

**14. How do lessons from one run reach the next?**
Reviews are drafted into short, general lessons per criterion. They're tested on a third of reviewed runs that the drafter never saw, and a person approves them in the console. From then on they're in every judge's prompt, versioned, and they can be rolled back. They live in that deployment's archive, so ADB's instance learns from ADB's experts. (`docs/judge-feedback/design.md`)

**15. Is it open source? Can Clay run it?**
Yes, under Apache-2.0 on GitHub. The infrastructure is code (CDK), and the developer guide covers setup and running in a fresh AWS account. (`LICENSE`, `docs/developer-guide.md`)
