"""Measure delayed book depth and fees for share-limited sales and budgeted entries."""

import re
import time
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from http.client import HTTPException

from .provider import decimal_value, read_public_json, units_from_micros as _units
from .public_fill import EXCHANGES

MARKETS = "https://clob.polymarket.com/clob-markets/"
DELAY_SECONDS = 2
TAKER_DELAY_MS = 250
MAX_RECEIPT_MS = 5000
MAX_SIGNAL_AGE_MS = 10_000
PRICE_ALLOWANCE = 30_000  # micro-pUSD per share from the leader's reported price
SCALE = 1_000_000
MAX_LEVELS = 3
FEE_QUANTUM = 10  # published five-decimal precision, expressed in micro-pUSD


def budget_amount(value):
    if (not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,4}(?:\.[0-9]{1,2})?", value)
            or not 1 <= Decimal(value) <= 1000):
        raise ValueError("Choose a research budget from 1 to 1,000 pUSD with at most two decimal places.")
    return format(Decimal(value), ".2f")


def _micros(value):
    number = Fraction(decimal_value(value)) * SCALE
    if number.denominator != 1:
        raise ValueError("Unsupported base-unit precision")
    return int(number)


def _terms(payload, event):
    if (not isinstance(payload, dict) or payload.get("c") != event["conditionId"]
            or not isinstance(payload.get("t"), list)
            or sum(isinstance(t, dict) and t.get("t") == event["tokenId"] for t in payload["t"]) != 1):
        raise ValueError("Market identity mismatch")
    fee = payload.get("fd")
    if (not isinstance(fee, dict) or fee.get("to") is not True or decimal_value(fee.get("e")) != 1
            or not 0 <= _micros(fee.get("r")) <= SCALE):
        raise ValueError("Unsupported fee schedule")
    minimum, tick = _micros(payload["mos"]), _micros(payload["mts"])
    if (minimum <= 0 or not 0 < tick <= SCALE or type(payload.get("ao")) is not bool
            or ("nr" in payload and type(payload["nr"]) is not bool)
            or type(payload.get("itode", False)) is not bool):
        raise ValueError("Unsupported market constraints")
    return {"takerRate": _units(_micros(fee["r"])), "feeExponent": 1, "takerOnly": True,
            "minimumOrderSize": _units(minimum), "priceTick": _units(tick), "acceptingOrders": payload["ao"],
            "negativeRisk": payload.get("nr"), "takerDelayMs": TAKER_DELAY_MS if payload.get("itode") else 0}


def _level_fee(quantity, price, rate):
    # Fee in micro-pUSD for C shares is C * rate * price * (1 - price).
    numerator = quantity * rate * price * (SCALE - price)
    denominator = SCALE * SCALE * FEE_QUANTUM
    if numerator < denominator:
        return 0
    return ((numerator + denominator - 1) // denominator) * FEE_QUANTUM


def _book_issue(sample, terms, side):
    book = sample.get("book")
    detected = sample["activityReceivedMs"]
    checked = sample["evidenceCheckedMs"]
    eligible_ms = checked + DELAY_SECONDS * 1000 + terms["takerDelayMs"]
    event_ms = sample["event"]["eventTimeSeconds"] * 1000
    if sample["participant"]["status"] != "matched" or not sample["activityCoverage"]["complete"]:
        return {"status": "incomplete", "reason": f"The window needs complete activity coverage and one matched participant {side}."}
    if (not book or not event_ms <= detected <= checked
            or not detected <= sample["participant"]["checkedMs"] <= checked
            or not detected <= sample["market"]["checkedMs"] <= checked
            or not eligible_ms <= sample["bookRequestedMs"] <= sample["bookReceivedMs"]
            or not eligible_ms <= book["sourceTimeMs"] <= sample["bookReceivedMs"] <= checked + MAX_RECEIPT_MS):
        return {"status": "incomplete", "reason": "A timely book update at or after the modeled delay was unavailable."}
    if sample["bookReceivedMs"] - event_ms > MAX_SIGNAL_AGE_MS:
        age = sample["bookReceivedMs"] - event_ms
        return {"status": "skipped", "reason": f"The book arrived {age:,} ms after the {side}. The research limit is {MAX_SIGNAL_AGE_MS:,} ms."}
    if not terms["acceptingOrders"]:
        return {"status": "skipped", "reason": "The market reported that it was closed to orders."}
    exchange_type = EXCHANGES[sample["participant"]["exchange"]]
    if (book["negativeRisk"] is not exchange_type
            or (terms["negativeRisk"] is not None and terms["negativeRisk"] is not exchange_type)):
        return {"status": "incomplete", "reason": "The market, book and Polygon exchange did not agree on the instrument."}
    if book["bidLevelCount"] is None or (book["spreadPerShare"] is not None and Decimal(book["spreadPerShare"]) <= 0):
        return {"status": "incomplete", "reason": "The opposite side of the book was missing or crossed."}
    if (book["minimumOrderShares"] is None or book["priceTick"] is None
            or _micros(book["minimumOrderShares"]) != _micros(terms["minimumOrderSize"])
            or _micros(book["priceTick"]) != _micros(terms["priceTick"])):
        return {"status": "incomplete", "reason": "Book and market size or tick constraints were missing or differed."}

    tick = _micros(terms["priceTick"])
    bid = book["bestBid"]
    if bid is not None:
        bid_price = _micros(bid["price"])
        if not 0 < bid_price < SCALE or bid_price % tick:
            return {"status": "incomplete", "reason": "The displayed best bid was outside the valid price range or off tick."}
    return None


def _estimate(sample, budget, terms):
    issue = _book_issue(sample, terms, "BUY")
    if issue:
        return issue
    book = sample["book"]
    bid = book["bestBid"]
    rate, tick = _micros(terms["takerRate"]), _micros(terms["priceTick"])
    cap = Fraction(sample["event"]["price"]) * SCALE + PRICE_ALLOWANCE
    remaining = _micros(budget)
    total_shares = gross = fees = 0
    previous = 0
    for level in book["bestAsks"]:
        price = _micros(level["price"])
        if price <= previous or price % tick or not 0 < price < SCALE:
            raise ValueError("Unexpected displayed price ladder")
        previous = price
        if price > cap:
            break
        # Gross cost plus the stepped fee is monotone in whole shares. Find
        # the largest displayed quantity whose rounded total fits the budget.
        quantity = 0
        upper = min(remaining // price, _micros(level["shares"]) // SCALE)
        while quantity < upper:
            trial = (quantity + upper + 1) // 2
            if trial * price + _level_fee(trial, price, rate) <= remaining:
                quantity = trial
            else:
                upper = trial - 1
        fee = _level_fee(quantity, price, rate)
        gross += quantity * price
        fees += fee
        remaining -= quantity * price + fee
        total_shares += quantity
    if total_shares * SCALE < _micros(book["minimumOrderShares"]):
        return {"status": "skipped", "reason": "The displayed asks within the price and budget limits could not cover the minimum size."}
    spread_pct = None
    if bid is not None:
        ask_price = _micros(book["bestAsks"][0]["price"])
        hundredths = ((ask_price - _micros(bid["price"])) * 10_000 + ask_price // 2) // ask_price
        spread_pct = f"{hundredths // 100}.{hundredths % 100:02d}"
    return {"status": "estimated", "shares": str(total_shares), "gross": _units(gross),
            "spreadPercentOfAsk": spread_pct,
            "feeEstimate": _units(fees), "unspent": _units(remaining),
            "reason": "Displayed capacity across the retained asks, assuming whole shares and no rebates."}


def market_terms(event):
    source = MARKETS + event["conditionId"]
    try:
        result = {"status": "available", **_terms(read_public_json(source, {}), event)}
    except (OSError, HTTPException, InvalidOperation, KeyError, ValueError, RecursionError):
        result = {"status": "unavailable", "reason": "Market fees or trading constraints were unavailable or unsupported."}
    return dict(result, source=source, checkedMs=time.time_ns() // 1_000_000)


def capacity_policy(budget):
    return {"budget": budget, "asset": "pUSD", "delaySeconds": DELAY_SECONDS,
            "maxReceiptMs": MAX_RECEIPT_MS, "maxSignalAgeMs": MAX_SIGNAL_AGE_MS,
            "bookSourceAfterDelay": True,
            "maxPriceIncrease": _units(PRICE_ALLOWANCE), "maxLevels": MAX_LEVELS, "enabledTakerDelayMs": TAKER_DELAY_MS,
            "feeQuantum": _units(FEE_QUANTUM), "feeRounding": "up per ask level, sub-minimum zero",
            "minimumNotional": None}


def measure_depth(sample, budget):
    policy = capacity_policy(budget)
    terms = sample["market"]
    if terms["status"] != "available":
        return dict(policy, status="incomplete", reason=terms["reason"])
    try:
        return dict(policy, **_estimate(sample, budget, terms))
    except (ValueError, InvalidOperation):
        return dict(policy, status="incomplete", reason="Displayed depth or precision failed validation.")


def sell_scope(condition, token, limit):
    if (not isinstance(condition, str) or not re.fullmatch("0x[0-9a-f]{64}", condition)
            or not isinstance(token, str) or not re.fullmatch("[0-9]{1,78}", token)
            or not isinstance(limit, str) or not re.fullmatch("[1-9][0-9]{0,9}", limit)):
        raise ValueError("Choose a held outcome and a positive whole-share limit.")
    return {"conditionId": condition, "tokenId": token, "maxShares": limit}


def measure_sale(sample):
    """Cap the reduction by the user's limit, the leader's sale and displayed bids."""
    terms, scope = sample["market"], sample["exitScope"]
    if terms["status"] != "available":
        return {"status": "incomplete", "reason": terms["reason"]}
    try:
        issue = _book_issue(sample, terms, "SELL")
        if issue:
            return issue
        book, event = sample["book"], sample["event"]
        bids = book["bestBids"]
        if not bids:
            return {"status": "skipped", "reason": "The book had no displayed bids."}
        if len(bids) > MAX_LEVELS or bids[0] != book["bestBid"]:
            raise ValueError("Inconsistent bids")
        if book["bestAsks"]:
            ask = _micros(book["bestAsks"][0]["price"])
            if not _micros(bids[0]["price"]) < ask < SCALE or ask % _micros(terms["priceTick"]):
                raise ValueError("Invalid opposite price")
        if event["side"] != "SELL" or any(event[k] != scope[k] for k in ("conditionId", "tokenId")):
            raise ValueError("Unexpected outcome")
        if any(not isinstance(event.get(key, ""), str) for key in ("marketTitle", "outcomeLabel")):
            raise ValueError("Invalid market labels")
        price = decimal_value(event["price"])
        source_shares = _micros(event["shares"])
        if not 0 < price <= 1 or str(source_shares) != sample["participant"]["sharesBaseUnits"]:
            raise ValueError("Unreconciled source trade")
        floor_price = Fraction(price) * SCALE - PRICE_ALLOWANCE
        target = min(int(scope["maxShares"]), source_shares // SCALE)
        remaining, gross, fees = target, 0, 0
        previous = SCALE + 1
        tick, rate = _micros(terms["priceTick"]), _micros(terms["takerRate"])
        for level in bids:
            bid = _micros(level["price"])
            if not 0 < bid < min(previous, SCALE) or bid % tick:
                raise ValueError("Invalid bid ladder")
            previous = bid
            if bid < floor_price or not remaining:
                break
            filled = min(remaining, _micros(level["shares"]) // SCALE)
            gross += filled * bid
            fees += _level_fee(filled, bid, rate)
            remaining -= filled
        quantity = target - remaining
        if not quantity or quantity * SCALE < _micros(terms["minimumOrderSize"]):
            return {"status": "skipped", "reason": "The size limit or eligible bids could not cover the minimum sale."}
        if fees > gross:
            raise ValueError("Fees exceed the sale")
        return {"status": "estimated", "targetShares": str(target), "shares": str(quantity),
                "gross": _units(gross), "feeEstimate": _units(fees), "proceeds": _units(gross-fees),
                "reason": "Estimated sale against delayed displayed bids."}
    except (ValueError, ArithmeticError):
        return {"status": "incomplete", "reason": "The sale price, size or fee data could not be reconciled."}
