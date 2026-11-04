"""Enforce mode: LGND area tools run inside the prompt's boundary; the model's own request is recorded."""

from types import SimpleNamespace

from agent.hooks import HarnessHooks

RING = {"ring": [{"lat": 0, "lon": 0}, {"lat": 0, "lon": 1}, {"lat": 1, "lon": 1}]}


def hooks(mode="enforce"):
    return HarnessHooks(
        tracer=None,
        writer=None,
        run_id="r",
        tools_available=[],
        limits={"max_steps": 40},
        server_of={
            "search_place_find": "lgnd",
            "toolbox_classifier_apply": "lgnd",
            "search_datasets": "roda",
        },
        search_area={"label": "ZIP 75080", "mode": mode, "lgnd_area": RING},
    )


def event(name, inp):
    return SimpleNamespace(tool_use={"toolUseId": "t1", "name": name, "input": inp})


def test_lgnd_area_is_enforced_and_request_recorded():
    h, ev = (
        hooks(),
        event(
            "search_place_find", {"scope": {"index": "naip", "area": {"lat": 1, "lon": 2, "radius_km": 9}}}
        ),
    )
    h._enforce_area(ev, "t1")
    assert ev.tool_use["input"]["scope"] == {"index": "naip", "area": RING}
    assert h._area_requested["t1"] == {"lat": 1, "lon": 2, "radius_km": 9}
    h2, ev2 = (
        hooks(),
        event("search_place_find", {"scope": {"index": "naip"}}),
    )  # no area: would be "everywhere"
    h2._enforce_area(ev2, "t1")
    assert ev2.tool_use["input"]["scope"]["area"] == RING and h2._area_requested["t1"] is None


def test_left_alone_when_not_applicable():
    for h, ev in [
        (hooks(), event("search_datasets", {"query": "x"})),  # RODA tool
        (hooks(), event("toolbox_classifier_apply", {"classifier": "c", "nodes": ["n1"]})),  # area ignored
        (hooks("observe"), event("search_place_find", {"scope": {"index": "naip"}})),  # observe mode
    ]:
        before = dict(ev.tool_use)
        h._enforce_area(ev, "t1")
        assert ev.tool_use == before and "t1" not in h._area_requested
