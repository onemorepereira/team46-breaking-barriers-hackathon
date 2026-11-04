import { test } from "node:test";
import assert from "node:assert/strict";
import { basePath, candidatesOf, formatScore, reviewPayload } from "./api.ts";
test("API URLs preserve workshop authentication proxy and work on localhost", () => {
  assert.equal(basePath("/proxy/8787/workspace/"), "/proxy/8787");
  assert.equal(basePath("/workspace/"), "");
  assert.equal(basePath("/proxy/8787/workspace"), "\/proxy/8787");
});
test("map candidates use recorded coordinates, deduplicate and keep zero coordinates", () => {
  const point = (c: any) => ({
    geometry: { coordinates: c },
    properties: { claim: "site", ref: "T2", inside: false },
  });
  const view: any = {
    map: {
      claims: {
        features: [
          point([0, 0]),
          point([0, 0]),
          point([12, 24]),
          point([NaN, 0]),
        ],
      },
    },
  };
  const sites = candidatesOf(view);
  assert.equal(sites.length, 2);
  assert.equal(sites[0].lat, 0);
  assert.equal(sites[1].lat, 24);
  assert.equal(sites[0].inside, false);
});
test("missing scores do not become a false zero", () => {
  assert.equal(formatScore(null), "—");
  assert.equal(formatScore(0), "0");
});
test("review payload distinguishes agreeing from suggested scores and requires authors/reasons", () => {
  assert.deepEqual(
    reviewPayload(" Ada ", "grounding", "agree", "0", "note", "T1").criteria,
    { grounding: { agree: true } },
  );
  assert.deepEqual(
    reviewPayload(
      "Ada",
      "grounding",
      "disagree",
      "1",
      "needs evidence",
      "T1, T2",
    ).criteria,
    {
      grounding: {
        agree: false,
        score: 1,
        reason: "needs evidence",
        refs: ["T1", "T2"],
      },
    },
  );
  assert.throws(() => reviewPayload("", "grounding", "agree", "1", "", ""));
  assert.throws(() =>
    reviewPayload("Ada", "grounding", "disagree", "1", "", ""),
  );
  assert.throws(() => reviewPayload("Ada", "", "note", "1", "note", ""));
});
