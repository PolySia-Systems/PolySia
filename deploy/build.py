"""Bundle the Python server and compiled SPA into a reproducible offline installer."""

import hashlib
import json
import os
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]


def main():
    web = ROOT / "apps/web/dist"
    if not (web / "index.html").is_file():
        raise SystemExit("Run make build to compile the web app before packaging.")
    entries = {"__main__.py": ROOT / "deploy/install.py", "polysia": ROOT / "deploy/start.py",
               "cloudflare_setup.py": ROOT / "deploy/cloudflare_setup.py",
               "prepare_host.py": ROOT / "deploy/prepare_host.py"}
    for path in sorted((ROOT / "apps/server").rglob("*.py")):
        entries[path.relative_to(ROOT).as_posix()] = path
    for path in sorted(web.rglob("*")):
        if path.is_file():
            entries[path.relative_to(ROOT).as_posix()] = path

    frontend = ROOT / "apps/web"
    packages = json.loads((frontend / "package-lock.json").read_bytes())["packages"]
    for package, metadata in packages.items():
        if package and not metadata.get("dev"):
            name = package.removeprefix("node_modules/")
            entries[f"licenses/{name}/LICENSE"] = frontend / package / "LICENSE"

    output = ROOT / "dist/polysia.pyz"
    output.parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as stage:
        candidate = Path(stage) / output.name
        with ZipFile(candidate, "w") as bundle:
            for name, path in sorted(entries.items()):
                entry = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                entry.compress_type = ZIP_DEFLATED
                entry.create_system = 3
                entry.external_attr = 0o100644 << 16
                bundle.writestr(entry, path.read_bytes())
        # A concurrent installer sees the previous or the complete new bundle.
        os.replace(candidate, output)
    print(f"{output.name}  sha256 {hashlib.sha256(output.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
