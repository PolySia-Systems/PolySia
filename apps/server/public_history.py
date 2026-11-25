"""A wallet's reported cumulative realized P/L on a bounded one-week grid."""

from datetime import datetime, timezone
from decimal import InvalidOperation
from http.client import HTTPException

from .provider import decimal_value, provider_error, read_public_json, validate_address


ENDPOINT = "https://data-api.polymarket.com/v2/user-pnl"


def _series(payload, address):
    data = payload["data"]
    if data is None:
        return [], None
    if (not isinstance(data, dict) or validate_address(data["proxy_wallet"]) != address
            or data["interval"] != "1w" or data["fidelity"] != "1d"):
        raise ValueError("Unexpected wallet or observation grid")
    samples = data["points"]
    source_grid = data["source_fidelity"]
    if source_grid not in ("1d", "18h", "12h", "3h", "1h") or not isinstance(samples, list) or len(samples) > 9:
        raise ValueError("Unexpected historical coverage")
    points = []
    previous = 0
    for sample in samples:
        if not isinstance(sample, dict):
            raise ValueError("Invalid P/L observation")
        when = sample["timestamp"]
        if type(when) is not int or not previous < when <= 253402300799:
            raise ValueError("Unexpected sample time")
        value = sample["realized_pnl"]
        points.append({"time": when, "value": None if value is None else format(decimal_value(value, signed=True), "f")})
        previous = when
    return points, source_grid


def pnl_history(address: str) -> dict:
    address = validate_address(address)
    try:
        payload = read_public_json(ENDPOINT, {"user": address, "interval": "1w", "fidelity": "1d"})
        if not isinstance(payload, dict):
            raise ValueError("Missing data envelope")
        points, source_grid = _series(payload, address)
        status, message = "available", "Polymarket cumulative realized P/L."
    except (KeyError, ValueError, OSError, HTTPException, InvalidOperation, RecursionError) as error:
        status, message = "unavailable", provider_error(error)
        points, source_grid = [], None
    return {
        "status": status, "message": message, "address": address, "sourceGrid": source_grid,
        "checkedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "points": points,
    }
