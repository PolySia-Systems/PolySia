"""Durable state for one local operator. All state transitions commit atomically."""

import json
import sqlite3
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from . import shadow
from .provider import validate_address


WORKSPACE_VERSION = 8


class Conflict(ValueError):
    """The client must load the latest state before it can retry."""


def timestamp():
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def create_schema_v1(db):
    """Create the version-1 catalog used by installations and archive verification."""
    # SQLite retains whitespace inside CREATE TABLE. Preserve the released DDL.
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


def add_public_runs(db):
    db.execute("""CREATE TABLE public_runs (
        id TEXT PRIMARY KEY, wallet TEXT NOT NULL, name TEXT NOT NULL,
        capital INTEGER NOT NULL, entry_cap INTEGER NOT NULL, policy TEXT NOT NULL,
        created TEXT NOT NULL, updated TEXT NOT NULL,
        status TEXT NOT NULL, revision INTEGER NOT NULL)""")
    db.execute("""CREATE TABLE public_decisions (
        run_id TEXT NOT NULL REFERENCES public_runs(id), revision INTEGER NOT NULL,
        recorded TEXT NOT NULL, kind TEXT NOT NULL, reason TEXT NOT NULL,
        source_order TEXT, condition_id TEXT, token_id TEXT, market TEXT, outcome TEXT,
        shares INTEGER NOT NULL, gross INTEGER NOT NULL, fee INTEGER NOT NULL, receipt TEXT,
        PRIMARY KEY (run_id, revision), UNIQUE (run_id, source_order))""")
    db.execute("PRAGMA user_version = 2")


def add_public_exits(db):
    db.execute("ALTER TABLE public_decisions ADD COLUMN released_cost INTEGER NOT NULL DEFAULT 0")
    db.execute("PRAGMA user_version = 3")


def add_saved_wallets(db):
    db.execute("CREATE TABLE saved_wallets (address TEXT PRIMARY KEY NOT NULL, label TEXT NOT NULL)")


def add_accent(db):
    db.execute("ALTER TABLE workspace ADD COLUMN accent TEXT NOT NULL DEFAULT 'forest' CHECK (accent IN ('forest','ocean'))")
    db.execute("ALTER TABLE workspace ADD COLUMN accent_revision INTEGER NOT NULL DEFAULT 0 CHECK (accent_revision >= 0)")


def wallet_label(value):
    if not isinstance(value, str) or len(value) > 64 or (value and not value.isprintable()):
        raise ValueError("Use a wallet name of up to 64 printable characters.")
    return value.strip()


def verify_saved_wallets(db):
    for address, label in db.execute("SELECT address, label FROM saved_wallets"):
        if validate_address(address) != address or wallet_label(label) != label:
            raise ValueError("Invalid saved wallet record.")


class Workspace:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with self.connection() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if not 0 <= version <= WORKSPACE_VERSION:
                raise ValueError(f"Unsupported workspace database version {version}")
            if version == 0:
                create_schema_v1(db)
            if version < 2:
                add_public_runs(db)
            if version < 3:
                add_public_exits(db)
            if version < 4:
                # Older writers understand the tables but ignore the recorded pre-BUY sale check.
                db.execute("PRAGMA user_version = 4")
            if version < 5:
                from .background import add_table
                add_table(db)
                add_saved_wallets(db)
                db.execute("PRAGMA user_version = 5")
            if version < 6:
                # Earlier writers cannot replay prospective per-entry cap changes.
                db.execute("PRAGMA user_version = 6")
            if version < 7:
                db.execute("PRAGMA user_version = 7")
            if version < 8:
                add_accent(db)
                db.execute("PRAGMA user_version = 8")

    @contextmanager
    def connection(self, write=True):
        with closing(sqlite3.connect(self.path, timeout=5)) as db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys = ON")
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
                "accent": {"preset": row["accent"], "revision": row["accent_revision"]},
                "accountRevision": row["account_revision"],
                "account": json.loads(row["account"]) if row["account"] is not None else None,
                "savedWallets": [dict(wallet) for wallet in db.execute(
                    "SELECT address, label FROM saved_wallets ORDER BY label COLLATE NOCASE, address"
                )],
                "run": shadow.run_report(run) if run else None,
            }

    def publish_accent(self, revision, preset):
        if type(revision) is not int or not 0 <= revision < 2**63 - 1 or preset not in ("forest", "ocean"):
            raise ValueError("Choose a supported accent preset and its current revision.")
        with self.connection() as db:
            result = db.execute("""UPDATE workspace SET accent=?, accent_revision=accent_revision+1
                                   WHERE id=1 AND accent_revision=?""", (preset, revision))
            if not result.rowcount:
                raise Conflict("The published accent changed. Review the current preset and preview again.")
            return {"preset": preset, "revision": revision + 1}

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

    def overview(self):
        with self.connection(write=False) as db:
            counts = dict(db.execute("SELECT status, count(*) FROM public_runs GROUP BY status"))
            background = db.execute("SELECT count(*) FROM background_runs").fetchone()[0]
            # A new observation can clear a provider warning. Changing the cap or
            # adding cash provides no evidence that the provider recovered.
            # Open shares remain meaningful after stop. Compute them only for stopped runs.
            issues = db.execute("""
                WITH issues AS (
                    SELECT r.id, r.name, d.recorded AS updated, d.kind, d.reason
                    FROM public_runs r JOIN public_decisions d ON d.run_id=r.id AND d.revision=(
                        SELECT recent.revision FROM public_decisions recent WHERE recent.run_id=r.id
                            AND recent.kind IN ('entry','exit','waiting','skipped','duplicate','unavailable','incomplete')
                        ORDER BY recent.revision DESC LIMIT 1)
                    WHERE r.status='running' AND d.kind IN ('unavailable','incomplete')
                    UNION ALL
                    SELECT r.id, r.name, r.updated, 'exposure', 'Stopped with open simulated shares.'
                    FROM public_runs r WHERE r.status='stopped' AND (
                        SELECT sum(CASE d.kind WHEN 'entry' THEN d.shares WHEN 'exit' THEN -d.shares ELSE 0 END)
                        FROM public_decisions d WHERE d.run_id=r.id
                    ) > 0
                )
                SELECT * FROM issues ORDER BY updated DESC, id LIMIT 6""").fetchall()
            return {"running": counts.get("running", 0), "paused": counts.get("paused", 0),
                    "stopped": counts.get("stopped", 0), "background": background,
                    "issues": [dict(row) for row in issues[:5]], "more": len(issues) > 5,
                    "checkedAt": timestamp()}

    def account_revision(self):
        with self.connection(write=False) as db:
            return db.execute("SELECT account_revision FROM workspace WHERE id = 1").fetchone()[0]

    def check_account_revision(self, revision):
        if type(revision) is not int or not 0 <= revision < 2**63:
            raise ValueError("Provide the integer revision of the displayed account watch.")
        if revision != self.account_revision():
            raise Conflict("The watched account changed. Review the current watch and try again.")

    def save_account(self, account, revision):
        # Provider I/O runs outside the transaction. A slow refresh must never
        # reconnect a watch that was disconnected or switched while it was away.
        with self.connection() as db:
            if account and account["status"] == "unavailable":
                row = db.execute(
                    "SELECT account FROM workspace WHERE id = 1 AND account_revision = ?", (revision,)
                ).fetchone()
                previous = json.loads(row["account"]) if row and row["account"] else None
                if previous and previous["address"] == account["address"]:
                    if previous["status"] == "available":
                        retained = {key: previous[key] for key in ("source", "observedAt", "positions", "complete")}
                    else:
                        retained = previous.get("lastSuccessful")
                    if retained is not None:
                        account = {**account, "lastSuccessful": retained}
            result = db.execute(
                """UPDATE workspace SET account = ?, account_revision = account_revision + 1
                   WHERE id = 1 AND account_revision = ?""",
                (json.dumps(account) if account is not None else None, revision),
            )
            if not result.rowcount:
                raise Conflict("The watched account changed. Review the current watch and try again.")
        return account

    def update_saved_wallet(self, address, revision, *, label=None, remove=False):
        address = validate_address(address)
        if not remove:
            label = wallet_label(label)
        if type(revision) is not int or not 0 <= revision < 2**63:
            raise ValueError("Provide the integer revision of the displayed account watch.")
        with self.connection() as db:
            active = db.execute("SELECT account, account_revision FROM workspace WHERE id = 1").fetchone()
            if (revision != active["account_revision"] or not active["account"]
                    or json.loads(active["account"])["address"] != address):
                raise Conflict("The selected account changed. Review the current watch and try again.")
            if remove:
                db.execute("DELETE FROM saved_wallets WHERE address = ?", (address,))
            else:
                db.execute("""INSERT INTO saved_wallets(address, label) VALUES (?, ?)
                              ON CONFLICT(address) DO UPDATE SET label=excluded.label""", (address, label))
            db.execute("UPDATE workspace SET account_revision = account_revision + 1 WHERE id = 1")
        return {"address": address, "saved": not remove}

    @staticmethod
    def latest_run(db):
        row = db.execute("SELECT record FROM runs ORDER BY rowid DESC LIMIT 1").fetchone()
        return json.loads(row["record"]) if row else None

    def get_run(self, run_id):
        with self.connection(write=False) as db:
            return shadow.run_report(self.find_run(db, run_id))

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
                      "updatedAt", "quantity", "cash", "marked_net_result", "realized_pnl", "fees", "scenario", "mode")
            summaries = []
            for row in rows[:20]:
                record = shadow.run_report(json.loads(row["record"]))
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
            return shadow.run_report(run)

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
            return shadow.run_report(run)
