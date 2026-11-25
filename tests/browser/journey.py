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
        scroll = page.evaluate("window.scrollY")
        page.evaluate("window.scrollTo(0, 0)")
        page.screenshot(path=output / f"{name}.png", full_page=True, animations="disabled")
        page.evaluate("y => window.scrollTo(0, y)", scroll)


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
    page.goto(origin)
    expect(page.get_by_role("heading", name="Shadow runs", exact=True)).to_be_visible()
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
    page.close()
    print("Passed budget comparison, missing depth, no-match, and exact policy handoff to replay.")


def public_rankings_journey(browser: Browser, origin: str, output: Path | None):
    """Mock only public reads; local account state and navigation use the application."""
    page = browser.new_page(viewport={"width": 1240, "height": 900})
    page.set_default_timeout(6000)
    wallet = "0x" + "36" * 20
    other = "0x" + "42" * 20
    stamp = "2026-11-25T12:00:00Z"
    pending = []
    delayed_period = None
    requested_periods = []
    fixture_state = "available"

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
            "complete": state != "unavailable", "leaders": leaders,
        }

    def rankings(route: Route):
        period = parse_qs(urlsplit(route.request.url).query).get("period", ["month"])[0]
        requested_periods.append(period)
        if period == delayed_period:
            pending.append(route)
        else:
            route.fulfill(json=ranking_payload(period, fixture_state))

    profile_reads = []
    compare_case = "shared"
    market_id = "0x" + "cd" * 32

    def profile(route: Route):
        address = urlsplit(route.request.url).path.rsplit("/", 1)[1]
        assert route.request.method == "GET" and address in (wallet, other)
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
        observation_calls.append((route.request.method, urlsplit(route.request.url).path))
        route.fulfill(json=receipt)

    page.route("**/api/v1/public/traders/*/observe", observation)
    page.route("**/api/v1/public/leaders*", rankings)
    page.route("**/api/v1/public/traders/*", profile)
    workspace = origin + "/api/v1/workspace"
    initial = page.request.get(workspace).json()
    page.goto(origin + "/#/discover")
    page.get_by_role("link", name="Public rankings", exact=True).click()
    lumen = page.get_by_role("button", name="Inspect Fixture Lumen")
    stone = page.get_by_role("button", name="Inspect Fixture Stone")
    expect(lumen).to_be_visible()
    search = page.get_by_label("Search public traders")
    search.fill("Lumen")
    expect(stone).to_have_count(0)
    expect(lumen).to_be_visible()
    search.fill("")
    expect(stone).to_be_visible()
    first = page.get_by_label("Select Fixture Lumen for comparison")
    second = page.get_by_label("Select Fixture Stone for comparison")
    compare = page.get_by_role("button", name="Compare wallets")
    comparison = page.get_by_role("region", name="Public wallet comparison")
    first.check()
    expect(compare).to_be_disabled()
    second.check()
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
            expect(comparison.get_by_text("Fixture opening day?", exact=True)).to_have_count(1)
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
    page.get_by_label("Ranking period").select_option("week")
    expect(comparison).to_have_count(0)
    expect(first).not_to_be_checked()
    expect(compare).to_be_disabled()
    page.get_by_label("Ranking period").select_option("month")
    lumen.click()
    expect(page.get_by_role("heading", name="Fixture Lumen", exact=True)).to_be_focused()
    expect(page.get_by_text("Fixture opening day?", exact=True)).to_be_visible()
    capture(page, output, "public-profile-fixture")
    page.set_viewport_size({"width": 390, "height": 844})
    check_width(page)
    positions = page.get_by_role("table", name="Positions in this snapshot")
    expect(positions.get_by_role("columnheader", name="State")).to_have_count(1)
    expect(positions.get_by_role("cell", name="7.125")).to_be_visible()
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
    lumen.click()
    expect(page.get_by_role("heading", name="Fixture Lumen", exact=True)).to_be_focused()
    assert not observation_calls
    page.get_by_role("button", name="Observe next BUY", exact=True).click()
    expect(page.get_by_role("heading", name="BUY and displayed book observed")).to_be_visible()
    expect(page.get_by_role("cell", name="0.86", exact=True)).to_be_visible()
    with page.expect_download() as download:
        page.get_by_role("link", name="Download observation").click()
    assert json.loads(download.value.path().read_text()) == receipt
    assert observation_calls == [("POST", "/api/v1/public/traders/" + wallet + "/observe")]
    samples = [
        {"status": "waiting", "reason": "No ordinary BUY visible. Indexing may lag."},
        {"status": "incomplete", "reason": "Book timestamp falls outside the interval from detection to receipt.",
         "event": {"eventTimeSeconds": 1795608002, "shares": "14", "price": "0.52", "fillId": None}},
        {"status": "unavailable", "reason": "Public endpoint unreachable or denied."},
        {"status": "observed", "reason": "Displayed depth only.",
         "event": {"eventTimeSeconds": 1795608002, "shares": "14", "price": "0.52", "fillId": None},
         "activityReceivedMs": 1795608005010, "bookReceivedMs": 1795608005060,
         "book": {"sourceTimeMs": 1795608005050, "sourceAgeAtDetectionMs": -40, "bestAskMinusLeaderPrice": "0.03", "askLevelCount": 1, "bestAsks": [{"price": "0.55", "shares": "21.25"}]}},
    ]

    def probe(route: Route):
        assert route.request.method == "POST" and route.request.post_data_json == {}
        route.fulfill(json={**samples.pop(0), "schemaVersion": 1, "wallet": wallet,
                            "windowStartSeconds": 1795608000, "windowEndSeconds": 1795608004})

    page.route("**/api/v1/public/traders/*/observe", probe)
    button = page.get_by_role("button", name="Observe next BUY")
    button.click()
    expect(page.get_by_role("heading", name="No BUY observed in this window")).to_be_visible()
    button.click()
    expect(page.get_by_role("heading", name="Partial evidence")).to_be_visible()
    expect(page.get_by_text("Individual fill identity", exact=False)).to_be_visible()
    with page.expect_download() as download:
        page.get_by_role("link", name="Download observation").click()
    receipt = json.loads(download.value.path().read_text())
    assert receipt["wallet"] == wallet and receipt["event"]["fillId"] is None
    capture(page, output, "public-observation-partial-fixture")
    button.click()
    expect(page.get_by_role("heading", name="Observation unavailable")).to_be_visible()
    button.click()
    expect(page.get_by_role("heading", name="BUY and displayed book observed")).to_be_visible()
    expect(page.get_by_role("cell", name="21.25", exact=True)).to_be_visible()
    expect(page.get_by_text("40 ms after detection", exact=True)).to_be_visible()
    expect(page.get_by_text("0.03 per share", exact=True)).to_be_visible()
    assert not samples
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
    delayed_period = None
    fixture_state = "empty"
    period.select_option(alternate)
    expect(page.get_by_text("Polymarket returned an empty page.", exact=True)).to_be_visible()
    expect(lumen).to_have_count(0)
    assert alternate in requested_periods and default_period in requested_periods
    page.close()
    print("Passed public ranking filters, stale and unavailable results, profile inspection and wallet prefill using fixture reads.")


def public_artifact_smoke(browser: Browser, cwd: Path, output: Path | None):
    """Opt-in. Inspect a real public ranking and persist one read-only watch."""
    # Reuse the installer test's launcher to exercise the actual shipped code.
    sys.path.insert(0, str(ROOT / "tests"))
    from install_smoke import app

    installer = [sys.executable, str(ROOT / "dist/polysia.pyz"), "--prefix", str(cwd / "app"), "--json"]
    installed = json.loads(subprocess.check_output(installer, cwd=cwd))
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
        print(f"Installed {installed['artifactSha256'][:12]}: {len(board['leaders'])} provider-ranked wallets; "
              f"{len(watch['positions'])} position rows, complete={watch['complete']}, retrieved {watch['observedAt']}.")
        page.get_by_role("button", name="Remove watch").click()
        expect(page.get_by_role("heading", name="Account scope")).to_be_visible()
        page.close()
    assert json.loads(subprocess.check_output(installer, cwd=cwd)) == installed


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
                    exercise(browser, origin, options.screenshots)
                    assisted_budget_journey(browser, origin, options.screenshots)
                    public_rankings_journey(browser, origin, options.screenshots)
        finally:
            browser.close()


if __name__ == "__main__":
    main()
