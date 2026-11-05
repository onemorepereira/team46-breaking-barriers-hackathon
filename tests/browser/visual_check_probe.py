"""Browser probe for docs/visual-check: run against a live console, not collected by pytest.

    uv run harness ui &                      # a console whose archive has a visually checked run
    uv run --no-project --with playwright python tests/browser/visual_check_probe.py RUN_ID [--base URL]

Checks the map caption and marker badges, then the inspector in each state: the checked image loaded (pill,
verdict, credit), still loading, failed to load (with Try again), switched to the agent's image, and at
phone width (no horizontal scroll). Prints one JSON object, and exits 1 if any check fails.
"""

from __future__ import annotations

import argparse
import json
import sys

from playwright.sync_api import Page, Route, sync_playwright


def text(page: Page, selector: str) -> str | None:
    loc = page.locator(selector)
    return loc.first.inner_text() if loc.count() else None


def open_site(page: Page, base: str, run_id: str, *, image_route=None) -> None:
    if image_route:
        page.route("**/api/runs/*/visual/*.jpg*", image_route)  # the retry adds ?retry=1
    page.goto(f"{base}/workspace/?run={run_id}")
    page.wait_for_selector(".evidence-marker", timeout=20_000)
    page.locator(".evidence-marker").first.dispatch_event("click")
    page.wait_for_selector(".tile-inspector", timeout=10_000)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_id")
    ap.add_argument("--base", default="http://127.0.0.1:8787")
    args = ap.parse_args()
    checks: dict[str, bool] = {}
    seen: dict[str, object] = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        errors: list[str] = []

        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("console", lambda m: m.type == "error" and errors.append(m.text))
        open_site(page, args.base, args.run_id)
        page.wait_for_selector(".tile-frame.loaded", timeout=15_000)
        seen.update(
            caption=text(page, ".map-key-caption"),
            badges=page.locator(".visual-badge").all_inner_texts(),
            pill=text(page, ".image-pill"),
            verdict=text(page, ".visual-verdict"),
            credit=text(page, ".tile-credit"),
            switch=page.locator(".image-switch button").all_inner_texts(),
        )
        checks["caption names the check"] = str(seen["caption"]).startswith("Visual")
        checks["markers carry a verdict badge"] = bool(seen["badges"])
        checks["checked image loaded with its pill"] = bool(seen["pill"]) and " m" in str(seen["pill"])
        checks["verdict shown"] = any(w in str(seen["verdict"]) for w in ("Seen", "Not seen", "Can’t tell"))
        checks["credit names the checker"] = str(seen["credit"]).startswith("Checked by")
        page.locator(".image-switch button").nth(1).dispatch_event("click")
        page.wait_for_timeout(300)
        checks["switch shows the agent's image"] = page.locator(".image-pill").count() == 0 and (
            page.locator(".image-switch button").nth(1).get_attribute("aria-pressed") == "true"
        )
        page.close()

        # Loading: hold the image response.
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        open_site(page, args.base, args.run_id, image_route=lambda route: None)  # never answered
        page.wait_for_timeout(500)
        seen["loading"] = text(page, ".tile-frame-note")
        checks["loading state"] = seen["loading"] == "Loading the checked image…"
        page.close()

        # Failed: abort the image request (twice: the inspector retries once on its own).
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        def abort(route: Route) -> None:
            route.abort()

        open_site(page, args.base, args.run_id, image_route=abort)
        page.wait_for_selector(".tile-frame.failed", timeout=10_000)
        seen["failed"] = text(page, ".tile-frame-note")
        checks["failed state offers a retry"] = "couldn’t be loaded" in str(seen["failed"]) and (
            page.locator(".tile-frame-note button").count() == 1
        )
        page.close()

        # Phone width.
        page = browser.new_page(viewport={"width": 375, "height": 812})
        page.on("console", lambda m: m.type == "error" and errors.append(m.text))
        open_site(page, args.base, args.run_id)
        page.wait_for_selector(".tile-frame.loaded", timeout=15_000)
        seen["phone_switch"] = page.locator(".image-switch button").all_inner_texts()
        checks["phone: short switch labels"] = seen["phone_switch"] == ["Checked", "Agent’s"]
        checks["phone: no horizontal scroll"] = not page.evaluate(
            "document.documentElement.scrollWidth > window.innerWidth"
        )
        page.close()
        checks["no console errors"] = not [e for e in errors if "visual" in e or "TypeError" in e]
        seen["console_errors"] = errors[:5]
        browser.close()
    print(json.dumps({"run": args.run_id, "checks": checks, "seen": seen}, ensure_ascii=False, indent=1))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
