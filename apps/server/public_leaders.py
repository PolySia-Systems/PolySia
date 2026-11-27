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
    return leaders, cursor


def leaderboard(period: str = "month", cursor: str | None = None) -> dict:
    """Return observed ranks intact, including ties. Never mix in local scenarios."""
    if period not in PERIODS:
        raise ValueError("Choose day, week, month, or all.")
    if cursor is not None and (not isinstance(cursor, str) or not 0 < len(cursor) <= 4096):
        raise ValueError("Invalid ranking page. Refresh the rankings.")
    params = {"time_period": period, "sort_by": "PNL"}
    if cursor is None:
        params["limit"] = PAGE_SIZE
    else:
        params["cursor"] = cursor
    try:
        leaders, next_cursor = _rows(read_public_json(ENDPOINT, params))
        if cursor is not None and next_cursor == cursor:
            raise ValueError("Ranking cursor did not advance")
        complete = next_cursor is None
        status = "available"
        message = "Provider-ranked by P/L across all categories, including combos."
    except (OSError, HTTPException, KeyError, ValueError, InvalidOperation, RecursionError) as error:
        leaders, next_cursor, complete = [], None, False
        status = "unavailable"
        message = provider_error(error)
    checked = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {
        "period": period, "source": "Polymarket Data API v2 · trader leaderboard",
        "checkedAt": checked, "observedAt": checked if status == "available" else None,
        "status": status, "complete": complete, "nextCursor": next_cursor, "message": message, "leaders": leaders,
    }
