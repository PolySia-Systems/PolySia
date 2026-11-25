"""Record a predeclared, finite series of public observation windows as JSON Lines."""

from collections import Counter
from decimal import InvalidOperation
from http.client import HTTPException
import json
import os
import time

from . import VERSION
from .observe import ACTIVITY, read_buy_page, sample_once
from .public_depth import budget_amount, capacity_policy
from .provider import validate_address


def _recheck_activity(wallet, receipt):
    start, end = receipt.get("windowStartSeconds"), receipt.get("windowEndSeconds")
    result = {"windowStartSeconds": start, "windowEndSeconds": end, "activitySource": ACTIVITY,
              "checkedMs": time.time_ns() // 1_000_000}
    if start is None or end is None:
        return dict(result, reason="The original process did not return window bounds.")
    try:
        buys, coverage, received = read_buy_page(wallet, start, end)
        return dict(result, activityCoverage=coverage, activityReceivedMs=received, visibleBuys=buys)
    except (OSError, HTTPException, KeyError, ValueError, InvalidOperation, RecursionError):
        return dict(result, reason="The activity recheck was unavailable or failed validation.")


def record_study(path, wallet, budget, seconds, windows, *, recheck_after=0):
    wallet = validate_address(wallet)
    budget = budget_amount(budget)
    if type(seconds) is not int or not 1 <= seconds <= 30 or type(windows) is not int or not 1 <= windows <= 10:
        raise ValueError("Choose 1–10 windows of 1–30 seconds each.")
    if type(recheck_after) is not int or not 0 <= recheck_after <= 300:
        raise ValueError("Choose an activity recheck delay between 0 and 300 seconds.")
    planned_rechecks = []
    outcomes = Counter()
    fills, orders = set(), set()
    with path.open("x", encoding="utf-8") as stream:
        def append(kind, **fields):
            stream.write(json.dumps({"type": kind, **fields}, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

        append("plan", schemaVersion=2, version=VERSION, wallet=wallet, **capacity_policy(budget),
               windows=windows, secondsPerWindow=seconds, recheckAfterSeriesSeconds=recheck_after,
               selection="Earliest ordinary BUY on the returned page. Provider order breaks time ties.")
        for index in range(1, windows + 1):
            append("attempt", number=index, startedMs=time.time_ns() // 1_000_000)
            try:
                receipt = sample_once(wallet, seconds, budget)
            except (OSError, ValueError):
                receipt = {"wallet": wallet, "status": "unavailable",
                           "reason": "The sampling process failed to return a receipt within its deadline."}
            outcome = receipt.get("capacity", {}).get("status", receipt["status"])
            append("window", number=index, outcome=outcome, receipt=receipt)
            if recheck_after:
                planned_rechecks.append((index, receipt))
            outcomes[outcome] += 1
            participant = receipt.get("participant", {})
            if participant.get("status") == "matched":
                fills.add(participant["fillId"])
                orders.add((participant["exchange"], participant["orderHash"]))
        summary = {"windows": windows, "outcomes": dict(outcomes),
                   "distinctParticipantFills": len(fills), "distinctSourceOrders": len(orders)}
        if recheck_after:
            time.sleep(recheck_after)
            comparable = later_positive = 0
            for index, receipt in planned_rechecks:
                result = _recheck_activity(wallet, receipt)
                append("activityRecheck", number=index, **result)
                if receipt["status"] == "waiting" and "activityCoverage" in result:
                    positive = bool(result["visibleBuys"])
                    if positive or result["activityCoverage"]["complete"]:
                        comparable += 1
                        later_positive += positive
            summary["waitingWindowsCompared"] = comparable
            summary["waitingWindowsWithLaterBuy"] = later_positive
        append("summary", **summary)
    return summary
