"""Cash movements and measured activity-page coverage for a forward shared portfolio."""

from datetime import timedelta

from . import sampling_coverage
from .provider import units_from_micros as units
from .public_shadow import _journal_time


class SharedWeek:
    def __init__(self, capital, created, through):
        self.through = through
        self.start = through - timedelta(days=7)
        self.created = _journal_time(created)
        self.capital = capital
        self.prior_cost = self.cost = self.fees = self.buys = 0

    def purchase(self, recorded, cost, fee):
        if _journal_time(recorded) < self.start:
            self.prior_cost += cost
        else:
            self.cost += cost
            self.fees += fee
            self.buys += 1

    def report(self, db, pool, members):
        result = {"from": self.start.isoformat(), "through": self.through.isoformat()}
        previous = self.created
        # Money follows shared commit order. A source clock can run behind a
        # different source or a control. Never assign that money to a guessed week.
        consistent = self.created <= self.through
        since = max(self.created, self.start)
        spans = {run: [] for run in members}
        receipts = {run: 0 for run in members}
        counts = {}
        rows = db.execute(f"""SELECT d.run_id,d.recorded,d.kind,c.recorded AS enabled,
                following.recorded AS disabled,{sampling_coverage.PAGE_FIELDS}
            FROM pool_windows w JOIN public_decisions d USING(run_id,revision)
            JOIN pool_controls c USING(pool_id,generation)
            LEFT JOIN pool_controls following ON following.pool_id=w.pool_id AND following.generation=w.generation+1
            WHERE w.pool_id=? ORDER BY w.sequence""", (pool,))
        for row in rows:
            recorded = _journal_time(row["recorded"])
            if (recorded < previous or recorded > self.through or recorded < _journal_time(row["enabled"])
                    or (row["disabled"] and recorded > _journal_time(row["disabled"]))):
                consistent = False
            previous = recorded
            if recorded < since or recorded > self.through:
                continue
            run, kind = row["run_id"], row["kind"]
            receipts[run] += 1
            counts[kind] = counts.get(kind, 0) + 1
            span = sampling_coverage.buy_span(row, recorded, since.timestamp(), self.through.timestamp())
            if span:
                spans[run].append(span)
        if not consistent:
            return dict(result, available=False, reason="The recorded clocks disagree with the order of shared decisions. All-time cash and holdings are available.")
        funding = self.capital if self.created >= self.start else 0
        opening = self.capital - funding - self.prior_cost
        coverage = {run: dict(sampling_coverage.coverage(since.timestamp(), self.through.timestamp(), windows),
                              receipts=receipts[run]) for run, windows in spans.items()}
        return dict(result, available=True, openingCash=units(opening), funding=units(funding),
                    purchaseCost=units(self.cost), includedFees=units(self.fees), buys=self.buys,
                    closingCash=units(opening + funding - self.cost), counts=counts, coverage=coverage,
                    netResult=None if self.prior_cost or self.cost else "0")
