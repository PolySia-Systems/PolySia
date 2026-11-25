"""Exercise the distributable twice from outside its source checkout."""

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
def app(launcher, cwd, database=None):
    # Use an ephemeral OS-selected port. Exclude development workspace overrides.
    env = {k: v for k, v in os.environ.items() if k not in ("POLYSIA_DB", "PYTHONPATH")}
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


def request(url, path, payload=None):
    req = Request(url + path, method="GET" if payload is None else "PUT")
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
        with app(installed["launcher"], cwd) as url:
            assert json.loads(request(url, "/api/v1/health"))
            assets = Assets()
            assets.feed(request(url, "/").decode())
            assert assets.scripts, "Installed index has no entry module"
            for script in assets.scripts:
                assert script.startswith("/assets/")
                assert len(request(url, script)) > 100, f"Missing installed script {script}"
            settings = json.loads(request(url, "/api/v1/workspace"))["settings"]
            assert settings["theme"] == "light"
            settings["theme"] = "dark"
            updated = json.loads(request(url, "/api/v1/settings", settings))
            assert updated["theme"] == "dark" and updated["revision"] > settings["revision"]
        env = {k: v for k, v in os.environ.items() if k not in ("POLYSIA_DB", "PYTHONPATH")}
        launcher = installed["launcher"]
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
        print(f"Offline install {installed['artifactSha256'][:12]} served the SPA and API. "
              "Reinstall, restart and restoring a backup preserved the preference and its revision.")


if __name__ == "__main__":
    verify()
