import { test } from "node:test";
import assert from "node:assert/strict";
import { summarise } from "./summary.ts";
import { imageForCandidate } from "./api.ts";
import {
  buildPrompt,
  hasTemplateBlanks,
  readPreference,
  writePreference,
  readAccessibility,
} from "./preferences.ts";
function view(): any {
  return {
    run: { area: "Napa" },
    kpis: {
      score: 80,
      verdict: "scored",
      claims_total: 3,
      claims_matched: 2,
      claims_inside: 0,
      claims_located: 1,
      tool_calls: 1,
      model_calls: 1,
    },
    map: {
      claims: {
        features: [
          { geometry: { coordinates: [1, 2] }, properties: { ref: "T1" } },
        ],
      },
    },
    timeline: [{ kind: "tool", title: "search" }],
    final_answer: "Candidate",
    explanation: null,
    conditions: null,
    licences: null,
    reference: null,
  };
}
test("summary leads with candidates and evidence gaps, never a false accuracy claim", () => {
  const s = summarise(view());
  assert.match(s.takeaway, /1 candidate location/);
  assert.match(s.missing, /1 declared values could not be matched/);
  assert.match(s.missing, /1 location entry is outside/);
  assert.match(s.missing, /accuracy and completeness are not established/);
  assert.match(s.method, /1 tool call and 1 model call/);
});
test("unscored and failed runs retain their failure status even when candidates exist", () => {
  const v = view();
  v.kpis.verdict = "not scored";
  v.kpis.not_scored_cause = "Extraction failed";
  assert.match(summarise(v).takeaway, /could not be fully evaluated/);
  assert.match(summarise(v).missing, /Extraction failed/);
  v.kpis.verdict = "FAILED";
  assert.match(summarise(v).takeaway, /did not deliver/);
});
test("a broken independent reference is not treated as a verified benchmark", () => {
  const v = view();
  v.reference = { error: "unavailable" };
  assert.match(
    summarise(v).missing,
    /accuracy and completeness are not established/,
  );
});
test("imagery inspection selects only a chip from the cited step and nearest location", () => {
  const v = view();
  const chip = (ref: string, c: number) => ({
    properties: { ref, tile_url: "/tiles/test" },
    geometry: {
      coordinates: [
        [
          [c, 2],
          [c + 0.1, 2],
          [c, 2.1],
          [c, 2],
        ],
      ],
    },
  });
  v.map.chips = { features: [chip("T2", 1), chip("T1", 7), chip("T1", 1)] };
  assert.equal(imageForCandidate(v, 0), 2);
  v.map.chips.features = [chip("T2", 1)];
  assert.equal(imageForCandidate(v, 0), null);
});
test("template blanks cannot accidentally be sent as the user's intended area", () => {
  assert.ok(hasTemplateBlanks(buildPrompt("", "")));
  assert.ok(hasTemplateBlanks(buildPrompt("farms", "")));
  assert.equal(hasTemplateBlanks(buildPrompt(" farms ", " Napa ")), false);
  assert.match(buildPrompt(" farms ", " Napa "), /^Find farms in Napa\./);
});
test("preferences round-trip and tolerate corrupt, unavailable or invalid browser storage", () => {
  const data = new Map<string, string>();
  const storage = {
    getItem: (k: string) => data.get(k) ?? null,
    setItem: (k: string, v: string) => data.set(k, v),
  };
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: storage,
  });
  writePreference("section.rubric", true);
  assert.equal(readPreference("section.rubric", false), true);
  data.set("foundry.ui.v2.accessibility", "null");
  assert.equal(readAccessibility().reading, false);
  data.set(
    "foundry.ui.v2.accessibility",
    '{"reading":"true","colour":"invalid"}',
  );
  assert.equal(readAccessibility().reading, false);
  assert.equal(readAccessibility().colour, "standard");
  data.set("foundry.ui.v2.section.rubric", "invalid-json");
  assert.equal(readPreference("section.rubric", false), false);
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    get() {
      throw new Error("blocked");
    },
  });
  assert.doesNotThrow(() => writePreference("section.rubric", true));
  assert.equal(readPreference("section.rubric", false), false);
  delete (globalThis as any).localStorage;
});
