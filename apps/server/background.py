"""Run opt-in, simulated BUY windows while the server is online."""

import logging
import sqlite3
from time import time
from uuid import uuid4

from . import public_shadow
from .store import Conflict

INTERVAL = 15
OUTAGE_DELAY = 60
# Longer than the bounded observation subprocess deadline.
CLAIM_SECONDS = 120


def add_table(db):
    db.execute("""CREATE TABLE background_runs (
        run_id TEXT PRIMARY KEY REFERENCES public_runs(id),
        due INTEGER NOT NULL CHECK (due >= 0), claim TEXT)""")


def configure(db, run_id, revision, enabled):
    public_shadow.require_revision(db, run_id, revision)
    current = bool(db.execute("SELECT 1 FROM background_runs WHERE run_id=?", (run_id,)).fetchone())
    if current == enabled:
        return public_shadow.report(db, run_id)
    if enabled:
        public_shadow.sampling_terms(db, run_id, revision)
        db.execute("INSERT OR IGNORE INTO background_runs VALUES(?,?,NULL)", (run_id, int(time())))
    else:
        db.execute("DELETE FROM background_runs WHERE run_id=?", (run_id,))
    return public_shadow.control(db, run_id, revision, "background-on" if enabled else "background-off")


def tick(store, sample, now=None):
    started = int(time()) if now is None else now
    query = """SELECT b.run_id, r.revision FROM background_runs b JOIN public_runs r ON r.id=b.run_id
               WHERE b.due <= ? OR b.due > ? ORDER BY b.due, b.run_id LIMIT 1"""
    bounds = (started, started + CLAIM_SECONDS)
    with store.connection(write=False) as db:
        if not db.execute(query, bounds).fetchone():
            return
    with store.connection() as db:
        row = db.execute(query, bounds).fetchone()
        if row is None:
            return
        run_id, revision = row
        try:
            wallet, budget, check_sales = public_shadow.sampling_terms(db, run_id, revision)
        except Conflict:
            db.execute("DELETE FROM background_runs WHERE run_id=?", (run_id,))
            return
        claim = uuid4().hex
        db.execute("UPDATE background_runs SET due=?,claim=? WHERE run_id=?",
                   (started + CLAIM_SECONDS, claim, run_id))

    delay = INTERVAL
    try:
        receipt = sample(wallet, budget, retry_empty=True, check_sales=check_sales)
        if (not isinstance(receipt, dict) or receipt.get("wallet") != wallet
                or receipt.get("researchBudget") != budget or receipt.get("status") not in
                ("observed", "waiting", "unavailable", "incomplete", "skipped")):
            raise ValueError("Malformed public observation.")
        if receipt.get("status") == "unavailable":
            delay = OUTAGE_DELAY
    except Conflict:
        receipt = None
    except (OSError, ValueError):
        delay = OUTAGE_DELAY
        receipt = {"wallet": wallet, "researchBudget": budget, "status": "unavailable",
                   "reason": "The public provider could not complete this background window."}

    with store.connection() as db:
        if not db.execute("SELECT 1 FROM background_runs WHERE run_id=? AND claim=?", (run_id, claim)).fetchone():
            return
        if receipt is not None:
            try:
                result = public_shadow.record(db, run_id, revision, receipt)
                if not result["nextBudget"]:
                    db.execute("DELETE FROM background_runs WHERE run_id=?", (run_id,))
                    return
            except Conflict:
                pass  # A newer decision or control supersedes this in-flight sample.
        finished = int(time()) if now is None else now
        db.execute("UPDATE background_runs SET due=?,claim=NULL WHERE run_id=?", (finished + delay, run_id))


def run(store, sample, stopped):
    while not stopped.is_set():
        try:
            tick(store, sample)
        except (sqlite3.Error, ValueError, OSError):
            logging.getLogger(__name__).exception("Background simulation check failed.")
        stopped.wait(1)
