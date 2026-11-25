"""Start the local workspace with python3 -m apps.server."""

import argparse
import json
import logging
import os
import sqlite3
from pathlib import Path

from .archive import copy_workspace
from .http import LocalServer
from .store import Workspace
from .study import record_study


def main(*, artifact_sha256=None):
    parser = argparse.ArgumentParser(description="Start the PolySia local workspace")
    parser.add_argument("--port", type=int, default=8765)
    commands = parser.add_subparsers(dest="command")
    backup = commands.add_parser("backup", help="Back up the current workspace to a new local file")
    backup.add_argument("--to", required=True, type=Path, metavar="NEW_BACKUP")
    restore = commands.add_parser("restore", help="Verify and restore a backup to a new database file")
    restore.add_argument("--from", required=True, type=Path, dest="source", metavar="BACKUP")
    restore.add_argument("--to", required=True, type=Path, metavar="NEW_DB")
    study = commands.add_parser("study", help="Record a finite public BUY study to a new JSON Lines file")
    study.add_argument("wallet", help="Public trading wallet")
    study.add_argument("--budget", required=True, metavar="pUSD", help="Unfunded budget for each window")
    study.add_argument("--windows", required=True, type=int, metavar="1..10")
    study.add_argument("--seconds", type=int, default=5, metavar="1..30")
    study.add_argument("--to", required=True, type=Path, metavar="NEW_JSONL")
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error("choose a port from 0 to 65535")
    state_home = Path(os.getenv("XDG_STATE_HOME") or Path.home() / ".local" / "state")
    path = Path(os.getenv("POLYSIA_DB") or state_home / "polysia" / "workspace.sqlite3")
    os.umask(0o077)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        if args.command == "study":
            summary = record_study(args.to, args.wallet, args.budget, args.seconds, args.windows)
            print(json.dumps(summary))
            return
        if args.command in ("backup", "restore"):
            source = args.source if args.command == "restore" else path
            copy_workspace(source, args.to)
            print(f"Verified workspace copy saved to {args.to}.")
            return
        with LocalServer(args.port, Workspace(path), artifact_sha256=artifact_sha256) as server:
            print(f"PolySia is running at http://127.0.0.1:{server.server_port}", flush=True)
            server.serve_forever()
    except KeyboardInterrupt:
        return
    except (OSError, ValueError, sqlite3.Error) as exc:
        parser.exit(1, f"PolySia could not complete the operation: {exc}\n")


if __name__ == "__main__":
    main()
