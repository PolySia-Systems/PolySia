"""Exercise public-address paste validation on the installed Accounts page."""

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS))
from install_smoke import app


def check(bundle):
    with tempfile.TemporaryDirectory() as directory, sync_playwright() as pw:
        root = Path(directory)
        with app(bundle, root, offline=True, install_prefix=root / "install") as origin:
            browser = pw.chromium.launch(executable_path=shutil.which("chromium"))
            try:
                page = browser.new_page(viewport={"width": 390, "height": 844},
                                        permissions=["clipboard-read", "clipboard-write"])
                page.goto(origin + "/#/accounts")
                field = page.get_by_role("textbox", name="Public wallet address")
                submissions = []

                def observe(route):
                    submissions.append(route.request.post_data_json["address"])
                    route.fulfill(status=400, json={"error": "Controlled request."})

                page.route("**/api/v1/account", observe)
                # Use the browser's clipboard path. Playwright fill() bypasses
                # parts of native input handling and can hide truncation bugs.
                for value in ("0x" + "1" * 64, "0x" + "a" * 40 + "7"):
                    field.focus()
                    page.keyboard.press("Control+a")
                    page.evaluate("text => navigator.clipboard.writeText(text)", value)
                    page.keyboard.press("Control+v")
                    page.keyboard.press("Enter")
                    assert not submissions, "An overlong input reached the local account endpoint."
                    expect(field).to_be_focused()
                    expect(field).to_have_value(value)
                    expect(field).to_have_attribute("aria-invalid", "true")
                    expect(field).to_have_accessible_description("Use 0x followed by exactly 40 hexadecimal characters.")
                valid = "0x" + "ab" * 20
                field.focus()
                page.keyboard.press("Control+a")
                page.evaluate("text => navigator.clipboard.writeText(text)", valid)
                page.keyboard.press("Control+v")
                with page.expect_request("**/api/v1/account"):
                    page.keyboard.press("Enter")
                assert submissions == [valid]
                print("Wallet field rejected both complete oversized pastes locally and submitted the valid address once.")
            finally:
                browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    check(parser.parse_args().bundle.resolve())
