"""Measured time and gaps in completed two-second public BUY activity pages."""

from datetime import UTC, datetime


PAGE_FIELDS = """json_extract(d.receipt,'$.windowStartSeconds') AS lo,
    json_extract(d.receipt,'$.windowEndSeconds') AS hi,
    json_type(d.receipt,'$.activityCoverage.complete') AS complete,
    json_extract(d.receipt,'$.activityReceivedMs') AS received,
    json_extract(d.receipt,'$.activityReads[#-1].requestedMs') AS requested"""


def buy_span(row, recorded, start, end):
    lo, hi, received = row["lo"], row["hi"], row["received"]
    # A worker requests two inclusive seconds. A missing or late-indexed
    # activity page cannot establish that the wallet made no trades.
    # A missing book can prevent a buy even when the activity page was complete.
    if (row["complete"] != "true"
            or type(lo) is not int or type(hi) is not int or hi != lo + 1
            or type(received) is not int or received < (hi + 1) * 1000
            or (row["requested"] is not None and
                (type(row["requested"]) is not int or not (hi + 1) * 1000 <= row["requested"] <= received))
            or received > recorded.timestamp() * 1000 + 1):
        return None
    left, right = max(start, lo), min(end, hi + 1)
    if right > left:
        return left, right
    return None


def coverage(start, end, windows):
    cursor = start
    longest = (start, start)
    seconds = 0
    for left, right in sorted(windows):
        if left - cursor > longest[1] - longest[0]:
            longest = (cursor, left)
        seconds += max(0, right - max(left, cursor))
        cursor = max(cursor, right)
    if end - cursor > longest[1] - longest[0]:
        longest = (cursor, end)
    gap = None
    if longest[1] > longest[0]:
        gap = {key: datetime.fromtimestamp(value, UTC).isoformat()
               for key, value in zip(("from", "through"), longest)}
    return {"completePageSeconds": round(seconds, 6), "periodSeconds": round(end - start, 6), "longestGap": gap}
