"""Exercise the built application in Chromium against a short-lived local workspace."""

import argparse
import hashlib
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
from urllib.parse import parse_qs, urlsplit
from urllib.error import URLError
from urllib.request import urlopen

from playwright.sync_api import Browser, Locator, Page, Route, expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]


@contextmanager
def isolated_server(directory: Path):
    # Force an offline provider only in this child so account failure tests are
    # deterministic. All tested browser requests still reach the real local API.
    env = {
        **os.environ,
        "POLYSIA_DB": str(directory / "installation/data/workspace.sqlite3"),
        "https_proxy": "http://127.0.0.1:1",
        "no_proxy": "localhost,127.0.0.1",
    }
    bundle = ROOT / "dist/polysia.pyz"
    expected = hashlib.sha256(bundle.read_bytes()).hexdigest()
    log = directory / "server.log"
    with log.open("w") as output:
        server = subprocess.Popen(
            [sys.executable, str(bundle), "--start", "--prefix", str(directory / "installation"), "--port", "0"],
            cwd=directory,
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
                        if reply.status == 200 and json.load(reply)["artifactSha256"] == expected:
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
        scroll = page.evaluate("window.scrollY")
        page.evaluate("window.scrollTo(0, 0)")
        page.screenshot(path=output / f"{name}.png", full_page=True, animations="disabled")
        page.evaluate("y => window.scrollTo(0, y)", scroll)


def check_width(page: Page):
    sizes = page.evaluate("() => [document.documentElement.scrollWidth, innerWidth]")
    assert sizes[0] <= sizes[1], f"Content overflowed the viewport: {sizes}"


def check_accent_contrast(page: Page):
    tokens = page.evaluate("""() => Object.fromEntries(['accent', 'accent-bg', 'bg', 'panel', 'side', 'soft']
        .map(name => [name, getComputedStyle(document.documentElement).getPropertyValue('--' + name).trim()]))""")

    def luminance(color):
        digits = color.removeprefix("#")
        if len(digits) == 3:
            digits = "".join(digit * 2 for digit in digits)
        channels = [int(digits[i:i+2], 16) / 255 for i in (0, 2, 4)]
        linear = [value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4 for value in channels]
        return sum(a * b for a, b in zip(linear, (.2126, .7152, .0722)))

    for key in ("accent-bg", "bg", "panel", "side", "soft"):
        low, high = sorted((luminance(tokens["accent"]), luminance(tokens[key])))
        assert (high + .05) / (low + .05) >= 4.5, (key, tokens)


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
    reads = []
    page.on("request", lambda request: reads.append(request.url))
    page.goto(origin)
    search = page.get_by_label("Search leaders")
    expect(search).to_be_visible()
    check_width(page)
    for title in ("Research public wallets", "Try a shadow replay"):
        expect(page.get_by_role("link", name=re.compile(title))).to_be_visible()
    assert not any("/api/v1/public/" in url for url in reads)
    capture(page, output, "discovery-desktop")
    page.get_by_role("link", name=re.compile("Try a shadow replay")).click()
    expect(page.get_by_role("button", name="Start shadow", exact=True)).to_be_visible()
    page.go_back()
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
    page.goto(origin)
    expect(page.get_by_role("heading", name="Scenario replays", exact=True)).to_be_visible()
    expect(page.get_by_text(re.compile("2 filled or partially filled · 1 skipped"))).to_be_visible()
    expect(page.get_by_text("Unavailable", exact=True).first).to_be_visible()
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
    expect(page.get_by_role("link", name="Set up public shadow run")).to_have_attribute("href", "#/paper/new?wallet=0x" + "1" * 40)
    page.get_by_label("Wallet name (optional)").fill("First wallet")
    page.get_by_role("button", name="Save wallet", exact=True).click()
    saved = page.get_by_role("combobox", name="Saved wallets")
    expect(saved).to_have_value("0x" + "1" * 40)
    cash = page.get_by_role("region", name="Cash balance")
    cash_sample = {"address": "0x" + "1" * 40, "status": "available", "value": "0.000001", "unit": "pUSD",
                   "checkedAt": "2026-11-25T12:00:00Z", "observedAt": "2026-11-25T12:00:00Z",
                   "source": "Polygon", "message": "Open orders may reserve part of this balance."}
    page.route("**/api/v1/public/traders/*/cash", lambda route: route.fulfill(json=cash_sample))
    cash.get_by_role("button", name="Read cash balance").click()
    expect(cash.get_by_text("0.000001 pUSD")).to_be_visible()
    cash_sample.update(status="unavailable", value=None, observedAt=None, message="Could not verify the balance.")
    cash.get_by_role("button", name="Refresh cash balance").click()
    expect(cash.get_by_text("Balance unavailable")).to_be_visible()
    expect(cash.get_by_text("0.000001 pUSD")).to_have_count(0)
    # An old wallet's slow value read must never appear in a replacement watch.
    delayed_value = []
    page.route("**/api/v1/public/traders/*/value", lambda route: delayed_value.append(route))
    holdings = page.get_by_role("region", name="Holdings value")
    assert not delayed_value
    with page.expect_request("**/api/v1/public/traders/*/value"):
        holdings.get_by_role("button", name="Load holdings value").click()
    wallet.fill("0x" + "2" * 40)
    page.get_by_role("button", name="Replace watched address").click()
    expect(holdings.get_by_role("button", name="Load holdings value")).to_be_enabled()
    expect(cash.get_by_role("button", name="Read cash balance")).to_be_enabled()
    delayed_value[0].fulfill(json={"address": "0x" + "1" * 40, "status": "available", "value": "987.1254",
                                   "unit": "USDC", "source": "Polymarket Data API v2", "message": "Old wallet.",
                                   "checkedAt": "2026-11-25T12:00:00Z", "observedAt": "2026-11-25T12:00:00Z"})
    expect(holdings.get_by_text("987.1254 USDC")).to_have_count(0)
    expect(page.get_by_text("Current positions unknown", exact=True)).to_be_visible()
    page.get_by_label("Wallet name (optional)").fill("Second wallet")
    page.get_by_role("button", name="Save wallet", exact=True).click()
    expect(saved).to_have_value("0x" + "2" * 40)
    page.reload()
    expect(saved).to_have_value("0x" + "2" * 40)
    saved.select_option("0x" + "1" * 40)
    expect(wallet).to_have_value("0x" + "1" * 40)
    expect(cash.get_by_role("button", name="Read cash balance")).to_be_enabled()
    expect(cash.get_by_text("0.000001 pUSD")).to_have_count(0)
    page.get_by_role("button", name="Remove from saved wallets", exact=True).click()
    expect(saved.get_by_role("option", name="First wallet", exact=False)).to_have_count(0)
    saved.select_option("0x" + "2" * 40)
    expect(wallet).to_have_value("0x" + "2" * 40)
    page.get_by_role("button", name="Remove from saved wallets", exact=True).click()
    expect(saved).to_have_count(0)
    page.get_by_role("button", name="Remove watch", exact=True).click()
    expect(page.get_by_role("heading", name="Account scope")).to_be_visible()
    expect(holdings).to_have_count(0)

    page.get_by_role("link", name="Notifications", exact=True).click()
    expect(page.get_by_text("No observation warnings have been recorded.")).to_be_visible()
    page.get_by_label("Show notifications").select_option("trades")
    expect(page.get_by_text("No simulated buys or sales have been recorded.")).to_be_visible()
    page.get_by_role("link", name="Settings", exact=True).click()
    forest = page.get_by_role("button", name="Forest (default)", exact=True)
    ocean = page.get_by_role("button", name="Ocean", exact=True)
    root = page.locator("html")
    expect(forest).to_have_attribute("aria-pressed", "true")
    check_accent_contrast(page)
    ocean.click()
    expect(root).to_have_attribute("data-accent", "ocean")
    check_accent_contrast(page)
    page.get_by_role("link", name="View discovery", exact=True).click()
    expect(page.get_by_label("Search leaders")).to_be_visible()
    expect(root).to_have_attribute("data-accent", "ocean")
    assert page.request.get(origin + "/api/v1/workspace").json()["accent"] == {"preset": "forest", "revision": 0}
    page.get_by_role("link", name="Return to Settings", exact=True).click()
    page.get_by_role("button", name="Discard preview").click()
    expect(root).to_have_attribute("data-accent", "forest")
    dark = page.get_by_role("button", name="Dark", exact=True)
    dark.click()
    expect(dark).to_have_attribute("aria-pressed", "true")
    check_accent_contrast(page)
    ocean.click()
    expect(root).to_have_attribute("data-accent", "ocean")
    check_accent_contrast(page)
    page.get_by_role("button", name="Publish accent").click()
    expect(page.get_by_text("Workspace accent published.", exact=True)).to_be_visible()
    page.reload()
    expect(dark).to_have_attribute("aria-pressed", "true")
    expect(ocean).to_have_attribute("aria-pressed", "true")
    forest.click()
    page.get_by_role("button", name="Publish accent").click()
    expect(page.get_by_text("Published accent · forest · Revision 2")).to_be_visible()
    page.get_by_role("link", name="System status", exact=True).click()
    expect(page.get_by_text("Local loopback", exact=True)).to_be_visible()
    capture(page, output, "system-status")
    page.get_by_role("link", name="Discover", exact=True).click()
    search.fill("")
    capture(page, output, "discovery-dark")
    page.set_viewport_size({"width": 390, "height": 844})
    check_width(page)
    opener = page.get_by_role("button", name="Open navigation")
    opener.click()
    dialog = page.get_by_role("dialog", name="Workspace menu")
    expect(dialog.get_by_role("link", name="Discover", exact=True)).to_be_focused()
    page.keyboard.press("Escape")
    expect(dialog).to_have_count(0)
    expect(opener).to_be_focused()
    capture(page, output, "discovery-mobile")
    leader.click()
    expect(page.get_by_role("heading", name="Atlas Meridian")).to_be_visible()
    check_width(page)
    capture(page, output, "leader-mobile")
    assert not errors, f"Uncaught browser errors: {errors}"
    page.close()
    print("Passed discovery, replay, stopped exposure, account outage, persistent theme and mobile layout.")
    return stopped


def assisted_budget_journey(browser: Browser, origin: str, output: Path | None):
    page = browser.new_page(viewport={"width": 390, "height": 844})
    page.goto(origin + "/#/discover")
    page.get_by_text("Find leaders for my simulated budget", exact=True).click()
    budget = page.get_by_label("Simulated budget (USD)")
    cap = page.get_by_label("Maximum per buy (USD)")
    budget.fill("1000")
    cap.fill("1000")
    page.get_by_role("button", name="Check budget").click()
    expect(page.get_by_role("heading", name="No complete buys observed at these limits")).to_be_visible()
    expect(budget).to_have_value("1000")
    expect(page.get_by_text("Book unavailable for 1 skipped buy.").first).to_be_visible()
    budget.fill("500.00")
    cap.fill("500.00")
    page.get_by_role("button", name="Check budget").click()
    expect(page.get_by_role("heading", name="4 scenarios matched")).to_be_visible()
    check_width(page)
    capture(page, output, "budget-finder-mobile")
    page.get_by_role("link", name="Preview Atlas Meridian at this budget").click()
    expect(page.get_by_label("Allocation (USD)", exact=False)).to_have_value("500.00")
    expect(page.get_by_label("Per-order cap (USD)", exact=False)).to_have_value("500.00")
    page.reload()
    expect(page.get_by_label("Allocation (USD)", exact=False)).to_have_value("500.00")
    page.get_by_role("button", name="Start shadow", exact=True).click()
    expect(page.get_by_role("button", name="Observe next signal", exact=True)).to_be_visible()
    run = page.request.get(origin + "/api/v1/workspace").json()["run"]
    assert (run["leader_id"], run["capital"], run["order_size"], run["cursor"]) == ("atlas", "500.00", "500.00", 0)
    history = page.get_by_role("region", name="Run history")
    old = history.get_by_role("link", name=re.compile("Review Atlas Meridian run"))
    expect(history.get_by_text("Unavailable", exact=True)).to_be_visible()
    old_href = old.get_attribute("href")
    tab_to(page, old)
    page.keyboard.press("Enter")
    expect(page.get_by_role("heading", name="Saved replay")).to_be_visible()
    page.reload()
    expect(page.get_by_text("BUY · skipped", exact=True)).to_be_visible()
    expect(page.get_by_role("button", name="Observe next signal")).to_have_count(0)
    expect(page.get_by_role("button", name="Stop run")).to_have_count(0)
    previous = page.request.get(origin + "/api/v1/runs/" + old_href.split("/")[-1]).json()
    assert previous["id"] != run["id"] and previous["status"] == "stopped"
    assert previous["marked_net_result"] is None
    expect(page.get_by_text(previous["quantity"] + " shares", exact=True)).to_be_visible()
    with page.expect_download() as event:
        page.get_by_role("link", name="Export run evidence").click()
    assert json.loads(event.value.path().read_text()) == previous
    check_width(page)
    capture(page, output, "saved-replay-mobile")
    page.get_by_role("link", name="Back to scenario replays").click()
    expect(page.get_by_role("button", name="Observe next signal")).to_be_enabled()
    assert page.request.get(origin + "/api/v1/workspace").json()["run"] == run
    page.close()
    print("Passed saved replay review across reload, export, and return to a distinct active run.")
    print("Passed budget comparison, missing depth, no-match, and exact policy handoff to replay.")


def public_rankings_journey(browser: Browser, origin: str, output: Path | None):
    """Mock only public reads; local account state and navigation use the application."""
    page = browser.new_page(viewport={"width": 1240, "height": 900})
    page.set_default_timeout(6000)
    wallet = "0x" + "36" * 20
    other = "0x" + "42" * 20
    unranked = "0x" + "ab" * 20
    stamp = "2026-11-25T12:00:00Z"
    pending = []
    delayed_period = None
    requested_periods = []
    fixture_state = "available"
    cursor_reads = []
    fail_next_page = True

    def ranking_payload(period, state):
        leaders = []
        if state == "available":
            leaders = [
                {"rank": 1, "address": wallet, "name": "Fixture Lumen", "pnl": "1830.54", "volumeShares": "19348.35"},
                {"rank": 2, "address": other, "name": "Fixture Stone", "pnl": "720", "volumeShares": "8904"},
                {"rank": 3, "address": "0x" + "53" * 20, "name": "Fixture Ash", "pnl": "120", "volumeShares": "632"},
            ]
        return {
            "period": period, "status": "unavailable" if state == "unavailable" else "available",
            "checkedAt": stamp, "observedAt": stamp if state != "unavailable" else None,
            "source": "Polymarket Data API v2 · trader leaderboard",
            "message": "Fixture rankings unavailable" if state == "unavailable" else "Public ranking fixture",
            "complete": state == "empty", "nextCursor": "next+/=" if state == "available" else None, "leaders": leaders,
        }

    def rankings(route: Route):
        query = parse_qs(urlsplit(route.request.url).query)
        period = query.get("period", ["month"])[0]
        requested_periods.append(period)
        if "cursor" in query:
            cursor_reads.append(query["cursor"][0])
            assert query["cursor"] == ["next+/="]
            if fail_next_page:
                route.fulfill(status=503, json={"error": "Next page temporarily unavailable."})
            else:
                more = ranking_payload(period, "available")
                row = {**more["leaders"][1], "rank": 4, "name": "Fixture Dune", "address": "0x" + "64" * 20}
                route.fulfill(json={**more, "leaders": [row], "complete": True, "nextCursor": None})
        elif period == delayed_period:
            pending.append(route)
        else:
            route.fulfill(json=ranking_payload(period, fixture_state))

    profile_reads = []
    compare_case = "shared"
    market_id = "0x" + "cd" * 32

    def profile(route: Route):
        address = urlsplit(route.request.url).path.rsplit("/", 1)[1]
        assert route.request.method == "GET" and address in (wallet, other, unranked)
        profile_reads.append(address)
        position = {"market": "Fixture opening day?", "conditionId": market_id, "outcome": "Yes", "shares": "7.125", "status": "OPEN"}
        rows = [position]
        if address == other:
            if compare_case == "error":
                route.fulfill(status=503, json={"error": "Position service unavailable"})
                return
            rows = [{**position, "outcome": "No"}, {**position, "shares": "1"}]
            if compare_case in ("zero", "partial"):
                rows = [{**position, "status": "REDEEMABLE"}, {**position, "shares": "0"},
                        {**position, "conditionId": "0x" + "ab" * 32}]
            if compare_case == "unknown-identity":
                rows = [{key: value for key, value in position.items() if key != "conditionId"}]
        complete = address == wallet or compare_case not in ("partial", "partial-shared")
        route.fulfill(json={
            "address": address, "status": "available", "checkedAt": stamp, "observedAt": stamp,
            "source": "Polymarket Data API v2 · open positions", "complete": complete,
            "nextCursor": None if complete else "more", "message": "Open ordinary positions",
            "positions": rows,
        })

    history_reads = []
    history_points = [
        {"time": 1795046400, "value": "100.000000001"},
        {"time": 1795132800, "value": None},
        {"time": 1795219200, "value": "140.000000001"},
    ]

    def history(route: Route):
        history_reads.append(route.request.url)
        route.fulfill(json={"status": "available", "checkedAt": stamp, "points": history_points,
                            "address": wallet, "sourceGrid": "1d", "message": "Polymarket cumulative realized P/L."})

    page.route("**/api/v1/public/traders/*/history", history)
    value_reads = []

    def read_value(route: Route):
        address = urlsplit(route.request.url).path.split("/")[-2]
        assert address == wallet and route.request.method == "GET"
        value_reads.append(address)
        first = len(value_reads) == 1
        route.fulfill(json={"address": wallet, "status": "available" if first else "unavailable",
                            "value": "1375.0421" if first else None, "unit": "USDC",
                            "source": "Polymarket Data API v2 · holdings value", "checkedAt": stamp,
                            "observedAt": stamp if first else None,
                            "message": "Single-market holdings at marked value and unresolved combos at cost."
                            if first else "The provider holdings value is unavailable."})

    page.route("**/api/v1/public/traders/*/value", read_value)
    observation_calls = []
    sample_time = 1_795_600_000
    receipt = {
        "schemaVersion": 1, "wallet": wallet, "status": "observed",
        "windowStartSeconds": sample_time, "windowEndSeconds": sample_time + 4,
        "reason": "Browser fixture of an observed public quote.",
        "event": {"eventTimeSeconds": sample_time + 1, "side": "BUY", "shares": "3.2", "price": "0.84", "fillId": None},
        "book": {"sourceTimeMs": (sample_time + 6) * 1000, "askLevelCount": 1,
                 "bestAsks": [{"price": "0.86", "shares": "4.2"}]},
    }

    def observation(route: Route):
        assert route.request.post_data_json == {"budget": "12.50"}
        observation_calls.append((route.request.method, urlsplit(route.request.url).path))
        route.fulfill(json=receipt)

    page.route("**/api/v1/public/traders/*/observe", observation)
    page.route("**/api/v1/public/leaders*", rankings)
    page.route("**/api/v1/public/traders/*", profile)
    workspace = origin + "/api/v1/workspace"
    initial = page.request.get(workspace).json()
    page.goto(origin + "/#/discover")
    page.set_viewport_size({"width": 390, "height": 844})
    card = page.get_by_role("link", name=re.compile("Research public wallets"))
    tab_to(page, card)
    page.keyboard.press("Enter")
    expect(page.get_by_role("heading", name="Public rankings", exact=True)).to_be_visible()
    page.set_viewport_size({"width": 1240, "height": 900})
    lumen = page.get_by_role("button", name="Inspect Fixture Lumen")
    stone = page.get_by_role("button", name="Inspect Fixture Stone")
    expect(lumen).to_be_visible()
    search = page.get_by_label("Search public traders")
    search.fill("Lumen")
    expect(stone).to_have_count(0)
    expect(lumen).to_be_visible()
    search.fill("")
    expect(stone).to_be_visible()
    first_pick = page.get_by_label("Select Fixture Lumen for comparison")
    second_pick = page.get_by_label("Select Fixture Stone for comparison")
    compare = page.get_by_role("button", name="Compare wallets")
    comparison = page.get_by_role("region", name="Public wallet comparison")
    first_pick.check()
    next_rankings = page.get_by_role("button", name="Next page")
    next_rankings.click()
    expect(page.get_by_role("alert")).to_contain_text("Next page temporarily unavailable")
    expect(first_pick).to_be_checked()
    fail_next_page = False
    next_rankings.click()
    dune = page.get_by_label("Select Fixture Dune for comparison")
    dune.check()
    expect(next_rankings).to_be_disabled()
    expect(compare).to_be_enabled()
    shortlist = page.get_by_role("region", name="Saved comparison shortlist")
    expect(shortlist.get_by_role("button", name="Remove Fixture Lumen from shortlist")).to_be_visible()
    page.get_by_role("button", name="Previous").click()
    expect(first_pick).to_be_checked()
    next_rankings.click()
    expect(dune).to_be_checked()
    dune.uncheck()
    page.get_by_role("button", name="Previous").click()
    assert cursor_reads == ["next+/=", "next+/="]
    expect(compare).to_be_disabled()
    second_pick.check()
    expect(compare).to_be_enabled()
    expect(page.get_by_label("Select Fixture Ash for comparison")).to_be_disabled()
    assert profile_reads == []
    for compare_case, expected in [
        ("shared", "1 shared open market."),
        ("zero", "0 shared open markets on the complete responses."),
        ("partial", "No shared markets found on the returned pages. Total overlap is unknown."),
        ("partial-shared", "At least 1 shared on the returned pages. Total overlap is unknown."),
        ("unknown-identity", "Unknown. Both wallets need available positions with verified market identities."),
        ("error", "Unknown. Both wallets need available positions with verified market identities."),
    ]:
        compare.click()
        expect(comparison.get_by_role("heading", name="Wallet comparison")).to_be_focused()
        expect(comparison.get_by_text(expected, exact=True)).to_be_visible()
        expect(comparison.get_by_text("19,348.35", exact=True)).to_be_visible()
        if compare_case == "shared":
            expect(comparison.get_by_text("1 of 1 shown", exact=True)).to_have_count(2)
            expect(comparison.get_by_text("Fixture opening day?", exact=True)).to_have_count(1)
            expect(comparison.get_by_text("Fixture Lumen · Yes", exact=True)).to_be_visible()
            expect(comparison.get_by_text("Fixture Stone · No, Yes", exact=True)).to_be_visible()
            capture(page, output, "public-wallet-comparison-desktop")
            page.set_viewport_size({"width": 390, "height": 844})
            check_width(page)
            capture(page, output, "public-wallet-comparison-mobile")
            page.set_viewport_size({"width": 1240, "height": 900})
        if compare_case == "error":
            expect(comparison.get_by_text("Complete response", exact=True)).to_be_visible()
            expect(comparison.get_by_text("Position service unavailable", exact=True)).to_be_visible()
        comparison.get_by_role("button", name="Back to rankings").click()
        expect(compare).to_be_focused()
    assert profile_reads.count(wallet) == profile_reads.count(other) == 6
    compare.click()
    expect(comparison.get_by_text("Position service unavailable", exact=True)).to_be_visible()
    comparison.get_by_role("button", name="Back to rankings").click()
    page.get_by_label("Ranking period").select_option("week")
    expect(comparison).to_have_count(0)
    expect(first_pick).not_to_be_checked()
    expect(compare).to_be_disabled()
    page.reload()
    expect(page.get_by_label("Ranking period")).to_have_value("week")
    expect(first_pick).not_to_be_checked()
    page.get_by_label("Ranking period").select_option("month")
    expect(first_pick).to_be_checked()
    expect(second_pick).to_be_checked()
    # The provider rank, wallet identity and period survive an ordinary reload.
    reads_before_reload = list(profile_reads)
    page.reload()
    expect(compare).to_be_enabled()
    expect(first_pick).to_be_checked()
    assert profile_reads == reads_before_reload
    page.set_viewport_size({"width": 390, "height": 844})
    check_width(page)
    capture(page, output, "public-shortlist-mobile")
    page.set_viewport_size({"width": 1240, "height": 900})
    board_budget = page.get_by_label("Simulated budget per buy")
    board_budget.fill("140.50")
    lumen.click()
    expect(page.get_by_role("heading", name="Fixture Lumen", exact=True)).to_be_focused()
    setup_link = page.get_by_role("link", name="Set up public shadow run")
    setup = browser.new_page()
    setup.goto(origin + "/" + setup_link.get_attribute("href"))
    expect(setup.get_by_label("Run name")).to_have_value("Fixture Lumen")
    expect(setup.get_by_label("Leader wallet")).to_have_value(wallet)
    expect(setup.get_by_label("Per-entry cap (pUSD)")).to_have_value("140.50")
    expect(setup.get_by_label("Starting cash (pUSD)")).to_have_value("")
    setup.get_by_text("Compare per-buy limits", exact=True).click()
    starting_cash = setup.get_by_label("Starting cash (pUSD)")
    per_buy = setup.get_by_label("Per-entry cap (pUSD)")
    starting_cash.fill("2")
    expect(setup.get_by_role("button", name="Use 25% · 0.50 pUSD")).to_be_disabled()
    expect(per_buy).to_have_value("140.50")
    starting_cash.fill("33.37")
    setup.get_by_role("button", name="Use 10% · 3.33 pUSD").click()
    expect(per_buy).to_have_value("3.33")
    expect(setup.get_by_text("If the first buy uses its full cap", exact=False)).to_contain_text("30.04 pUSD")
    setup.get_by_role("button", name="Use 25% · 8.34 pUSD").click()
    expect(per_buy).to_have_value("8.34")
    expect(setup.get_by_text("If the first buy uses its full cap", exact=False)).to_contain_text("25.03 pUSD")
    expect(starting_cash).to_have_value("33.37")
    setup.close()
    expect(page.get_by_text("Fixture opening day?", exact=True)).to_be_visible()
    capture(page, output, "public-profile-fixture")
    page.set_viewport_size({"width": 390, "height": 844})
    check_width(page)
    positions = page.get_by_role("table", name="Positions in this snapshot")
    expect(positions.get_by_role("columnheader", name="State")).to_have_count(1)
    expect(positions.get_by_role("cell", name="7.125")).to_be_visible()
    holdings = page.get_by_role("region", name="Holdings value")
    assert not value_reads
    holdings.get_by_role("button", name="Load holdings value").click()
    expect(holdings.get_by_text("1375.0421 USDC")).to_be_visible()
    expect(holdings.get_by_text("unresolved combos at cost", exact=False)).to_be_visible()
    expect(holdings.get_by_text(re.compile("Polymarket Data API v2.*Checked.*UTC"))).to_be_visible()
    if output:
        holdings.screenshot(path=output / "holdings-value-mobile.png")
    holdings.get_by_role("button", name="Refresh holdings value").click()
    expect(holdings.get_by_text("Value unavailable", exact=True)).to_be_visible()
    expect(holdings.get_by_text("1375.0421 USDC")).to_have_count(0)
    expect(positions.get_by_role("cell", name="7.125")).to_be_visible()
    assert value_reads == [wallet, wallet]
    expect(page.get_by_role("columnheader", name="Volume (shares)")).to_have_count(0)
    expect(page.get_by_text(re.compile(r"Reported volume.*19,348.35 shares"))).to_be_visible()
    assert not history_reads
    page.get_by_role("button", name="Load P/L history").click()
    expect(page.get_by_role("img", name="Cumulative observations.", exact=False)).to_be_visible()
    assert len(history_reads) == 1
    expect(page.locator("figure.public-pnl-plot line")).to_have_count(0)
    page.get_by_text("View 3 daily-grid samples").click()
    table = page.get_by_role("table", name="Polymarket realized P/L samples")
    for value in ("100.000000001", "Unavailable", "140.000000001"):
        expect(table.get_by_role("cell", name=value, exact=True)).to_be_visible()
    check_width(page)
    capture(page, output, "public-profile-mobile-fixture")
    page.get_by_role("button", name="Back to rankings", exact=True).click()
    expect(lumen).to_be_focused()
    expect(board_budget).to_have_value("140.50")
    lumen.click()
    expect(page.get_by_role("heading", name="Fixture Lumen", exact=True)).to_be_focused()
    assert not observation_calls
    page.get_by_label("Budget per buy (pUSD)").fill("12.50")
    retry = page.get_by_role("checkbox", name="Check again if the first read is empty")
    expect(retry).not_to_be_checked()
    page.get_by_role("button", name="Check next buy", exact=True).click()
    expect(page.get_by_role("heading", name="BUY and displayed book observed")).to_be_visible()
    timing = page.get_by_text("Window, timing and ask levels", exact=True)
    timing.click()
    expect(page.get_by_role("cell", name="0.86", exact=True)).to_be_visible()
    with page.expect_download() as download:
        page.get_by_role("link", name="Download observation").click()
    assert json.loads(download.value.path().read_text()) == receipt
    assert observation_calls == [("POST", "/api/v1/public/traders/" + wallet + "/observe")]
    samples = [
        {"status": "waiting", "reason": "No ordinary BUY visible. Indexing may lag."},
        {"status": "incomplete", "reason": "Book timestamp falls outside the interval from detection to receipt.",
         "activityCoverage": {"rowsReturned": 20, "ordinaryBuyRows": 14, "complete": False},
         "event": {"eventTimeSeconds": 1795608002, "shares": "14", "price": "0.52", "fillId": None}},
        {"status": "unavailable", "reason": "Public endpoint unreachable or denied."},
        {"status": "observed", "reason": "A matching book update arrived after detection.",
         "capacity": {"status": "skipped", "budget": "12.50", "reason": "The book arrived 10,555 ms after the BUY. The research limit is 10,000 ms."}},
        {"status": "observed", "reason": "Displayed depth only.",
         "event": {"eventTimeSeconds": 1795608002, "shares": "14", "price": "0.52", "fillId": None,
                   "marketTitle": "Will the fixture market settle above its threshold?", "outcomeLabel": "Yes"},
         "participant": {"status": "matched", "role": "maker", "blockNumber": 123, "logIndex": 7},
         "capacity": {"status": "estimated", "budget": "12.50", "shares": "21", "gross": "11.55",
                      "feeEstimate": "0.25988", "unspent": "0.69012", "maxPriceIncrease": "0.03", "maxLevels": 3,
                      "spreadPercentOfAsk": "3.64"},
         "activityReceivedMs": 1795608005010, "evidenceCheckedMs": 1795608005210,
         "bookRequestedMs": 1795608007210, "bookReceivedMs": 1795608007360,
         "book": {"sourceTimeMs": 1795608007250, "sourceAgeAtDetectionMs": -2240, "bestAskMinusLeaderPrice": "0.03", "askLevelCount": 1,
                  "spreadPerShare": "0.02", "bestBid": {"price": "0.53", "shares": "12"},
                  "bestAsks": [{"price": "0.55", "shares": "21.25"}]}},
    ]

    def probe(route: Route):
        assert route.request.method == "POST" and route.request.post_data_json == {"budget": "12.50"}
        route.fulfill(json={**samples.pop(0), "schemaVersion": 1, "wallet": wallet,
                            "windowStartSeconds": 1795608000, "windowEndSeconds": 1795608004})

    page.route("**/api/v1/public/traders/*/observe", probe)
    button = page.get_by_role("button", name="Check next buy")
    button.click()
    expect(page.get_by_role("heading", name="No BUY observed in this window")).to_be_visible()
    button.click()
    expect(page.get_by_role("heading", name="Partial evidence")).to_be_visible()
    timing.click()
    expect(page.get_by_text(re.compile("14 ordinary BUY rows among 20 returned"))).to_be_visible()
    expect(page.get_by_text("Individual fill identity", exact=False)).to_be_visible()
    with page.expect_download() as download:
        page.get_by_role("link", name="Download observation").click()
    receipt = json.loads(download.value.path().read_text())
    assert receipt["wallet"] == wallet and receipt["event"]["fillId"] is None
    capture(page, output, "public-observation-partial-fixture")
    button.click()
    expect(page.get_by_role("heading", name="Observation unavailable")).to_be_visible()
    button.click()
    expect(page.get_by_role("heading", name="Budget check skipped")).to_be_visible()
    expect(page.get_by_text("10,555 ms", exact=False)).to_be_visible()
    check_filter = page.get_by_label("Buy check at this budget")
    page.get_by_role("button", name="Back to rankings", exact=True).click()
    check_filter.select_option("skipped")
    expect(lumen).to_be_visible()
    expect(page.get_by_role("button", name="Inspect Fixture Stone", exact=True)).to_have_count(0)
    lumen.click()
    button.click()
    expect(page.get_by_role("heading", name="Displayed capacity estimated")).to_be_visible()
    expect(page.get_by_text("0.02 pUSD per share", exact=True)).to_be_visible()
    expect(page.get_by_text("21 whole shares")).to_be_visible()
    expect(page.get_by_text("Will the fixture market settle above its threshold?", exact=True)).to_be_visible()
    expect(page.get_by_text("14 shares on Yes at 0.52 pUSD per share.", exact=False)).to_be_visible()
    expect(page.get_by_text("3.64% of the best ask.", exact=False)).to_be_visible()
    expect(page.get_by_role("heading", name="Research budget · 12.50 pUSD")).to_be_visible()
    expect(page.get_by_text("Matched the wallet’s maker order", exact=False)).to_be_visible()
    check_width(page)
    capture(page, output, "public-capacity-mobile-fixture")
    timing.click()
    expect(page.get_by_role("cell", name="21.25", exact=True)).to_be_visible()
    expect(page.get_by_text("2240 ms after detection", exact=True)).to_be_visible()
    expect(page.get_by_text("0.03 per share", exact=True)).to_be_visible()
    assert not samples
    page.get_by_role("button", name="Back to rankings", exact=True).click()
    reads_before_filtering = list(profile_reads)
    check_filter.select_option("estimated")
    expect(lumen).to_be_visible()
    board_budget.fill("5")
    expect(lumen).to_have_count(0)
    check_filter.select_option("unchecked")
    expect(lumen).to_be_visible()
    board_budget.fill("12.5")
    expect(lumen).to_have_count(0)
    check_filter.select_option("estimated")
    expect(lumen).to_be_visible()
    check_width(page)
    capture(page, output, "public-budget-filter-mobile")
    assert profile_reads == reads_before_filtering
    board_budget.fill("12.50")
    lumen.click()

    # The second public read covers the original interval. Export every actual
    # read even when a follow-up fails or yields an incomplete page.
    retry.focus()
    page.keyboard.press("Space")
    expect(retry).to_be_checked()
    window = {"schemaVersion": 3, "wallet": wallet, "researchBudget": "12.50",
              "windowStartSeconds": sample_time, "windowEndSeconds": sample_time + 1,
              "retryAfterWindowMs": 3000}
    closed = (sample_time + 2) * 1000
    no_buys = {"rowsReturned": 0, "ordinaryBuyRows": 0, "complete": True}
    empty = {"requestedMs": closed, "receivedMs": closed + 400, "activityCoverage": no_buys}
    second_start = closed + 3000
    second = {"requestedMs": second_start, "receivedMs": second_start + 500}
    one_buy = {"rowsReturned": 1, "ordinaryBuyRows": 1, "complete": True}
    detected = {**window, "status": "incomplete", "reason": "The book timestamp preceded the modeled delay.",
                "detectionRead": 2, "activityReceivedMs": second["receivedMs"], "activityCoverage": one_buy,
                "event": {"eventTimeSeconds": sample_time, "shares": "5", "price": "0.002", "fillId": None},
                "participant": {"status": "matched", "role": "taker", "logIndex": 136, "blockNumber": 97946137,
                                "grossCollateral": "0.01", "chargedFee": "0.00049", "totalCollateral": "0.01049"},
                "activityReads": [empty, {**second, "activityCoverage": one_buy}]}
    failed = {**window, "status": "unavailable", "reason": "Activity request failed.",
              "activityReads": [empty, {"requestedMs": second_start, "reason": "Activity request failed."}]}
    capped = {**window, "status": "incomplete", "reason": "More rows exist on the activity endpoint.",
              "activityReads": [empty, {**second, "activityCoverage": {
                  "rowsReturned": 20, "ordinaryBuyRows": 0, "complete": False}}]}
    missed = {**window, "status": "incomplete", "reason": "The second read missed its deadline.",
              "activityReads": [empty]}
    retry_receipts = [detected, failed, capped, missed]

    def retry_probe(route: Route):
        assert route.request.post_data_json == {"budget": "12.50", "retryEmpty": True}
        route.fulfill(json=retry_receipts.pop(0))

    page.route("**/api/v1/public/traders/*/observe", retry_probe)
    button.click()
    reads = page.get_by_role("region", name="Activity reads")
    expect(reads.get_by_role("heading", name="BUY first visible on the second read")).to_be_visible()
    expect(reads.get_by_role("listitem").first).to_contain_text("0 ordinary BUY rows among 0 returned · Complete page")
    expect(reads.get_by_role("listitem").last).to_contain_text("1 ordinary BUY row among 1 returned · Complete page")
    expect(reads.get_by_text(re.compile(r"^Requested [\d:.]+ UTC$"))).to_have_count(2)
    expect(reads.get_by_text(re.compile(r"^Received [\d:.]+ UTC$"))).to_have_count(2)
    expect(page.get_by_text("0.01 pUSD in shares + 0.00049 pUSD charged fee = 0.01049 pUSD total.",
                            exact=False)).to_be_visible()
    with page.expect_download() as download:
        page.get_by_role("link", name="Download observation").click()
    assert json.loads(download.value.path().read_text()) == detected
    check_width(page)
    if output:
        panel = page.locator("section.panel").filter(has=page.get_by_role("heading", name="Test a buy with your budget"))
        panel.screenshot(path=output / "activity-reads-mobile.png")
        page.set_viewport_size({"width": 1240, "height": 900})
        panel.screenshot(path=output / "activity-reads-desktop.png")
        page.set_viewport_size({"width": 390, "height": 844})
    button.click()
    expect(reads.get_by_role("listitem").last).to_contain_text("Activity request failed.")
    expect(page.get_by_text("Activity request failed.", exact=True)).to_have_count(1)
    expect(reads.get_by_role("listitem").last).not_to_contain_text("Received")
    with page.expect_download() as download:
        page.get_by_role("link", name="Download observation").click()
    assert json.loads(download.value.path().read_text()) == failed
    button.click()
    expect(reads.get_by_role("listitem").last).to_contain_text("0 ordinary BUY rows among 20 returned · First page only")
    button.click()
    expect(page.get_by_text("The second read missed its deadline.")).to_be_visible()
    expect(reads.get_by_role("listitem")).to_have_count(1)
    assert not retry_receipts
    retry.uncheck()

    def timeout(route: Route):
        assert route.request.post_data_json == {"budget": "12.50"}
        route.fulfill(status=504, json={"error": "Observation timed out. Try another window."})

    page.route("**/api/v1/public/traders/*/observe", timeout)
    button.click()
    expect(page.get_by_role("alert")).to_have_text("Observation timed out. Try another window.")
    expect(reads).to_have_count(0)
    expect(page.get_by_role("link", name="Download observation")).to_have_count(0)
    page.get_by_role("button", name="Back to rankings", exact=True).click()
    check_filter.select_option("inconclusive")
    expect(lumen).to_be_visible()
    check_filter.select_option("all")
    first_pick.check()
    second_pick.check()
    compare.click()
    expect(comparison.get_by_text("Buy check · 12.50 pUSD", exact=True)).to_be_visible()
    expect(comparison.get_by_text("Observation timed out. Try another window.", exact=True)).to_be_visible()
    comparison.get_by_role("button", name="Open profile for Fixture Lumen").click()
    expect(page.get_by_label("Budget per buy (pUSD)")).to_have_value("12.50")
    page.get_by_role("button", name="Back to comparison").click()
    expect(comparison.get_by_role("heading", name="Wallet comparison")).to_be_focused()
    comparison.get_by_role("button", name="Open profile for Fixture Lumen").click()
    page.get_by_role("link", name="Watch this address").click()
    expect(page.get_by_label("Public wallet address")).to_have_value(wallet)
    check_width(page)
    page.set_viewport_size({"width": 1240, "height": 900})
    after = page.request.get(workspace).json()
    assert (initial["account"], initial["accountRevision"]) == (after["account"], after["accountRevision"])
    page.get_by_role("link", name="Public rankings", exact=True).click()
    expect(lumen).to_be_visible()
    period = page.get_by_label("Ranking period")
    default_period = period.input_value()
    values = period.locator("option").evaluate_all("opts => opts.map(o => o.value)")
    alternate = next(value for value in values if value != default_period)
    delayed_period = alternate
    with page.expect_request("**/api/v1/public/leaders*"):
        period.select_option(alternate)
    fixture_state = "unavailable"
    period.select_option(default_period)
    expect(page.get_by_text("Fixture rankings unavailable", exact=False)).to_be_visible()
    assert pending, "Old-period fixture was never requested"
    pending[0].fulfill(json=ranking_payload(alternate, "available"))
    page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
    expect(lumen).to_have_count(0)
    expect(page.get_by_text("Fixture rankings unavailable", exact=False)).to_be_visible()
    # An outage must leave saved snapshots inspectable and removable.
    compare.click()
    expect(comparison.get_by_role("heading", name="Wallet comparison")).to_be_visible()
    expect(comparison.get_by_text("19,348.35", exact=True)).to_be_visible()
    comparison.get_by_role("button", name="Back to rankings").click()
    page.set_viewport_size({"width": 390, "height": 844})
    shortlist.get_by_role("button", name="Remove Fixture Lumen from shortlist").click()
    expect(compare).to_be_disabled()
    check_width(page)
    page.reload()
    expect(shortlist.get_by_role("button", name="Remove Fixture Stone from shortlist")).to_be_visible()
    expect(shortlist.get_by_role("button", name="Remove Fixture Lumen from shortlist")).to_have_count(0)
    # A direct lookup reads one wallet, even when the board is unavailable.
    # Typing alone must not transmit the pasted address or replace a saved watch.
    page.set_viewport_size({"width": 390, "height": 844})
    page.request.post(origin + "/api/v1/account", data={"address": wallet, "revision": initial["accountRevision"]})
    watched = page.request.get(workspace).json()
    assert watched["account"]["address"] == wallet
    reads_before = list(profile_reads)
    search.fill("0x1234")
    expect(page.get_by_role("button", name="Inspect wallet", exact=True)).to_have_count(0)
    search.fill("  0x" + "AB" * 20 + "  ")
    expect(page.get_by_role("button", name="Inspect wallet", exact=True)).to_be_enabled()
    assert profile_reads == reads_before
    search.press("Enter")
    expect(page.get_by_role("heading", name="Public wallet", exact=True)).to_be_focused()
    expect(page.get_by_role("heading", name="Open positions")).to_be_visible()
    expect(page.get_by_text("Provider rank", exact=False)).to_have_count(0)
    assert profile_reads == [*reads_before, unranked]
    assert page.request.get(workspace).json() == watched
    check_width(page)
    capture(page, output, "direct-wallet-mobile")
    page.get_by_role("button", name="Back to rankings").click()
    expect(search).to_be_focused()
    page.request.delete(origin + "/api/v1/account", data={"revision": watched["accountRevision"]})
    search.fill("")
    delayed_period = None
    fixture_state = "empty"
    period.select_option(alternate)
    expect(page.get_by_text("Polymarket returned an empty page.", exact=True)).to_be_visible()
    expect(lumen).to_have_count(0)
    assert alternate in requested_periods and default_period in requested_periods
    # Browser policies may block writes after a shortlist was saved.
    fixture_state = "available"
    period.select_option(default_period)
    expect(shortlist.get_by_role("button", name="Remove Fixture Stone from shortlist")).to_be_visible()
    page.evaluate("""() => {Storage.prototype.removeItem = () => {throw new Error('storage blocked')}}""")
    shortlist.get_by_role("button", name="Remove Fixture Stone from shortlist").click()
    expect(page.get_by_text("Browser storage is unavailable.", exact=False)).to_be_visible()
    period.select_option(alternate)
    period.select_option(default_period)
    expect(second_pick).not_to_be_checked()
    expect(shortlist).to_have_count(0)
    page.close()
    print("Passed ranking filters, stale and unavailable results, direct wallet inspection, watch preservation and wallet prefill.")


def change_cap_journey(browser: Browser, origin: str):
    page = browser.new_page(viewport={"width": 390, "height": 844})
    try:
        page.goto(origin + "/#/paper/new")
        page.get_by_label("Leader wallet").fill("0x" + "cd" * 20)
        page.get_by_role("button", name="Create shadow run").click()
        disclosure = page.get_by_text("Change future BUY cap", exact=True)
        disclosure.click()
        page.get_by_label("New per-entry cap (pUSD)").fill("3.50")
        page.get_by_role("button", name="Save future cap").click()
        expect(page.get_by_text("Changed future simulated BUY cap from 10 to 3.5 pUSD.")).to_be_visible()
        page.reload()
        expect(page.get_by_text("Changed future simulated BUY cap from 10 to 3.5 pUSD.")).to_be_visible()
        page.get_by_text("Withdraw simulated cash", exact=True).click()
        page.get_by_label("Simulated withdrawal (pUSD)").fill("98")
        page.get_by_role("button", name="Record simulated withdrawal").click()
        expect(page.get_by_text("Simulated withdrawal recorded. Available cash is 2 pUSD.")).to_be_visible()
        page.reload()
        week = page.get_by_role("region", name="Last seven days")
        expect(week.get_by_text("Withdrawn 98", exact=False)).to_be_visible()
        with page.expect_download() as file:
            week.get_by_role("button", name="Export this period").click()
        period = json.loads(file.value.path().read_text())["period"]
        assert (period["closingCash"], period["withdrawals"], period["netResult"]) == ("2", "98", "0")
        check_width(page)
    finally:
        page.close()


def public_shadow_journey(browser: Browser, cwd: Path, output: Path | None):
    from datetime import UTC, datetime, timedelta
    from threading import Event, Thread
    from unittest.mock import patch

    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "tests"))
    from apps.server import public_marks, public_shadow
    from apps.server.http import LocalServer
    from apps.server.store import Workspace
    from install_smoke import app
    from test_public_shadow import observed_buy, observed_sell, WALLET
    from test_observe import book

    installer = [sys.executable, str(ROOT / "dist/polysia.pyz"), "--prefix", str(cwd / "public-app"), "--json"]
    installed = json.loads(subprocess.check_output(installer, cwd=cwd))
    server = LocalServer(0, Workspace(Path(installed["data"]) / "workspace.sqlite3"))
    origin = f"http://127.0.0.1:{server.server_port}"
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
    thread.start()
    page = browser.new_page(viewport={"width": 1380, "height": 960}, reduced_motion="reduce")
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.goto(origin + "/#/paper")
        expect(page.get_by_role("heading", name="Follow your first public wallet")).to_be_visible()
        page.get_by_role("link", name="New run").click()
        page.get_by_label("Leader wallet").fill(WALLET)
        page.get_by_label("Run name").fill("Weekend research")
        page.get_by_label("Starting cash").fill("25")
        # Keep the complete controlled sequence inside the returning operator's
        # seven-day window, including after restarting the packaged server.
        start = int(time.time()) - 86400
        with patch.object(public_shadow, "timestamp", return_value=datetime.fromtimestamp(start - 5, UTC).isoformat(timespec="milliseconds")):
            page.get_by_role("button", name="Create shadow run").click()
            expect(page.get_by_role("heading", name="Weekend research")).to_be_visible()
        route = page.url
        receipt = observed_buy(WALLET, "10.00", start=start)
        unavailable = dict(wallet=WALLET, researchBudget="10.00", status="unavailable", reason="Public endpoint unreachable or denied.")
        # Advance a controlled clock past the delayed book. Every browser action
        # passes through the real HTTP service, SQLite transactions and UI.
        recorded = datetime.fromtimestamp(start - 4, UTC)

        def record_time():
            nonlocal recorded
            recorded += timedelta(seconds=10)
            return recorded.isoformat(timespec="milliseconds")

        quiet = dict(wallet=WALLET, researchBudget="10.00", status="waiting", reason="No ordinary BUY visible.")
        sale_check = dict(receipt["saleCheck"], firstSale=receipt["event"] | {"side": "SELL", "eventTimeSeconds": start + 1},
                          coverage={"rowsReturned": 1, "matchingSellRows": 1, "complete": True})
        reversed_entry = receipt | {"saleCheck": sale_check}
        responses = [unavailable, reversed_entry, receipt, receipt, quiet, quiet, quiet, quiet]
        with patch.object(server, "sample_buy", side_effect=responses), patch.object(public_shadow, "timestamp", side_effect=record_time):
            sample = page.get_by_role("button", name="Sample next window")
            sample.click()
            expect(page.get_by_text("Observation unavailable", exact=True)).to_be_visible()
            capture(page, output, "public-run-unavailable")
            sample.click()
            blocked = page.locator(".paper-journal li").first
            expect(blocked).to_contain_text("Entry skipped")
            expect(blocked).to_contain_text("Public activity showed a sale of this outcome")
            expect(page.get_by_text("No modeled BUY has opened a position.")).to_be_visible()
            expect(page.locator(".paper-metrics dd").first).to_have_text("25 pUSD")
            sample.click()
            expect(page.get_by_text("19 shares", exact=True)).to_be_visible()
            expect(page.locator("dd").filter(has_text="15.14256")).to_be_visible()
            page.get_by_text("Observation details", exact=True).first.click()
            expect(page.get_by_text("Polygon exchange and source order", exact=True)).to_be_visible()
            mark_ms = int((recorded + timedelta(seconds=1)).timestamp() * 1000)
            current_book = book(timestamp=str(mark_ms), bids=[{"price": "0.49", "size": "5"}],
                                asks=[{"price": "0.51", "size": "2"}])
            with (patch.object(public_marks, "read_public_json", side_effect=[current_book, TimeoutError()]),
                  patch.object(public_marks.time, "time_ns", return_value=mark_ms * 1_000_000)):
                page.get_by_role("button", name="Check price estimate").click()
                expect(page.get_by_text("9.5 pUSD estimated value", exact=True)).to_be_visible()
                expect(page.get_by_text("-0.35744 pUSD versus purchase cost", exact=False)).to_be_visible()
                capture(page, output, "public-run-desktop")
                page.get_by_role("button", name="Refresh price estimate").click()
                expect(page.get_by_text("Price estimate unavailable", exact=True)).to_be_visible()
                expect(page.get_by_text("9.5 pUSD estimated value", exact=True)).to_have_count(0)
            page.get_by_label("Windows to sample").select_option("5")
            page.get_by_role("button", name="Start sampling").click()
            expect(page.get_by_text("5 of 5 windows recorded.")).to_be_visible()
            expect(page.get_by_text("Already modeled", exact=True)).to_be_visible()
            page.get_by_role("button", name="Pause entries").click()
            page.reload()
            expect(page.get_by_role("button", name="Resume entries")).to_be_visible()
            page.get_by_label("Decision history filter").select_option("trades")
            expect(page.get_by_text("Already modeled", exact=True)).to_have_count(0)
            expect(page.get_by_text("Modeled BUY", exact=True)).to_be_visible()
            sale_start = int(recorded.timestamp()) + 1
            def sell(wallet, scope):
                return observed_sell(wallet, scope, start=sale_start)
            page.get_by_text("Follow a leader SELL", exact=True).click()
            page.get_by_label("Maximum shares to sell").fill("11")
            with patch.object(server, "sample_sell", side_effect=sell):
                page.get_by_role("button", name="Observe leader SELL").click()
                expect(page.get_by_role("region", name="Open simulated positions").get_by_text("11 shares", exact=True)).to_be_visible()
                expect(page.get_by_text("Modeled SELL", exact=True)).to_be_visible()
                expect(page.get_by_text("Sold 8 simulated shares", exact=False)).to_be_visible()
            assert page.locator("dd").filter(has_text="18.88272").count() == 1
            quote_ms = int((recorded + timedelta(seconds=1)).timestamp() * 1000)
            with (patch.object(public_marks, "read_public_json", side_effect=[current_book | {"timestamp": str(quote_ms)}, TimeoutError()]),
                  patch.object(public_marks.time, "time_ns", return_value=quote_ms * 1_000_000)):
                page.get_by_role("button", name="Check portfolio value").click()
                expect(page.get_by_text("24.38272", exact=False)).to_be_visible()
                expect(page.get_by_text("-0.61728", exact=False)).to_be_visible()
                expect(page.get_by_text("The simulated return on starting cash is -2.4691%.", exact=False)).to_be_visible()
                page.get_by_text("Valuation evidence", exact=True).click()
                with page.expect_download() as valuation_file:
                    page.get_by_role("link", name="Download valuation").click()
                value = json.loads(valuation_file.value.path().read_text())
                assert (value["equity"], value["unrealized"], value["netResult"]) == ("24.38272", "-0.206939", "-0.61728")
                assert value["cashBenchmark"]["netReturnPct"] == "-2.4691"
                assert value["cashBenchmark"]["throughMs"] == value["checkedMs"]
                assert value["cashBenchmark"]["endValue"] == value["capital"] == "25"
                capture(page, output, "public-sale-valuation-desktop")
                if output:
                    page.locator(".paper-workbench").screenshot(path=output / "public-sale-controls.png")
                page.get_by_role("button", name="Refresh portfolio value").click()
                expect(page.get_by_text("0 of 1 open position priced", exact=False)).to_be_visible()
                expect(page.get_by_text("would need a combined value of 6.11728 pUSD", exact=False)).to_be_visible()
                expect(page.get_by_text("24.38272", exact=False)).to_have_count(0)
                page.set_viewport_size({"width": 390, "height": 844})
                check_width(page)
                capture(page, output, "public-sale-unknown-mobile")
            page.get_by_role("button", name="Resume entries").click()
            page.set_viewport_size({"width": 390, "height": 844})
            page.get_by_role("button", name="Stop run").click()
            confirmation = page.get_by_role("group", name="Stop this run permanently")
            remaining = "11 simulated shares remain in Fixture opening day? · Yes."
            expect(confirmation).to_contain_text(remaining)
            confirmation.get_by_role("button", name="Keep run").click()
            expect(confirmation).to_have_count(0)
            page.get_by_role("button", name="Stop run").click()
            confirmation.get_by_role("button", name="Confirm stop").click()
            expect(page.get_by_role("status").filter(has_text=remaining)).to_be_visible()
            expect(page.get_by_role("heading", name="Run closed to observations")).to_be_visible()
            expect(page.get_by_role("region", name="Open simulated positions").get_by_text("11 shares", exact=True)).to_be_visible()
            check_width(page)
            capture(page, output, "public-run-mobile")
        with page.expect_download() as download:
            page.get_by_role("link", name="Export run").click()
        exported = json.loads(download.value.path().read_text())
        assert [d["kind"] for d in exported["decisions"]] == ["unavailable", "skipped", "entry", "duplicate", *(["waiting"] * 4), "pause", "exit", "resume", "stop"]
        assert exported["cash"] == "18.88272" and exported["decisions"][2]["receipt"] == receipt
        page.get_by_role("link", name="All public runs").click()
        page.get_by_role("link", name=re.compile("Weekend research")).click()
        expect(page).to_have_url(route)
        expect(page.get_by_text("Stopped", exact=True)).to_be_visible()
        expect(page.get_by_role("status").filter(has_text=remaining)).to_be_visible()
        page.get_by_role("link", name="All public runs").click()
        page.get_by_role("link", name="New run").click()
        page.get_by_label("Leader wallet").fill(WALLET)
        page.get_by_role("button", name="Create shadow run").click()
        page.get_by_label("Windows to sample").select_option("5")
        second = page.url.split("/")[-1]
        entered, release = Event(), Event()

        def pending(wallet, budget, **options):
            entered.set()
            assert release.wait(10)
            return dict(quiet, wallet=wallet, researchBudget=budget)

        with patch.object(server, "sample_buy", side_effect=pending) as provider:
            page.get_by_role("button", name="Start sampling").click()
            try:
                assert entered.wait(3)
                page.get_by_role("link", name="All public runs").click()
                expect(page.get_by_role("heading", name="Saved public runs")).to_be_visible()
            finally:
                with page.expect_response("**/api/v1/public-runs/*/sample"):
                    release.set()
            assert page.request.get(origin + "/api/v1/public-runs/" + second).json()["revision"] == 2
            provider.assert_called_once()
        page.get_by_text("Replay buys with one shared budget", exact=True).click()
        page.get_by_role("checkbox", name=re.compile("^Public wallet")).check()
        page.get_by_role("checkbox", name=re.compile("^Weekend research")).check()
        page.get_by_label("Shared starting cash").fill("10")
        page.get_by_role("button", name="Replay selected buys").click()
        pooled = page.get_by_role("region", name="Shared budget result")
        expect(pooled.get_by_text("0.14256 pUSD cash left")).to_be_visible()
        expect(pooled).to_contain_text("1 modeled sale and 5 quiet windows")
        pooled.get_by_text("Other recorded decisions", exact=True).click()
        expect(pooled.get_by_text("Incomplete evidence", exact=True)).to_be_visible()
        for width in (390, 1380):
            page.set_viewport_size({"width": width, "height": 900})
            check_width(page)
        page.get_by_label("Shared starting cash").fill("1")
        expect(pooled).to_have_count(0)
        page.get_by_role("button", name="Replay selected buys").click()
        expect(pooled.get_by_text("1 pUSD cash left")).to_be_visible()
        page.get_by_text("Replay buys with one shared budget", exact=True).click()
        page.get_by_role("link", name=re.compile(r"^Public wallet")).click()
        expect(page.get_by_role("heading", name="Public wallet", exact=True)).to_be_visible()
        now = int(time.time()) + 1
        clocks = [datetime.fromtimestamp(now + seconds, UTC).isoformat(timespec="milliseconds") for seconds in (6, 16)]
        sale_started, finish_sale = Event(), Event()
        def delayed_sale(wallet, scope):
            sale_started.set()
            assert finish_sale.wait(10)
            return observed_sell(wallet, scope, start=now + 10, depth="25")

        with (patch.object(public_shadow, "timestamp", side_effect=clocks),
              patch.object(server, "sample_buy", return_value=observed_buy(WALLET, "10.00", start=now)),
              patch.object(server, "sample_sell", side_effect=delayed_sale)):
            page.get_by_role("button", name="Sample next window").click()
            page.get_by_text("Follow a leader SELL", exact=True).click()
            expect(page.get_by_text("0.03 pUSD per share below the leader", exact=False)).to_be_visible()
            expect(page.get_by_text("pooled cost, floor to micro-pUSD", exact=False)).to_be_visible()
            page.get_by_label("Maximum shares to sell").fill("19")
            page.get_by_role("button", name="Observe leader SELL").click()
            try:
                assert sale_started.wait(3)
                expect(page.get_by_role("button", name="Pause entries")).to_be_disabled()
                expect(page.get_by_role("button", name="Stop run", exact=True)).to_be_enabled()
            finally:
                finish_sale.set()
            closed = page.get_by_role("region", name="Closed simulated positions")
            expect(closed.get_by_text("-0.97456 pUSD realized", exact=True)).to_be_visible()
            expect(closed.get_by_text("8.88288 pUSD received after sale fees", exact=False)).to_be_visible()
        page.reload()
        expect(page.get_by_text("All simulated positions are closed.", exact=True)).to_be_visible()
        with patch.object(public_marks.time, "time_ns", return_value=(now + 17) * 1_000_000_000):
            page.get_by_role("button", name="Check portfolio value").click()
            expect(page.get_by_text("All value is held in simulated cash.", exact=False)).to_be_visible()
        assert page.locator("dd").filter(has_text="99.02544").count() == 2
        check_width(page)
        capture(page, output, "public-closed-portfolio")
        assert not errors, errors
        print("Passed public portfolio setup, BUY, partial and full SELL, closed positions, filtered history, valuation, missing prices, stop and export.")
    finally:
        page.close()
        server.shutdown()
        server.server_close()
        thread.join()

    assert json.loads(subprocess.check_output(installer, cwd=cwd)) == installed
    with app(installed["launcher"], cwd, offline=True) as reopened:
        page = browser.new_page(viewport={"width": 390, "height": 844})
        try:
            page.goto(reopened + "/#" + route.split("#", 1)[1])
            expect(page.get_by_role("status").filter(has_text=remaining)).to_be_visible()
            with page.expect_download() as download:
                page.get_by_role("link", name="Export run").click()
            assert json.loads(download.value.path().read_text()) == exported
            page.goto(reopened + "/#/status")
            overview = page.get_by_role("region", name="Shadow portfolio overview")
            expect(overview.get_by_text("Stopped with open simulated shares.", exact=False).first).to_be_visible()
            linked = overview.locator('a[href="' + route[route.index("#"):] + '"]')
            expect(linked).to_be_visible()
            linked.click()
            expect(page.get_by_role("status").filter(has_text=remaining)).to_be_visible()
            week = page.get_by_role("region", name="Last seven days")
            expect(week.get_by_text("Net result in period", exact=True)).to_be_visible()
            expect(week.get_by_text("Unknown", exact=True)).to_be_visible()
            expect(week.get_by_text("Sampling has stopped.", exact=False)).to_be_visible()
            week.get_by_text("Remaining positions", exact=True).click()
            expect(week.get_by_role("listitem").first).to_contain_text("shares")
            with page.expect_download() as period_file:
                with page.expect_request(lambda r: r.url.endswith("/week/export")) as requested:
                    week.get_by_role("button", name="Export this period").click()
            fixed = json.loads(period_file.value.path().read_text())
            assert fixed["period"]["through"] == requested.value.post_data_json["through"]
            assert fixed["period"]["revision"] == exported["revision"]
            assert fixed["period"]["closingCash"] == exported["cash"] and fixed["period"]["netResult"] is None
            assert fixed["run"]["positions"] == exported["positions"]
            assert [d["kind"] for d in fixed["decisions"]] == [d["kind"] for d in exported["decisions"]]
            print("Installed restart after reinstall preserved the stopped portfolio, partial exit and complete export.")
        finally:
            page.close()


def public_artifact_smoke(browser: Browser, cwd: Path, output: Path | None):
    """Opt-in. Inspect a real public ranking and persist one read-only watch."""
    # Reuse the installer test's launcher to exercise the actual shipped code.
    sys.path.insert(0, str(ROOT / "tests"))
    from install_smoke import app

    installer = [sys.executable, str(ROOT / "dist/polysia.pyz"), "--prefix", str(cwd / "app"), "--json"]
    installed = json.loads(subprocess.check_output(installer, cwd=cwd))
    sell = json.loads((ROOT / "tests/fixtures/polygon-sell.json").read_text())
    event = sell["event"]
    scope = {"conditionId": event["conditionId"], "tokenId": event["tokenId"], "maxShares": "5"}
    result = subprocess.run([sys.executable, "-B", "-m", "apps.server.observe", sell["wallet"],
                             "--seconds", "2", "--retry-empty", "--sell", scope["conditionId"], scope["tokenId"], "5"],
                            cwd=Path(installed["launcher"]).resolve().parent, capture_output=True, timeout=45)
    assert result.returncode in (0, 2), result.returncode
    window = json.loads(result.stdout)
    assert window["schemaVersion"] == 4 and window["wallet"] == sell["wallet"] and window["exitScope"] == scope
    assert window["activityReads"] and window["windowEndSeconds"] == window["windowStartSeconds"] + 1
    print(f"Installed SELL observer recorded {window['status']} across {len(window['activityReads'])} activity read(s).")
    with app(installed["launcher"], cwd) as origin:
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        with page.expect_response("**/api/v1/public/leaders*") as reply:
            page.goto(origin + "/#/rankings")
        board = reply.value.json()
        assert board["status"] == "available" and board["leaders"], board["message"]
        first = board["leaders"][0]
        with page.expect_response("**/api/v1/public/traders/*") as reply:
            page.get_by_role("button", name="Inspect " + first["name"], exact=True).first.click()
        profile = reply.value.json()
        assert profile["status"] == "available" and profile["address"] == first["address"], profile["message"]
        expect(page.get_by_role("heading", name="Open positions")).to_be_visible()
        with page.expect_response("**/api/v1/public/traders/*/history") as history_response:
            page.get_by_role("button", name="Load P/L history").click()
        history = history_response.value.json()
        assert history["status"] == "available" and history["address"] == first["address"], history["message"]
        if history["points"]:
            page.get_by_text(f"View {len(history['points'])} daily-grid samples").click()
            expect(page.get_by_role("table", name="Polymarket realized P/L samples")).to_be_visible()
        else:
            expect(page.get_by_text("Polymarket returned no samples for this week.")).to_be_visible()
        print(f"Public history returned {len(history['points'])} cumulative observations.")
        capture(page, output, "public-profile-provider")
        page.get_by_role("link", name="Watch this address").click()
        expect(page.get_by_label("Public wallet address")).to_have_value(first["address"])
        page.get_by_role("button", name="Watch account", exact=True).click()
        expect(page.get_by_role("button", name="Remove watch")).to_be_visible(timeout=10000)
        workspace = page.request.get(origin + "/api/v1/workspace").json()
        watch = workspace["account"]
        assert watch["status"] == "available" and watch["address"] == first["address"], watch["message"]
        assert workspace["run"] is None
        holdings = page.get_by_role("region", name="Holdings value")
        with page.expect_response("**/api/v1/public/traders/" + first["address"] + "/value") as value_response:
            holdings.get_by_role("button", name="Load holdings value").click()
        value = value_response.value.json()
        assert value["status"] == "available" and value["address"] == first["address"], value["message"]
        assert value["unit"] == "USDC" and isinstance(value["value"], str)
        expect(holdings.get_by_text(value["value"] + " USDC", exact=True)).to_be_visible()
        assert page.request.get(origin + "/api/v1/workspace").json() == workspace
        print(f"Installed holdings value matched the provider read in {value['unit']} and preserved the watch.")
        print(f"Installed {installed['artifactSha256'][:12]}: {len(board['leaders'])} provider-ranked wallets; "
              f"{len(watch['positions'])} position rows, complete={watch['complete']}, retrieved {watch['observedAt']}.")
        # Inspect the public SDK example wallet independently of the saved watch.
        sample = "0x7c3db723f1d4d8cb9c550095203b686cb11e5c6b"
        page.goto(origin + "/#/rankings")
        lookup = page.get_by_role("searchbox", name="Search public traders")
        lookup.fill(sample)
        with page.expect_response("**/api/v1/public/traders/" + sample) as reply:
            lookup.press("Enter")
        direct = reply.value.json()
        assert direct["address"] == sample and direct["status"] == "available", direct["message"]
        expect(page.get_by_role("heading", name="Open positions")).to_be_visible()
        page.set_viewport_size({"width": 390, "height": 844})
        retry = page.get_by_role("checkbox", name="Check again if the first read is empty")
        expect(retry).not_to_be_checked()
        retry.check()
        with page.expect_response("**/api/v1/public/traders/" + sample + "/observe", timeout=45000) as reply:
            page.get_by_role("button", name="Check next buy").click()
        receipt = reply.value.json()
        assert reply.value.ok and receipt["wallet"] == sample and receipt["researchBudget"] == "10.00"
        assert receipt["schemaVersion"] == 3 and receipt["retryAfterWindowMs"] == 3000
        reads = receipt["activityReads"]
        assert isinstance(reads, list) and len(reads) <= 2
        for read in reads:
            assert type(read["requestedMs"]) is int and ("activityCoverage" in read or "reason" in read)
        if "event" in receipt:
            assert 1 <= receipt["detectionRead"] <= len(reads)
        if reads:
            expect(page.get_by_role("region", name="Activity reads").get_by_role("listitem")).to_have_count(len(reads))
        with page.expect_download() as download:
            page.get_by_role("link", name="Download observation").click()
        assert json.loads(download.value.path().read_text()) == receipt
        check_width(page)
        if output:
            output.mkdir(parents=True, exist_ok=True)
            panel = page.locator("section.panel").filter(has=page.get_by_role("heading", name="Test a buy with your budget"))
            panel.screenshot(path=output / "installed-observation-mobile.png")
        print(f"Installed observation exported its {receipt.get('capacity', {}).get('status', receipt['status'])} receipt.")
        assert page.request.get(origin + "/api/v1/workspace").json() == workspace
        print(f"Direct wallet lookup returned {len(direct['positions'])} rows and preserved the original watch.")
        page.get_by_role("link", name="Set up public shadow run").click()
        expect(page.get_by_label("Leader wallet")).to_have_value(sample)
        page.get_by_role("button", name="Create shadow run").click()
        with page.expect_response("**/api/v1/public-runs/*/sample", timeout=50000) as reply:
            page.get_by_role("button", name="Sample next window").click()
        portfolio = reply.value.json()
        assert reply.value.ok and portfolio["wallet"] == sample and portfolio["revision"] == 2
        run_path = "/api/v1/public-runs/" + portfolio["id"]
        saved = page.request.get(origin + run_path + "/export").json()
        decision, = saved["decisions"]
        assert decision["receipt"]["wallet"] == sample and decision["receipt"]["researchBudget"] == "10.00"
        assert saved["cash"] == portfolio["cash"] and saved["positions"] == portfolio["positions"]
        assert page.request.get(origin + "/api/v1/workspace").json() == workspace
        print(f"Installed public shadow window recorded {decision['kind']}, cash {saved['cash']} pUSD, {len(saved['positions'])} positions.")
        page.get_by_role("button", name="Stop run", exact=True).click()
        with page.expect_response("**/api/v1/public-runs/*/stop") as stopped_reply:
            page.get_by_role("button", name="Confirm stop").click()
        assert stopped_reply.value.ok
        stopped = page.request.get(origin + run_path + "/export").json()
        assert stopped["status"] == "stopped" and stopped["revision"] == portfolio["revision"] + 1
        assert stopped["decisions"][:-1] == saved["decisions"] and stopped["decisions"][-1]["kind"] == "stop"
        assert stopped["positions"] == saved["positions"] and stopped["cash"] == saved["cash"]
        page.get_by_role("button", name="Open navigation").click()
        page.get_by_role("dialog", name="Workspace menu").get_by_role("link", name="Accounts", exact=True).click()
        page.get_by_role("button", name="Remove watch").click()
        expect(page.get_by_role("heading", name="Account scope")).to_be_visible()
        page.close()
    assert json.loads(subprocess.check_output(installer, cwd=cwd)) == installed
    with app(installed["launcher"], cwd) as restarted_origin:
        page = browser.new_page()
        page.goto(restarted_origin + "/#/paper/" + portfolio["id"])
        with page.expect_download() as download:
            page.get_by_role("link", name="Export run").click()
        assert json.loads(download.value.path().read_text()) == stopped
        page.close()
        print("Restarted installed public portfolio preserved the complete stopped journal.")



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshots", type=Path, help="Write rendered evidence in this directory.")
    parser.add_argument("--public-smoke", action="store_true", help="Test the installed artifact with actual public provider reads.")
    options = parser.parse_args()
    if not (ROOT / "apps/web/dist/index.html").is_file():
        sys.exit("Build the web application before running the browser journey.")
    with tempfile.TemporaryDirectory(prefix="polysia-browser-") as temp, sync_playwright() as pw:
        chromium = os.environ.get("CHROMIUM_PATH") or shutil.which("chromium")
        browser = pw.chromium.launch(executable_path=chromium)
        try:
            if options.public_smoke:
                public_artifact_smoke(browser, Path(temp), options.screenshots)
            else:
                with isolated_server(Path(temp)) as origin:
                    stopped = exercise(browser, origin, options.screenshots)
                with isolated_server(Path(temp)) as origin:
                    page = browser.new_page()
                    page.goto(origin)
                    page.get_by_role("link", name="Review Atlas Meridian run " + stopped["id"][:8]).click()
                    expect(page.get_by_text(stopped["quantity"] + " shares", exact=True).first).to_be_visible()
                    assert page.request.get(origin + "/api/v1/runs/" + stopped["id"]).json() == stopped
                    page.close()
                    assisted_budget_journey(browser, origin, options.screenshots)
                    public_rankings_journey(browser, origin, options.screenshots)
                    change_cap_journey(browser, origin)
                public_shadow_journey(browser, Path(temp), options.screenshots)
        finally:
            browser.close()


if __name__ == "__main__":
    main()
