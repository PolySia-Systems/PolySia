"""Corroborate one ordinary Data API trade against its owner's Polygon exchange log."""

import json
import re
import time
from decimal import InvalidOperation
from fractions import Fraction
from http.client import HTTPException
from urllib.request import Request

from .provider import decimal_value, read_json_response, units_from_micros

RPC = "https://polygon-bor-rpc.publicnode.com"
# Polygon CTF Exchange V2 deployments, keyed by address with their negative-risk flag.
EXCHANGES = {"0xe111180000d2663c0091e4f400237545b87b996b": False,
             "0xe2222d279d744050d28e00520010520000310f59": True}
ORDER_FILLED = "0xd543adfd945773f1a62f74f0ee55a5e3b9b1a28262980ba90b1a89f2ea84d8ee"
ORDERS_MATCHED = "0x174b3811690657c217184f89418266767c87e4805d09680c39fc9c031c0cab7c"
REPORTED_PRICE_SCALE = 10 ** 10


def _hex(value, pattern):
    if not isinstance(value, str) or not re.fullmatch(pattern, value):
        raise ValueError("Malformed receipt field")
    return value.lower()


def _quantity(value):
    return int(_hex(value, r"0x(?:0|[1-9a-fA-F][0-9a-fA-F]{0,63})"), 16)


def _receipt(tx):
    # Only these two reads can be sent. Scope and provider are fixed in code.
    batch = [{"jsonrpc": "2.0", "id": 1, "method": "eth_chainId", "params": []},
             {"jsonrpc": "2.0", "id": 2, "method": "eth_getTransactionReceipt", "params": [tx]}]
    reply = read_json_response(Request(RPC, data=json.dumps(batch).encode(),
                                       headers={"Content-Type": "application/json"}))
    if not isinstance(reply, list) or len(reply) != 2:
        raise ValueError("Invalid RPC batch")
    results = {}
    for item in reply:
        if (not isinstance(item, dict) or item.get("jsonrpc") != "2.0"
                or type(item.get("id")) is not int or "error" in item):
            raise ValueError("Invalid RPC response")
        results[item["id"]] = item["result"]
    if results.keys() != {1, 2} or results[1] != "0x89":
        raise ValueError("Unexpected chain or response ID")
    return results[2]


def _amount_match_basis(event, role, paid, shares, fee):
    if not 0 < paid <= shares or Fraction(decimal_value(event["shares"])) * 1_000_000 != shares:
        return None
    selling = event.get("side", "BUY") == "SELL"
    if selling and fee > paid:
        return None
    settlement = paid - fee if selling else paid + fee
    reported = event.get("reportedCollateral")
    if reported is not None and Fraction(decimal_value(reported)) * 1_000_000 != settlement:
        return None
    price = Fraction(decimal_value(event["price"]))
    if not 0 < price <= 1:
        return None
    chain_price = Fraction(paid, shares)
    if price == chain_price:
        return "exact-price-and-shares"
    if not selling and role == "taker" and reported is not None:
        # Two paired taker settlements report gross plus the charged fee and a
        # price rounded to ten decimals. Reject ties and off-grid prices.
        scaled = price * REPORTED_PRICE_SCALE
        if scaled.denominator == 1 and abs(scaled - chain_price * REPORTED_PRICE_SCALE) * 2 < 1:
            return "fee-inclusive-collateral-and-rounded-price"
    return None


def _settlement_fields(event, role, paid, shares, fee):
    basis = _amount_match_basis(event, role, paid, shares, fee)
    if not basis or role not in ("maker", "taker"):
        raise ValueError("Participant amounts do not reconcile with the public trade.")
    fields = {"amountMatchBasis": basis}
    if role == "taker":
        selling = event.get("side", "BUY") == "SELL"
        fields.update(grossCollateral=units_from_micros(paid), chargedFee=units_from_micros(fee))
        fields["netProceeds" if selling else "totalCollateral"] = units_from_micros(paid - fee if selling else paid + fee)
    return fields


def verify_retained_amounts(receipt, side):
    participant = receipt.get("participant")
    if not isinstance(participant, dict) or participant.get("status") != "matched":
        return
    event = receipt["event"]
    if event["side"] != side or receipt["schemaVersion"] not in ((4,) if side == "SELL" else (2, 3)):
        raise ValueError("Participant side or receipt version mismatch.")
    amounts = []
    for key in ("collateralBaseUnits", "sharesBaseUnits", "feeBaseUnits"):
        value = participant[key]
        if not isinstance(value, str) or not re.fullmatch(r"0|[1-9][0-9]{0,77}", value) or int(value).bit_length() > 256:
            raise ValueError("Invalid participant base units.")
        amounts.append(int(value))
    expected = _settlement_fields(event, participant["role"], *amounts)
    keys = ("amountMatchBasis", "grossCollateral", "chargedFee", "netProceeds", "totalCollateral")
    if {key: participant[key] for key in keys if key in participant} != expected:
        raise ValueError("Retained participant settlement fields disagree.")


def _match(receipt, wallet, event):
    side_name = event.get("side", "BUY")
    if side_name not in ("BUY", "SELL"):
        raise ValueError("Unsupported trade side")
    selling = side_name == "SELL"
    tx = event["transactionHash"]
    if (not isinstance(receipt, dict) or receipt.get("status") != "0x1"
            or receipt.get("transactionHash") != tx or wallet in EXCHANGES):
        raise ValueError("Missing or unsuccessful participant receipt")
    block = _quantity(receipt["blockNumber"])
    block_hash = _hex(receipt["blockHash"], r"0x[0-9a-fA-F]{64}")
    logs = receipt["logs"]
    if not isinstance(logs, list):
        raise ValueError("Invalid receipt logs")
    by_index = {}
    candidates = []
    owner = "0x" + "0" * 24 + wallet[2:]
    for log in logs:
        if (not isinstance(log, dict) or log.get("removed") is not False
                or log.get("transactionHash") != tx or log.get("blockHash") != block_hash
                or _quantity(log["blockNumber"]) != block):
            raise ValueError("Inconsistent receipt")
        index = _quantity(log["logIndex"])
        if index in by_index:
            raise ValueError("Repeated log index")
        by_index[index] = log
        exchange = _hex(log["address"], r"0x[0-9a-fA-F]{40}")
        topics = log["topics"]
        if not isinstance(topics, list):
            raise ValueError("Invalid topics")
        if exchange not in EXCHANGES or topics[:1] != [ORDER_FILLED]:
            continue
        if len(topics) != 4:
            raise ValueError("Invalid exchange log")
        order = _hex(topics[1], r"0x[0-9a-fA-F]{64}")
        maker, taker = (_hex(topic, r"0x0{24}[0-9a-fA-F]{40}") for topic in topics[2:])
        data = _hex(log["data"], r"0x[0-9a-fA-F]{448}")[2:]
        side, token, making, taking, fee = (int(data[i:i+64], 16) for i in range(0, 320, 64))
        if maker == owner and side == int(selling) and str(token) == event["tokenId"]:
            paid, shares = (taking, making) if selling else (making, taking)
            candidates.append((index, exchange, order, taker, data, paid, shares, fee))

    if len(candidates) != 1:
        return {"status": "unresolved", "reason": f"The receipt did not isolate one {side_name} order for this wallet and token."}
    index, exchange, order, taker, data, paid, shares, fee = candidates[0]
    if taker == owner:
        return {"status": "unresolved", "reason": "The participant was also recorded as its own counterparty."}
    role = "maker"
    counterparty = "0x" + taker[-40:]
    if counterparty == exchange:
        # The taker's OrderFilled and adjacent OrdersMatched represent one action.
        summary = by_index.get(index + 1, {})
        if (summary.get("address") != exchange or summary.get("topics") != [ORDERS_MATCHED, order, owner]
                or summary.get("data") != "0x" + data[:256]):
            return {"status": "unresolved", "reason": "The taker order had no matching settlement summary."}
        role = "taker"
    elif counterparty in EXCHANGES:
        return {"status": "unresolved", "reason": "The counterparty was a different exchange contract."}
    try:
        amounts = _settlement_fields(event, role, paid, shares, fee)
    except ValueError:
        return {"status": "unresolved", "reason": f"The participant amounts did not reconcile with the public {side_name}."}
    return {"status": "matched", "chainId": 137, "blockNumber": block, "blockHash": block_hash,
            "transactionHash": tx, "exchange": exchange, "logIndex": index, "orderHash": order,
            "fillId": f"137:{tx}:{index}", "role": role, "sharesBaseUnits": str(shares),
            "collateralBaseUnits": str(paid), "feeBaseUnits": str(fee), **amounts}


def identify_trade(wallet, event):
    try:
        match = _match(_receipt(event["transactionHash"]), wallet, event)
    except (OSError, HTTPException, KeyError, ValueError, InvalidOperation, RecursionError):
        match = {"status": "unavailable", "reason": "The Polygon receipt was missing, unreachable or inconsistent."}
    return dict(match, source=RPC, checkedMs=time.time_ns() // 1_000_000)


def identify_buy(wallet, event):
    if event.get("side", "BUY") != "BUY":
        raise ValueError("Expected a BUY")
    return identify_trade(wallet, event)
