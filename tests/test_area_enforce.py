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


def test_a_narrower_area_inside_the_boundary_is_kept():
    """Live run c251934d: a 30 km circle round Paradise, inside the area, was widened back to the area."""
    square = {"type": "Polygon", "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]]}
    h = hooks()
    h.search_area["geometry"] = square
    inside = [
        {"lat": 5, "lon": 5, "radius_km": 30},
        {"west": 2, "east": 3, "south": 2, "north": 3},
        {"ring": [{"lat": 1, "lon": 1}, {"lat": 1, "lon": 2}, {"lat": 2, "lon": 2}]},
    ]
    for area in inside:
        ev = event("search_place_find", {"scope": {"index": "s2", "area": area}})
        h._enforce_area(ev, "t1")
        assert ev.tool_use["input"]["scope"]["area"] == area and "t1" not in h._area_requested
    for area in [
        {"lat": 9.9, "lon": 5, "radius_km": 30},
        {"west": -1, "east": 3, "south": 2, "north": 3},
        {"lat": 5, "lon": 5},
    ]:  # fmt: skip  (reaches outside; a shape we can't read)
        ev = event("search_place_find", {"scope": {"index": "s2", "area": area}})
        h._enforce_area(ev, "t2")
        assert ev.tool_use["input"]["scope"]["area"] == RING and h._area_requested["t2"] == area


def test_narrowing_works_through_the_real_payload_wiring():
    """Live run fdacf7cf: the agent payload has no `geometry` (attach_area drops it), so each narrower circle
    was widened to all of Texas. Build the payload the way the harness does and check the hook keeps it."""
    from harness import area as geo
    from harness import invoke

    square = {"type": "Polygon", "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]]}
    plan = SimpleNamespace(payload={}, manifest={"snapshot": {}})
    invoke.attach_area(
        plan, geo.payload_area(geo.Area("Squareland", "region", "test", square, (5, 5)), "enforce")
    )
    assert "geometry" not in plan.payload["search_area"]  # the payload exactly as the agent receives it
    h = HarnessHooks(
        tracer=None,
        writer=None,
        run_id="r",
        tools_available=[],
        limits={"max_steps": 40},
        server_of={"search_place_find": "lgnd"},
        search_area=plan.payload["search_area"],
    )
    inside = {"lat": 5, "lon": 5, "radius_km": 30}
    ev = event("search_place_find", {"scope": {"index": "naip", "area": inside}})
    h._enforce_area(ev, "t1")
    assert ev.tool_use["input"]["scope"]["area"] == inside and "t1" not in h._area_requested
    outside = {"lat": 9.9, "lon": 5, "radius_km": 100}
    ev = event("search_place_find", {"scope": {"index": "naip", "area": outside}})
    h._enforce_area(ev, "t2")
    assert ev.tool_use["input"]["scope"]["area"] == plan.payload["search_area"]["lgnd_area"]
