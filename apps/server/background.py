"""Observe opt-in simulated purchases and inventory-limited sales while the server is online."""

import logging
import sqlite3
from time import time
from uuid import uuid4

from . import capital_pool, public_shadow
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
        _next_window(db, run_id, revision)
        db.execute("INSERT OR IGNORE INTO background_runs VALUES(?,?,NULL)", (run_id, int(time())))
    else:
        db.execute("DELETE FROM background_runs WHERE run_id=?", (run_id,))
    return public_shadow.control(db, run_id, revision, "background-on" if enabled else "background-off")


def _next_window(db, run_id, revision):
    run = db.execute("""SELECT *,json_extract(policy,'$.backgroundSaleLimit') AS sale_limit
                        FROM public_runs WHERE id=?""", (run_id,)).fetchone()
    if run["sale_limit"] and run["status"] == "running":
        held = sorted(public_shadow._positions(db, run_id), key=lambda p: p["token_id"])
        if held:
            # Alternate sides when cash can fund another BUY. Rotate through held tokens
            # using committed receipts so restarting the server preserves the sequence.
            last = db.execute("""SELECT json_extract(receipt,'$.backgroundSale') FROM public_decisions
                WHERE run_id=? AND (json_type(receipt,'$.serverWorker') IS NOT NULL
                OR json_extract(receipt,'$.backgroundSale')=1) ORDER BY revision DESC LIMIT 1""", (run_id,)).fetchone()
            _, cash = public_shadow._balances(run, public_shadow._totals(db, run_id))
            if cash < 1_000_000 or not (last and last[0]):
                previous = db.execute("""SELECT json_extract(receipt,'$.exitScope.tokenId') FROM public_decisions
                    WHERE run_id=? AND json_extract(receipt,'$.backgroundSale')=1
                    ORDER BY revision DESC LIMIT 1""", (run_id,)).fetchone()
                pos = next((p for p in held if previous and p["token_id"] > previous[0]), held[0])
                limit = str(min(pos["quantity"], int(run["sale_limit"])))
                return run["wallet"], None, {"exit_scope": public_shadow.sell_scope(pos["condition_id"], pos["token_id"], limit)}
    wallet, budget, check_sales = public_shadow.sampling_terms(db, run_id, revision)
    return wallet, budget, {"retry_empty": True, "check_sales": check_sales}


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
            wallet, budget, options = _next_window(db, run_id, revision)
        except Conflict:
            db.execute("DELETE FROM background_runs WHERE run_id=?", (run_id,))
            return
        claim = uuid4().hex
        opened = capital_pool.control_boundary(db)
        db.execute("UPDATE background_runs SET due=?,claim=? WHERE run_id=?",
                   (started + CLAIM_SECONDS, claim, run_id))

    delay = INTERVAL
    scope = options.get("exit_scope")
    expected = {"exitScope": scope} if scope else {"researchBudget": budget}
    try:
        receipt = sample(wallet, budget, **options)
        if (not isinstance(receipt, dict) or receipt.get("wallet") != wallet
                or any(receipt.get(k) != v for k, v in expected.items()) or receipt.get("status") not in
                ("observed", "waiting", "unavailable", "incomplete", "skipped")):
            raise ValueError("Malformed public observation.")
        if receipt.get("status") == "unavailable":
            delay = OUTAGE_DELAY
    except Conflict:
        receipt = None
    except (OSError, ValueError):
        delay = OUTAGE_DELAY
        receipt = {"wallet": wallet, **expected, "status": "unavailable",
                   "reason": "The public provider could not complete this background window."}

    with store.connection() as db:
        if not db.execute("SELECT 1 FROM background_runs WHERE run_id=? AND claim=?", (run_id, claim)).fetchone():
            return
        if receipt is not None:
            try:
                if scope:
                    public_shadow.record_sale(db, run_id, revision, scope["tokenId"], scope["maxShares"], receipt, background=True)
                else:
                    result = public_shadow.record(db, run_id, revision, receipt)
                    capital_pool.capture(db, run_id, result["revision"], claim, opened)
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
