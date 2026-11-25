"""Measure one prospective public BUY observation and its subsequent displayed book."""

import argparse
import json
import math
import re
import signal
import time
from decimal import Decimal, InvalidOperation
from http.client import HTTPException

from .provider import read_public_json, unpack_page, validate_address


ACTIVITY = "https://data-api.polymarket.com/v2/activity"
BOOK = "https://clob.polymarket.com/book"
LIMIT = 20


def _quantity(value, *, price=False):
    if type(value) not in (Decimal, int, str):
        raise ValueError("Missing numeric field")
    number = Decimal(value)
    if not number.is_finite() or number <= 0 or number.adjusted() > 80 or abs(number.as_tuple().exponent) > 80:
        raise ValueError("Invalid quantity")
    if price and number > 1:
        raise ValueError("Invalid price")
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


def _book(payload, event):
    if not isinstance(payload, dict) or payload.get("asset_id", payload.get("token_id")) != event["tokenId"]:
        raise ValueError("Book token mismatch")
    if str(payload.get("market")).lower() != event["conditionId"]:
        raise ValueError("Book market mismatch")
    timestamp = payload["timestamp"]
    if not isinstance(timestamp, str) or not re.fullmatch(r"[0-9]{13}", timestamp):
        raise ValueError("Missing millisecond book timestamp")
    asks = payload["asks"]
    if not isinstance(asks, list) or any(not isinstance(level, dict) for level in asks):
        raise ValueError("Invalid ask depth")
    levels = [{"price": _quantity(level["price"], price=True), "shares": _quantity(level["size"])}
              for level in asks]
    levels.sort(key=lambda level: Decimal(level["price"]))
    return {"sourceTimeMs": int(timestamp), "askLevelCount": len(levels), "bestAsks": levels[:3]}


def observe(address: str, seconds: int) -> dict:
    """Use one new window and at most two GETs. All clock values are UTC Unix times."""
    address = validate_address(address)
    if type(seconds) is not int or not 1 <= seconds <= 30:
        raise ValueError("Choose an observation window between 1 and 30 seconds.")
    start = math.floor(time.time()) + 1
    end = start + seconds - 1
    result = {
        "schemaVersion": 1, "wallet": address, "windowStartSeconds": start,
        "windowEndSeconds": end, "activitySource": ACTIVITY, "status": "unavailable",
    }
    time.sleep(max(0, end + 1 - time.time()))
    try:
        payload = read_public_json(ACTIVITY, {
            "user": address, "type": "TRADE", "side": "BUY", "sort_direction": "ASC",
            "start": start, "end": end, "exclude_deposits_withdrawals": "false", "limit": LIMIT,
        })
        result["activityReceivedMs"] = time.time_ns() // 1_000_000
        rows, cursor = unpack_page(payload, LIMIT)
        if cursor is not None:
            return dict(result, status="incomplete", reason="Window exceeds the single-page budget.")
        buys = [event for row in rows if (event := _buy(row, address, start, end)) is not None]
        if not buys:
            return dict(result, status="waiting", reason="No ordinary BUY visible in this response. Indexing may lag.")
        event = min(buys, key=lambda e: e["eventTimeSeconds"])
        result.update(event=event, bookSource=BOOK, status="incomplete",
                      identityLimit="Public TRADE rows expose a transaction hash without a per-fill identity.")
        result["bookRequestedMs"] = time.time_ns() // 1_000_000
        payload = read_public_json(BOOK, {"token_id": event["tokenId"]})
        result["bookReceivedMs"] = time.time_ns() // 1_000_000
        book = _book(payload, event)
        result["book"] = book
        if not event["eventTimeSeconds"] * 1000 <= book["sourceTimeMs"] <= result["bookReceivedMs"]:
            return dict(result, reason="Book source time predates the event or exceeds receipt time. Check freshness and clock skew.")
        if not book["bestAsks"]:
            return dict(result, reason="The returned book has no displayed asks.")
        return dict(result, status="observed", reason="Displayed depth only. Fill identity, executable price and fees remain unverified.")
    except (OSError, HTTPException):
        return dict(result, reason="Public endpoint unreachable or denied.")
    except (KeyError, ValueError, InvalidOperation, RecursionError):
        return dict(result, reason="Response shape, identity or time failed validation.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wallet", type=validate_address)
    parser.add_argument("--seconds", type=int, choices=range(1, 31), default=5, metavar="1..30")
    args = parser.parse_args()

    def deadline(*_):
        raise TimeoutError("Observation deadline exceeded")

    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(args.seconds + 12)
    try:
        result = observe(args.wallet, args.seconds)
        print(json.dumps(result, indent=2))
        return 0 if result["status"] in ("observed", "waiting") else 2
    finally:
        signal.alarm(0)


if __name__ == "__main__":
    raise SystemExit(main())
