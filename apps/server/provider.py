"""Public Polymarket position reads. This module needs only a wallet address."""

import json
import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from http.client import HTTPException
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from . import VERSION


POSITIONS_ENDPOINT = "https://data-api.polymarket.com/v2/positions"
VALUE_ENDPOINT = "https://data-api.polymarket.com/v2/value"
SOURCE = "Polymarket Data API v2 · open positions"
PAGE_SIZE = 20
USER_AGENT = f"PolySia/{VERSION} (+https://github.com/PolySia-Systems/PolySia)"
MAX_BODY_BYTES = 256 * 1024


def validate_address(address: str) -> str:
    if not isinstance(address, str) or not re.fullmatch(r"0x[0-9a-fA-F]{40}", address.strip()):
        raise ValueError("Enter a public wallet address starting with 0x followed by 40 hex characters.")
    return address.strip().lower()


class _FixedOrigin(HTTPRedirectHandler):
    """A public lookup should send the wallet address only to the selected origin."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def read_public_json(endpoint: str, params: dict) -> dict:
    query = urlencode(params)
    request = Request(f"{endpoint}?{query}" if query else endpoint)
    return read_json_response(request)


def read_json_response(request: Request) -> dict:
    request.add_header("Accept", "application/json")
    request.add_header("User-Agent", USER_AGENT)
    with build_opener(_FixedOrigin()).open(request, timeout=4) as response:
        body = response.read(MAX_BODY_BYTES + 1)
    if len(body) > MAX_BODY_BYTES:
        raise ValueError("Response too large")
    return json.loads(body, parse_float=Decimal)


def _read_page(address: str) -> dict:
    return read_public_json(POSITIONS_ENDPOINT, {"user": address, "status": "OPEN", "limit": PAGE_SIZE})


def _optional_label(value: object, fallback: str) -> str:
    if value is None or value == "":
        return fallback
    if not isinstance(value, str) or len(value) > 1000:
        raise ValueError("Unexpected label")
    return value


def decimal_value(value: object, *, signed: bool = False) -> Decimal:
    if type(value) not in (Decimal, int, str):
        raise ValueError("Invalid public numeric field")
    number = Decimal(value)
    if (not number.is_finite() or (not signed and number < 0)
            or abs(number.as_tuple().exponent) > 80 or number.adjusted() > 80):
        raise ValueError("Invalid public numeric field")
    return number


def units_from_micros(micros: int) -> str:
    """Format a nonnegative base-unit quantity for JSON without binary rounding."""
    whole, fraction = divmod(micros, 1_000_000)
    return f"{whole}.{fraction:06d}".rstrip("0").rstrip(".")


def unpack_page(payload: object, limit: int) -> tuple[list, str | None]:
    if not isinstance(payload, dict):
        raise ValueError("Missing v2 envelope")
    rows = payload.get("data")
    page = payload.get("pagination")
    if not isinstance(rows, list) or len(rows) > limit or not isinstance(page, dict):
        raise ValueError("Invalid data page")
    cursor = page["next_cursor"]
    if cursor is not None and (not isinstance(cursor, str) or not 0 < len(cursor) <= 4096):
        raise ValueError("Invalid page cursor")
    if page.get("has_more") is not (cursor is not None):
        raise ValueError("Inconsistent pagination")

    return rows, cursor


def market_end_date(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return None


def _positions(payload: object, address: str) -> tuple[list[dict], str | None]:
    rows, cursor = unpack_page(payload, PAGE_SIZE)
    positions = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or validate_address(row.get("proxy_wallet")) != address:
            raise ValueError("Position belongs to an unexpected address")
        token = row["token_id"]
        condition = row["condition_id"]
        if not isinstance(token, str) or not re.fullmatch(r"[0-9]{1,78}", token):
            raise ValueError("Invalid token identity")
        if not isinstance(condition, str) or not re.fullmatch(r"0x[0-9a-fA-F]{64}", condition):
            raise ValueError("Invalid market identity")
        if token in seen or row.get("status") not in ("OPEN", "REDEEMABLE"):
            raise ValueError("Unexpected position identity or status")
        seen.add(token)
        positions.append({
            "conditionId": condition.lower(),
            "market": _optional_label(row.get("title"), condition),
            "outcome": _optional_label(row.get("outcome"), "Outcome unavailable"),
            "shares": format(decimal_value(row["current_size"]), "f"),
            "status": row["status"],
        })
        end = market_end_date(row.get("end_date"))
        if end:
            positions[-1]["endDate"] = end
    return positions, cursor


def provider_error(error: Exception) -> str:
    if isinstance(error, HTTPError):
        status = error.code
        error.close()
        if status == 429:
            return "Polymarket rate-limited this lookup. Try again later."
        if status == 403:
            return "Polymarket denied this public lookup (HTTP 403). Check access before refreshing."
        return f"Polymarket returned HTTP {status}. The requested public data is unavailable."
    if isinstance(error, (OSError, HTTPException)):
        return "Could not reach Polymarket. Check access to data-api.polymarket.com and refresh."
    return "The response did not match the supported provider contract."


def inspect_account(address: str) -> dict:
    """Inspect one bounded, explicit snapshot. A failed lookup never fabricates holdings."""
    address = validate_address(address)
    positions, cursor = [], None
    available = False
    try:
        positions, cursor = _positions(_read_page(address), address)
        available = True
        if cursor is not None:
            message = "More open positions exist. This snapshot shows the first page."
        elif not positions:
            message = "Polymarket returned no open ordinary positions for this address."
        else:
            message = "Open ordinary positions reported by Polymarket."
    except (OSError, HTTPException, KeyError, ValueError, InvalidOperation, RecursionError) as error:
        message = provider_error(error)
    checked = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {
        "address": address, "status": "available" if available else "unavailable",
        "source": SOURCE, "checkedAt": checked, "observedAt": checked if available else None,
        "message": message, "positions": positions, "complete": available and cursor is None,
        "nextCursor": cursor,
    }


def holdings_value(address: str) -> dict:
    """Read the provider's unfiltered wallet aggregate independently of the positions page."""
    address = validate_address(address)
    value = None
    try:
        payload = read_public_json(VALUE_ENDPOINT, {"user": address})
        if not isinstance(payload, dict) or "pagination" in payload or not isinstance(payload.get("data"), dict):
            raise ValueError("Expected one aggregate")
        data = payload["data"]
        if validate_address(data["proxy_wallet"]) != address:
            raise ValueError("Unexpected portfolio wallet")
        amount = decimal_value(data["value"])
        if 10_000 % amount.as_integer_ratio()[1]:
            raise ValueError("Unsupported holdings precision")
        value = format(amount, "f")
        message = ("Polymarket marks single-market holdings to market and values unresolved combos at cost. "
                   "Cash and trading fees for a possible sale are outside this estimate.")
    except (KeyError, ValueError, OSError, HTTPException, InvalidOperation, RecursionError) as error:
        message = provider_error(error)
    checked = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {
        "address": address, "status": "available" if value is not None else "unavailable",
        "source": "Polymarket Data API v2 · portfolio value", "value": value, "unit": "USDC",
        "checkedAt": checked, "observedAt": checked if value is not None else None, "message": message,
    }
