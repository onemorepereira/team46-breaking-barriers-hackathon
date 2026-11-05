"""Quick feedback is archived against the score seen, never applied as a numeric review."""

import json

from tests.test_feedback import api


def test_quick_votes_and_optional_comments_survive_reload_without_changing_scores(tmp_path, monkeypatch):
    client, run = api(
        tmp_path, monkeypatch, lambda *_: (_ for _ in ()).throw(AssertionError("no model calls"))
    )
    url = f"/api/runs/{run.run_id}"
    before = client.get(url).json()["scorecard"]
    body = {"judged_at": before["judged_at"], "target": "overall", "vote": "up"}
    up = client.post(f"{url}/reactions", json=body)
    assert up.status_code == 200
    assert up.json()["score"] == before["overall"]
    down = client.post(f"{url}/reactions", json={**body, "target": "efficiency", "vote": "down"}).json()
    assert down["comment"] == ""  # optional, no suggested rating or reason required
    comment = client.put(f"{url}/reactions/{down['id']}", json={"comment": " Check step T1. "})
    assert comment.status_code == 200 and comment.json()["comment"] == "Check step T1."
    records = client.get(f"{url}/reactions").json()["reactions"]
    assert {r["id"] for r in records} == {up.json()["id"], down["id"]}
    assert all(r["current"] for r in records)
    assert client.get(url).json()["scorecard"] == before
    assert client.get(f"{url}/reviews").json()["reviews"] == []  # no fabricated human rubric scores
    assert len(list((tmp_path / "deploy/feedback/reactions" / run.run_id).glob("*.json"))) == 2


def test_reactions_validate_targets_values_comments_and_stale_judgements(tmp_path, monkeypatch):
    client, run = api(tmp_path, monkeypatch, lambda *_: "")
    url = f"/api/runs/{run.run_id}/reactions"
    card = client.get(f"/api/runs/{run.run_id}").json()["scorecard"]
    body = {"judged_at": card["judged_at"], "target": "overall", "vote": "down"}
    assert client.post(url, json={**body, "target": "imaginary"}).status_code == 400
    assert client.post(url, json={**body, "vote": "other"}).status_code == 422
    assert client.post(url, json={**body, "judged_at": "old"}).status_code == 409
    assert client.put(f"{url}/not-a-record", json={"comment": "x"}).status_code == 404
    up = client.post(url, json={**body, "vote": "up"}).json()
    assert client.put(f"{url}/{up['id']}", json={"comment": "x"}).status_code == 400
    down = client.post(url, json=body).json()
    assert client.put(f"{url}/{down['id']}", json={"comment": "x" * 2001}).status_code == 422
    jd = run.judgement
    jd["judged_at"] = "new-judgement"
    run.store.write_text(f"runs/{run.run_id}/judgement.json", json.dumps(jd))
    assert client.post(url, json=body).status_code == 409
    assert not any(r["current"] for r in client.get(url).json()["reactions"])
    # A later comment stays tied to its original judgement, never the new one.
    assert (
        client.put(f"{url}/{down['id']}", json={"comment": "Earlier score"}).json()["judged_at"]
        == body["judged_at"]
    )


def test_not_scored_or_live_run_cannot_accept_score_feedback(tmp_path, monkeypatch):
    from harness.web import live

    client, run = api(tmp_path, monkeypatch, lambda *_: "")
    card = client.get(f"/api/runs/{run.run_id}").json()["scorecard"]
    body = {"judged_at": card["judged_at"], "target": "overall", "vote": "up"}
    state = live.RunState(run.run_id, tmp_path / "live.jsonl")
    monkeypatch.setitem(live.RUNS, run.run_id, state)
    assert client.post(f"/api/runs/{run.run_id}/reactions", json=body).status_code == 409
    state.done = True
    jd = run.judgement
    jd["passes"] = []
    run.store.write_text(f"runs/{run.run_id}/judgement.json", json.dumps(jd))
    assert client.post(f"/api/runs/{run.run_id}/reactions", json=body).status_code == 409
