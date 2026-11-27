"""Seven-day simulated cash movements from recorded decisions, in micro-pUSD."""

from datetime import UTC, datetime, timedelta

from .provider import units_from_micros
from .public_shadow import _run, _signed


def summary(db, run_id, *, now=None):
    run = _run(db, run_id)
    through = now or datetime.now(UTC)
    through = through.replace(microsecond=through.microsecond // 1000 * 1000)
    start = through - timedelta(days=7)
    bounds = (start.isoformat(timespec="milliseconds"), through.isoformat(timespec="milliseconds"))
    created = datetime.fromisoformat(run["created"])
    opening = run["capital"] if created < start else 0
    funding = run["capital"] if start <= created <= through else 0
    # Group by temporal boundary and kind. Use integer units throughout. Positive
    # total shares is only used to detect whether a boundary needs asset prices.
    rows = db.execute("""SELECT julianday(recorded) >= julianday(?) AS in_week, kind,
                         count(*) AS n, sum(gross) AS gross, sum(fee) AS fees,
                         sum(shares) AS shares, sum(released_cost) AS released,
                         sum(CASE WHEN kind='deposit' THEN json_extract(receipt,'$.amountMicros') ELSE 0 END) AS funding
                         FROM public_decisions WHERE run_id=? AND julianday(recorded) <= julianday(?)
                         GROUP BY in_week,kind""", (bounds[0], run_id, bounds[1]))
    counts = {}
    buys = sales = fees = realized = 0
    shares_before = shares_at_end = 0
    for row in rows:
        kind = row["kind"]
        if kind == "deposit":
            if row["in_week"]:
                funding += row["funding"]
            else:
                opening += row["funding"]
        if kind in ("entry", "exit"):
            direction = 1 if kind == "entry" else -1
            shares_at_end += direction * row["shares"]
            if row["in_week"]:
                fees += row["fees"]
                if kind == "entry":
                    buys += row["gross"]
                else:
                    sales += row["gross"]
                    realized += row["gross"] - row["fees"] - row["released"]
            else:
                opening -= direction * row["gross"] + row["fees"]
                shares_before += direction * row["shares"]
        if row["in_week"]:
            counts[kind] = row["n"]

    last = db.execute("""SELECT kind,reason,recorded FROM public_decisions WHERE run_id=?
                         AND kind IN ('entry','exit','skipped','duplicate','waiting','incomplete','unavailable')
                         AND julianday(recorded) BETWEEN julianday(?) AND julianday(?)
                         ORDER BY revision DESC LIMIT 1""", (run_id, *bounds)).fetchone()
    observation_kinds = ("entry", "exit", "skipped", "duplicate", "waiting", "incomplete", "unavailable")
    cash_change = sales - buys - fees
    closing = opening + funding + cash_change
    return {"runId": run_id, "revision": run["revision"], "from": bounds[0], "through": bounds[1],
            "asset": "pUSD", "openingCash": units_from_micros(opening), "funding": units_from_micros(funding),
            "purchases": units_from_micros(buys), "sales": units_from_micros(sales), "fees": units_from_micros(fees),
            "closingCash": units_from_micros(closing), "realizedOnSales": _signed(realized),
            "netResult": _signed(cash_change) if not shares_before and not shares_at_end else None,
            "observations": sum(counts.get(kind, 0) for kind in observation_kinds),
            "counts": counts, "latestObservation": dict(last) if last else None}
