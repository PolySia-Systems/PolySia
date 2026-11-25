"""User-stepped shadow portfolios for one public wallet. Amounts in SQLite are micro-pUSD."""

import json
import re
from datetime import datetime
from decimal import Decimal

from .provider import decimal_value, units_from_micros as units, validate_address
from .public_depth import budget_amount, capacity_policy, measure_depth
from .public_fill import EXCHANGES
from .store import Conflict, timestamp


PAGE = 20
MODE = "public-shadow"
MODEL = "displayed-asks-v1"
CONTROLS = {"pause": ("running", "paused"), "resume": ("paused", "running"), "stop": (None, "stopped")}
CONTROL_REASONS = {"pause": "New entries paused.", "resume": "Ready for another observation.",
                   "stop": "Run stopped. Existing simulated positions remain open."}


def _budget(value):
    return int(Decimal(budget_amount(value)) * 1_000_000)


def _money(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,10}(?:\.[0-9]{1,6})?", value):
        raise ValueError("Invalid amount in observation")
    return int(Decimal(value) * 1_000_000)


def _run(db, run_id):
    row = db.execute("SELECT * FROM public_runs WHERE id=?", (run_id,)).fetchone()
    if row is None:
        raise KeyError("Public shadow run not found.")
    return row


def _policy(budget):
    return {**capacity_policy(budget), "model": MODEL, "side": "BUY", "entryModel": "displayed whole shares",
            "windowSeconds": 2, "retryEmpty": True, "venueMinimumNotionalEnforced": False,
            "exitModel": None, "markModel": "on-demand two-sided midpoint"}


def create(db, run_id, wallet, name, capital, cap):
    wallet = validate_address(wallet)
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
        raise ValueError("Give the run a name of 1–80 characters.")
    config = (wallet, name.strip(), _budget(capital), _budget(cap))
    if config[3] > config[2]:
        raise ValueError("The per-entry budget must fit within the starting cash.")
    now = timestamp()
    policy = _policy(budget_amount(cap))
    db.execute("""INSERT INTO public_runs VALUES (?,?,?,?,?,?,?,?,'running',1)
                  ON CONFLICT(id) DO NOTHING""", (run_id, *config, json.dumps(policy), now, now))
    row = _run(db, run_id)
    if tuple(row[k] for k in ("wallet", "name", "capital", "entry_cap")) != config:
        raise Conflict("This run already exists with different settings.")
    return report(db, run_id)


def _totals(db, run_id):
    return db.execute("""SELECT coalesce(sum(gross),0), coalesce(sum(fee),0),
                         count(CASE WHEN kind='entry' THEN 1 END) FROM public_decisions WHERE run_id=?""",
                      (run_id,)).fetchone()


def _next_budget(cash, cap):
    # Public observations accept cent-denominated budgets. Keep sub-cent cash in the ledger.
    cents = min(cash, cap) // 10_000
    return f"{cents // 100}.{cents % 100:02d}" if cents >= 100 else None


def _summary(row, gross, fee, entries):
    cash = row["capital"] - gross - fee
    return {"id": row["id"], "name": row["name"], "wallet": row["wallet"], "mode": MODE,
            "model": MODEL, "asset": "pUSD", "status": row["status"], "revision": row["revision"],
            "createdAt": row["created"], "updatedAt": row["updated"], "capital": units(row["capital"]),
            "entryCap": units(row["entry_cap"]), "cash": units(cash), "gross": units(gross), "fees": units(fee),
            "entries": entries, "nextBudget": _next_budget(cash, row["entry_cap"])}


def listing(db, before=None):
    cursor = 2**63 - 1
    if before:
        row = db.execute("SELECT rowid FROM public_runs WHERE id=?", (before,)).fetchone()
        if not row:
            raise ValueError("Unknown public run cursor.")
        cursor = row[0]
    rows = db.execute("SELECT * FROM public_runs WHERE rowid < ? ORDER BY rowid DESC LIMIT ?",
                      (cursor, PAGE + 1)).fetchall()
    items = [_summary(row, *_totals(db, row["id"])) for row in rows[:PAGE]]
    return {"runs": items, "nextCursor": items[-1]["id"] if len(rows) > PAGE else None}


def report(db, run_id, *, export=False, before=None):
    row = _run(db, run_id)
    result = _summary(row, *_totals(db, run_id))
    result["policy"] = json.loads(row["policy"])
    result["positions"] = [
        {"conditionId": p["condition_id"], "tokenId": p["token_id"], "market": p["market"],
         "outcome": p["outcome"], "shares": str(p["quantity"]), "cost": units(p["cost"])}
        for p in db.execute("""SELECT condition_id, token_id, max(market) AS market, max(outcome) AS outcome,
                            sum(shares) AS quantity, sum(gross+fee) AS cost FROM public_decisions
                            WHERE run_id=? AND kind='entry' GROUP BY condition_id, token_id ORDER BY min(revision)""", (run_id,))]
    fields = "revision, recorded, kind, reason, shares, gross, fee, market, outcome, token_id, source_order"
    fields += """, json_extract(receipt,'$.windowStartSeconds') AS window_start,
                 json_extract(receipt,'$.windowEndSeconds') AS window_end,
                 json_extract(receipt,'$.event.eventTimeSeconds') AS event_time,
                 json_extract(receipt,'$.bookReceivedMs') AS book_time,
                 json_extract(receipt,'$.researchBudget') AS budget"""
    if export:
        rows = db.execute(f"SELECT {fields},receipt FROM public_decisions WHERE run_id=? ORDER BY revision", (run_id,))
    else:
        rows = db.execute(f"""SELECT {fields} FROM public_decisions WHERE run_id=? AND revision < ?
                           ORDER BY revision DESC LIMIT ?""", (run_id, before or 2**63 - 1, PAGE))
    decisions = []
    for d in rows:
        decision = {"revision": d["revision"], "at": d["recorded"], "kind": d["kind"], "reason": d["reason"],
                    "shares": str(d["shares"]), "gross": units(d["gross"]), "fee": units(d["fee"]),
                    "market": d["market"], "outcome": d["outcome"], "tokenId": d["token_id"], "sourceOrder": d["source_order"]}
        if d["budget"] is not None:
            decision["observation"] = {"windowStartSeconds": d["window_start"], "windowEndSeconds": d["window_end"],
                                       "eventTimeSeconds": d["event_time"], "bookReceivedMs": d["book_time"],
                                       "budget": d["budget"]}
        if export:
            decision["receipt"] = json.loads(d["receipt"]) if d["receipt"] else None
        decisions.append(decision)
    result["decisions"] = decisions
    result["nextCursor"] = decisions[-1]["revision"] if not export and decisions and decisions[-1]["revision"] > 2 else None
    return result


def _check_revision(row, revision):
    if type(revision) is not int or revision != row["revision"]:
        raise Conflict("The run changed. Reload the latest decisions before continuing.")


def _check_control(status, action):
    prior, after = CONTROLS[action]
    if status == "stopped" or (prior and status != prior):
        raise Conflict("This control is unavailable for the current run state.")
    return after


def position_basis(db, run_id, token, revision):
    row = _run(db, run_id)
    _check_revision(row, revision)
    positions = db.execute("""SELECT condition_id, sum(shares), sum(gross+fee) FROM public_decisions
                              WHERE run_id=? AND token_id=? AND kind='entry' GROUP BY condition_id""",
                           (run_id, token)).fetchall()
    if len(positions) != 1:
        raise ValueError("Choose an existing position with an unambiguous market.")
    condition, shares, cost = positions[0]
    return {"runId": run_id, "revision": revision, "conditionId": condition, "tokenId": token,
            "shares": str(shares), "cost": units(cost)}


def control(db, run_id, revision, action):
    row = _run(db, run_id)
    _check_revision(row, revision)
    status = _check_control(row["status"], action)
    now = timestamp()
    db.execute("""INSERT INTO public_decisions(run_id,revision,recorded,kind,reason,shares,gross,fee)
                  VALUES(?,?,?,?,?,0,0,0)""", (run_id, revision + 1, now, action, CONTROL_REASONS[action]))
    db.execute("UPDATE public_runs SET revision=revision+1, status=?, updated=? WHERE id=?", (status, now, run_id))
    return report(db, run_id)


def sampling_terms(db, run_id, revision):
    row = _run(db, run_id)
    _check_revision(row, revision)
    if row["status"] != "running":
        raise Conflict("Only a running public shadow portfolio can sample a BUY.")
    gross, fee, _ = _totals(db, run_id)
    budget = _next_budget(row["capital"] - gross - fee, row["entry_cap"])
    if not budget:
        raise Conflict("Less than 1 pUSD of simulated cash remains. Review the open positions.")
    return row["wallet"], budget


def _entry(receipt, budget):
    """Translate a locally produced, qualifying capacity receipt into a hypothetical entry."""
    cap, event, participant = receipt["capacity"], receipt["event"], receipt["participant"]
    if (receipt["status"] != "observed" or receipt["asset"] != "pUSD" or cap["asset"] != "pUSD"
            or cap["budget"] != budget or event["side"] != "BUY" or participant["status"] != "matched"
            or participant["chainId"] != 137 or participant["transactionHash"] != event["transactionHash"]
            or not re.fullmatch("0x[0-9a-f]{64}", event["transactionHash"])
            or participant["exchange"] not in EXCHANGES or not re.fullmatch("0x[0-9a-f]{64}", participant["orderHash"])
            or not re.fullmatch("0x[0-9a-f]{64}", event["conditionId"])
            or not re.fullmatch("[0-9]{1,78}", event["tokenId"])):
        raise ValueError("Receipt identity or policy mismatch")
    shares = cap["shares"]
    if not isinstance(shares, str) or not re.fullmatch("[1-9][0-9]{0,9}", shares):
        raise ValueError("Invalid modeled quantity")
    gross, fee, unspent = (_money(cap[key]) for key in ("gross", "feeEstimate", "unspent"))
    if not gross or gross + fee + unspent != _money(budget):
        raise ValueError("The modeled entry does not reconcile with its budget.")
    return (participant["exchange"] + "/" + participant["orderHash"], event["conditionId"], event["tokenId"],
            event.get("marketTitle"), event.get("outcomeLabel"), int(shares), gross, fee)


def _check_entry_policy(run, receipt, recorded):
    policy = json.loads(run["policy"])
    cap = receipt["capacity"]
    if any(cap[k] != policy[k] for k in capacity_policy(cap["budget"]) if k != "budget"):
        raise ValueError("The capacity assumptions changed since the run was created.")
    if (not 0 < decimal_value(receipt["event"]["price"]) <= 1
            or not 0 < len(receipt["book"]["bestAsks"]) <= policy["maxLevels"]
            or any(not isinstance(receipt["event"].get(key, ""), str) for key in ("marketTitle", "outcomeLabel"))):
        raise ValueError("Invalid source price, book depth or market labels.")
    if measure_depth(receipt, cap["budget"]) != cap:
        raise ValueError("The estimated entry differs from the retained book and market terms.")
    start = receipt["windowStartSeconds"]
    if (type(start) is not int or start < datetime.fromisoformat(run["created"]).timestamp()
            or receipt["windowEndSeconds"] != start + 1
            or receipt["bookReceivedMs"] > datetime.fromisoformat(recorded).timestamp() * 1000 + 1
            or not start <= receipt["event"]["eventTimeSeconds"] <= receipt["windowEndSeconds"]):
        raise ValueError("The source BUY falls outside the run's observation period.")


NO_ENTRY = (None, None, None, None, None, 0, 0, 0)


def _decision(run, budget, receipt, recorded, seen):
    if receipt["wallet"] != run["wallet"] or receipt["researchBudget"] != budget:
        raise ValueError("Receipt scope mismatch")
    capacity = receipt.get("capacity", {})
    kind = capacity.get("status", receipt["status"])
    if kind == "estimated":
        _check_entry_policy(run, receipt, recorded)
        candidate = _entry(receipt, budget)
        if seen(candidate[0]):
            return "duplicate", "This source order already has a modeled entry in this run.", NO_ENTRY
        return "entry", "Modeled a BUY against the delayed displayed asks.", candidate
    reason = capacity.get("reason") or receipt["reason"]
    if kind not in ("waiting", "incomplete", "unavailable", "skipped") or not isinstance(reason, str):
        raise ValueError("Unknown observation outcome")
    return kind, reason, NO_ENTRY


def record(db, run_id, revision, receipt):
    wallet, budget = sampling_terms(db, run_id, revision)
    now = timestamp()

    def seen(source):
        return db.execute("SELECT 1 FROM public_decisions WHERE run_id=? AND source_order=?", (run_id, source)).fetchone()

    try:
        kind, reason, amounts = _decision(_run(db, run_id), budget, receipt, now, seen)
    except (AttributeError, ArithmeticError, IndexError, KeyError, TypeError, ValueError):
        kind, reason, amounts = "incomplete", "The observation could not be reconciled with this run and its budget.", NO_ENTRY
        receipt = {"wallet": wallet, "researchBudget": budget, "status": kind, "reason": reason}
    db.execute("INSERT INTO public_decisions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (run_id, revision + 1, now, kind, reason, *amounts, json.dumps(receipt, allow_nan=False)))
    db.execute("UPDATE public_runs SET revision=revision+1, updated=? WHERE id=?", (now, run_id))
    return report(db, run_id)


def verify_archive(db):
    """Replay persisted control and money decisions against their frozen receipts."""
    if db.execute("PRAGMA foreign_key_check").fetchone():
        raise ValueError("A public shadow decision has no run.")
    for run in db.execute("SELECT * FROM public_runs"):
        if (not re.fullmatch("[0-9a-f]{32}", run["id"]) or validate_address(run["wallet"]) != run["wallet"]
                or not isinstance(run["name"], str) or not 1 <= len(run["name"].strip()) <= 80
                or not 1_000_000 <= run["entry_cap"] <= run["capital"] <= 1_000_000_000
                or run["capital"] % 10_000 or run["entry_cap"] % 10_000):
            raise ValueError("Invalid public shadow configuration.")
        cash, status, revision, last = run["capital"], "running", 1, run["created"]
        policy = json.loads(run["policy"])
        if policy != _policy(_next_budget(run["entry_cap"], run["entry_cap"])):
            raise ValueError("Invalid public shadow policy.")
        datetime.fromisoformat(last)
        used = set()
        for item in db.execute("SELECT * FROM public_decisions WHERE run_id=? ORDER BY revision", (run["id"],)):
            revision += 1
            kind, last = item["kind"], item["recorded"]
            datetime.fromisoformat(last)
            if item["revision"] != revision or not isinstance(item["reason"], str):
                raise ValueError("Invalid public shadow journal sequence.")
            if kind in CONTROLS:
                status = _check_control(status, kind)
                expected, reason = NO_ENTRY, CONTROL_REASONS[kind]
                if item["receipt"] is not None:
                    raise ValueError("Unexpected receipt on a public shadow control.")
            else:
                budget = _next_budget(cash, run["entry_cap"])
                if status != "running" or budget is None:
                    raise ValueError("Receipt outside the run's scope.")
                receipt = json.loads(item["receipt"])
                outcome, reason, expected = _decision(run, budget, receipt, last, used.__contains__)
                if kind != outcome:
                    raise ValueError("The public shadow decision differs from its receipt.")
                if kind == "entry":
                    used.add(expected[0])
            if item["reason"] != reason:
                raise ValueError("The saved explanation differs from the public shadow decision.")
            actual = tuple(item[k] for k in ("source_order", "condition_id", "token_id", "market", "outcome",
                                             "shares", "gross", "fee"))
            if actual != expected:
                raise ValueError("The public shadow journal disagrees with its recorded amounts.")
            cash -= item["gross"] + item["fee"]
        if (revision, status, last) != (run["revision"], run["status"], run["updated"]):
            raise ValueError("The public shadow run disagrees with its journal.")
