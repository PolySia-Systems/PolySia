"""Deterministic, user-stepped training tape. Contains no external execution adapter."""
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import re

START = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)
SCENARIO = "order-book-workshop/1"
LIMITS = {"min_allocation": "1.00", "max_allocation": "10000.00",
          "min_order_size": "1.00", "max_order_size": "1000.00"}
POLICY = {"version": 1, "fee_bps": 100, "delay_seconds": 2,
          "max_age_seconds": 10, "max_slippage_cents": 3, "lot_shares": 1}

# The period series depicts synthetic cumulative P/L (USD). Volume, resolved-market
# counts and wins are independent sample facts, not estimated from the P/L series.
@dataclass(frozen=True)
class Profile:
    id: str
    name: str
    category: str
    description: str
    market: str
    color: str
    volume: int
    markets: int
    wins: int
    anchor_cents: int
    history: tuple[int, ...]


PROFILES = (
    Profile("atlas", "Atlas Meridian", "Macro", "Tracks inflation releases and central bank decisions.",
            "Will the Fed cut rates in December?", "#7b78cc", 618400, 84, 56, 49,
            (0, 1400, 300, 3720, 2880, 6200, 8960, 7410, 14000, 12400, 17120, 24860)),
    Profile("juniper", "Juniper Lane", "Politics", "Follows election calendars and legislative votes.",
            "Will the budget pass this month?", "#44896f", 492700, 72, 44, 57,
            (0, 880, -320, 2400, 2210, 5700, 7330, 5980, 9090, 12600, 13200, 18420)),
    Profile("mira", "Mira Vale", "Technology", "Studies product launches and public release windows.",
            "Will the next chip launch this quarter?", "#4e8dac", 388100, 51, 30, 45,
            (0, 660, 720, -450, 1100, 2900, 2710, 5120, 7000, 6200, 9800, 14380)),
    Profile("northline", "Northline", "Sports", "Focuses on regular-season matches and tournament outcomes.",
            "Will the home team win the final?", "#bc7e48", 723500, 96, 58, 54,
            (0, -600, 3200, 2820, 4200, 3900, 5020, 6710, 6300, 7720, 7400, 11920)),
    Profile("cobalt", "Cobalt Index", "Crypto", "Tracks spot-price milestones and weekly closes.",
            "Will Bitcoin close above the weekly target?", "#5579b8", 531200, 64, 35, 38,
            (0, -1200, 640, 1080, 2420, 1900, 3200, 2900, 5400, 4720, 7510, 9320)),
    Profile("solstice", "Solstice", "Climate", "Follows temperature thresholds and forecast revisions.",
            "Will the city exceed its monthly temperature record?", "#b16c8f", 216800, 39, 22, 61,
            (0, 180, 500, 120, 1400, 970, 2320, 2820, 2490, 4100, 5010, 6840)),
)


def leaders() -> list[dict]:
    return [
        {"id": p.id, "name": p.name, "handle": p.id, "category": p.category,
         "description": p.description, "market": p.market, "color": p.color,
         "pnl": f"{p.history[-1] - p.history[0]}.00", "volume": f"{p.volume}.00",
         "markets": p.markets, "win_rate": round(100 * p.wins / p.markets),
         "wins": p.wins, "history": list(p.history), "source": "scenario"}
        for p in PROFILES
    ]


def _profile(leader_id: str) -> Profile:
    for profile in PROFILES:
        if profile.id == leader_id:
            return profile
    raise ValueError("Choose a leader from the scenario directory.")


def _time(seconds: int) -> str:
    return (START + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


def _money(cents: int) -> str:
    return format(Decimal(cents).scaleb(-2), ".2f")


def _input_cents(value: str, field: str, label: str) -> int:
    if not isinstance(value, str) or not re.fullmatch(r"(?:0|[1-9][0-9]{0,4})(?:\.[0-9]{1,2})?", value):
        raise ValueError(f"{label} must be a dollar amount with at most two decimal places.")
    cents = int(Decimal(value) * 100)
    minimum = _cents(LIMITS[f"min_{field}"])
    maximum = _cents(LIMITS[f"max_{field}"])
    if not minimum <= cents <= maximum:
        raise ValueError(f"{label} must be between ${minimum // 100:,} and ${maximum // 100:,}.")
    return cents


def _cents(value: str) -> int:
    return int(Decimal(value) * 100)


@dataclass(frozen=True)
class Signal:
    # One normalized, fully executed source order, with an unambiguous identity.
    order: str
    side: str
    executed: int
    observed: int
    leader_price: int
    sold: int = 0
    inventory_before: int | None = None


@dataclass(frozen=True)
class Book:
    time: int
    asks: tuple[tuple[int, int], ...]  # price in cents, available whole shares
    bids: tuple[tuple[int, int], ...]


def _tape(profile: Profile) -> list[tuple[Signal, Book | None]]:
    p = profile.anchor_cents

    def book(time: int, shift: int = 0, depth: int = 1000) -> Book:
        return Book(time, ((p + shift + 1, min(12, depth)), (p + shift + 2, max(0, depth - 12))),
                    ((p + shift - 1, depth), (p + shift - 2, 20)))

    return [
        (Signal("pre-run", "BUY", -2, 0, p), book(2)),
        (Signal("entry-1", "BUY", 19, 20, p), book(22)),
        (Signal("entry-2", "BUY", 39, 40, p + 1), book(42, 1, 4)),
        (Signal("gap", "BUY", 59, 60, p), None),
        (Signal("delayed", "BUY", 64, 80, p), book(82)),
        (Signal("reduction", "SELL", 99, 100, p + 3, 50, 100), book(102, 3)),
        (Signal("reduction", "SELL", 99, 120, p + 3, 50, 100), book(122, 3)),
        (Signal("unknown-basis", "SELL", 139, 140, p + 2, 5), book(142, 2, 3)),
    ]


def create_run(leader_id: str, allocation: str = "100.00", order_size: str = "10.00") -> dict:
    profile = _profile(leader_id)
    capital = _input_cents(allocation, "allocation", "Allocation")
    cap = _input_cents(order_size, "order_size", "Per-order cap")
    if cap > capital:
        raise ValueError("Per-order cap cannot exceed the allocation.")
    remaining = sum(s.executed > 0 for s, _ in _tape(profile))
    return {
        "leader_id": profile.id, "leader_name": profile.name, "source": "scenario",
        "mode": "shadow", "scenario": SCENARIO, "observation_start": _time(0),
        "account": "Simulated wallet", "currency": "USD",
        "model": "Fee-inclusive cap per distinct source order. Immediate whole-share fills at displayed depth. The unfilled remainder expires.",
        "market": profile.market, "outcome": "Yes", "policy": dict(POLICY),
        "status": "running", "capital": _money(capital), "order_size": _money(cap),
        "cash": _money(capital), "quantity": "0", "cost_basis": "0.00",
        "fees": "0.00", "realized_pnl": "0.00", "marked_value": "0.00",
        "liquidation_value": "0.00", "valuation_as_of": None,
        "pending_commitments": "0.00", "events": [], "cursor": 0,
        "total_steps": remaining, "remaining_steps": remaining,
    }


def _fee(gross: int) -> int:
    # One fee calculation on the aggregate matched notional for the source order.
    return (gross * POLICY["fee_bps"] + 9999) // 10000


def _walk(levels: tuple[tuple[int, int], ...], quantity: int) -> tuple[int, int]:
    gross, shares = 0, 0
    for price, available in levels:
        take = min(available, quantity - shares)
        gross += take * price
        shares += take
        if shares == quantity:
            break
    return gross, shares


def _residual_book(book: Book, side: str, filled_shares: int) -> Book:
    # Marketable buys consume asks; sells consume bids. Immediately following
    # valuations cannot count consumed liquidity a second time.
    levels = book.asks if side == "BUY" else book.bids
    remaining = []
    for price, depth in levels:
        consumed = min(depth, filled_shares)
        filled_shares -= consumed
        if depth > consumed:
            remaining.append((price, depth - consumed))
    if side == "BUY":
        return Book(book.time, tuple(remaining), book.bids)
    return Book(book.time, book.asks, tuple(remaining))


def _mark(run: dict, book: Book | None) -> None:
    quantity = int(run["quantity"])
    run["valuation_as_of"] = _time(book.time) if book else None
    if quantity == 0:
        run.update(marked_value="0.00", liquidation_value="0.00")
    elif book is None:
        run.update(marked_value=None, liquidation_value=None)
    else:
        # Midpoint mark is a valuation only. Keep fractional cents for estimates.
        run["marked_value"] = None
        if book.bids and book.asks:
            midpoint_cents = Decimal(book.bids[0][0] + book.asks[0][0]) / 2
            run["marked_value"] = format((quantity * midpoint_cents / 100).normalize(), "f")
        gross, available = _walk(book.bids, quantity)
        run["liquidation_value"] = _money(gross - _fee(gross)) if available == quantity else None


def _apply_signal(run: dict, signal: Signal, book: Book | None) -> dict:
    sell = signal.side == "SELL"
    decision = signal.observed + POLICY["delay_seconds"]
    limit = signal.leader_price + (-1 if sell else 1) * POLICY["max_slippage_cents"]
    quantity = int(run["quantity"])
    cash, basis = _cents(run["cash"]), _cents(run["cost_basis"])
    valid_book = book is not None and book.time == decision
    event = {
        "id": f"{run['leader_id']}/{run['cursor'] + 1}", "source_order": signal.order,
        "market": run["market"], "side": signal.side, "status": "skipped",
        "requested": run["order_size"] if not sell else None, "target_quantity": None,
        "filled": "0.00", "quantity": "0", "fee": "0.00", "price": None,
        "entry_state": run["status"], "leader_price": _money(signal.leader_price),
        "limit_price": _money(limit), "leader_sold": signal.sold if sell else None,
        "leader_inventory_before": signal.inventory_before,
        "book": {"asks": [{"price": _money(p), "shares": n} for p, n in book.asks if n],
                 "bids": [{"price": _money(p), "shares": n} for p, n in book.bids if n]} if valid_book else None,
        "executed_at": _time(signal.executed), "observed_at": _time(signal.observed),
        "decided_at": _time(decision), "book_at": _time(book.time) if valid_book else None,
    }

    def skip(reason: str) -> dict:
        event["reason"] = reason
        return event

    if any(old["source_order"] == signal.order for old in run["events"]):
        return skip("Duplicate source order. Its first decision still applies.")
    if run["status"] == "paused" and not sell:
        return skip("New entries are paused. This entry will not be replayed.")
    if decision - signal.executed > POLICY["max_age_seconds"]:
        return skip("Source execution was over 10 seconds old at the decision.")
    if not valid_book:
        return skip("No book at the modeled decision time.")
    if sell:
        if not signal.inventory_before or not 0 < signal.sold <= signal.inventory_before:
            return skip("Unknown leader inventory before sale. The reduction cannot be sized.")
        target = quantity * signal.sold // signal.inventory_before
        eligible = tuple(level for level in book.bids if level[0] >= limit)
    else:
        budget = min(cash, _cents(run["order_size"]))
        # Reserve using the worst accepted price, including fees. The integer floor
        # exactly enforces ceil(gross * fee_bps / 10000) + gross <= budget.
        target = budget * 10000 // (limit * (10000 + POLICY["fee_bps"]))
        eligible = tuple(level for level in book.asks if level[0] <= limit)
    event["target_quantity"] = str(target)
    if not target:
        return skip("Available cash or attributable shares cannot cover one whole share.")

    gross, shares = _walk(eligible, target)
    if not shares:
        return skip("No executable depth inside the price limit.")
    fee = _fee(gross)
    if sell:
        released_basis = basis * shares // quantity
        proceeds = gross - fee
        run.update(cash=_money(cash + proceeds), quantity=str(quantity - shares),
                   cost_basis=_money(basis - released_basis),
                   realized_pnl=_money(_cents(run["realized_pnl"]) + proceeds - released_basis))
    else:
        run.update(cash=_money(cash - gross - fee), quantity=str(quantity + shares),
                   cost_basis=_money(basis + gross + fee))
    run["fees"] = _money(_cents(run["fees"]) + fee)
    complete = shares == target
    event.update(status="filled" if complete else "partial",
                 reason="Filled the modeled target." if complete else "Available depth filled part of the target. The remainder expired.",
                 quantity=str(shares), fee=_money(fee), filled=_money(gross),
                 price=format((Decimal(gross) / (100 * shares)).quantize(Decimal("0.0001")), "f"))
    return event


def apply_action(original: dict, action: str) -> dict:
    """Apply one action to an immutable persisted snapshot; caller commits by revision."""
    if action != "stop" and (original["scenario"] != SCENARIO or original["policy"] != POLICY):
        raise ValueError("The saved run requires a different scenario or policy version.")
    if original["status"] in {"completed", "stopped"}:
        raise ValueError("This run has ended. Its recorded positions and cash remain available.")
    run = deepcopy(original)
    if action == "stop":
        run["status"] = "stopped"
    elif action == "pause" and run["status"] == "running":
        run["status"] = "paused"
    elif action == "resume" and run["status"] == "paused":
        run["status"] = "running"
    elif action == "step":
        tape = [(s, b) for s, b in _tape(_profile(run["leader_id"])) if s.executed > 0]
        signal, book = tape[run["cursor"]]
        event = _apply_signal(run, signal, book)
        run["events"].append(event)
        if book and int(event["quantity"]):
            book = _residual_book(book, signal.side, int(event["quantity"]))
        _mark(run, book if event["book_at"] else None)
        run["cursor"] += 1
        run["remaining_steps"] = run["total_steps"] - run["cursor"]
        if not run["remaining_steps"]:
            run["status"] = "completed"
    else:
        raise ValueError("This action is unavailable in the current run state.")
    return run
