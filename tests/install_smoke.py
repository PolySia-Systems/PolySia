"""Exercise the offline distributable, with an optional upgrade from a saved prior artifact."""

import argparse
import hashlib
import json
import os
import pty
import re
import select
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        src = dict(attrs).get("src")
        if tag == "script" and src:
            self.scripts.append(src)


@contextmanager
def app(launcher, cwd, database=None, offline=False, install_prefix=None):
    # Use an ephemeral OS-selected port. Exclude development workspace overrides.
    env = {k: v for k, v in os.environ.items() if k not in ("POLYSIA_DB", "PYTHONPATH")}
    if offline:
        env.update(https_proxy="http://127.0.0.1:1", no_proxy="127.0.0.1,localhost")
    if database is not None:
        env["POLYSIA_DB"] = str(database)
    command = [launcher] if install_prefix is None else [
        sys.executable, launcher, "--start", "--prefix", install_prefix
    ]
    with subprocess.Popen([*command, "--port", "0"], cwd=cwd, env=env,
                          stdout=subprocess.PIPE, text=True) as server:
        try:
            if not select.select([server.stdout], [], [], 15)[0]:
                raise RuntimeError("Installed application timed out during startup.")
            line = server.stdout.readline().strip()
            url = line.removeprefix("PolySia is running at ")
            if not url.startswith("http://127.0.0.1:"):
                raise RuntimeError(f"Unexpected startup result {line!r}")
            yield url
        finally:
            server.terminate()
            server.wait(timeout=10)


def request(url, path, payload=None, method=None):
    req = Request(url + path, method=method or ("GET" if payload is None else "PUT"))
    if payload is not None:
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps(payload).encode()
    with urlopen(req, timeout=5) as response:
        return response.read()


def verify():
    with tempfile.TemporaryDirectory(prefix="polysia-install-") as temp:
        cwd = Path(temp)
        bundle = cwd / "polysia.pyz"
        shutil.copyfile(ROOT / "dist/polysia.pyz", bundle)
        prefix = cwd / "test installation"
        command = [sys.executable, str(bundle), "--prefix", str(prefix), "--json"]
        shared = cwd / "shared"
        shared.mkdir()
        shared.chmod(0o777)
        unsafe = subprocess.run([sys.executable, str(bundle), "--prefix", str(shared / "app"), "--cloudflare"],
                                cwd=cwd, capture_output=True, text=True, timeout=5)
        assert unsafe.returncode and "private home" in unsafe.stderr and not (shared / "app").exists()
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            busy = subprocess.run([*command[:-1], "--start", "--port", str(listener.getsockname()[1])],
                                  cwd=cwd, capture_output=True, text=True, timeout=10)
            assert busy.returncode and "choose another port" in busy.stderr and not (prefix / "current").exists()
        with app(bundle, cwd, offline=True, install_prefix=prefix) as url:
            health = json.loads(request(url, "/api/v1/health"))
            assert health["status"] == "ok" and health["version"]
            assets = Assets()
            assets.feed(request(url, "/").decode())
            assert assets.scripts, "Installed index has no entry module"
            for script in assets.scripts:
                assert script.startswith("/assets/")
                assert len(request(url, script)) > 100, f"Missing installed script {script}"
            # An explicitly started offline probe must leave the installed code
            # directory intact for subsequent integrity-checked reinstalls.
            path = "/api/v1/public/traders/0x" + "1" * 40 + "/observe"
            probe = Request(url + path, data=b"{}", headers={"Content-Type": "application/json"})
            with urlopen(probe, timeout=22) as response:
                assert json.loads(response.read())["status"] == "unavailable"
            settings = json.loads(request(url, "/api/v1/workspace"))["settings"]
            assert settings["theme"] == "light"
            settings["theme"] = "dark"
            updated = json.loads(request(url, "/api/v1/settings", settings))
            assert updated["theme"] == "dark" and updated["revision"] > settings["revision"]
            run = json.loads(request(url, "/api/v1/runs",
                                     {"leaderId": "atlas", "allocation": "100", "orderSize": "10"}, "POST"))
            route = "/api/v1/runs/" + run["id"]
            fill = json.loads(request(url, route + "/step", {"revision": run["revision"]}, "POST"))
            stopped = json.loads(request(url, route + "/stop", {"revision": fill["revision"]}, "POST"))
            assert int(stopped["quantity"]) > 0 and stopped["status"] == "stopped"
        installed = json.loads(subprocess.check_output(command, cwd=cwd))
        assert health["artifactSha256"] == installed["artifactSha256"]
        env = {k: v for k, v in os.environ.items() if k not in ("POLYSIA_DB", "PYTHONPATH")}
        launcher = installed["launcher"]
        study_path = cwd / "public-study.jsonl"
        offline = {**env, "https_proxy": "http://127.0.0.1:1", "no_proxy": "127.0.0.1,localhost"}
        study_command = [launcher, "study", "0x" + "1" * 40, "--budget", "10", "--seconds", "2",
                         "--windows", "1", "--retry-empty", "--recheck-after", "1", "--to", str(study_path)]
        study = json.loads(subprocess.check_output(study_command, cwd=cwd, env=offline, timeout=35))
        assert study["outcomes"] == {"unavailable": 1}
        rows = [json.loads(line) for line in study_path.read_text().splitlines()]
        assert [r["type"] for r in rows] == ["plan", "attempt", "window", "activityRecheck", "summary"]
        assert "reason" in rows[3] and study["initiallyEmptyWindowsCompared"] == 0
        assert rows[0]["schemaVersion"] == 3 and study["retriesAttempted"] == 0
        assert len(rows[2]["receipt"]["activityReads"]) == 1
        assert rows[2]["receipt"]["researchBudget"] == "10.00"
        backup, restore = cwd / "backup.db", cwd / "restored.db"
        subprocess.run([launcher, "backup", "--to", backup], cwd=cwd, env=env, check=True)
        subprocess.run([launcher, "restore", "--from", backup, "--to", restore],
                       cwd=cwd, env=env, check=True)
        with app(launcher, cwd, restore) as url:
            restored = json.loads(request(url, "/api/v1/workspace"))
            assert restored["settings"] == updated and restored["run"] == stopped

        repeated = json.loads(subprocess.check_output(command, cwd=cwd))
        assert installed == repeated
        assert len(list((prefix / "releases").iterdir())) == 1
        with app(repeated["launcher"], cwd) as url:
            state = json.loads(request(url, "/api/v1/workspace"))
            assert state["settings"] == updated and state["run"] == stopped
            # Initial HTTPS deployment cannot adopt a local installation, even while it is running.
            conversion = subprocess.run([*command[:-1], "--cloudflare"], cwd=cwd, capture_output=True,
                                        text=True, timeout=5)
            assert conversion.returncode and "fresh prefix" in conversion.stderr, conversion.stderr
            assert not (prefix / "remote").exists()
            assert json.loads(request(url, "/api/v1/workspace")) == state
        # Model the mode reservation from the HTTPS installer. Check all local startup
        # paths before any service, database or activation change can take place.
        remote = prefix / "remote"
        remote.mkdir(mode=0o700)
        (remote / "deployment.json").write_text("{}")
        for local in ([*command[:-1], "--start", "--port", "0"], [*command[:-1], "--service"], [launcher, "--port", "0"]):
            denied = subprocess.run(local, cwd=cwd, env=env, capture_output=True, text=True, timeout=5)
            assert denied.returncode and "owner-only HTTPS" in denied.stderr, denied.stderr
        copy = cwd / "owner-backup.db"
        subprocess.run([launcher, "backup", "--to", copy], cwd=cwd, env=env, check=True)
        (remote / "deployment.json").unlink()
        remote.rmdir()
        # A damaged code directory cannot be reported as a successful reinstall.
        index = Path(repeated["launcher"]).parent / "apps/web/dist/index.html"
        index.write_text("changed locally")
        damaged = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
        assert damaged.returncode and "differs from the artifact" in damaged.stderr
        assert index.read_text() == "changed locally"
        print(f"Offline install {installed['artifactSha256'][:12]} served the SPA and API. "
              "Reinstall, restart and restoring a backup preserved the preference and its revision.")


def verify_upgrade(previous):
    with tempfile.TemporaryDirectory(prefix="polysia-upgrade-") as temp:
        cwd = Path(temp)
        prefix = cwd / "installed workspace"

        def install(bundle):
            output = subprocess.check_output(
                [sys.executable, str(bundle), "--prefix", str(prefix), "--json"], cwd=cwd
            )
            return json.loads(output)

        original = install(previous.resolve())
        previous_launcher = Path(original["launcher"]).resolve()
        with app(original["launcher"], cwd, offline=True) as url:
            prior_version = json.loads(request(url, "/api/v1/health"))["version"]
            request(url, "/api/v1/settings", {"version": 1, "revision": 0, "theme": "dark"})
            run = json.loads(request(url, "/api/v1/runs",
                                     {"leaderId": "atlas", "allocation": "100", "orderSize": "10"}, "POST"))
            route = "/api/v1/runs/" + run["id"]
            fill = json.loads(request(url, route + "/step", {"revision": run["revision"]}, "POST"))
            request(url, route + "/pause", {"revision": fill["revision"]}, "POST")
            legacy = None
            legacy_path = "/api/v1/public-runs/" + "30" * 16
            if prior_version in ("0.3.0", "0.4.0", "0.5.0", "0.6.0", "0.7.0", "0.8.0"):
                request(url, legacy_path, {"name": "Legacy rules", "wallet": "0x" + "bc" * 20, "capital": "15", "cap": "5"})
                legacy = json.loads(request(url, legacy_path + "/pause", {"revision": 1}, "POST"))
            saved = json.loads(request(url, "/api/v1/workspace"))
            assert saved["run"]["status"] == "paused" and int(saved["run"]["quantity"]) > 0

        with sqlite3.connect(Path(original["data"]) / "workspace.sqlite3") as db:
            previous_schema = db.execute("PRAGMA user_version").fetchone()[0]
        db.close()
        database = Path(original["data"]) / "workspace.sqlite3"
        saved_file = cwd / "original.sqlite3"
        database.rename(saved_file)
        database.write_bytes(b"incomplete workspace")
        rejected = subprocess.run([sys.executable, ROOT / "dist/polysia.pyz", "--prefix", prefix],
                                  capture_output=True, timeout=10)
        assert rejected.returncode and Path(original["launcher"]).resolve() == previous_launcher
        assert database.read_bytes() == b"incomplete workspace"
        saved_file.replace(database)
        upgraded = install(ROOT / "dist/polysia.pyz")
        assert original["artifactSha256"] != upgraded["artifactSha256"]
        snapshot, = (prefix / "backups").glob("*.sqlite3")
        with app(previous_launcher, cwd, snapshot, offline=True) as url:
            assert json.loads(request(url, "/api/v1/workspace")) == saved
        launcher = upgraded["launcher"]
        with app(launcher, cwd, offline=True) as url:
            health = json.loads(request(url, "/api/v1/health"))
            assert health["artifactSha256"] == upgraded["artifactSha256"]
            assert json.loads(request(url, "/api/v1/workspace")) == {"savedWallets": [], **saved}
            stopped = json.loads(request(url, route + "/stop", {"revision": saved["run"]["revision"]}, "POST"))
            assert stopped["revision"] == saved["run"]["revision"] + 1
            assert stopped["quantity"] == saved["run"]["quantity"] and stopped["events"] == saved["run"]["events"]
            end_state = json.loads(request(url, "/api/v1/workspace"))
            if legacy:
                prior = json.loads(request(url, legacy_path))
                assert prior["backgroundEnabled"] is False
                assert prior["policy"] == legacy["policy"] and prior["decisions"] == legacy["decisions"]
                assert prior["cash"] == legacy["cash"]
                if prior_version in ("0.3.0", "0.4.0"):
                    assert "checkSalesBeforeEntry" not in prior["policy"]
                changed = prior
                if prior_version == "0.3.0":
                    assert not prior["exitsEnabled"]
                    changed = json.loads(request(url, legacy_path + "/enable-exits", {"revision": prior["revision"]}, "POST"))
                assert changed["exitsEnabled"] and changed["status"] == "paused"
            public_route = "/api/v1/public-runs/" + "a1" * 16
            public_run = json.loads(request(url, public_route, {"wallet": "0x" + "ab" * 20,
                             "name": "Upgrade trial", "capital": "30", "cap": "10"}))
            assert public_run["status"] == "running" and public_run["cash"] == "30"
            assert public_run["policy"]["checkSalesBeforeEntry"] is True
            public_end = json.loads(request(url, public_route + "/pause", {"revision": 1}, "POST"))
        backup, recovered = cwd / "backup.db", cwd / "restored.db"
        env = {k: v for k, v in os.environ.items() if k not in ("POLYSIA_DB", "PYTHONPATH")}
        subprocess.run([launcher, "backup", "--to", backup], cwd=cwd, env=env, check=True)
        subprocess.run([launcher, "restore", "--from", backup, "--to", recovered], cwd=cwd, env=env, check=True)
        with app(launcher, cwd, recovered, offline=True) as url:
            assert json.loads(request(url, "/api/v1/workspace")) == end_state
            assert json.loads(request(url, public_route)) == public_end
            if legacy:
                assert json.loads(request(url, legacy_path)) == changed
        if previous_schema < 7:
            old = subprocess.run([previous_launcher, "--port", "0"], cwd=cwd, capture_output=True, text=True,
                                 env={**env, "POLYSIA_DB": str(recovered)}, timeout=5)
            assert old.returncode and "Unsupported workspace database version 7" in old.stderr, old.stderr
            with app(launcher, cwd, recovered, offline=True) as url:
                assert json.loads(request(url, public_route)) == public_end
        print(f"Upgrade {prior_version} to {health['version']} preserved a paused position, "
              "settings and revisions. Restore retained recorded fills and the new public shadow run.")


def verify_readme(bundle, release_guide):
    """Run the copyable command on its destination. Substitute only the two downloads."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    install = readme.split("## Install on Linux", 1)[1].split("\n## ", 1)[0]
    command = re.search(r"```sh\n(.+?)\n```", install, re.S).group(1)
    bootstrap = release_guide.read_bytes()
    assert bootstrap == (ROOT / "install").read_bytes(), "The release installer differs from the reviewed entry"
    tag = re.search(rb"^version=([\d.]+)$", bootstrap, re.M).group(1).decode()
    digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
    assert f"sha256={digest}".encode() in bootstrap.splitlines(), "The installer digest differs from the bundle"
    with tempfile.TemporaryDirectory(prefix="polysia-readme-") as directory:
        fixture = Path(directory)
        cwd = fixture / "empty"
        cwd.mkdir()
        curl = fixture / "curl"
        curl.write_text("""#!/bin/sh
set -eu
for url do :; done
case "$url" in
  https://github.com/PolySia-Systems/PolySia/releases/latest/download/install)
    cat "$ENTRY"
    exit "${ENTRY_STATUS:-0}" ;;
  "$ASSET_URL")
    while [ "$1" != --output ]; do shift; done
    cp "$ARCHIVE" "$2" ;;
  *) exit 22 ;;
esac
""")
        curl.chmod(0o700)
        entry = fixture / "entry"
        archive = fixture / "archive"
        env = {"HOME": str(cwd), "PATH": str(fixture) + ":" + os.environ["PATH"],
               "ENTRY": str(entry), "ARCHIVE": str(archive),
               "ASSET_URL": f"https://github.com/PolySia-Systems/PolySia/releases/download/v{tag}/polysia.pyz"}
        # A transport failure can leave complete, executable lines in the response.
        entry.write_text('touch "$HOME/executed"\n')
        rejected = subprocess.run(["sh", "-c", command], cwd=cwd, env={**env, "ENTRY_STATUS": "18"})
        assert rejected.returncode and not (cwd / "executed").exists()

        entry.write_bytes(bootstrap)
        archive.write_text("from pathlib import Path\nPath('executed').touch()\n")
        master, slave = pty.openpty()
        try:
            os.write(master, b"1\n")
            rejected = subprocess.run(["sh", "-c", command], cwd=cwd, env=env, stdin=slave,
                                      capture_output=True, timeout=10)
            assert rejected.returncode and b"integrity check" in rejected.stderr and not (cwd / "executed").exists()
            assert not (cwd / ".local").exists()
            shutil.copyfile(bundle, archive)
            os.write(master, "wrong\n ۱ \n".encode())
            log_path = fixture / "output.log"
            with log_path.open("w") as output:
                server = subprocess.Popen(["sh", "-c", command], cwd=cwd, env=env, stdout=output,
                                          stderr=output, stdin=slave, start_new_session=True)
            try:
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline:
                    log = log_path.read_text()
                    assert server.poll() is None, log
                    started = re.search(r"PolySia is running at (http://127\.0\.0\.1:\d+)", log)
                    if started:
                        break
                    time.sleep(0.1)
                else:
                    raise RuntimeError("README startup timed out: " + log)
                health = json.loads(request(started.group(1), "/api/v1/health"))
                assert health["status"] == "ok" and health["version"] == tag, health
                assert health["artifactSha256"] == digest, health
                assert "Enter the number beside your choice." in log
            finally:
                if server.poll() is None:
                    os.killpg(server.pid, signal.SIGTERM)
                server.wait(timeout=5)
        finally:
            os.close(master)
            os.close(slave)
        print(f"README rejected incomplete and changed downloads and started verified PolySia {tag} ({digest}).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-guide", type=Path, default=ROOT / "install",
                        help="Check the exact guided installation script shipped alongside the bundle.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--release-bundle", type=Path, help="Check the README against these release bytes.")
    mode.add_argument("--upgrade-from", type=Path, metavar="PREVIOUS.pyz",
                        help="Exercise an upgrade from this prior offline bundle.")
    args = parser.parse_args()
    if args.release_bundle:
        verify_readme(args.release_bundle, args.release_guide)
    elif args.upgrade_from:
        verify_upgrade(args.upgrade_from)
    else:
        verify()
