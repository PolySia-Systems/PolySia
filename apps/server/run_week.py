"""Seven-day simulated cash movements from recorded decisions, in micro-pUSD."""

from datetime import UTC, datetime, timedelta

from .provider import units_from_micros
from .public_shadow import _journal_time, _run, _signed


OBSERVATIONS = {"entry", "exit", "skipped", "duplicate", "waiting", "incomplete", "unavailable"}


def summary(db, run_id, *, now=None):
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
    rows = db.execute("""SELECT recorded,kind,gross,fee,shares,released_cost,reason,
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

    cash_change = sales - buys - fees
    closing = opening + funding + cash_change
    return {"runId": run_id, "revision": run["revision"], "from": start.isoformat(), "through": through.isoformat(),
            "asset": "pUSD", "openingCash": units_from_micros(opening), "funding": units_from_micros(funding),
            "purchases": units_from_micros(buys), "sales": units_from_micros(sales), "fees": units_from_micros(fees),
            "closingCash": units_from_micros(closing), "realizedOnSales": _signed(realized),
            "netResult": _signed(cash_change) if not shares_before and not shares_at_end else None,
            "observations": sum(counts.get(kind, 0) for kind in OBSERVATIONS), "counts": counts, "latestObservation": last}
