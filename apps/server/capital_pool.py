"""Forward, entry-only portfolios sharing durable background observations."""

import json
import re
from itertools import zip_longest

from . import shared_replay
from .provider import units_from_micros
from .public_shadow import _budget, _journal_time, _recorded_time
from .store import Conflict, timestamp


MODEL = "shared-background-buys/1"
TRANSITIONS = {"running": ("paused", "stopped"), "paused": ("running", "stopped"), "stopped": ()}


def add_tables(db):
    db.execute("""CREATE TABLE capital_pools (id TEXT PRIMARY KEY, name TEXT NOT NULL,
        capital INTEGER NOT NULL, model TEXT NOT NULL, created TEXT NOT NULL)""")
    db.execute("""CREATE TABLE pool_members (pool_id TEXT NOT NULL REFERENCES capital_pools(id),
        run_id TEXT NOT NULL REFERENCES public_runs(id), start_revision INTEGER NOT NULL,
        PRIMARY KEY (pool_id,run_id))""")
    db.execute("CREATE INDEX pool_members_run ON pool_members(run_id)")
    db.execute("""CREATE TABLE pool_controls (boundary INTEGER PRIMARY KEY, pool_id TEXT NOT NULL REFERENCES capital_pools(id),
        generation INTEGER NOT NULL, status TEXT NOT NULL, recorded TEXT NOT NULL,
        UNIQUE(pool_id,generation))""")
    db.execute("""CREATE TABLE worker_windows (ordinal INTEGER PRIMARY KEY, run_id TEXT NOT NULL, revision INTEGER NOT NULL,
        claim TEXT NOT NULL UNIQUE, opened INTEGER NOT NULL, completed INTEGER NOT NULL,
        FOREIGN KEY(run_id,revision) REFERENCES public_decisions(run_id,revision), UNIQUE(run_id,revision))""")
    db.execute("""CREATE TABLE pool_windows (sequence INTEGER PRIMARY KEY, pool_id TEXT NOT NULL,
        generation INTEGER NOT NULL, run_id TEXT NOT NULL, revision INTEGER NOT NULL,
        FOREIGN KEY(pool_id,generation) REFERENCES pool_controls(pool_id,generation),
        FOREIGN KEY(pool_id,run_id) REFERENCES pool_members(pool_id,run_id),
        FOREIGN KEY(run_id,revision) REFERENCES public_decisions(run_id,revision),
        UNIQUE(pool_id,run_id,revision))""")
    db.execute("CREATE INDEX pool_windows_order ON pool_windows(pool_id,sequence)")


def _current(db, pool):
    row = db.execute("SELECT generation,status,recorded FROM pool_controls WHERE pool_id=? ORDER BY generation DESC LIMIT 1",
                     (pool,)).fetchone()
    if row is None:
        raise KeyError("Shared portfolio unavailable.")
    return row


def create(db, pool, name, capital, run_ids):
    if (not isinstance(name, str) or not name.strip() or len(name.strip()) > 80 or not name.strip().isprintable()
            or not isinstance(run_ids, list) or len(run_ids) < 2
            or any(not isinstance(i, str) or not re.fullmatch("[0-9a-f]{32}", i) for i in run_ids)
            or len(set(run_ids)) != len(run_ids)):
        raise ValueError("Name the portfolio and choose distinct background runs for at least two leaders.")
    name, micros = name.strip(), _budget(capital)
    existing = db.execute("SELECT name,capital FROM capital_pools WHERE id=?", (pool,)).fetchone()
    if existing:
        prior = {r[0] for r in db.execute("SELECT run_id FROM pool_members WHERE pool_id=?", (pool,))}
        if tuple(existing) != (name, micros) or prior != set(run_ids):
            raise Conflict("This portfolio already has a different configuration.")
        return report(db, pool)
    wallets = set()
    for run_id in run_ids:
        member = db.execute("""SELECT wallet FROM public_runs r JOIN background_runs b ON b.run_id=r.id
                               WHERE r.id=? AND r.status='running'""", (run_id,)).fetchone()
        if not member or member[0] in wallets:
            raise ValueError("Enable background sampling for each selected run and choose different leader wallets.")
        wallets.add(member[0])
    now = timestamp()
    db.execute("INSERT INTO capital_pools VALUES(?,?,?,?,?)", (pool, name, micros, MODEL, now))
    db.execute("INSERT INTO pool_controls(pool_id,generation,status,recorded) VALUES(?,1,'running',?)", (pool, now))
    db.executemany("INSERT INTO pool_members SELECT ?,id,revision FROM public_runs WHERE id=?",
                   ((pool, run_id) for run_id in run_ids))
    return report(db, pool)


def control(db, pool, generation, status):
    current = _current(db, pool)
    if (type(generation) is not int or generation != current["generation"]
            or status not in TRANSITIONS[current["status"]]):
        raise Conflict("The shared portfolio changed or this control is unavailable. Refresh its status.")
    now = _recorded_time(current["recorded"], timestamp())
    db.execute("INSERT INTO pool_controls(pool_id,generation,status,recorded) VALUES(?,?,?,?)", (pool, generation + 1, status, now))
    return report(db, pool)


def control_boundary(db):
    return db.execute("SELECT coalesce(max(boundary),0) FROM pool_controls").fetchone()[0]


# A member must have the same running generation at claim and completion.
# Both logical boundaries are captured inside the source worker's write transactions.
ELIGIBLE = """SELECT c.pool_id,c.generation,w.run_id,w.revision FROM worker_windows w
    JOIN pool_members m ON m.run_id=w.run_id AND m.start_revision<w.revision
    JOIN pool_controls c ON c.pool_id=m.pool_id AND c.status='running'
        AND c.boundary=(SELECT max(at_open.boundary) FROM pool_controls at_open
                        WHERE at_open.pool_id=m.pool_id AND at_open.boundary<=w.opened)
    WHERE NOT EXISTS(SELECT 1 FROM pool_controls later WHERE later.pool_id=c.pool_id
                     AND later.boundary>w.opened AND later.boundary<=w.completed)"""


def capture(db, run_id, revision, claim, opened):
    completed = control_boundary(db)
    ordinal = db.execute("""INSERT INTO worker_windows(run_id,revision,claim,opened,completed) VALUES(?,?,?,?,?)""",
                         (run_id, revision, claim, opened, completed)).lastrowid
    marker = json.dumps([ordinal, claim, opened, completed])
    db.execute("""UPDATE public_decisions SET receipt=json_set(receipt,'$.serverWorker',json(?))
                  WHERE run_id=? AND revision=?""", (marker, run_id, revision))
    db.execute("INSERT INTO pool_windows(pool_id,generation,run_id,revision) " + ELIGIBLE + " AND w.ordinal=?", (ordinal,))


def listing(db):
    return [dict(row) for row in db.execute("""SELECT p.id,p.name,c.status FROM capital_pools p JOIN pool_controls c
            ON c.pool_id=p.id AND c.generation=(SELECT max(generation) FROM pool_controls WHERE pool_id=p.id)
            ORDER BY p.rowid DESC""")]


def report(db, pool):
    current = _current(db, pool)
    row = db.execute("SELECT name,capital,model,created FROM capital_pools WHERE id=?", (pool,)).fetchone()
    members = dict(db.execute("""SELECT m.run_id,b.run_id IS NOT NULL FROM pool_members m LEFT JOIN background_runs b
                                 ON b.run_id=m.run_id WHERE m.pool_id=?""", (pool,)))
    pooled = shared_replay.allocate(db, list(members), units_from_micros(row["capital"]), pool=pool)
    for run in pooled["runs"]:
        run["sourceBackgroundEnabled"] = bool(members[run["id"]])
    windows = db.execute("SELECT count(*) FROM pool_windows WHERE pool_id=?", (pool,)).fetchone()[0]
    latest = db.execute("""SELECT d.recorded,d.kind,d.reason,w.run_id FROM pool_windows w
        JOIN public_decisions d USING(run_id,revision) WHERE w.pool_id=? ORDER BY w.sequence DESC LIMIT 1""",
        (pool,)).fetchone()
    return dict(pooled, id=pool, name=row["name"], model=row["model"], created=row["created"],
                generation=current["generation"], status=current["status"], windows=windows,
                latestSourceWindow=dict(latest) if latest else None)


def verify(db):
    if db.execute("PRAGMA foreign_key_check").fetchone():
        raise ValueError("A shared portfolio record has a missing reference.")
    previous = 0
    boundaries = {0} | {r[0] for r in db.execute("SELECT boundary FROM pool_controls")}
    records = db.execute("""SELECT w.*,json_extract(d.receipt,'$.serverWorker') AS marker
        FROM worker_windows w JOIN public_decisions d USING(run_id,revision) ORDER BY ordinal""")
    for r in records:
        expected = [r["ordinal"], r["claim"], r["opened"], r["completed"]]
        if (r["ordinal"] <= 0 or not re.fullmatch("[0-9a-f]{32}", r["claim"])
                or type(r["opened"]) is not int or type(r["completed"]) is not int
                or r["opened"] not in boundaries or r["completed"] not in boundaries
                or r["opened"] > r["completed"] or r["completed"] < previous
                or r["marker"] != json.dumps(expected, separators=(",", ":"))):
            raise ValueError("A background source receipt disagrees with its worker claim.")
        previous = r["completed"]
    orphan_marker = db.execute("""SELECT 1 FROM public_decisions d LEFT JOIN worker_windows w USING(run_id,revision)
        WHERE json_type(d.receipt,'$.serverWorker') IS NOT NULL AND w.ordinal IS NULL LIMIT 1""").fetchone()
    if orphan_marker:
        raise ValueError("A source receipt has no corresponding worker claim.")
    for row in db.execute("SELECT * FROM capital_pools"):
        pool = row["id"]
        if (not re.fullmatch("[0-9a-f]{32}", pool) or not isinstance(row["name"], str)
                or not 1 <= len(row["name"]) <= 80 or not row["name"].isprintable()
                or type(row["capital"]) is not int or _budget(units_from_micros(row["capital"])) != row["capital"]
                or row["model"] != MODEL):
            raise ValueError("Invalid shared portfolio configuration.")
        previous = _journal_time(row["created"])
        status, last_boundary = None, 0
        for expected, change in enumerate(db.execute("SELECT * FROM pool_controls WHERE pool_id=? ORDER BY generation", (pool,)), 1):
            recorded = _journal_time(change["recorded"])
            allowed = ("running",) if status is None else TRANSITIONS[status]
            if (change["generation"] != expected or change["status"] not in allowed or recorded < previous
                    or change["boundary"] <= last_boundary):
                raise ValueError("Invalid shared portfolio controls.")
            status, previous, last_boundary = change["status"], recorded, change["boundary"]
        members = db.execute("""SELECT r.wallet,m.start_revision,r.revision FROM pool_members m JOIN public_runs r
                                ON r.id=m.run_id WHERE m.pool_id=?""", (pool,)).fetchall()
        if (status is None or len({r[0] for r in members}) != len(members) or len(members) < 2
                or any(type(start) is not int or not 1 <= start <= latest for _, start, latest in members)):
            raise ValueError("Invalid shared portfolio membership.")
        invalid = db.execute("""SELECT 1 FROM pool_windows w JOIN pool_members m USING(pool_id,run_id)
            JOIN pool_controls c USING(pool_id,generation) JOIN public_decisions d USING(run_id,revision)
            WHERE w.pool_id=? AND (c.status!='running' OR w.revision<=m.start_revision OR
            d.kind NOT IN ('entry','skipped','duplicate','waiting','incomplete','unavailable')) LIMIT 1""", (pool,)).fetchone()
        if invalid:
            raise ValueError("Invalid shared BUY window.")
        generation, revisions = 0, {}
        for epoch, run_id, revision in db.execute("""SELECT generation,run_id,revision FROM pool_windows
                WHERE pool_id=? ORDER BY sequence""", (pool,)):
            if epoch < generation or revision <= revisions.get(run_id, 0):
                raise ValueError("Shared observations are out of order.")
            generation, revisions[run_id] = epoch, revision
    elected = db.execute(ELIGIBLE + " ORDER BY c.pool_id,w.ordinal")
    saved = db.execute("SELECT pool_id,generation,run_id,revision FROM pool_windows ORDER BY pool_id,sequence")
    if any(a != b for a, b in zip_longest(elected, saved)):
        raise ValueError("Shared portfolio windows differ from the authorized background claims or their commit order.")
