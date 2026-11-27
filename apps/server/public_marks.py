"""On-demand public midpoint estimates for simulated holdings and portfolio equity."""

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from decimal import Decimal, InvalidOperation, localcontext
from http.client import HTTPException

from .observe import BOOK, normalize_book
from .provider import read_public_json

MAX_BOOK_AGE_MS = 60_000
MAX_PORTFOLIO_BOOKS = 12


def read_mark(basis):
    result = {**basis, "source": BOOK, "method": "two-sided midpoint", "asset": "pUSD",
              "maxBookAgeMs": MAX_BOOK_AGE_MS, "bookTimeMs": None, "bid": None, "ask": None,
              "midpoint": None, "value": None, "changeFromCost": None}
    try:
        payload = read_public_json(BOOK, {"token_id": basis["tokenId"]})
        book = normalize_book(payload, basis)
        received = time.time_ns() // 1_000_000
        bid = book["bestBid"]
        asks = book["bestAsks"]
        result.update(bookTimeMs=book["sourceTimeMs"], bid=bid["price"] if bid else None,
                      ask=asks[0]["price"] if asks else None)
        if not 0 <= received - book["sourceTimeMs"] <= MAX_BOOK_AGE_MS:
            reason = "The book timestamp fell outside the one-minute freshness window."
        elif book["sourceTimeMs"] < round(datetime.fromisoformat(basis.get("lastChangeAt", basis["lastEntryAt"])).timestamp() * 1000):
            reason = "The book was last updated before the latest change to this position."
        elif not bid or not asks or Decimal(book["spreadPerShare"]) <= 0:
            reason = "A midpoint needs a bid below the ask on the same book."
        else:
            with localcontext() as arithmetic:
                arithmetic.prec = 100
                midpoint = (Decimal(result["bid"]) + Decimal(result["ask"])) / 2
                value = int(basis["shares"]) * midpoint
                result.update(midpoint=format(midpoint.normalize(), "f"), value=format(value.normalize(), "f"),
                              changeFromCost=format((value - Decimal(basis["cost"])).normalize(), "f"))
            reason = "Estimate at the displayed midpoint, before any exit fees."
    except (OSError, HTTPException, InvalidOperation, KeyError, TypeError, ValueError, RecursionError):
        received = time.time_ns() // 1_000_000
        reason = "A matching public order book could not be read."
    return dict(result, checkedMs=received, reason=reason)


def portfolio_value(basis):
    positions = basis["positions"]
    with ThreadPoolExecutor(max_workers=3) as readers:
        marks = list(readers.map(read_mark, positions[:MAX_PORTFOLIO_BOOKS]))
    checked = time.time_ns() // 1_000_000
    for mark in marks:
        if mark["value"] is not None and not 0 <= checked - mark["bookTimeMs"] <= MAX_BOOK_AGE_MS:
            mark.update(value=None, changeFromCost=None, midpoint=None,
                        reason="The quote fell outside the freshness window before the portfolio check finished.")
    priced = [Decimal(mark["value"]) for mark in marks if mark["value"] is not None]
    complete = len(priced) == len(positions)
    # Midpoints may have fractional micro-pUSD. Cash and cost remain integer-backed.
    with localcontext() as arithmetic:
        arithmetic.prec = 110
        marked = sum(priced, Decimal(0))
        equity = Decimal(basis["cash"]) + marked
        deposited = basis.get("deposits", "0")
        funded = basis.get("fundedCapital", basis["capital"])
        capital = Decimal(funded)
        net = equity - capital
        benchmark = {"strategy": "hold starting cash" if deposited == "0" else "hold all contributed cash",
                     "from": basis["createdAt"], "throughMs": checked,
                     "endValue": funded, "assumedYield": "0", "additionalFlows": deposited,
                     "netReturnPct": None, "unpricedValueNeededToMatchCash": None}
        if complete:
            pct = (net * 100 / capital).quantize(Decimal("0.0001"))
            benchmark["netReturnPct"] = format(pct.normalize(), "f") if pct else "0"
        else:
            # With missing marks this is a break-even requirement, not a valuation.
            benchmark["unpricedValueNeededToMatchCash"] = format(max(Decimal(0), -net).normalize(), "f")
        return {"runId": basis["id"], "revision": basis["revision"], "wallet": basis["wallet"],
                "mode": basis["mode"], "asset": "pUSD", "source": BOOK, "checkedMs": checked,
                "cashBenchmark": benchmark, "grossPurchases": basis["gross"], "grossSales": basis["sales"],
                "modeledFees": basis["fees"], "entryCap": basis["entryCap"],
                "capital": basis["capital"], "cash": basis["cash"], "realized": basis["realized"],
                "openCost": basis["openCost"], "complete": complete, "total": len(positions),
                "priced": len(priced), "checked": len(marks), "maxBooks": MAX_PORTFOLIO_BOOKS, "marks": marks,
                "uncheckedPositions": positions[MAX_PORTFOLIO_BOOKS:],
                "pricedValue": format(marked.normalize(), "f") if priced or not positions else None,
                "equity": format(equity.normalize(), "f") if complete else None,
                "unrealized": format((marked - Decimal(basis["openCost"])).normalize(), "f") if complete else None,
                "netResult": format(net.normalize(), "f") if complete else None}
