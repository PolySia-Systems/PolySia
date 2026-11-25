"""Online SQLite backup and restore to a new local file."""

import json
import os
import re
import sqlite3
from contextlib import closing
from datetime import datetime
from decimal import InvalidOperation
from pathlib import Path
from tempfile import NamedTemporaryFile

from .provider import decimal_value, validate_address


def _cents(value):
    """Journal amounts in schema 1 are decimal strings with exactly two places."""
    if not isinstance(value, str) or not re.fullmatch(r"-?[0-9]+\.[0-9]{2}", value):
        raise ValueError("Invalid replay amount.")
    return int(value.replace(".", ""))


def _shares(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+", value):
        raise ValueError("Invalid whole-share quantity.")
    return int(value)


def _verify_journal(record, stored_id):
    if record["id"] != stored_id or record["mode"] != "shadow" or record["source"] != "scenario":
        raise ValueError("Replay identity or mode mismatch.")
    # Schema 1 writes midpoint estimates as plain USD decimals, including fractional cents.
    mark = record["marked_value"]
    if mark is not None and (not isinstance(mark, str) or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", mark)):
        raise ValueError("Invalid midpoint estimate.")
    if record["status"] not in ("running", "paused", "stopped", "completed"):
        raise ValueError("Unknown replay status.")
    if type(record["revision"]) is not int or record["revision"] < 1:
        raise ValueError("Invalid replay revision.")
    for field in ("leader_id", "leader_name", "market", "scenario"):
        if not isinstance(record[field], str):
            raise ValueError("Missing replay metadata.")
    for field in ("createdAt", "updatedAt"):
        datetime.fromisoformat(record[field])
    events = record["events"]
    if not isinstance(events, list) or type(record["cursor"]) is not int or len(events) != record["cursor"]:
        raise ValueError("Inconsistent replay cursor.")
    total, remaining = record["total_steps"], record["remaining_steps"]
    if type(total) is not int or type(remaining) is not int or remaining < 0 or len(events) + remaining != total:
        raise ValueError("Inconsistent replay length.")
    if (record["status"] == "completed") != (remaining == 0) or not isinstance(record["policy"], dict):
        raise ValueError("Invalid replay state or policy.")
    capital = _cents(record["capital"])
    if not 0 < _cents(record["order_size"]) <= capital:
        raise ValueError("Invalid replay allocation or order cap.")
    cash, shares, fees = capital, 0, 0
    for event in events:
        if event["side"] not in ("BUY", "SELL") or event["status"] not in ("skipped", "partial", "filled"):
            raise ValueError("Unknown journal entry.")
        gross, fee, count = _cents(event["filled"]), _cents(event["fee"]), _shares(event["quantity"])
        if min(gross, fee, count) < 0 or (event["status"] == "skipped" and any((gross, fee, count))):
            raise ValueError("Invalid journal entry amounts.")
        if event["status"] != "skipped" and (not gross or not count):
            raise ValueError("Recorded fill has no shares or notional.")
        direction = 1 if event["side"] == "BUY" else -1
        cash -= direction * gross + fee
        shares += direction * count
        fees += fee
        if min(cash, shares) < 0:
            raise ValueError("The journal spends unavailable cash or shares.")
    if (cash, shares, fees) != (_cents(record["cash"]), _shares(record["quantity"]), _cents(record["fees"])):
        raise ValueError("Journal totals disagree with the saved balances.")
    if cash + _cents(record["cost_basis"]) != capital + _cents(record["realized_pnl"]):
        raise ValueError("Cost basis and realized result do not reconcile.")


def _verify_position_page(page, available):
    rows = page["positions"]
    if not isinstance(rows, list) or type(page["complete"]) is not bool or not isinstance(page["source"], str):
        raise ValueError("Invalid position page.")
    if available:
        datetime.fromisoformat(page["observedAt"])
    elif page["observedAt"] is not None or rows or page["complete"]:
        raise ValueError("An unavailable snapshot claims current position data.")
    for row in rows:
        # Earlier schema-1 positions can lack market identity and lifecycle.
        if not all(isinstance(row[field], str) for field in ("market", "outcome", "shares")):
            raise ValueError("Unreadable position row.")
        decimal_value(row["shares"])


def _verify_records(db, stored_account):
    if stored_account is not None:
        try:
            account = json.loads(stored_account)
            validate_address(account["address"])
            datetime.fromisoformat(account["checkedAt"])
            if account["status"] not in ("available", "unavailable") or not isinstance(account["message"], str):
                raise ValueError("Invalid public watch.")
            _verify_position_page(account, account["status"] == "available")
            if "lastSuccessful" in account:
                _verify_position_page(account["lastSuccessful"], True)
        except (ValueError, KeyError, TypeError, InvalidOperation) as exc:
            raise ValueError("The saved account watch could not be read.") from exc

    # Stream one run at a time. Reconcile its recorded fills independently of the
    # current tape or policy so a software update cannot rewrite past economics.
    for run_id, raw in db.execute("SELECT id, record FROM runs"):
        try:
            _verify_journal(json.loads(raw), run_id)
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError(f"Saved replay {run_id} failed its integrity check: {exc}") from exc


def copy_workspace(source: Path, destination: Path):
    source = source.expanduser().resolve(strict=True)
    destination = destination.expanduser().absolute()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Destination already exists: {destination}")
    if not destination.parent.is_dir():
        raise ValueError("Choose an existing destination directory.")

    # Link only a complete, verified snapshot. A racing process that creates
    # the destination first wins; no existing backup or DB can be replaced.
    with NamedTemporaryFile(dir=destination.parent, prefix=".polysia-backup-") as staging:
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as reader:
            with closing(sqlite3.connect(staging.name)) as writer:
                reader.backup(writer, pages=256)
                if writer.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                    raise ValueError("The copied database failed the SQLite integrity check.")
                if writer.execute("PRAGMA user_version").fetchone()[0] != 1:
                    raise ValueError("This file is not a supported PolySia workspace.")
                tables = set(writer.execute(
                    "SELECT name FROM sqlite_schema WHERE type = 'table' AND name IN ('workspace', 'runs')"
                ))
                if tables != {("workspace",), ("runs",)}:
                    raise ValueError("The workspace schema is incomplete.")
                row = writer.execute(
                    "SELECT theme, account_revision, settings_revision, account FROM workspace WHERE id = 1"
                ).fetchone()
                if row is None or row[0] not in ("light", "dark"):
                    raise ValueError("The workspace settings are missing or invalid.")
                if any(type(revision) is not int or revision < 0 for revision in row[1:3]):
                    raise ValueError("The workspace revisions are invalid.")
                _verify_records(writer, row[3])
        os.fsync(staging.fileno())
        os.link(staging.name, destination)
        dir_fd = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
