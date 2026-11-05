# Q&A Prep

Short answers, each sourced to the repo. Say the first sentence; use the rest only if asked to go deeper.

**1. Aren't AI judges biased, or just guessing?**
Three judges from three companies, so no single vendor carries a majority. Each votes three times, in parallel, and a criterion's score is the average of every vote. A judge never grades an agent from its own family: on a Kimi run, Kimi steps down and a reserve sits. And what code can check (provenance, area, request conditions) is never left to the judges. (`docs/judging/guide.md`; `harness.yaml`, `judging`)

**2. How do you know the evaluator itself is right?**
We plant known defects and check that the right criterion drops. All three did, live. That's calibration, and it once caught a bug in our own evidence builder. We're also clear that confidence measures agreement, not ground truth. (`docs/judging/handoff.md:45–65`)

**3. What does α 0.50 mean?**
Krippendorff's α measures how far judges agree beyond chance: 1 is perfect, 0 is chance. Ours is 0.50 across 7 real runs. Human experts reached about 0.56 in the GRA paper Clay shared. Our interval is wide (0.12–0.67), because 7 runs is few. (`docs/judging/handoff.md:116`, `docs/judging/paper-notes.md:17`)

**4. Why three judges, not one, or five?**
Three families is enough that no vendor carries a majority. We started with five. We dropped the slowest (it averaged 143 s and was the only one to error), and moved two to reserve. Three is faster and cheaper with no loss of independence. Instead of more judges, each judge votes three times at once: one vote per judge let identical evidence score anywhere from 83 to 94, and three passes averaged hold it within a couple of points, in about 20 s. (`docs/judging/handoff.md`, "Tribunal of three"; `docs/judging-stability/handoff.md`, "Proof")

**5. What does a run cost?**
About $0.30–0.80 for the agent in our runs. Judging is about $0.22 with three passes, plus a few cents for the visual check ($0.06 on the Egypt run). (`docs/presentation/claims.md`)

**6. What is verified, and what is judged?**
Measured, not voted: every claimed value appears in the tool result it cites; every site is inside the requested area; each distance or location condition in the prompt has supporting evidence; and each site visibly shows the asset in the sharpest open image (a vision model's verdict, archived). Judged: tool choice, arguments, sequencing, efficiency, relevance, grounding, completeness, and honest uncertainty. (`rubrics/geo-dataset-v1.yaml`, version 3)

**7. Does it know whether a site is really a data center?**
Partly. A vision model looks at each reported site in the sharpest open image (Vantor, OpenAerialMap, NAIP, then Sentinel-2) and says seen, not seen or can't tell. On a wind run it found a field of stored turbine blades, and the score dropped from 96.2 to 89.4. It's one vote per site, and at 10 m a small site can't be told. What it can't say is what the agent missed: that needs an answer key. We have one for Pecos County solar (the USGS inventory, in the demo), and more are our top next step. (`docs/visual-check/handoff.md`; `docs/judging/gaps.md`)

**8. What happens when tools or the area lookup fail?**
The trace shows it, and the verdict says which kind of failure it was. If no model call succeeded at all (e.g. expired credentials), the run is **not scored**: it's an infrastructure failure, not the agent's. If the agent ran but gave no answer, or no tool call succeeded, it's **FAILED**, like the Texas parks run in the demo. A place with no official boundary runs without an area check, and the page says so. These cases were found and fixed from real runs. (`docs/developer-guide.md`, Troubleshooting)

**9. Could ADB use its own rubric?**
Yes: it's one YAML file, with no code changes. The judges read whatever criteria it defines, and calibration says which criterion each planted defect should lower. (`docs/judging/guide.md`, "To use ADB's rubric")

**10. Why AWS Bedrock and AgentCore?**
One place for the agent runtime, the models and the judges, with OpenTelemetry tracing built in. And every part is swappable: the models and judges by config, the tracing backend by config (proved in CI). (`README.md`, "Decisions")

**11. Can I trust a run whose judges disagree?**
That's what confidence is for: wide disagreement lowers it to Medium or Low, so you know to look closer. The Texas parks contrast run is an example: its judges gave 18.8, 43.8 and 93.8, and the page shows why, vote by vote. (`docs/presentation/claims.md`, slide 3)

**12. Can a person overrule the judges?**
Not overrule: correct. An expert reviews a run criterion by criterion, and the judges reconsider against the trace. They keep their vote when the review isn't supported, and say why. We tested that with a deliberately wrong review, and Opus corrected us from the steps. The expert's own score sits beside the panel's and is never mixed in. (`docs/judging/guide.md`, "Human feedback"; `docs/judge-feedback/handoff.md`)

**13. Doesn't that make the judges sycophantic?**
That's the risk we test for. `harness calibrate --feedback` sends a wrong review, the same one with "I insist", and one with injected instructions, and checks against a control that none of them moves the scores. Live, all three were resisted. (`docs/judge-feedback/handoff.md`, AC7)

**14. How do lessons from one run reach the next?**
Reviews are drafted into short, general lessons per criterion. They're tested on a third of reviewed runs that the drafter never saw, and a person approves them in the console. From then on they're in every judge's prompt, versioned, and they can be rolled back. They live in that deployment's archive, so ADB's instance learns from ADB's experts. (`docs/judge-feedback/design.md`)

**15. Is it open source? Can Clay run it?**
Yes, under Apache-2.0 on GitHub. The infrastructure is code (CDK), and the developer guide covers setup and running in a fresh AWS account. (`LICENSE`, `docs/developer-guide.md`)

**16. Can we show the imagery to ADB or the public?**
Check first. Every run lists the data and licences it used, and whether the result is presentable. Vantor's sharp images are CC BY-NC 4.0 (no commercial use), so a run whose visual check used one says "check before sharing". NAIP is public domain with attribution, Sentinel-2 is free and open, and each OpenAerialMap image has its own licence. (`docs/visual-check/handoff.md`, "Licences"; `docs/observed-scenes/handoff.md`, "Licences")
