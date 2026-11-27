"""Install the bundled release offline locally or configure an owner-only HTTPS deployment."""

import argparse
import fcntl
import hashlib
import http.client
import json
import os
import re
import shlex
import socket
import sqlite3
import stat
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from zipfile import ZipFile


def install(archive: Path, prefix: Path):
    # The shipped SQLite schema and runtime use the Python 3.12 stdlib baseline.
    if sys.version_info < (3, 12):
        raise ValueError("PolySia requires Python 3.12 or newer with sqlite3.")
    # Exercise the extension before publishing the release.
    with sqlite3.connect(":memory:") as db:
        db.execute("SELECT 1")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    relative_release = Path("releases") / digest
    release = prefix / relative_release
    current = prefix / "current"
    if current.is_symlink():
        previous = Path(os.readlink(current))
        if previous.parent != Path("releases") or not re.fullmatch(r"[0-9a-f]{64}", previous.name):
            raise ValueError("The installation prefix contains an unrelated current symlink.")
    elif current.exists():
        raise ValueError("The installation prefix already contains an unrelated current entry.")
    if release.parent.is_symlink() or release.is_symlink():
        raise ValueError("Choose a dedicated prefix with a local releases directory.")
    release.parent.mkdir(mode=0o700, exist_ok=True)
    if release.exists():
        # A directory named after the archive does not prove its contents
        # survived intact. Preserve local modifications and report them.
        with ZipFile(archive) as bundle:
            expected = set(bundle.namelist()) - {"__main__.py"}
            for item in release.rglob("*"):
                if item.is_dir() and not item.is_symlink():
                    continue
                name = item.relative_to(release).as_posix()
                if item.is_symlink() or not item.is_file() or name not in expected:
                    raise ValueError(f"Unexpected installed file: {item}. Preserve the directory and install in a fresh prefix.")
                if item.read_bytes() != bundle.read(name):
                    raise ValueError(f"Installed file differs from the artifact: {item}. Preserve the directory and install in a fresh prefix.")
                expected.remove(name)
            if expected or not os.access(release / "polysia", os.X_OK):
                raise ValueError("Installed release is incomplete. Preserve the directory and install in a fresh prefix.")
    else:
        with tempfile.TemporaryDirectory(prefix=".prepare-", dir=release.parent) as stage:
            staged = Path(stage) / "release"
            staged.mkdir()
            with ZipFile(archive) as bundle:
                for name in bundle.namelist():
                    if name != "__main__.py":
                        bundle.extract(name, staged)
            (staged / "polysia").chmod(0o700)
            staged.rename(release)
    database = prefix / "data/workspace.sqlite3"
    if current.is_symlink() and previous != relative_release and database.is_file():
        backups = prefix / "backups"
        if backups.is_symlink():
            raise ValueError("The backups directory must be inside the installation.")
        backups.mkdir(mode=0o700, exist_ok=True)
        snapshot = backups / f"{previous.name}-{uuid.uuid4().hex}.sqlite3"
        subprocess.run([sys.executable, "-I", str(release / "polysia"), "restore",
                        "--from", str(database), "--to", str(snapshot)], stdout=sys.stderr, check=True)
        print(f"Pre-upgrade workspace backup: {snapshot}", file=sys.stderr)
    with tempfile.TemporaryDirectory(prefix=".activate-", dir=prefix) as stage:
        link = Path(stage) / "current"
        link.symlink_to(relative_release)
        os.replace(link, current)
    return {"artifactSha256": digest, "launcher": str(current / "polysia"),
            "data": str(prefix / "data"), "defaultUrl": "http://127.0.0.1:8765"}


def check_port(port):
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError as exc:
            raise ValueError(f"Cannot use local port {port}: {exc.strerror}. "
                             "Stop its listener or choose another port with --port PORT.") from exc


def prepare_remote_prefix(prefix):
    """Check each directory before creating anything beneath it."""
    uid = os.geteuid()
    for directory in (*reversed(prefix.parents), prefix):
        directory.mkdir(mode=0o700, exist_ok=True)
        info = directory.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid not in (0, uid)
                or (info.st_mode & 0o022 and not info.st_mode & stat.S_ISVTX)):
            raise ValueError("Choose an HTTPS install path under the dedicated service user's private home.")
    if info.st_uid != uid or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError("The HTTPS installation prefix must belong to the service user and have mode 0700.")


def manager(*arguments, allow_missing_unit=False):
    result = subprocess.run(arguments, capture_output=True, text=True, timeout=45)
    missing = (allow_missing_unit and result.returncode == 4 and "LoadState=not-found" in result.stdout.splitlines())
    if result.returncode and not missing:
        raise ValueError(f"{shlex.join(arguments)} failed: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout.strip()


def prepare_service(prefix, port):
    if manager("loginctl", "show-user", str(os.getuid()), "-p", "Linger", "--value") != "yes":
        raise ValueError("Boot startup requires a lingering systemd user manager. Enable lingering for "
                         "this OS user with loginctl enable-linger, or use --start for foreground use.")
    unit = Path(os.getenv("XDG_CONFIG_HOME") or Path.home() / ".config") / "systemd/user/polysia.service"
    launcher = str(prefix / "current/polysia")

    def quote(value):
        if not value.isprintable():
            raise ValueError("The Python and installation paths must contain printable characters.")
        return '"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%').replace('$', '$$') + '"'

    definition = (
        "[Unit]\nDescription=PolySia local simulated trading workspace\n\n"
        "[Service]\nType=notify\nTimeoutStartSec=25\nUMask=0077\n"
        "UnsetEnvironment=POLYSIA_DB PYTHONHOME PYTHONPATH\n"
        f"ExecStart={quote(sys.executable)} -I {quote(launcher)} --port {port}\n"
        "Restart=on-failure\nRestartSec=5\n\n[Install]\nWantedBy=default.target\n"
    )
    if unit.is_symlink() or (unit.exists() and unit.read_text() != definition):
        raise ValueError(f"Conflicting service at {unit}. Keep its original settings or use --start.")
    props = manager("systemctl", "--user", "show", "polysia.service",
                    "-p", "FragmentPath", "-p", "DropInPaths", "-p", "ActiveState", "-p", "LoadState",
                    "--all", allow_missing_unit=True)
    state = dict(line.split("=", 1) for line in props.splitlines())
    fragment = state.get("FragmentPath")
    if (state["LoadState"] not in ("not-found", "loaded") or state["DropInPaths"]
            or (fragment and (Path(fragment) != unit or not unit.exists()))):
        raise ValueError("Another polysia.service definition is present. Inspect systemctl --user cat polysia.service.")
    if state["ActiveState"] not in ("active", "failed", "inactive"):
        raise ValueError("The service is changing state. Retry once systemctl --user status polysia.service is stable.")
    return unit, definition, state["ActiveState"] == "active"


def service_health(port, digest):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        connection.request("GET", "/api/v1/health")
        response = connection.getresponse()
        health = json.loads(response.read(8192))
        if (response.status != 200 or not isinstance(health, dict) or health.get("status") != "ok"
                or health.get("artifactSha256") != digest or not isinstance(health.get("version"), str)):
            raise ValueError("The running service does not match the bundle. Back up the workspace, "
                             "stop polysia.service and retry the installation.")
        return health
    finally:
        connection.close()


def start_service(unit, definition, port, result):
    unit.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not unit.exists():
        with tempfile.TemporaryDirectory(dir=unit.parent) as tmp:
            staged = Path(tmp) / unit.name
            staged.write_text(definition)
            os.link(staged, unit)
    manager("systemctl", "--user", "daemon-reload")
    manager("systemctl", "--user", "start", unit.name)
    health = service_health(port, result["artifactSha256"])
    manager("systemctl", "--user", "enable", unit.name)
    result.update(service=unit.name, url=f"http://127.0.0.1:{port}", health=health)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", type=Path, default=Path.home() / ".local/share/polysia",
                        help="Dedicated local install and data directory.")
    parser.add_argument("--json", action="store_true", help="Print the installed paths as JSON.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--start", action="store_true", help="Install, verify storage and serve the local workspace from this terminal.")
    mode.add_argument("--service", action="store_true", help="Install and enable a persistent systemd user service; requires lingering.")
    mode.add_argument("--cloudflare", action="store_true", help="Guide single-owner HTTPS deployment on a dedicated Linux host.")
    mode.add_argument("--prepare-cloudflare-host", action="store_true", help=(
        "Ubuntu 26.04 amd64, root: prepare a dedicated polysia-service user, Ubuntu JWT packages, "
        "pinned cloudflared and boot persistence, then continue owner-only deployment as that user."))
    parser.add_argument("--port", type=int, help="Local port for --start or --service (default 8765).")
    recovery = parser.add_mutually_exclusive_group()
    recovery.add_argument("--recover", dest="recover_tunnel", action="store_const", const="auto",
                          help="Transfer this hostname's verified PolySia tunnel to the current host.")
    # Existing scripts may pin an expected UUID. Recovery still discovers and checks the DNS target.
    recovery.add_argument("--recover-tunnel", type=uuid.UUID, metavar="UUID",
                          help=argparse.SUPPRESS)
    workspace = parser.add_mutually_exclusive_group()
    workspace.add_argument("--workspace-backup", type=Path, metavar="FILE", help="Restore a verified workspace during transfer.")
    workspace.add_argument("--empty-workspace", action="store_true", help="Accept a fresh workspace after losing the original.")
    args = parser.parse_args()
    if args.recover_tunnel and not (args.cloudflare or args.prepare_cloudflare_host):
        parser.error("Recovery requires an HTTPS deployment mode.")
    if (args.workspace_backup or args.empty_workspace) and not args.recover_tunnel:
        parser.error("Workspace recovery options require --recover.")
    os.umask(0o077)
    if args.start and args.json:
        parser.error("--json is available for install-only or --service.")
    if args.cloudflare and args.json:
        parser.error("--cloudflare uses guided deployment output.")
    if args.prepare_cloudflare_host and (args.json or args.prefix != Path.home() / ".local/share/polysia"):
        parser.error("--prepare-cloudflare-host uses a dedicated service home and guided output.")
    if args.port is not None and not (args.start or args.service):
        parser.error("--port requires --start or --service.")
    port = args.port if args.port is not None else 8765
    if not 0 <= port <= 65535 or (args.service and not port):
        parser.error("choose a port from 1 to 65535, or use --start --port 0 for an available port.")
    try:
        if args.prepare_cloudflare_host:
            from prepare_host import prepare
            prepare(Path(sys.argv[0]).resolve(strict=True), args.recover_tunnel,
                    args.workspace_backup, args.empty_workspace)
            return
        prefix = args.prefix.resolve()
        archive = Path(sys.argv[0])
        if args.cloudflare:
            prepare_remote_prefix(prefix)
        else:
            prefix.mkdir(mode=0o700, parents=True, exist_ok=True)
        with (prefix / ".polysia-install.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ValueError("Another PolySia installation is running. Finish it before retrying.") from None
            remote = prefix / "remote"
            if args.cloudflare:
                if not (remote / "deployment.json").is_file() and any(
                        (prefix / item).exists() for item in ("current", "releases", "data")):
                    raise ValueError("This prefix already contains an installation. Choose a fresh prefix "
                                     "for owner-only HTTPS and keep the existing workspace in its original prefix.")
                from cloudflare_setup import setup
                setup(archive=archive, prefix=prefix, install=install,
                      recovery_id=str(args.recover_tunnel) if args.recover_tunnel else None,
                      backup=args.workspace_backup, empty_workspace=args.empty_workspace)
                return
            if remote.exists():
                raise ValueError("This prefix is reserved for owner-only HTTPS. Rerun with --cloudflare "
                                 "or choose a separate prefix for a local installation.")
            if args.service:
                unit, definition, active = prepare_service(prefix, port)
                if active:
                    service_health(port, hashlib.sha256(archive.read_bytes()).hexdigest())
                else:
                    check_port(port)
            elif args.start:
                check_port(port)
            result = install(archive, prefix)
            if args.service:
                start_service(unit, definition, port, result)
        if args.start:
            launcher = prefix / "releases" / result["artifactSha256"] / "polysia"
            print("Starting your local workspace. Press Ctrl-C to stop.", file=sys.stderr, flush=True)
            env = {**os.environ, "POLYSIA_DB": str(prefix / "data/workspace.sqlite3")}
            os.execve(sys.executable, [sys.executable, "-I", str(launcher), "--port", str(port)], env)
    except (EOFError, KeyboardInterrupt):
        parser.exit(1, "\nSetup interrupted. Rerun the installer on this host to continue.\n")
    except (OSError, ValueError, http.client.HTTPException, subprocess.SubprocessError) as exc:
        parser.exit(1, f"Installation failed: {exc}\n")
    if args.json:
        print(json.dumps(result))
    elif args.service:
        print(f"PolySia {result['health']['version']} is healthy at {result['url']}.")
        print("Starts at boot. Inspect or stop with systemctl --user status or stop polysia.service.")
    else:
        print(f"Installed PolySia {result['artifactSha256'][:12]}.")
        print(f"Start the local application with {shlex.quote(result['launcher'])}")
        print(f"Then open {result['defaultUrl']}. Data is stored in {result['data']}.")


if __name__ == "__main__":
    main()
