"""Exercise the offline distributable, with an optional upgrade from a saved prior artifact."""

import argparse
import json
import os
import select
import shutil
import subprocess
import sys
import tempfile
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
def app(launcher, cwd, database=None, offline=False):
    # Use an ephemeral OS-selected port. Exclude development workspace overrides.
    env = {k: v for k, v in os.environ.items() if k not in ("POLYSIA_DB", "PYTHONPATH")}
    if offline:
        env.update(https_proxy="http://127.0.0.1:1", no_proxy="127.0.0.1,localhost")
    if database is not None:
        env["POLYSIA_DB"] = str(database)
    with subprocess.Popen([launcher, "--port", "0"], cwd=cwd, env=env,
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
        installed = json.loads(subprocess.check_output(command, cwd=cwd))
        with app(installed["launcher"], cwd, offline=True) as url:
            assert json.loads(request(url, "/api/v1/health"))["artifactSha256"] == installed["artifactSha256"]
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
        env = {k: v for k, v in os.environ.items() if k not in ("POLYSIA_DB", "PYTHONPATH")}
        launcher = installed["launcher"]
        study_path = cwd / "public-study.jsonl"
        offline = {**env, "https_proxy": "http://127.0.0.1:1", "no_proxy": "127.0.0.1,localhost"}
        study_command = [launcher, "study", "0x" + "1" * 40, "--budget", "10", "--seconds", "1",
                         "--windows", "1", "--to", str(study_path)]
        study = json.loads(subprocess.check_output(study_command, cwd=cwd, env=offline, timeout=35))
        assert study["outcomes"] == {"unavailable": 1}
        rows = [json.loads(line) for line in study_path.read_text().splitlines()]
        assert [r["type"] for r in rows] == ["plan", "attempt", "window", "summary"]
        assert rows[2]["receipt"]["researchBudget"] == "10.00"
        backup, restore = cwd / "backup.db", cwd / "restored.db"
        subprocess.run([launcher, "backup", "--to", backup], cwd=cwd, env=env, check=True)
        subprocess.run([launcher, "restore", "--from", backup, "--to", restore],
                       cwd=cwd, env=env, check=True)
        with app(launcher, cwd, restore) as url:
            assert json.loads(request(url, "/api/v1/workspace"))["settings"] == updated

        repeated = json.loads(subprocess.check_output(command, cwd=cwd))
        assert installed == repeated
        assert len(list((prefix / "releases").iterdir())) == 1
        with app(repeated["launcher"], cwd) as url:
            assert json.loads(request(url, "/api/v1/workspace"))["settings"] == updated
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
        with app(original["launcher"], cwd, offline=True) as url:
            prior_version = json.loads(request(url, "/api/v1/health"))["version"]
            request(url, "/api/v1/settings", {"version": 1, "revision": 0, "theme": "dark"})
            run = json.loads(request(url, "/api/v1/runs",
                                     {"leaderId": "atlas", "allocation": "100", "orderSize": "10"}, "POST"))
            route = "/api/v1/runs/" + run["id"]
            fill = json.loads(request(url, route + "/step", {"revision": run["revision"]}, "POST"))
            request(url, route + "/pause", {"revision": fill["revision"]}, "POST")
            saved = json.loads(request(url, "/api/v1/workspace"))
            assert saved["run"]["status"] == "paused" and int(saved["run"]["quantity"]) > 0

        upgraded = install(ROOT / "dist/polysia.pyz")
        assert original["artifactSha256"] != upgraded["artifactSha256"]
        launcher = upgraded["launcher"]
        with app(launcher, cwd, offline=True) as url:
            health = json.loads(request(url, "/api/v1/health"))
            assert health["artifactSha256"] == upgraded["artifactSha256"]
            assert json.loads(request(url, "/api/v1/workspace")) == saved
            stopped = json.loads(request(url, route + "/stop", {"revision": saved["run"]["revision"]}, "POST"))
            assert stopped["revision"] == saved["run"]["revision"] + 1
            assert stopped["quantity"] == saved["run"]["quantity"] and stopped["events"] == saved["run"]["events"]
            end_state = json.loads(request(url, "/api/v1/workspace"))
        backup, recovered = cwd / "backup.db", cwd / "restored.db"
        env = {k: v for k, v in os.environ.items() if k not in ("POLYSIA_DB", "PYTHONPATH")}
        subprocess.run([launcher, "backup", "--to", backup], cwd=cwd, env=env, check=True)
        subprocess.run([launcher, "restore", "--from", backup, "--to", recovered], cwd=cwd, env=env, check=True)
        with app(launcher, cwd, recovered, offline=True) as url:
            assert json.loads(request(url, "/api/v1/workspace")) == end_state
        print(f"Upgrade {prior_version} to {health['version']} preserved a paused position, "
              "settings and revisions. Stop and restore retained the recorded fills.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upgrade-from", type=Path, metavar="PREVIOUS.pyz",
                        help="Exercise an upgrade from this prior offline bundle.")
    previous = parser.parse_args().upgrade_from
    if previous is None:
        verify()
    else:
        verify_upgrade(previous)
