"""One bounded, on-demand page of Polymarket's public trader leaderboard."""

from datetime import datetime, timezone
from decimal import InvalidOperation
from http.client import HTTPException

from .provider import decimal_value, provider_error, read_public_json, unpack_page, validate_address


ENDPOINT = "https://data-api.polymarket.com/v2/leaderboard"
PAGE_SIZE = 10
PERIODS = ("day", "week", "month", "all")


def _rows(page):
    rows, cursor = unpack_page(page, PAGE_SIZE)
    leaders = []
    seen = set()
    previous_rank = 0
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid leaderboard entry")
        address = validate_address(row["user_id"])
        rank = row["rank"]
        if address in seen or type(rank) is not int or rank < max(1, previous_rank):
            raise ValueError("Ambiguous ranking")
        name = row.get("user_name")
        if name is not None and (not isinstance(name, str) or len(name) > 1000):
            raise ValueError("Invalid profile name")
        seen.add(address)
        previous_rank = rank
        leaders.append({
            "address": address, "name": name or address, "rank": rank,
            "pnl": format(decimal_value(row["pnl"], signed=True), "f"),
            "volumeShares": format(decimal_value(row["volume"]), "f"),
        })
    return leaders, cursor is None


def leaderboard(period: str = "month") -> dict:
    """Return observed ranks intact, including ties. Never mix in local scenarios."""
    if period not in PERIODS:
        raise ValueError("Choose day, week, month, or all.")
    try:
        page = read_public_json(ENDPOINT, {"time_period": period, "sort_by": "PNL", "limit": PAGE_SIZE})
        leaders, complete = _rows(page)
        status = "available"
        message = "Provider-ranked by P/L across all categories, including combos."
        if not complete:
            message += " Showing the first page."
    except (OSError, HTTPException, KeyError, ValueError, InvalidOperation, RecursionError) as error:
        leaders, complete = [], False
        status = "unavailable"
        message = provider_error(error)
    checked = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {
        "period": period, "source": "Polymarket Data API v2 · trader leaderboard",
        "checkedAt": checked, "observedAt": checked if status == "available" else None,
        "status": status, "complete": complete, "message": message, "leaders": leaders,
    }
