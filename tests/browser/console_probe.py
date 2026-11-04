"""Browser probe for docs/console-polish: run against a live console, not collected by pytest.

    uv run harness ui &                      # a console with at least one archived run
    uv run --no-project --with playwright python tests/browser/console_probe.py [RUN_ID] [--base URL]

Waits on events (the map's `idle`, two animation frames of a stable scrollY), not sleeps. Prints one JSON
object, and exits 1 if any check fails.
"""

from __future__ import annotations

import argparse
import json
import sys

from playwright.sync_api import Page, sync_playwright

SETTLE = """() => new Promise((resolve) => {  // scrollY stable for two animation frames
  let last = scrollY, same = 0;
  const tick = () => {
    same = scrollY === last ? same + 1 : 0;
    last = scrollY;
    if (same >= 2) resolve(scrollY); else requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
})"""


# Body text and page background as rgb(), via a canvas (computed styles may use oklch() or color()).
TEXT_COLORS = """() => {
  const ctx = document.createElement("canvas").getContext("2d", { willReadFrequently: true });
  const rgb = (c) => {
    ctx.clearRect(0, 0, 1, 1); ctx.fillStyle = c; ctx.fillRect(0, 0, 1, 1);
    const [r, g, b] = ctx.getImageData(0, 0, 1, 1).data; return `rgb(${r}, ${g}, ${b})`;
  };
  const cs = getComputedStyle(document.body);
  const transparent = cs.backgroundColor === "rgba(0, 0, 0, 0)";
  const bg = transparent ? getComputedStyle(document.documentElement).backgroundColor : cs.backgroundColor;
  return [rgb(cs.color), rgb(bg)];
}"""


def settle(pg: Page) -> float:
    pg.evaluate("window.__foundryIdle()")
    return float(pg.evaluate(SETTLE))


def contained(inner: dict, outer: dict) -> bool:
    return (inner["x"] >= outer["x"] - 1 and inner["y"] >= outer["y"] - 1
            and inner["x"] + inner["width"] <= outer["x"] + outer["width"] + 1
            and inner["y"] + inner["height"] <= outer["y"] + outer["height"] + 1)  # fmt: skip


def luminance(rgb: tuple[int, int, int]) -> float:
    def ch(c: int) -> float:
        x = c / 255
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4

    r, g, b = (ch(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(fg: str, bg: str) -> float:
    def parse(c: str) -> tuple[int, int, int]:
        v = [int(float(x)) for x in c[c.index("(") + 1 : c.index(")")].split(",")[:3]]
        return v[0], v[1], v[2]

    a, b = sorted((luminance(parse(fg)), luminance(parse(bg))), reverse=True)
    return round((a + 0.05) / (b + 0.05), 2)


def probe(base: str, run_id: str, width: int, height: int) -> dict:
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": width, "height": height})
        errors: list[str] = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(f"{base}/runs/{run_id}")
        pg.wait_for_function("document.getElementById('k-score').textContent.trim() !== '—'", timeout=30000)
        out: dict = {"viewport": [width, height], "theme": pg.get_attribute("html", "data-bs-theme")}
        body = pg.evaluate(TEXT_COLORS)
        out["body_contrast"] = contrast(body[0], body[1])
        pg.evaluate("document.getElementById('map').scrollIntoView({block: 'center'})")
        y = settle(pg)
        clicks = []
        tiles = pg.query_selector_all("#tiles .foundry-tile")
        for i in [0, min(5, len(tiles) - 1), min(12, len(tiles) - 1)]:
            tiles[i].scroll_into_view_if_needed()  # click() would scroll too; keep it out of the measure
            y = settle(pg)
            tiles[i].click()
            y2 = settle(pg)
            panel = pg.query_selector("#detail").bounding_box()
            mapbox = pg.query_selector("#map").bounding_box()
            clicks.append(
                {"tile": i, "page_scrolled": y2 - y, "panel_in_map": bool(panel and contained(panel, mapbox))}
            )
            y = y2
        out["tile_clicks"] = clicks
        out["map_padding_after"] = pg.evaluate("window.__foundryPadding()")
        out["focus_in_panel"] = pg.evaluate(
            "document.activeElement && document.activeElement.id === 'detail-close'"
        )
        pg.keyboard.press("Escape")
        y2 = settle(pg)
        back_on_tile = pg.evaluate("document.activeElement.classList.contains('foundry-tile')")
        out["esc"] = {
            "closed": pg.is_hidden("#detail"),
            "page_scrolled": y2 - y,
            "focus_back_on_tile": back_on_tile,
        }
        y = y2
        # a step link from the panel: the page stays put (the list scrolls), or a toast offers the jump
        pg.query_selector_all("#tiles .foundry-tile")[0].click()
        y = settle(pg)
        link = pg.query_selector("#detail .ref-link")
        if link:
            list_top0 = pg.evaluate("document.getElementById('timeline').scrollTop")
            link.click()
            y2 = settle(pg)
            list_moved = pg.evaluate("document.getElementById('timeline').scrollTop") != list_top0
            out["ref_link"] = {
                "page_scrolled": y2 - y,
                "toast": pg.is_visible("#toast"),
                "list_scrolled": list_moved,
            }
        # the wheel over the map scrolls the page (cooperative gestures)
        pg.evaluate("window.scrollTo(0, 0)")
        settle(pg)
        mb = pg.query_selector("#map").bounding_box()
        pg.evaluate(f"window.scrollTo(0, {mb['y'] - 100})")
        y = settle(pg)
        mb = pg.query_selector("#map").bounding_box()
        pg.mouse.move(mb["x"] + mb["width"] / 3, mb["y"] + 60)
        pg.mouse.wheel(0, 400)
        y2 = settle(pg)
        out["wheel_over_map_page_scrolled"] = y2 - y
        out["page_errors"] = errors
        b.close()
    return out


def failures(r: dict) -> list[str]:
    bad = []
    if r["theme"] != "dark":
        bad.append("not dark")
    if r["body_contrast"] < 4.5:
        bad.append(f"body contrast {r['body_contrast']}")
    for c in r["tile_clicks"]:
        if c["page_scrolled"] or not c["panel_in_map"]:
            bad.append(f"tile click {c}")
    if r["map_padding_after"] and any(r["map_padding_after"].values()):
        bad.append(f"persistent map padding {r['map_padding_after']}")
    if (
        not r["focus_in_panel"]
        or not r["esc"]["closed"]
        or r["esc"]["page_scrolled"]
        or not r["esc"]["focus_back_on_tile"]
    ):
        bad.append(f"esc/focus {r['esc']}")
    ref = r.get("ref_link")
    if ref and (ref["page_scrolled"] or not (ref["list_scrolled"] or ref["toast"])):
        bad.append(f"ref link {ref}")
    if r["wheel_over_map_page_scrolled"] <= 0:
        bad.append("wheel over the map didn't scroll the page")
    if r["page_errors"]:
        bad.append(f"page errors {r['page_errors']}")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_id", nargs="?", default="a9a69e76-f4ae-49a8-b03c-e88682cdb60b")
    ap.add_argument("--base", default="http://127.0.0.1:8787")
    args = ap.parse_args()
    results = [probe(args.base, args.run_id, w, h) for w, h in [(1366, 860), (390, 900)]]
    bad = [f"{r['viewport']}: {f}" for r in results for f in failures(r)]
    print(json.dumps({"results": results, "failures": bad}, indent=1))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
