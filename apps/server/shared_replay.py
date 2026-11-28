"""Replay retained public BUY decisions against one simulated balance and ask ladder."""

import json
import re

from . import public_depth, public_shadow
from .provider import units_from_micros as units


def replay(db, run_ids, capital):
    if (not isinstance(run_ids, list) or len(run_ids) < 2
            or any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{32}", value) for value in run_ids)
            or len(set(run_ids)) != len(run_ids)):
        raise ValueError("Select two or more distinct saved public runs.")
    return allocate(db, run_ids, capital)


def allocate(db, run_ids, capital, *, pool=None, week=None):
    """Price retained BUYs in receipt order, or in immutable forward-pool commit order."""
    cash = public_depth._micros(public_depth.budget_amount(capital))
    starting = cash
    placeholders = ",".join("?" for _ in run_ids)
    runs = {}
    for row in db.execute(f"SELECT id,name,wallet,revision FROM public_runs WHERE id IN ({placeholders}) ORDER BY id", run_ids):
        runs[row["id"]] = {**dict(row), "recordedBuys": 0, "modeledBuys": 0, "sharesByToken": {}, "costMicros": 0}
    if len(runs) != len(run_ids):
        raise ValueError("One of the selected public runs is no longer available.")
    source = "public_decisions d"
    order = "received,d.run_id,d.revision"
    scope = f"d.run_id IN ({placeholders})"
    values = run_ids
    if pool is not None:
        source += " JOIN pool_windows w ON w.run_id=d.run_id AND w.revision=d.revision"
        scope, values, order = "w.pool_id=?", (pool,), "w.sequence"
    covered = db.execute(f"""SELECT kind,count(*) FROM {source} WHERE {scope}
        AND kind IN ('waiting','unavailable','incomplete','skipped','duplicate','exit') GROUP BY kind""", values)
    other = dict(covered)
    # Sort just identifiers and times. Receipts contain full books and are read one at a time.
    buys = db.execute(f"""SELECT d.rowid, d.run_id, d.recorded, source_order, json_extract(receipt,'$.bookReceivedMs') AS received
                          FROM {source} WHERE {scope} AND kind='entry' ORDER BY {order}""", values)
    used = {}
    seen = set()
    fees = duplicates = insufficient = missing = 0
    first = last = None
    for row in buys:
        run = runs[row["run_id"]]
        run["recordedBuys"] += 1
        first = row["received"] if first is None else min(first, row["received"])
        last = row["received"] if last is None else max(last, row["received"])
        key = (run["wallet"], row["source_order"])
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        receipt = json.loads(db.execute("SELECT receipt FROM public_decisions WHERE rowid=?", (row["rowid"],)).fetchone()[0])
        # Early releases could admit a BUY without checking for an intervening sale.
        try:
            sale_issue = public_shadow._sale_check_issue(receipt)
        except (KeyError, TypeError, ValueError):
            # Older runs accepted BUY evidence without a complete reversal check.
            sale_issue = True
        if sale_issue:
            missing += 1
            continue
        budget = public_shadow._next_budget(cash, public_depth._micros(receipt["researchBudget"]))
        if budget is None:
            insufficient += 1
            continue
        token = receipt["event"]["tokenId"]
        levels = used.setdefault(token, {})
        estimate = public_depth._estimate(receipt, budget, receipt["market"], consumed=levels)
        if estimate["status"] != "estimated":
            insufficient += 1
            continue
        fee = public_depth._micros(estimate["feeEstimate"])
        cost = public_depth._micros(estimate["gross"]) + fee
        cash -= cost
        fees += fee
        if week is not None:
            week.purchase(row["recorded"], cost, fee)
        run["costMicros"] += cost
        run["modeledBuys"] += 1
        shares = run["sharesByToken"]
        shares[token] = shares.get(token, 0) + int(estimate["shares"])
    for run in runs.values():
        run["cost"] = units(run.pop("costMicros"))
    return {"startingCash": units(starting), "cash": units(cash), "fees": units(fees), "cost": units(starting - cash),
            "duplicateOrders": duplicates, "missingSaleChecks": missing, "limitedBuys": insufficient,
            "firstBookMs": first, "lastBookMs": last, "otherRecordedDecisions": other, "runs": list(runs.values())}
