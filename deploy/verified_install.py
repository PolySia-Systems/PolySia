"""Verify a supplied PolySia release and hand the exact bytes to its bundled installer."""

import argparse
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__, epilog=(
        "Obtain the expected SHA-256 from your trusted release record. "
        "Pass installer options after -- (for example -- --start)."))
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--file", type=Path, help="Path to an already transferred polysia.pyz")
    source.add_argument("--release", metavar="TAG", help="Download a tagged release using GitHub CLI")
    parser.add_argument("--sha256", required=True, help="Trusted SHA-256 of the exact tested release")
    parser.add_argument("options", nargs=argparse.REMAINDER, help="Options passed to the official installer")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-fA-F]{64}", args.sha256):
        parser.error("The expected SHA-256 must contain 64 hexadecimal characters.")
    if args.release is not None and not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}", args.release):
        parser.error("Choose a version tag such as v0.4.1.")
    options = args.options
    if options[:1] == ["--"]:
        options = options[1:]
    try:
        with tempfile.TemporaryDirectory(prefix="polysia-verify-") as stage:
            # Keep the verified snapshot independent of later writes to the source.
            archive = Path(stage) / "polysia.pyz"
            if args.file:
                shutil.copyfile(args.file, archive)
            else:
                subprocess.run(["gh", "release", "download", args.release, "--repo", "github.com/PolySia-Systems/PolySia",
                                "--pattern", "polysia.pyz", "--dir", stage], check=True)
            with archive.open("rb") as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
            if actual != args.sha256.lower():
                parser.exit(1, "Release verification failed. Check the selected version and its trusted SHA-256.\n")
            print(f"Verified PolySia release {actual}.", file=sys.stderr, flush=True)
            return subprocess.run([sys.executable, "-I", str(archive), *options]).returncode
    except FileNotFoundError as exc:
        if exc.filename == "gh":
            parser.exit(1, "Use the README install command, install GitHub CLI, or supply --file after a transfer.\n")
        parser.exit(1, "Could not open the selected release file. Check its path and retry.\n")
    except subprocess.CalledProcessError:
        parser.exit(1, "Download failed. Check the release tag and existing repository access, or supply --file.\n")
    except OSError as exc:
        parser.exit(1, f"Could not prepare the release: {exc}\n")


if __name__ == "__main__":
    sys.exit(main())
