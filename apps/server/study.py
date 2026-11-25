"""Record a predeclared, finite series of public observation windows as JSON Lines."""

from collections import Counter
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from . import VERSION
from .observe import ACTIVITY, RETRY_AFTER_WINDOW_MS, read_buy_page, sample_once
from .public_depth import budget_amount, capacity_policy
from .provider import validate_address


REFERENCE_TIMEOUT_SECONDS = 12


def _reference_page(wallet, start, end):
    # A socket timeout only bounds individual reads. A disposable child also
    # bounds a slow stream and leaves the study writer free to record failure.
    child = subprocess.run([sys.executable, "-B", "-m", "apps.server.study", wallet, str(start), str(end)],
                           cwd=Path(__file__).resolve().parents[2], stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL, timeout=REFERENCE_TIMEOUT_SECONDS, check=True)
    return json.loads(child.stdout)


def _recheck_activity(wallet, receipt):
    start, end = receipt.get("windowStartSeconds"), receipt.get("windowEndSeconds")
    result = {"windowStartSeconds": start, "windowEndSeconds": end, "activitySource": ACTIVITY,
              "checkedMs": time.time_ns() // 1_000_000}
    if start is None or end is None:
        return dict(result, reason="The original process did not return window bounds.")
    try:
        buys, coverage, received = _reference_page(wallet, start, end)
        return dict(result, activityCoverage=coverage, activityReceivedMs=received, visibleBuys=buys)
    except (OSError, ValueError, subprocess.SubprocessError):
        return dict(result, reason="The activity recheck was unavailable or failed validation.")


def _initially_empty(receipt):
    reads = receipt.get("activityReads", [])
    if not reads or "reason" in reads[0]:
        return False
    coverage = reads[0].get("activityCoverage", {})
    return coverage.get("complete") is True and coverage.get("ordinaryBuyRows") == 0


def _retry_summary(receipts):
    reads = [receipt.get("activityReads", []) for receipt in receipts]
    followups = [window[1] for window in reads if len(window) == 2]
    valid_coverage = [read["activityCoverage"] for read in followups
                      if "activityCoverage" in read and "reason" not in read]
    second_detections = [receipt for receipt in receipts if receipt.get("detectionRead") == 2]
    return {
        "firstReadDetections": sum(receipt.get("detectionRead") == 1 for receipt in receipts),
        "initiallyEmptyWindows": sum(_initially_empty(receipt) for receipt in receipts),
        "retriesAttempted": len(followups),
        "secondReadDetections": len(second_detections),
        "secondReadCapacityEstimates": sum(receipt.get("capacity", {}).get("status") == "estimated"
                                          for receipt in second_detections),
        "secondReadsUnavailable": len(followups) - len(valid_coverage),
        "secondReadsPartial": sum(not coverage["complete"] for coverage in valid_coverage),
        "windowsWithoutReadEvidence": sum(not window for window in reads),
    }


def record_study(path, wallet, budget, seconds, windows, *, recheck_after=0, retry_empty=False):
    wallet = validate_address(wallet)
    budget = budget_amount(budget)
    if type(seconds) is not int or not 1 <= seconds <= 30 or type(windows) is not int or not 1 <= windows <= 10:
        raise ValueError("Choose 1–10 windows of 1–30 seconds each.")
    if type(recheck_after) is not int or not 0 <= recheck_after <= 300:
        raise ValueError("Choose an activity recheck delay between 0 and 300 seconds.")
    if type(retry_empty) is not bool or (retry_empty and seconds != 2):
        raise ValueError("Use --seconds 2 for a study with --retry-empty.")
    receipts = []
    outcomes = Counter()
    fills, orders = set(), set()
    with path.open("x", encoding="utf-8") as stream:
        def append(kind, **fields):
            stream.write(json.dumps({"type": kind, **fields}, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

        policy = {"retryEmpty": True, "retryAfterWindowMs": RETRY_AFTER_WINDOW_MS,
                  "maxActivityReadsPerWindow": 2} if retry_empty else {}
        append("plan", schemaVersion=3 if retry_empty else 2, version=VERSION, wallet=wallet,
               **capacity_policy(budget), **policy,
               windows=windows, secondsPerWindow=seconds, recheckAfterSeriesSeconds=recheck_after,
               selection="Earliest ordinary BUY on the returned page. Provider order breaks time ties.")
        for index in range(1, windows + 1):
            append("attempt", number=index, startedMs=time.time_ns() // 1_000_000)
            try:
                receipt = sample_once(wallet, seconds, budget, retry_empty=retry_empty)
            except (OSError, ValueError):
                receipt = {"wallet": wallet, "status": "unavailable",
                           "reason": "The sampling process failed to return a receipt within its deadline."}
            outcome = receipt.get("capacity", {}).get("status", receipt["status"])
            append("window", number=index, outcome=outcome, receipt=receipt)
            receipts.append(receipt)
            outcomes[outcome] += 1
            participant = receipt.get("participant", {})
            if participant.get("status") == "matched":
                fills.add(participant["fillId"])
                orders.add((participant["exchange"], participant["orderHash"]))
        summary = {"windows": windows, "outcomes": dict(outcomes),
                   "distinctParticipantFills": len(fills), "distinctSourceOrders": len(orders)}
        if retry_empty:
            summary.update(_retry_summary(receipts))
        if recheck_after:
            time.sleep(recheck_after)
            comparable = later_positive = 0
            for index, receipt in enumerate(receipts, 1):
                result = _recheck_activity(wallet, receipt)
                append("activityRecheck", number=index, **result)
                initially_empty = _initially_empty(receipt) if retry_empty else receipt["status"] == "waiting"
                if initially_empty and "activityCoverage" in result:
                    positive = bool(result["visibleBuys"])
                    if positive or result["activityCoverage"]["complete"]:
                        comparable += 1
                        later_positive += positive
            group = "initiallyEmptyWindows" if retry_empty else "waitingWindows"
            summary[group + "Compared"] = comparable
            summary[group + "WithLaterBuy"] = later_positive
        append("summary", **summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Read one public activity page for a completed study window.")
    parser.add_argument("wallet", type=validate_address)
    parser.add_argument("start", type=int)
    parser.add_argument("end", type=int)
    args = parser.parse_args()
    print(json.dumps(read_buy_page(args.wallet, args.start, args.end), allow_nan=False))
