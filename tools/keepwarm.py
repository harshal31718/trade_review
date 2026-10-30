"""Open the deployed app so Streamlit Community Cloud does not put it to sleep.

Waits for the app title. If the sleeping page appears, clicks the wake button and
waits again. Exits non-zero if the app title never shows up.
Env: APP_URL (required), KEEPWARM_CHANNEL (optional, e.g. "chrome" to use installed Chrome).
"""
import os
import sys
import time

from playwright.sync_api import sync_playwright

TITLE = "Post-trade review"
WAKE_TEXT = "get this app back up"
IFRAME = 'iframe[title="streamlitApp"]'
WAIT_SECONDS = 150
POLL_SECONDS = 3


def title_visible(page) -> bool:
    """The app renders in the page itself or, on Community Cloud, inside an iframe."""
    for scope in (page, page.frame_locator(IFRAME)):
        if scope.get_by_role("heading", name=TITLE).count():
            return True
    return False


def wait_for_title(page, seconds: int) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if title_visible(page):
            return True
        time.sleep(POLL_SECONDS)
    return False


def main() -> int:
    url = os.environ.get("APP_URL", "").strip()
    if not url:
        print("APP_URL is not set (add it as a repository variable).", file=sys.stderr)
        return 2
    with sync_playwright() as p:
        channel = os.environ.get("KEEPWARM_CHANNEL") or None
        browser = p.chromium.launch(headless=True, channel=channel)
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(5_000)
        wake = page.get_by_text(WAKE_TEXT, exact=False)
        if wake.count():
            print("App was asleep; clicking the wake button.")
            wake.first.click()
        ok = wait_for_title(page, WAIT_SECONDS)
        browser.close()
    print("App is up." if ok else f"App title '{TITLE}' not found after {WAIT_SECONDS}s.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
