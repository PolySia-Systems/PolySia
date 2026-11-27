"""Public reads from Polygon for Polymarket trading wallets."""

import json
import re
from datetime import datetime, timezone
from http.client import HTTPException
from urllib.request import Request

from .provider import read_json_response, units_from_micros, validate_address

RPC = "https://polygon-bor-rpc.publicnode.com"
PUSD = "0xc011a7e12a19f7b1f670d46f03b03f3342e82dfb"


def _read(method, params):
    batch = [{"jsonrpc": "2.0", "id": 1, "method": "eth_chainId", "params": []},
             {"jsonrpc": "2.0", "id": 2, "method": method, "params": params}]
    reply = read_json_response(Request(RPC, data=json.dumps(batch).encode(),
                                       headers={"Content-Type": "application/json"}))
    if not isinstance(reply, list) or len(reply) != 2:
        raise ValueError("Invalid RPC batch")
    results = {}
    for item in reply:
        if (not isinstance(item, dict) or item.get("jsonrpc") != "2.0"
                or type(item.get("id")) is not int or "error" in item or "result" not in item):
            raise ValueError("Invalid RPC response")
        results[item["id"]] = item["result"]
    if results.keys() != {1, 2} or results[1] != "0x89":
        raise ValueError("Unexpected chain or response ID")
    return results[2]


def transaction_receipt(tx):
    return _read("eth_getTransactionReceipt", [tx])


def cash_balance(address: str) -> dict:
    address = validate_address(address)
    value = None
    try:
        # ERC-20 balanceOf(address), at the official six-decimal Polygon pUSD contract.
        call = {"to": PUSD, "data": "0x70a08231" + address[2:].rjust(64, "0")}
        word = _read("eth_call", [call, "latest"])
        if not isinstance(word, str) or not re.fullmatch(r"0x[0-9a-fA-F]{64}", word):
            raise ValueError("Invalid token balance")
        value = units_from_micros(int(word, 16))
        message = "Open orders may reserve part of this balance."
    except (OSError, HTTPException, ValueError, RecursionError):
        message = "Could not verify the pUSD balance on Polygon. Try again."
    checked = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {"address": address, "status": "available" if value is not None else "unavailable",
            "value": value, "unit": "pUSD", "source": "Polygon · Polymarket pUSD",
            "checkedAt": checked, "observedAt": checked if value is not None else None, "message": message}
