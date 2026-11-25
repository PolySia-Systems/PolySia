#!/usr/bin/env python3
"""Entry point inside an installed release. Keep mutable state outside its code."""

import os
import runpy
import sys
from pathlib import Path

sys.dont_write_bytecode = True
release = Path(__file__).resolve().parent
sys.path.insert(0, str(release))
os.environ.setdefault("POLYSIA_DB", str(release.parents[1] / "data/workspace.sqlite3"))
os.umask(0o077)
runpy.run_module("apps.server", run_name="__main__", alter_sys=True)
