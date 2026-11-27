"""Seven-day simulated cash movements from recorded decisions, in micro-pUSD."""

import json
from datetime import UTC, datetime, timedelta

from .provider import units_from_micros
from .public_shadow import _journal_time, _run, _signed, report, require_revision


OBSERVATIONS = {"entry", "exit", "skipped", "duplicate", "waiting", "incomplete", "unavailable"}


def summary(db, run_id, *, now=None, evidence=None):
    run = _run(db, run_id)
    through = now or datetime.now(UTC)
    start = through - timedelta(days=7)
    previous = _journal_time(run["created"])
    opening = run["capital"] if previous < start else 0
    funding = run["capital"] if start <= previous <= through else 0
    buys = sales = fees = realized = 0
    shares_before = shares_at_end = 0
    counts = {}
    last = None
    # Restore and reporting use the same timestamp parser. Walk in revision
    # order so a clock correction or sub-millisecond boundary is visible.
    detail = "" if evidence is None else """, revision, condition_id, token_id, source_order,
                CASE WHEN kind='change-cap' THEN receipt END AS cap_change"""
    rows = db.execute(f"""SELECT recorded,kind,gross,fee,shares,released_cost,reason{detail},
                         CASE WHEN kind='deposit' THEN json_extract(receipt,'$.amountMicros') END AS deposit
                         FROM public_decisions WHERE run_id=? ORDER BY revision""", (run_id,))
    for row in rows:
        recorded = _journal_time(row["recorded"])
        if recorded < previous:
            raise ValueError("Weekly totals are unavailable because the recorded clock moved backwards. The decision journal is available.")
        previous = recorded
        if recorded > through:
            continue
        kind = row["kind"]
        in_week = recorded >= start
        if kind == "deposit":
            if in_week:
                funding += row["deposit"]
            else:
                opening += row["deposit"]
        elif kind in ("entry", "exit"):
            direction = 1 if kind == "entry" else -1
            shares_at_end += direction * row["shares"]
            if in_week:
                fees += row["fee"]
                if kind == "entry":
                    buys += row["gross"]
                else:
                    sales += row["gross"]
                    realized += row["gross"] - row["fee"] - row["released_cost"]
            else:
                opening -= direction * row["gross"] + row["fee"]
                shares_before += direction * row["shares"]
        if in_week:
            counts[kind] = counts.get(kind, 0) + 1
            if kind in OBSERVATIONS:
                last = {key: row[key] for key in ("kind", "reason", "recorded")}
            if evidence is not None:
                evidence.append(_period_decision(row))

    cash_change = sales - buys - fees
    closing = opening + funding + cash_change
    return {"runId": run_id, "revision": run["revision"], "from": start.isoformat(), "through": through.isoformat(),
            "asset": "pUSD", "openingCash": units_from_micros(opening), "funding": units_from_micros(funding),
            "purchases": units_from_micros(buys), "sales": units_from_micros(sales), "fees": units_from_micros(fees),
            "closingCash": units_from_micros(closing), "realizedOnSales": _signed(realized),
            "netResult": _signed(cash_change) if not shares_before and not shares_at_end else None,
            "observations": sum(counts.get(kind, 0) for kind in OBSERVATIONS), "counts": counts, "latestObservation": last}


def _period_decision(row):
    item = {"revision": row["revision"], "recorded": row["recorded"], "kind": row["kind"], "reason": row["reason"]}
    if row["kind"] in ("entry", "exit"):
        item.update(conditionId=row["condition_id"], tokenId=row["token_id"], sourceReference=row["source_order"],
                    shares=str(row["shares"]), gross=units_from_micros(row["gross"]), fee=units_from_micros(row["fee"]))
        if row["kind"] == "exit":
            item.update(releasedCost=units_from_micros(row["released_cost"]),
                        realizedOnSale=_signed(row["gross"] - row["fee"] - row["released_cost"]))
    elif row["kind"] == "deposit":
        item["funding"] = units_from_micros(row["deposit"])
    elif row["kind"] == "change-cap":
        item.update(json.loads(row["cap_change"]))
    return item


def export_week(db, run_id, revision, through):
    require_revision(db, run_id, revision)
    if not isinstance(through, str) or len(through) > 40:
        raise ValueError("Use the end time from the displayed seven-day report.")
    end = _journal_time(through)
    if end.utcoffset() != timedelta(0) or end.year < 2:
        raise ValueError("Use the UTC end time from the displayed seven-day report.")
    decisions = []
    period = summary(db, run_id, now=end, evidence=decisions)
    state = report(db, run_id)
    return {"formatVersion": 1, "period": period, "decisions": decisions,
            "run": {key: state[key] for key in ("id", "name", "wallet", "mode", "model", "asset", "createdAt",
                                                "capital", "policy", "revision", "status", "entryCap",
                                                "backgroundEnabled", "exitsEnabled", "positions", "openCost")},
            "method": "Both UTC boundaries are inclusive. Funding includes the initial contribution if it falls in the period. Closing cash equals opening cash plus funding and gross sales, less purchases and estimated fees.",
            "limitations": "Amounts are simulated pUSD. Realized sales deduct sale fees and released purchase cost. Open positions at either period boundary leave net result unknown. Current positions and controls describe the exported run revision. Raw observation receipts are available in Export run."}
