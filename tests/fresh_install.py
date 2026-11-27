"""Exercise the published installation journey in a disposable minimal Ubuntu image."""

import argparse
import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", action="store_true",
                        help="Fetch the named prerelease installer before promoting it to latest.")
    args = parser.parse_args()
    entry = (ROOT / "install").read_text(encoding="utf-8")
    version = re.search(r"^version=([\d.]+)$", entry, re.M)[1]
    digest = re.search(r"^sha256=([0-9a-f]{64})$", entry, re.M)[1]
    guide = (ROOT / "docs/operations.md").read_text(encoding="utf-8")
    section = guide.split("### Minimal Ubuntu images", 1)[1].split("\n## ", 1)[0]
    command = re.search(r"```sh\n(.+?)\n```", section, re.S)[1]
    if args.candidate:
        assert command.count("releases/latest/download/install") == 1
        command = command.replace("releases/latest/download/install", f"releases/download/v{version}/install")

    # A terminal on the target receives one answer. No source tree, credentials,
    # dependencies or downloaded assets are copied into this container.
    start = """
        set -eu
        for tool in curl python3 gh git; do
            if command -v "$tool" >/dev/null; then echo "Unexpected preinstalled $tool"; exit 1; fi
        done
        test ! -s /etc/ssl/certs/ca-certificates.crt
        cd "$(mktemp -d)"
        printf '1\\n' | script -qefc "$1" /dev/null
    """
    container = subprocess.check_output(["docker", "run", "-d", "ubuntu:26.04", "sh", "-c",
                                         start, "terminal", command], text=True).strip()
    try:
        # The shell exits if the install fails. A surprise question times out.
        probe = "until curl -qfsS http://127.0.0.1:8765/api/v1/health 2>/dev/null; do sleep 1; done"
        response = subprocess.check_output(["docker", "exec", container, "sh", "-c", probe],
                                           timeout=420, text=True)
        health = json.loads(response)
        assert health["status"] == "ok" and health["liveExecution"] is False, health
        assert health["version"] == version and health["artifactSha256"] == digest, health
        page = subprocess.check_output(["docker", "exec", container, "curl", "-qfsS", "http://127.0.0.1:8765/"])
        assert b"/assets/" in page, "The installed web UI has no built assets"
        log = subprocess.check_output(["docker", "logs", container], stderr=subprocess.STDOUT)
        assert b"Choose 1, 2 or 3:" in log and b"Geographic area:" not in log
        print(f"Fresh Ubuntu reached PolySia {version} ({digest}) with a single local-mode choice.")
    except (AssertionError, ValueError, subprocess.SubprocessError):
        subprocess.run(["docker", "logs", "--tail", "24", container], check=False)
        raise
    finally:
        subprocess.run(["docker", "rm", "-f", container], check=True, stdout=subprocess.DEVNULL)


if __name__ == "__main__":
    main()
