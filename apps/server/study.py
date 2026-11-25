"""Record a predeclared, finite series of public observation windows as JSON Lines."""

from collections import Counter
import json
import os
import time

from . import VERSION
from .observe import sample_once
from .public_depth import budget_amount, capacity_policy
from .provider import validate_address


def record_study(path, wallet, budget, seconds, windows):
    wallet = validate_address(wallet)
    budget = budget_amount(budget)
    if type(seconds) is not int or not 1 <= seconds <= 30 or type(windows) is not int or not 1 <= windows <= 10:
        raise ValueError("Choose 1–10 windows of 1–30 seconds each.")
    outcomes = Counter()
    fills, orders = set(), set()
    with path.open("x", encoding="utf-8") as stream:
        def append(kind, **fields):
            stream.write(json.dumps({"type": kind, **fields}, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

        append("plan", schemaVersion=1, version=VERSION, wallet=wallet, **capacity_policy(budget),
               windows=windows, secondsPerWindow=seconds,
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
            outcomes[outcome] += 1
            participant = receipt.get("participant", {})
            if participant.get("status") == "matched":
                fills.add(participant["fillId"])
                orders.add((participant["exchange"], participant["orderHash"]))
        summary = {"windows": windows, "outcomes": dict(outcomes),
                   "distinctParticipantFills": len(fills), "distinctSourceOrders": len(orders)}
        append("summary", **summary)
    return summary
