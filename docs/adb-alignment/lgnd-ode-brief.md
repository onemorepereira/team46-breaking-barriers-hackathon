# What the LGND/Ode Inception Report Means for Track 1

**The source:** the LGND/Ode inception and discovery report for ADB (Draft V1, dated 20 October 2026), shared with the team by Clay/LGND on 2026-11-04. It's an internal draft, so it is **not in this repo** and nothing here quotes it. This page paraphrases only the parts relevant to Track 1, with the report's section numbers so a reader holding the report can check them. All claims about the report are **[ext]**. Our own conclusions are **[team]**.

## What their project is
Ode and LGND are building a **benchmark of geospatial foundation-model workflows** for ADB. It asks whether AEF, Clay and FarSLIP embeddings with simple classifiers can build asset datasets more cheaply and more transferably than buying imagery and detectors (§1, §2) **[ext]**.
- **Users:** disaster risk finance, post-disaster needs assessments (PDNA), ADB's Disaster Risk Analytics Explorer, and project and sector teams that monitor funded assets (§4.1) **[ext]**.
- **Delivery:** it runs to mid-January 2027. The deliverable that matters most to us is an **evaluation harness and metrics**, scheduled October to December 2026. One of its listed delivery options is a standalone web app (§2.1) **[ext]**.

## The part that is our track: agentic evaluation (§5.8)
They separate two questions **[ext]**:
- how well a defined workflow performs, which is their committed benchmark;
- whether an **off-the-shelf agent harness**, given geospatial tools over an MCP connector, reproduces that performance when asked to do the same task.

The second is listed as **exploratory and outside the core deliverables**. If time allows, they plan to run their inventory task through an agent harness with the LGND Geo MCP connector, then report the pitfalls and a **proposed rubric** for agentic geoAI systems **[ext]**. They name the dimensions such a rubric should cover:
- how the agent plans;
- whether its searches cover the requested **area and period**;
- whether it uses tools correctly;
- whether its answer is consistent with the evidence and honest about limits;
- how it combines imagery with web sources;
- how efficiently it reaches an answer.

**What this means for us [team]:** this is the harness and rubric Track 1 already built, running on the LGND Geo MCP connector. Our rubric covers planning, area, tool use, evidence consistency, honest limits and efficiency. The gaps are listed below.

## Their requirements for any evaluation (§4.2) [ext]
1. **Per asset class:** report accuracy for each asset class, checked against reference records, not as one aggregate.
2. **New geographies:** test in places the workflow has never seen, and report those results separately.
3. **Uncertainty:** record whether it is stated, and whether it matches the error observed against reference data.
4. **Effort:** record the effort to build the dataset (labels, analyst review).
5. **Cost per run:** imagery, storage, compute.
6. **Sources and licences:** record the imagery, models and reference data each evaluation used, with their licences, including whether they permit presentation to governments and third parties.
7. **Reproducibility:** code, data and method documented, so ADB can repeat an evaluation the same way in every country.

## Their evaluation vocabulary [ext]
- **Tasks (§4, Table 6):** five analyst tasks. The one an agent run maps to is **T1, inventory: "where are all the assets of this type here?"**. The others cover sizing (T2), checking a register (T3), counting event damage (T4) and transfer to a new place (T5).
- **The components of a run (§5.2):** reference data with a recorded completeness class and licence; a unit (the asset, predicted on 160 m grid cells); a matching rule (an asset is found when any flagged cell touches it, and counts once); scores; labelling cost; and a transfer test. All are **fixed before results are examined**.
- **Metrics (§5.7):** site recall (and recall within the top k), grid-cell precision, lift over random, **count ratio** (implied count ÷ reference count), AUROC, review effort, and transfer gap (home score minus new-place score).
- **Completeness rule (§7.2.1):** recall is defined only against **complete** reference data. Incomplete data supports precision and ranking only.
- **Licence rule (Table 1, §7.4):** no academic-only or non-commercial datasets in ADB's outputs. Prefer CC BY, MIT and public-domain sources, or hand labels.

## Concepts and places (§2, §5.4, Appendix A) [ext]
- **Concepts:**
  - warehouses (large logistics or storage buildings);
  - above-ground oil and fuel tanks;
  - road, rail and pedestrian bridges of 10 m or more;
  - substations and transmission lines;
  - utility-scale solar and wind farms.
- **Places:** Nagoya and Gifu (benchmark and cross-city transfer); Manila (the first ADB city); Port Vila; then Kathmandu, Visakhapatnam and Vijayawada–Guntur. A Central Asian city (e.g. Tashkent) is proposed.
- **Training regions:** China and the US, used only for training, never as test places.
- **Complete reference sets** they report having:
  - warehouses in Nagoya and Gifu (Japan's PLATEAU building register);
  - hand-labelled fuel tanks in Nagoya test blocks;
  - national-road bridges in Metro Manila (the Philippines' DPWH inventory);
  - Port Vila's surveyed exposure data (PCRAFI).

  Most other ADB places need hand-labelled test blocks.

## Findings worth knowing (Appendix B) [ext]
- **Zero-shot text search** for "warehouse" finds a bit over half of Nagoya's warehouses within the top-ranked cells, and about half in Gifu. That's a useful **floor for an agent that relies on LGND's search** [team].
- **Transfer roughly halves recall** for classifiers moved from Nagoya to Gifu.
- **Typical false positives:** large sealed roofs, rail yards, truck parks and quays. **Small warehouses** in dense blocks are often missed.
- **For tanks**, a supervised detector on sharp imagery far outperforms embeddings. Embeddings are better at narrowing where to look than at finding every tank.

## Gaps between our harness and the report [team]
| Their ask | Our status before this effort | Effort |
| --- | --- | --- |
| §5.8 dimensions: plan, tools, evidence, honesty, efficiency | Covered by the rubric | — |
| §5.8 area coverage | Covered: the area is enforced and `area_compliance` is measured | — |
| §5.8 **period** coverage | Only judged (the time range in `tool_arguments`); nothing measures it | Overlaps the open prompt-compliance slice (PR #7), so we coordinate rather than collide |
| §5.8 **web sources** | Not covered: the agent has no web tool | Out of scope |
| §4.2(1) **per asset class** | Not covered: `compare` groups by prompt and model, not by concept | **This effort** |
| §4.2(2) **new geographies**, transfer gap | Not covered | **This effort**: suite metadata and a transfer view |
| §4.2(3) uncertainty **stated** | Judged (`calibration`) | — |
| §4.2(3) uncertainty **calibrated against reference** | Not covered | Needs reference data, below |
| §4.2(4–5) effort and cost | Covered: cost, tokens, steps and runtime are recorded per run | — |
| §4.2(6) **sources and licences** per evaluation | Not covered | **This effort** |
| §4.2(7) reproducibility | Covered: archive replay, plus rubric, panel and guidance versions on every score | — |
| §5.2/§5.7 **reference data, recall, precision, count ratio** under their matching rule | Not covered: our top gap ("no answer key") | **This effort**: the reference-set format and metrics, with a public-domain US set first |
| §5.2 concepts and places | Partly covered by example cards | **This effort**: a suite with their concepts and places |
