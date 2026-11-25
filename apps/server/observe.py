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
    return {
        "eventTimeSeconds": timestamp, "conditionId": row["condition_id"].lower(),
        "tokenId": token, "transactionHash": row["transaction_hash"].lower(),
        "price": _quantity(row["price"], price=True), "shares": _quantity(row["size"]),
        "fillId": None, "side": "BUY",
    }


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


def observe(address: str, seconds: int, index_wait_seconds: int = 0, *, budget: str | None = None) -> dict:
    """Sample one new window. A research budget enables a delayed book and corroborating reads."""
    address = validate_address(address)
    if type(seconds) is not int or not 1 <= seconds <= 30:
        raise ValueError("Choose an observation window between 1 and 30 seconds.")
    if type(index_wait_seconds) is not int or not 0 <= index_wait_seconds <= 300:
        raise ValueError("Choose an indexing wait between 0 and 300 seconds.")
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
    time.sleep(max(0, end + 1 + index_wait_seconds - time.time()))
    try:
        payload = read_public_json(ACTIVITY, {
            "user": address, "type": "TRADE", "side": "BUY", "sort_direction": "ASC",
            "start": start, "end": end, "exclude_deposits_withdrawals": "false", "limit": LIMIT,
        })
        result["activityReceivedMs"] = time.time_ns() // 1_000_000
        rows, cursor = unpack_page(payload, LIMIT)
        buys = [event for row in rows if (event := _buy(row, address, start, end)) is not None]
        # Page completeness and evidence for one visible BUY answer different
        # questions. Never chase pagination during the sampling window.
        result["activityCoverage"] = {"rowsReturned": len(rows), "complete": cursor is None,
                                      "ordinaryBuyRows": len(buys)}
        if not buys and cursor is not None:
            return dict(result, status="incomplete", reason="No ordinary BUY on the first page; later rows were not read.")
        if not buys:
            return dict(result, status="waiting", reason="No ordinary BUY visible in this response. Indexing may lag.")
        event = min(buys, key=lambda e: e["eventTimeSeconds"])
        result.update(event=event, bookSource=BOOK, status="incomplete",
                      identityLimit="Public TRADE rows expose a transaction hash without a per-fill identity.")
    except (OSError, HTTPException):
        return dict(result, reason="Public endpoint unreachable or denied.")
    except (KeyError, ValueError, InvalidOperation, RecursionError):
        return dict(result, reason="Response shape, identity or time failed validation.")

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
    time.sleep(public_depth.DELAY_SECONDS)
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


def sample_once(address, seconds, budget=None):
    """Run one bounded observation in a disposable process from source or the installed release."""
    command = [sys.executable, "-B", "-m", "apps.server.observe", address, "--seconds", str(seconds)]
    if budget is not None:
        command.extend(["--budget", budget])
    try:
        child = subprocess.run(command, cwd=Path(__file__).resolve().parents[2],
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               timeout=seconds + (30 if budget else 15), check=False)
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
    args = parser.parse_args()

    # Socket timeouts alone cannot bound a slow stream. The CLI is a disposable
    # child of the HTTP server and owns no persistent state.
    deadline = Timer(args.seconds + args.index_wait + (25 if args.budget else 12), os._exit, args=(124,))
    deadline.daemon = True
    deadline.start()
    try:
        result = observe(args.wallet, args.seconds, args.index_wait, budget=args.budget)
        print(json.dumps(result, indent=2))
        complete = result["status"] in ("observed", "waiting") and result.get("capacity", {}).get("status") != "incomplete"
        return 0 if complete else 2
    finally:
        deadline.cancel()


if __name__ == "__main__":
    raise SystemExit(main())
