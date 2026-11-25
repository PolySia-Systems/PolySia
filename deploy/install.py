"""Install the bundled PolySia release locally. No network access is required."""

import argparse
import fcntl
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
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
    prefix.mkdir(mode=0o700, parents=True, exist_ok=True)
    current = prefix / "current"
    with (prefix / ".polysia-install.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if current.is_symlink():
            previous = Path(os.readlink(current))
            if previous.parent != Path("releases") or len(previous.name) != 64:
                raise ValueError("The installation prefix contains an unrelated current symlink.")
        elif current.exists():
            raise ValueError("The installation prefix already contains an unrelated current entry.")
        release.parent.mkdir(mode=0o700, exist_ok=True)
        if not release.exists():
            with tempfile.TemporaryDirectory(prefix=".prepare-", dir=release.parent) as stage:
                staged = Path(stage) / "release"
                staged.mkdir()
                with ZipFile(archive) as bundle:
                    for name in bundle.namelist():
                        if name != "__main__.py":
                            bundle.extract(name, staged)
                (staged / "polysia").chmod(0o700)
                staged.rename(release)
        with tempfile.TemporaryDirectory(prefix=".activate-", dir=prefix) as stage:
            link = Path(stage) / "current"
            link.symlink_to(relative_release)
            os.replace(link, current)
    return {"artifactSha256": digest, "launcher": str(current / "polysia"),
            "data": str(prefix / "data"), "defaultUrl": "http://127.0.0.1:8765"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", type=Path, default=Path.home() / ".local/share/polysia",
                        help="Dedicated local install and data directory.")
    parser.add_argument("--json", action="store_true", help="Print the installed paths as JSON.")
    args = parser.parse_args()
    os.umask(0o077)
    try:
        result = install(Path(sys.argv[0]), args.prefix.resolve())
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Installation failed: {exc}\n")
    if args.json:
        print(json.dumps(result))
    else:
        print(f"Installed PolySia {result['artifactSha256'][:12]}.")
        print(f"Start the local application with {result['launcher']}")
        print(f"Then open {result['defaultUrl']}. Data is stored in {result['data']}.")


if __name__ == "__main__":
    main()
