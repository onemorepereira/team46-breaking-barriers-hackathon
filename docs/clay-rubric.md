# Clay: change the evaluation rubric

The current rubric is a starting point for Clay to review and adapt. Its score is evidence for a review, not a certificate that a dataset is correct. Getting Clay's actual questions and examples into it matters more than polishing one universal score.

## Edit it without changing application code

1. Copy `rubrics/geo-dataset-v1.yaml` to `rubrics/clay.yaml`.
2. Set its `id` to `clay` and `version` to `1`. Change each criterion's `question`, its plain-English `plain` label, and the descriptions of what scores 0, 1 and 2 mean. Keep the existing `workflow` and `output` dimensions and 0/1/2 scale for the simplest supported setup.
3. Point your ignored `harness.local.yaml` at it:

   ```yaml
   judging:
     rubric: rubrics/clay.yaml
   ```

4. Validate it from the repository folder:

   ```sh
   uv run python -c "from analysis.judging.rubric import load; r=load('rubrics/clay.yaml'); print(r.id, r.version, len(r.criteria), r.sha256)"
   ```

5. Restart the console. Run one known-good and one deliberately incomplete task. Read the judges' explanations and evidence, not just the total. Clay can also use **Your review** to disagree with a judgement; **Guidance** supports reviewed, evaluated judging instructions.

You can add or remove **judged** criteria. Update the `calibration` references if a criterion is removed or renamed. **Measured** checks require implementations: the supported IDs are `claim_provenance`, `area_compliance` and `condition_compliance`. Keep those IDs; do not relabel an existing computation as a new kind of measurement. New measurement types, dimensions or weighting rules need code work.

## Keep comparisons honest

Increase the rubric version when scoring rules change. Each judgement saves its rubric contents, version and hash. **Re-judge** calls the judges again under the current rubric; earlier judgements are retained. **Replay** rebuilds the saved report and does not apply a new rubric or make new judge calls. Compare model scores under the same rubric and conditions.

The present spatial-evidence caps and missing-evidence rules are code-level protections. Changing rubric prose alone does not disable them. Similarity scores, source-text matches and agreement between judges do not independently establish real-world truth.
