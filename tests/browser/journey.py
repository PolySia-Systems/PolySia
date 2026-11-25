"""Exercise the built application in Chromium against a short-lived local workspace."""

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.request import urlopen

from playwright.sync_api import Browser, Locator, Page, expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]


@contextmanager
def isolated_server(directory: Path):
    # Force an offline provider only in this child so account failure tests are
    # deterministic. All tested browser requests still reach the real local API.
    env = {
        **os.environ,
        "POLYSIA_DB": str(directory / "workspace.sqlite3"),
        "https_proxy": "http://127.0.0.1:1",
        "no_proxy": "localhost,127.0.0.1",
    }
    log = directory / "server.log"
    with log.open("w") as output:
        server = subprocess.Popen(
            [sys.executable, "-m", "apps.server", "--port", "0"],
            cwd=ROOT,
            env=env,
            stdout=output,
            stderr=subprocess.STDOUT,
        )
        try:
            for _ in range(100):
                if server.poll() is not None:
                    raise RuntimeError(f"Application exited during startup.\n{log.read_text()}")
                address = re.search(r"http://127[.]0[.]0[.]1:[0-9]+", log.read_text())
                if not address:
                    time.sleep(0.1)
                    continue
                origin = address.group()
                try:
                    with urlopen(f"{origin}/api/v1/health", timeout=1) as reply:
                        if reply.status == 200:
                            break
                except (URLError, TimeoutError):
                    time.sleep(0.1)
            else:
                raise RuntimeError(f"Application did not become healthy.\n{log.read_text()}")
            yield origin
        finally:
            server.terminate()
            server.wait(timeout=10)


def capture(page: Page, output: Path | None, name: str):
    if output is not None:
        output.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=output / f"{name}.png", full_page=True, animations="disabled")


def check_width(page: Page):
    sizes = page.evaluate("() => [document.documentElement.scrollWidth, innerWidth]")
    assert sizes[0] <= sizes[1], f"Content overflowed the viewport: {sizes}"


def tab_to(page: Page, control: Locator):
    """Reach the control by keyboard, even with other tab stops before it."""
    expect(control).to_be_visible()
    for _ in range(80):
        if control.evaluate("(el) => el === document.activeElement"):
            return
        page.keyboard.press("Tab")
    raise AssertionError(f"Could not reach {control} from the tab order")


def exercise(browser: Browser, origin: str, output: Path | None):
    page = browser.new_page(viewport={"width": 1440, "height": 1000}, reduced_motion="reduce")
    page.set_default_timeout(6000)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(origin)
    search = page.get_by_label("Search leaders")
    expect(search).to_be_visible()
    check_width(page)
    capture(page, output, "discovery-desktop")
    atlas_save = page.get_by_role("button", name="Save Atlas Meridian to shortlist")
    atlas_save.click()
    page.get_by_role("button", name="Save Juniper Lane to shortlist").click()
    page.get_by_role("link", name="Compare", exact=True).click()
    expect(page.get_by_role("heading", name="Shortlisted leaders")).to_be_visible()
    expect(page.get_by_text("Atlas Meridian", exact=True).filter(visible=True)).to_be_visible()
    expect(page.get_by_text("Juniper Lane", exact=True).filter(visible=True)).to_be_visible()
    page.go_back()
    tab_to(page, search)
    page.keyboard.type("no such leader")
    expect(page.get_by_text(re.compile("no (matching |saved )?leaders", re.I)).first).to_be_visible()
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.type("Atlas")
    leader = page.get_by_role("link", name=re.compile("^Atlas Meridian"))
    tab_to(page, leader)
    page.keyboard.press("Enter")
    expect(page.get_by_role("heading", name="Atlas Meridian")).to_be_visible()
    capture(page, output, "leader-desktop")
    page.go_back()
    expect(search).to_have_value("Atlas")
    leader.click()
    page.get_by_text("Preview shadow", exact=True).click()
    page.get_by_role("button", name="Start shadow", exact=True).click()
    step = page.get_by_role("button", name="Observe next signal", exact=True)
    expect(step).to_be_enabled()

    def run_state():
        reply = page.request.get(origin + "/api/v1/workspace")
        assert reply.ok, reply.status
        return reply.json()["run"]

    run = run_state()
    assert run["leader_id"] == "atlas" and run["source"] == "scenario"
    assert run["cursor"] == 0 and run["events"] == []
    step.click()
    expect(page.get_by_text(re.compile("^BUY · filled$", re.I)).first).to_be_visible()
    filled = run_state()
    assert filled["cursor"] == 1 and int(filled["quantity"]) > 0
    step.click()
    expect(page.get_by_text("BUY · partial", exact=True)).to_be_visible()
    partial = run_state()
    assert int(partial["quantity"]) > int(filled["quantity"])
    tab_to(page, page.get_by_role("button", name="Pause new entries", exact=True))
    page.keyboard.press("Enter")
    expect(page.get_by_role("button", name=re.compile("resume", re.I))).to_be_visible()
    page.reload()
    expect(page.get_by_role("button", name=re.compile("resume", re.I))).to_be_visible()
    step.click()
    expect(page.get_by_text(re.compile("^BUY · skipped$", re.I)).first).to_be_visible()
    assert run_state()["quantity"] == partial["quantity"]
    page.get_by_role("button", name="Stop run", exact=True).click()
    expect(page.get_by_text(re.compile("^Stopped$", re.I)).first).to_be_visible()
    stopped = run_state()
    assert stopped["status"] == "stopped" and stopped["quantity"] == partial["quantity"]
    expect(page.get_by_text(stopped["quantity"] + " shares", exact=True)).to_be_visible()
    with page.expect_download() as event:
        page.get_by_role("link", name=re.compile("Export Atlas Meridian run")).click()
    download = event.value
    assert download.failure() is None
    exported = json.loads(download.path().read_text())
    assert exported == stopped, "Downloaded evidence differs from the persisted replay"
    capture(page, output, "replay-stopped")

    page.get_by_role("link", name="Accounts", exact=True).click()
    wallet = page.get_by_role("textbox", name="Public wallet address")
    wallet.fill("unknown")
    page.get_by_role("button", name="Watch account", exact=True).click()
    assert wallet.evaluate("el => el.validity.patternMismatch")
    wallet.fill("0x" + "1" * 40)
    page.get_by_role("button", name="Watch account", exact=True).click()
    expect(page.get_by_text("Current positions unknown", exact=True)).to_be_visible()
    expect(page.get_by_text("Public read only", exact=True)).to_be_visible()
    page.get_by_role("button", name="Remove watch", exact=True).click()
    expect(page.get_by_role("heading", name="Account scope")).to_be_visible()

    page.get_by_role("link", name="Settings", exact=True).click()
    dark = page.get_by_role("button", name="Dark", exact=True)
    dark.click()
    expect(dark).to_have_attribute("aria-pressed", "true")
    page.reload()
    expect(dark).to_have_attribute("aria-pressed", "true")
    page.get_by_role("link", name="Discover", exact=True).click()
    search.fill("")
    capture(page, output, "discovery-dark")
    page.set_viewport_size({"width": 390, "height": 844})
    check_width(page)
    capture(page, output, "discovery-mobile")
    leader.click()
    expect(page.get_by_role("heading", name="Atlas Meridian")).to_be_visible()
    check_width(page)
    capture(page, output, "leader-mobile")
    assert not errors, f"Uncaught browser errors: {errors}"
    page.close()
    print("Passed discovery, replay, stopped exposure, account outage, persistent theme and mobile layout.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshots", type=Path, help="Write rendered evidence in this directory.")
    options = parser.parse_args()
    if not (ROOT / "apps/web/dist/index.html").is_file():
        sys.exit("Build the web application before running the browser journey.")
    with tempfile.TemporaryDirectory(prefix="polysia-browser-") as temp, sync_playwright() as pw:
        with isolated_server(Path(temp)) as origin:
            chromium = os.environ.get("CHROMIUM_PATH") or shutil.which("chromium")
            browser = pw.chromium.launch(executable_path=chromium)
            try:
                exercise(browser, origin, options.screenshots)
            finally:
                browser.close()


if __name__ == "__main__":
    main()
