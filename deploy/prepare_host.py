"""Prepare a dedicated Ubuntu host for the same owner-only installer."""
import fcntl
import grp
import hashlib
import json
import os
import platform
import pwd
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from urllib.request import urlopen

USER = "polysia-service"
HOME_DIR = Path("/var/lib") / USER
ROOT = Path("/opt/polysia-host")
SYSTEM_PATH = "/usr/sbin:/usr/bin:/sbin:/bin"
CLOUDFLARED = "https://github.com/cloudflare/cloudflared/releases/download/2026.11.2/cloudflared-linux-amd64"
CONNECTOR_HASH = "56f13335143ec0e22772963290683a84a04114a35ec64cbc794a4d39ff9bb8cf"
RUNTIME_TEST = ("import sys, sqlite3, jwt; from jwt.algorithms import RSAAlgorithm; "
                "assert sys.version_info >= (3,12) and jwt.__version__.startswith('2.')")


def run(*args, capture=False):
    return subprocess.run(args, check=True, stdout=subprocess.PIPE if capture else None,
                          text=True, stdin=subprocess.DEVNULL, cwd="/",
                          env={"PATH": SYSTEM_PATH, "LC_ALL": "C", "DEBIAN_FRONTEND": "noninteractive",
                               "NEEDRESTART_MODE": "l"}).stdout


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


@contextmanager
def host_lock():
    fd = os.open(ROOT.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def install_bytes(target, expected, reader, mode):
    if target.exists() or target.is_symlink():
        if (target.is_symlink() or not target.is_file() or target.stat().st_uid != 0
                or stat.S_IMODE(target.stat().st_mode) != mode or digest(target) != expected):
            raise ValueError(f"Conflicting file at {target}. Existing contents were preserved.")
        return
    with tempfile.TemporaryDirectory(dir=target.parent) as tmp:
        staged = Path(tmp) / target.name
        with reader() as src, staged.open("xb") as out:
            shutil.copyfileobj(src, out)
        if digest(staged) != expected:
            raise ValueError(f"Integrity verification failed for {target.name}. Retry with the trusted artifact.")
        staged.chmod(mode)
        os.link(staged, target)


def workspace():
    parent = ROOT.parent
    if parent.is_symlink() or parent.stat().st_uid != 0 or parent.stat().st_mode & 0o022:
        raise ValueError(f"Host preparation requires a root-owned, protected {parent}.")
    marker = ROOT / "installation.json"
    if not ROOT.exists() and not ROOT.is_symlink():
        with tempfile.TemporaryDirectory(dir=parent) as tmp:
            staged = Path(tmp) / "managed"
            staged.mkdir()
            staged.chmod(0o755)
            (staged / marker.name).write_text(json.dumps({"account": USER, "instance": uuid.uuid4().hex}))
            staged.rename(ROOT)
    if (ROOT.is_symlink() or not ROOT.is_dir() or ROOT.stat().st_uid != 0 or ROOT.stat().st_mode & 0o022
            or marker.is_symlink() or not marker.is_file() or marker.stat().st_uid != 0
            or marker.stat().st_mode & 0o022):
        raise ValueError(f"Refusing to adopt existing host directory {ROOT}.")
    saved = json.loads(marker.read_text())
    if saved.get("account") != USER or uuid.UUID(hex=saved.get("instance", "")).hex != saved.get("instance"):
        raise ValueError("Unrecognized installation record in the host directory.")
    return "PolySia " + saved["instance"]


def dedicated_user(tag):
    try:
        entry = pwd.getpwnam(USER)
    except KeyError:
        if HOME_DIR.exists() or HOME_DIR.is_symlink():
            raise ValueError(f"Existing service home {HOME_DIR} belongs to a different installation.")
        try:
            grp.getgrnam(USER)
        except KeyError:
            pass
        else:
            raise ValueError(f"The existing {USER} group is unrelated to this installation.")
        run("/usr/sbin/useradd", "--system", "--user-group", "--create-home", "--home-dir", str(HOME_DIR),
            "--shell", "/usr/sbin/nologin", "--comment", tag, USER)
        entry = pwd.getpwnam(USER)
    if (entry.pw_gecos != tag or entry.pw_dir != str(HOME_DIR) or entry.pw_shell != "/usr/sbin/nologin"
            or not 0 < entry.pw_uid < 1000 or grp.getgrgid(entry.pw_gid).gr_name != USER
            or set(os.getgrouplist(USER, entry.pw_gid)) != {entry.pw_gid}
            or HOME_DIR.is_symlink() or not HOME_DIR.is_dir() or HOME_DIR.stat().st_uid != entry.pw_uid
            or HOME_DIR.stat().st_mode & 0o022):
        raise ValueError(f"Conflicting service account {USER}. Existing ownership and privileges were preserved.")
    return entry


def install_runtime():
    check = ["/usr/bin/python3", "-I", "-c", RUNTIME_TEST]
    if subprocess.run(check, cwd="/", env={"PATH": SYSTEM_PATH}, stdin=subprocess.DEVNULL,
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
        return
    run("/usr/bin/apt-get", "-qq", "update")
    args = ["--no-install-recommends", "--no-upgrade", "--no-remove", "install", "python3-jwt", "python3-cryptography"]
    preview = run("/usr/bin/apt-get", "-s", *args, capture=True)
    if any(line.startswith("Remv ") or (line.startswith("Inst ") and "[" in line.split("(", 1)[0])
           for line in preview.splitlines()):
        raise ValueError("Ubuntu requires unrelated package upgrades or removals. Resolve these before deployment.")
    run("/usr/bin/apt-get", "-y", *args)
    run(*check)


def prepare(archive):
    if sys.platform != "linux" or os.geteuid() != 0:
        raise ValueError("Use sudo for --prepare-cloudflare-host on the designated Ubuntu host.")
    os_release = platform.freedesktop_os_release()
    if (os_release.get("ID"), os_release.get("VERSION_ID"), platform.machine()) != ("ubuntu", "26.04", "x86_64"):
        raise ValueError("Automated host preparation supports Ubuntu 26.04 LTS amd64.")
    if Path("/proc/1/comm").read_text().strip() != "systemd":
        raise ValueError("Boot this host with systemd before preparing the persistent deployment.")
    # Bootstrap ownership under an existing root-owned directory, without following account-controlled files.
    with host_lock():
        tag = workspace()
        entry = dedicated_user(tag)
        install_runtime()
        print("Verifying the pinned Cloudflare connector and staging the installation bundle…", flush=True)
        cloudflared = ROOT / "cloudflared"
        install_bytes(cloudflared, CONNECTOR_HASH, lambda: urlopen(CLOUDFLARED, timeout=30), 0o755)
        checksum = digest(archive)
        bundle = ROOT / ("release-" + checksum + ".pyz")
        install_bytes(bundle, checksum, lambda: archive.open("rb"), 0o644)
        run("/usr/bin/loginctl", "enable-linger", USER)
    runtime = Path("/run/user") / str(entry.pw_uid)
    for _ in range(50):
        if (runtime / "bus").is_socket():
            break
        time.sleep(0.2)
    else:
        raise ValueError("The systemd user bus is unavailable. Inspect loginctl user-status " + USER + " and retry.")
    env = {"HOME": str(HOME_DIR), "USER": USER, "LOGNAME": USER, "LANG": "C.UTF-8",
           "PATH": f"{ROOT}:{SYSTEM_PATH}", "XDG_RUNTIME_DIR": str(runtime)}
    for key in ("POLYSIA_HOSTNAME", "POLYSIA_OWNER_EMAIL", "POLYSIA_ACCESS_TEAM", "TERM"):
        if value := os.getenv(key):
            env[key] = value
    # Continue as the service user before prompting for the management token.
    os.chdir(HOME_DIR)
    os.setgroups([entry.pw_gid])
    os.setgid(entry.pw_gid)
    os.setuid(entry.pw_uid)
    os.execve("/usr/bin/python3", ["python3", "-I", str(bundle), "--cloudflare"], env)
