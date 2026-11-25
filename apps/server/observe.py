"""Measure one prospective public BUY observation and its subsequent displayed book."""

import argparse
import json
import math
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal, InvalidOperation, localcontext
from http.client import HTTPException
from pathlib import Path
from threading import Timer

from . import public_depth, public_fill
from .provider import decimal_value, read_public_json, unpack_page, validate_address


ACTIVITY = "https://data-api.polymarket.com/v2/activity"
BOOK = "https://clob.polymarket.com/book"
LIMIT = 20
RETRY_AFTER_WINDOW_MS = 3000
# Allow the scheduled wait and one additional socket timeout in the child and parent deadlines.
RETRY_TIMEOUT_SECONDS = 7


def _quantity(value, *, price=False):
    number = decimal_value(value)
    if number == 0 or (price and number > 1):
        raise ValueError("Invalid quantity or price")
    return format(number, "f")


def _buy(row, address, start, end):
    if not isinstance(row, dict) or validate_address(row.get("proxy_wallet")) != address:
        raise ValueError("Wallet mismatch")
    if row.get("type") != "TRADE" or row.get("side") != "BUY":
        raise ValueError("Unexpected activity")
    timestamp = row.get("timestamp")
    if type(timestamp) is not int or not start <= timestamp <= end:
        raise ValueError("Activity outside the requested UTC window")
    if row.get("is_combo") is True:
        return None
    if row.get("is_combo", False) is not False:
        raise ValueError("Ambiguous instrument")
    token = row["token_id"]
    if not isinstance(token, str) or not re.fullmatch(r"[0-9]{1,78}", token):
        raise ValueError("Invalid outcome token")
    for key in ("condition_id", "transaction_hash"):
        if not isinstance(row[key], str) or not re.fullmatch(r"0x[0-9a-fA-F]{64}", row[key]):
            raise ValueError("Invalid activity reference")
    event = {
        "eventTimeSeconds": timestamp, "conditionId": row["condition_id"].lower(),
        "tokenId": token, "transactionHash": row["transaction_hash"].lower(),
        "price": _quantity(row["price"], price=True), "shares": _quantity(row["size"]),
        "fillId": None, "side": "BUY",
    }
    for source, field in (("title", "marketTitle"), ("outcome", "outcomeLabel")):
        label = row.get(source)
        if isinstance(label, str) and 0 < len(label) <= 1000 and label.strip():
            event[field] = label.strip()
    return event


def _levels(rows):
    if not isinstance(rows, list) or any(not isinstance(level, dict) for level in rows):
        raise ValueError("Invalid book depth")
    return [{"price": _quantity(level["price"], price=True), "shares": _quantity(level["size"])} for level in rows]


def _book(payload, event):
    if not isinstance(payload, dict) or payload.get("asset_id", payload.get("token_id")) != event["tokenId"]:
        raise ValueError("Book token mismatch")
    if str(payload.get("market")).lower() != event["conditionId"]:
        raise ValueError("Book market mismatch")
    timestamp = payload["timestamp"]
    if not isinstance(timestamp, str) or not re.fullmatch(r"[0-9]{13}", timestamp):
        raise ValueError("Missing millisecond book timestamp")
    levels = sorted(_levels(payload["asks"]), key=lambda level: Decimal(level["price"]))
    bids = _levels(payload["bids"]) if "bids" in payload else None
    best_bid = max(bids or [], key=lambda level: Decimal(level["price"]), default=None)
    with localcontext() as arithmetic:
        arithmetic.prec = 81
        spread = format(Decimal(levels[0]["price"]) - Decimal(best_bid["price"]), "f") if levels and best_bid else None
    return {
        "sourceTimeMs": int(timestamp), "askLevelCount": len(levels), "bestAsks": levels[:public_depth.MAX_LEVELS],
        "bestBid": best_bid, "bidLevelCount": len(bids) if bids is not None else None,
        "spreadPerShare": spread, "negativeRisk": payload.get("neg_risk") if type(payload.get("neg_risk")) is bool else None,
        "minimumOrderShares": _quantity(payload["min_order_size"]) if "min_order_size" in payload else None,
        "priceTick": _quantity(payload["tick_size"], price=True) if "tick_size" in payload else None,
    }


def read_buy_page(address, start, end):
    payload = read_public_json(ACTIVITY, {
        "user": address, "type": "TRADE", "side": "BUY", "sort_direction": "ASC",
        "start": start, "end": end, "exclude_deposits_withdrawals": "false", "limit": LIMIT,
    })
    received = time.time_ns() // 1_000_000
    rows, cursor = unpack_page(payload, LIMIT)
    buys = [event for row in rows if (event := _buy(row, address, start, end)) is not None]
    return buys, {"rowsReturned": len(rows), "complete": cursor is None, "ordinaryBuyRows": len(buys)}, received


def _validate_retry(retry_empty, seconds, budget, index_wait=0):
    if type(retry_empty) is not bool:
        raise ValueError("The second activity read must be enabled with true or false.")
    if retry_empty and (seconds != 2 or budget is None or index_wait != 0):
        raise ValueError("The second activity read requires a two-second window, a budget and no indexing wait.")


def _can_still_sample(event_second, now_ms):
    return now_ms + public_depth.DELAY_SECONDS * 1000 <= event_second * 1000 + public_depth.MAX_SIGNAL_AGE_MS


def _detect_buys(result, retry_empty):
    start, end = result["windowStartSeconds"], result["windowEndSeconds"]
    close_ms = (end + 1) * 1000
    last_read = 2 if retry_empty else 1
    for number in range(1, last_read + 1):
        earliest_ms = close_ms
        if number == 2:
            scheduled_ms = close_ms + RETRY_AFTER_WINDOW_MS
            now = time.time_ns() // 1_000_000
            if now < result["activityReceivedMs"]:
                result.update(status="incomplete", reason="Local clock moved backward after the first activity read.")
                return []
            if now < scheduled_ms:
                time.sleep((scheduled_ms - now) / 1000)
            earliest_ms = max(scheduled_ms, result["activityReceivedMs"])
        requested = time.time_ns() // 1_000_000
        if retry_empty and requested < earliest_ms:
            result.update(status="incomplete", reason="Local clock moved before the activity read was due.")
            return []
        if number == 2 and not _can_still_sample(end, requested):
            result.update(status="incomplete", reason="The second read was skipped. Even the latest BUY in the window "
                          "could no longer meet the age limit after the modeled delay.")
            return []
        attempt = {"requestedMs": requested}
        if retry_empty:
            result["activityReads"].append(attempt)
        try:
            buys, coverage, received = read_buy_page(result["wallet"], start, end)
        except (OSError, HTTPException):
            attempt["reason"] = "Public endpoint unreachable or denied."
        except (KeyError, ValueError, InvalidOperation, RecursionError):
            attempt["reason"] = "Response shape, identity or time failed validation."
        if "reason" in attempt:
            # The final read failed. Its predecessor's coverage remains in the read history.
            result.pop("activityCoverage", None)
            result.pop("activityReceivedMs", None)
            result["reason"] = attempt["reason"]
            return []
        attempt.update(activityCoverage=coverage, receivedMs=received)
        result.update(activityCoverage=coverage, activityReceivedMs=received)
        if retry_empty and received < requested:
            attempt["reason"] = "Local activity receipt time preceded its request."
            result.update(status="incomplete", reason=attempt["reason"])
            return []
        if buys:
            if retry_empty:
                result["detectionRead"] = number
            return buys
        if not coverage["complete"]:
            result.update(status="incomplete", reason="No ordinary BUY on the first page; later rows were not read.")
            return []
    reason = ("Neither activity read showed an ordinary BUY. Indexing may lag." if retry_empty else
              "No ordinary BUY visible in this response. Indexing may lag.")
    result.update(status="waiting", reason=reason)
    return []


def observe(address: str, seconds: int, index_wait_seconds: int = 0, *, budget: str | None = None,
            retry_empty: bool = False) -> dict:
    """Sample one new window. A research budget enables a delayed book and corroborating reads."""
    address = validate_address(address)
    if type(seconds) is not int or not 1 <= seconds <= 30:
        raise ValueError("Choose an observation window between 1 and 30 seconds.")
    if type(index_wait_seconds) is not int or not 0 <= index_wait_seconds <= 300:
        raise ValueError("Choose an indexing wait between 0 and 300 seconds.")
    _validate_retry(retry_empty, seconds, budget, index_wait_seconds)
    if budget is not None:
        budget = public_depth.budget_amount(budget)
    start = math.floor(time.time()) + 1
    end = start + seconds - 1
    result = {
        "schemaVersion": 1, "wallet": address, "windowStartSeconds": start,
        "windowEndSeconds": end, "indexWaitSeconds": index_wait_seconds,
        "activitySource": ACTIVITY, "status": "unavailable",
    }
    if budget is not None:
        result.update(schemaVersion=2, researchBudget=budget, asset="pUSD",
                      delaySeconds=public_depth.DELAY_SECONDS)
    if retry_empty:
        result.update(schemaVersion=3, retryAfterWindowMs=RETRY_AFTER_WINDOW_MS, activityReads=[])
    time.sleep(max(0, end + 1 + index_wait_seconds - time.time()))
    buys = _detect_buys(result, retry_empty)
    if not buys:
        return result
    event = min(buys, key=lambda e: e["eventTimeSeconds"])
    result.update(event=event, status="incomplete",
                  identityLimit="Public TRADE rows expose a transaction hash without a per-fill identity.")
    if retry_empty and not _can_still_sample(event["eventTimeSeconds"], result["activityReceivedMs"]):
        reason = "The BUY was detected too late to sample its book within the age limit after the modeled delay."
        result.update(reason=reason, capacity=dict(public_depth.capacity_policy(budget), status="skipped", reason=reason))
        return result
    result["bookSource"] = BOOK

    if budget is None:
        return _sample_book(result, event)

    # Read independent prerequisites concurrently, then start the follower clock.
    # Still sample depth on an unresolved BUY so failed windows retain evidence.
    with ThreadPoolExecutor(max_workers=1) as worker:
        terms = worker.submit(public_depth.market_terms, event)
        same_order_scope = sum(b["transactionHash"] == event["transactionHash"] and b["tokenId"] == event["tokenId"]
                               for b in buys)
        result["participant"] = (
            {"status": "unresolved", "reason": "Several public BUY rows shared the transaction and outcome."}
            if same_order_scope > 1 else public_fill.identify_buy(address, event)
        )
        result["market"] = terms.result()
    result["evidenceCheckedMs"] = time.time_ns() // 1_000_000
    time.sleep(public_depth.DELAY_SECONDS + result["market"].get("takerDelayMs", 0) / 1000)
    result = _sample_book(result, event)
    result["capacity"] = public_depth.measure_depth(result, budget)
    return result


def _sample_book(result, event):
    try:
        result["bookRequestedMs"] = time.time_ns() // 1_000_000
        payload = read_public_json(BOOK, {"token_id": event["tokenId"]})
        result["bookReceivedMs"] = time.time_ns() // 1_000_000
        book = _book(payload, event)
        book["sourceAgeAtDetectionMs"] = result["activityReceivedMs"] - book["sourceTimeMs"]
        # Both validated probabilities are in (0, 1] with at most 80 decimal places.
        with localcontext() as arithmetic:
            arithmetic.prec = 81
            book["bestAskMinusLeaderPrice"] = (
                format(Decimal(book["bestAsks"][0]["price"]) - Decimal(event["price"]), "f")
                if book["bestAsks"] else None
            )
        result["book"] = book
        if not event["eventTimeSeconds"] * 1000 <= result["activityReceivedMs"] <= result["bookRequestedMs"] <= result["bookReceivedMs"]:
            return dict(result, reason="Local sampling times are inconsistent. Check clock synchronization.")
        if not result["activityReceivedMs"] <= book["sourceTimeMs"] <= result["bookReceivedMs"]:
            return dict(result, reason="Book timestamp falls outside the interval from detection to receipt. Post-detection depth is unverified.")
        if not book["bestAsks"]:
            return dict(result, reason="The returned book has no displayed asks.")
        if book["spreadPerShare"] is not None and Decimal(book["spreadPerShare"]) <= 0:
            return dict(result, reason="The displayed bids and asks overlapped. The quote is inconsistent.")
        if not result["activityCoverage"]["complete"]:
            return dict(result, reason="A BUY on the first page had a matching displayed book. The full activity window was not read.")
        return dict(result, status="observed", reason="A matching book update arrived after detection. Displayed asks can change before execution.")
    except (OSError, HTTPException):
        return dict(result, reason="Public endpoint unreachable or denied.")
    except (KeyError, ValueError, InvalidOperation, RecursionError):
        return dict(result, reason="Response shape, identity or time failed validation.")


def sample_once(address, seconds, budget=None, *, retry_empty=False):
    """Run one bounded observation in a disposable process from source or the installed release."""
    command = [sys.executable, "-B", "-m", "apps.server.observe", address, "--seconds", str(seconds)]
    _validate_retry(retry_empty, seconds, budget)
    if budget is not None:
        command.extend(["--budget", budget])
    if retry_empty:
        command.append("--retry-empty")
    timeout = seconds + (30 if budget else 15) + (RETRY_TIMEOUT_SECONDS if retry_empty else 0)
    try:
        child = subprocess.run(command, cwd=Path(__file__).resolve().parents[2],
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        raise TimeoutError("Observation timed out. Try another window.") from None
    if child.returncode == 124:
        raise TimeoutError("Observation deadline reached. Try another window.")
    if child.returncode not in (0, 2) or not child.stdout:
        raise OSError("The public observation could not complete. Try a new window.")
    return json.loads(child.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wallet", type=validate_address)
    parser.add_argument("--seconds", type=int, choices=range(1, 31), default=5, metavar="1..30")
    parser.add_argument("--index-wait", type=int, choices=range(301), default=0, metavar="0..300",
                        help="Wait after the predeclared window before reading potentially delayed activity.")
    parser.add_argument("--budget", type=public_depth.budget_amount, metavar="pUSD",
                        help="Measure displayed capacity for this unfunded research budget at a two-second delay.")
    parser.add_argument("--retry-empty", action="store_true",
                        help="Reread an initially empty two-second budgeted window three seconds after it closes.")
    args = parser.parse_args()
    try:
        _validate_retry(args.retry_empty, args.seconds, args.budget, args.index_wait)
    except ValueError as error:
        parser.error(str(error))

    # Socket timeouts alone cannot bound a slow stream. The CLI is a disposable
    # child of the HTTP server and owns no persistent state.
    timeout = args.seconds + args.index_wait + (25 if args.budget else 12)
    deadline = Timer(timeout + (RETRY_TIMEOUT_SECONDS if args.retry_empty else 0), os._exit, args=(124,))
    deadline.daemon = True
    deadline.start()
    try:
        result = observe(args.wallet, args.seconds, args.index_wait, budget=args.budget, retry_empty=args.retry_empty)
        print(json.dumps(result, indent=2))
        complete = result["status"] in ("observed", "waiting") and result.get("capacity", {}).get("status") != "incomplete"
        return 0 if complete else 2
    finally:
        deadline.cancel()


if __name__ == "__main__":
    raise SystemExit(main())
