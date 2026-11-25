"""One explicit midpoint check for an existing simulated position."""

import time
from datetime import datetime
from decimal import Decimal, InvalidOperation, localcontext
from http.client import HTTPException

from .observe import BOOK, normalize_book
from .provider import read_public_json

MAX_BOOK_AGE_MS = 60_000


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
        elif book["sourceTimeMs"] < round(datetime.fromisoformat(basis["lastEntryAt"]).timestamp() * 1000):
            reason = "The book was last updated before this position’s most recent purchase."
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
