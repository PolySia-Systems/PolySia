"""Durable state for one local operator. All state transitions commit atomically."""

import json
import sqlite3
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from . import shadow


class Conflict(ValueError):
    """The client must load the latest state before it can retry."""


def timestamp():
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class Workspace:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with self.connection() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise ValueError(f"Unsupported workspace database version {version}")
            if version == 0:
                db.execute("""
                    CREATE TABLE workspace (
                        id INTEGER PRIMARY KEY CHECK (id = 1),
                        theme TEXT NOT NULL CHECK (theme IN ('light', 'dark')),
                        settings_revision INTEGER NOT NULL,
                        account TEXT,
                        account_revision INTEGER NOT NULL
                    )
                """)
                db.execute("INSERT INTO workspace VALUES (1, 'light', 0, NULL, 0)")
                db.execute("CREATE TABLE runs (id TEXT PRIMARY KEY, record TEXT NOT NULL)")
                db.execute("PRAGMA user_version = 1")

    @contextmanager
    def connection(self, write=True):
        with closing(sqlite3.connect(self.path, timeout=5)) as db:
            db.row_factory = sqlite3.Row
            with db:
                db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
                yield db

    @staticmethod
    def settings(row):
        return {"version": 1, "revision": row["settings_revision"], "theme": row["theme"]}

    def read(self):
        with self.connection(write=False) as db:
            row = db.execute("SELECT * FROM workspace WHERE id = 1").fetchone()
            run = self.latest_run(db)
            return {
                "settings": self.settings(row),
                "account": json.loads(row["account"]) if row["account"] is not None else None,
                "run": run,
            }

    def set_theme(self, version, revision, theme):
        if type(version) is not int or version != 1 or type(revision) is not int or not 0 <= revision < 2**63:
            raise ValueError("Provide settings version 1 and its integer revision.")
        if theme not in ("light", "dark"):
            raise ValueError("Choose the light or dark theme.")
        with self.connection() as db:
            result = db.execute(
                """UPDATE workspace SET theme = ?, settings_revision = settings_revision + 1
                   WHERE id = 1 AND settings_revision = ?""",
                (theme, revision),
            )
            if not result.rowcount:
                raise Conflict("Settings changed. Reload before saving.")
            return self.settings(db.execute("SELECT * FROM workspace WHERE id = 1").fetchone())

    def account_revision(self):
        with self.connection(write=False) as db:
            return db.execute("SELECT account_revision FROM workspace WHERE id = 1").fetchone()[0]

    def save_account(self, account, revision):
        # Provider I/O runs outside the transaction. A slow refresh must never
        # reconnect a watch that was disconnected or switched while it was away.
        with self.connection() as db:
            result = db.execute(
                """UPDATE workspace SET account = ?, account_revision = account_revision + 1
                   WHERE id = 1 AND account_revision = ?""",
                (json.dumps(account), revision),
            )
            if not result.rowcount:
                raise Conflict("The watched account changed. Reload before refreshing.")
        return account

    def disconnect(self):
        with self.connection() as db:
            db.execute("UPDATE workspace SET account = NULL, account_revision = account_revision + 1 WHERE id = 1")

    @staticmethod
    def latest_run(db):
        row = db.execute("SELECT record FROM runs ORDER BY rowid DESC LIMIT 1").fetchone()
        return json.loads(row["record"]) if row else None

    def get_run(self, run_id):
        with self.connection(write=False) as db:
            return self.find_run(db, run_id)

    def run_history(self, before):
        with self.connection(write=False) as db:
            params = ()
            condition = ""
            if before is not None:
                cursor = db.execute("SELECT rowid FROM runs WHERE id = ?", (before,)).fetchone()
                if not cursor:
                    raise ValueError("Unknown replay history cursor.")
                condition = "WHERE rowid < ?"
                params = (cursor[0],)
            rows = db.execute(
                f"SELECT record FROM runs {condition} ORDER BY rowid DESC LIMIT 21", params,
            ).fetchall()
            fields = ("id", "leader_name", "capital", "order_size", "status", "createdAt",
                      "updatedAt", "quantity", "cash", "realized_pnl", "fees", "scenario", "mode")
            summaries = []
            for row in rows[:20]:
                record = json.loads(row["record"])
                summaries.append({key: record[key] for key in fields})
            return {"runs": summaries, "nextCursor": summaries[-1]["id"] if len(rows) > 20 else None}

    @staticmethod
    def find_run(db, run_id):
        row = db.execute("SELECT record FROM runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            raise KeyError("Replay not found.")
        return json.loads(row["record"])

    def create_run(self, leader_id, allocation, order_size):
        if not all(isinstance(x, str) for x in (leader_id, allocation, order_size)):
            raise ValueError("Provide a leader ID and decimal strings for both dollar amounts.")
        with self.connection() as db:
            previous = self.latest_run(db)
            if previous and previous["status"] not in ("stopped", "completed"):
                raise Conflict("Finish or stop the current replay before starting another.")
            run = shadow.create_run(leader_id, allocation, order_size)
            now = timestamp()
            run.update(id=uuid4().hex, revision=1, createdAt=now, updatedAt=now)
            db.execute("INSERT INTO runs (id, record) VALUES (?, ?)", (run["id"], json.dumps(run)))
            return run

    def change_run(self, run_id, action, revision):
        if type(revision) is not int:
            raise ValueError("Provide the integer revision of the displayed replay.")
        with self.connection() as db:
            current = self.find_run(db, run_id)
            if revision != current["revision"]:
                raise Conflict("The replay changed. Reload before applying another action.")
            run = shadow.apply_action(current, action)
            run.update(id=run_id, revision=revision + 1, createdAt=current["createdAt"], updatedAt=timestamp())
            db.execute("UPDATE runs SET record = ? WHERE id = ?", (json.dumps(run), run_id))
            return run
