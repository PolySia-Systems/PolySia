"""User-stepped shadow portfolios for one public wallet. Amounts in SQLite are micro-pUSD."""

import json
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from .provider import decimal_value, units_from_micros as units, validate_address
from .public_depth import DELAY_SECONDS, MINIMUM_SALE_REASON, budget_amount, capacity_policy, measure_depth, measure_sale, sell_scope
from .public_fill import EXCHANGES, verify_retained_amounts
from .store import WORKSPACE_VERSION, Conflict, timestamp


PAGE = 20
MODE = "public-shadow"
MODEL = "displayed-asks-v1"
CONTROLS = {"pause": ("running", "paused"), "resume": ("paused", "running"), "stop": (None, "stopped")}
CONTROL_REASONS = {"pause": "New entries paused.", "resume": "Ready for another observation.",
                   "stop": "Run stopped. Existing simulated positions remain open."}


def _budget(value):
    return int(Decimal(budget_amount(value)) * 1_000_000)


def _money(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,10}(?:\.[0-9]{1,6})?", value):
        raise ValueError("Invalid amount in observation")
    return int(Decimal(value) * 1_000_000)


def _run(db, run_id):
    row = db.execute("SELECT * FROM public_runs WHERE id=?", (run_id,)).fetchone()
    if row is None:
        raise KeyError("Public shadow run not found.")
    return row


def _journal_time(value):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("Portfolio timestamps require a UTC offset.")
    return parsed


def _recorded_time(previous, observed):
    # Keep revision order when the system clock steps backwards. The observation
    # retains its original provider times and uses the real clock for validation.
    return previous if _journal_time(previous) > _journal_time(observed) else observed


EXIT_MODEL = {"model": "displayed-bids-v1", "sizing": "operator limit capped by observed leader sale and owned shares",
              "maxPriceDecrease": "0.03", "costMethod": "pooled cost, floor to micro-pUSD"}
ENABLE_REASON = "Enabled operator-capped SELL windows for this run."
BACKGROUND_REASONS = {"background-on": "Enabled background BUY sampling.",
                      "background-off": "Disabled background BUY sampling."}
CUMULATIVE_SELL = "cumulative verified fills capped by the first share limit per source order"


def _policy(budget, exits=False, check_sales=False, cumulative=False):
    policy = {**capacity_policy(budget), "model": MODEL, "side": "BUY", "entryModel": "displayed whole shares",
            "windowSeconds": 2, "retryEmpty": True, "venueMinimumNotionalEnforced": False,
            "exitModel": EXIT_MODEL if exits else None, "markModel": "on-demand two-sided midpoint"}
    if check_sales:
        policy["checkSalesBeforeEntry"] = True
    if cumulative:
        policy["saleSizing"] = CUMULATIVE_SELL
    return policy


def create(db, run_id, wallet, name, capital, cap):
    wallet = validate_address(wallet)
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
        raise ValueError("Give the run a name of 1–80 characters.")
    config = (wallet, name.strip(), _budget(capital), _budget(cap))
    if config[3] > config[2]:
        raise ValueError("The per-entry budget must fit within the starting cash.")
    now = timestamp()
    policy = _policy(budget_amount(cap), exits=True, check_sales=True, cumulative=True)
    db.execute("""INSERT INTO public_runs VALUES (?,?,?,?,?,?,?,?,'running',1)
                  ON CONFLICT(id) DO NOTHING""", (run_id, *config, json.dumps(policy), now, now))
    row = _run(db, run_id)
    initial_cap = _budget(json.loads(row["policy"])["budget"])
    if (row["wallet"], row["name"], row["capital"], initial_cap) != config:
        raise Conflict("This run already exists with different settings.")
    return report(db, run_id)


def _totals(db, run_id):
    return db.execute("""SELECT coalesce(sum(CASE WHEN kind='entry' THEN gross END),0),
                         coalesce(sum(fee),0), count(CASE WHEN kind='entry' THEN 1 END),
                         coalesce(sum(CASE WHEN kind='exit' THEN gross END),0),
                         coalesce(sum(CASE WHEN kind='exit' THEN gross-fee-released_cost END),0),
                         count(CASE WHEN kind='exit' THEN 1 END),
                         coalesce(sum(CASE WHEN kind='deposit' THEN json_extract(receipt,'$.amountMicros') END),0)
                         FROM public_decisions WHERE run_id=?""", (run_id,)).fetchone()


def _enabled(db, row):
    return bool(json.loads(row["policy"])["exitModel"] or db.execute(
        "SELECT 1 FROM public_decisions WHERE run_id=? AND kind='enable-exits' LIMIT 1", (row["id"],)).fetchone())


def _signed(micros):
    return ("-" if micros < 0 else "") + units(abs(micros))


def _next_budget(cash, cap):
    # Public observations accept cent-denominated budgets. Keep sub-cent cash in the ledger.
    cents = min(cash, cap) // 10_000
    return f"{cents // 100}.{cents % 100:02d}" if cents >= 100 else None


def _summary(row, gross, fee, entries, sales, realized, exits, deposits):
    funded = row["capital"] + deposits
    cash = funded - gross - fee + sales
    return {"id": row["id"], "name": row["name"], "wallet": row["wallet"], "mode": MODE,
            "model": MODEL, "asset": "pUSD", "status": row["status"], "revision": row["revision"],
            "createdAt": row["created"], "updatedAt": row["updated"], "capital": units(row["capital"]),
            "entryCap": units(row["entry_cap"]), "cash": units(cash), "gross": units(gross), "fees": units(fee),
            "fundedCapital": units(funded), "deposits": units(deposits), "openCost": units(funded + realized - cash),
            "entries": entries, "sales": units(sales), "realized": _signed(realized), "exits": exits, "nextBudget": _next_budget(cash, row["entry_cap"])}


def listing(db, before=None):
    cursor = 2**63 - 1
    if before:
        row = db.execute("SELECT rowid FROM public_runs WHERE id=?", (before,)).fetchone()
        if not row:
            raise ValueError("Unknown public run cursor.")
        cursor = row[0]
    rows = db.execute("SELECT * FROM public_runs WHERE rowid < ? ORDER BY rowid DESC LIMIT ?",
                      (cursor, PAGE + 1)).fetchall()
    items = [_summary(row, *_totals(db, row["id"])) for row in rows[:PAGE]]
    return {"runs": items, "nextCursor": items[-1]["id"] if len(rows) > PAGE else None}


def report(db, run_id, *, export=False, before=None, trades=False):
    row = _run(db, run_id)
    result = _summary(row, *_totals(db, run_id))
    result["policy"] = json.loads(row["policy"])
    result["backgroundEnabled"] = bool(db.execute("SELECT 1 FROM background_runs WHERE run_id=?", (run_id,)).fetchone())
    result["exitsEnabled"] = _enabled(db, row)
    result["activeExitPolicy"] = EXIT_MODEL if result["exitsEnabled"] else None
    result["positions"], result["closedPositions"] = [], []
    for p in _positions(db, run_id, include_closed=True):
        holding = {"conditionId": p["condition_id"], "tokenId": p["token_id"], "market": p["market"],
                   "outcome": p["outcome"], "shares": str(p["quantity"]), "cost": units(p["cost"]),
                   "soldShares": str(p["sold"]), "saleProceeds": units(p["proceeds"]),
                   "releasedCost": units(p["released"]), "realized": _signed(p["proceeds"] - p["released"])}
        if p["quantity"]:
            result["positions"].append(holding)
        else:
            result["closedPositions"].append(dict(holding, closedAt=p["last_change"]))
    fields = "revision, recorded, kind, reason, shares, gross, fee, market, outcome, token_id, source_order, released_cost"
    fields += """, json_extract(receipt,'$.windowStartSeconds') AS window_start,
                 json_extract(receipt,'$.windowEndSeconds') AS window_end,
                 json_extract(receipt,'$.event.eventTimeSeconds') AS event_time,
                 json_extract(receipt,'$.bookReceivedMs') AS book_time,
                 json_extract(receipt,'$.researchBudget') AS budget,
                 json_extract(receipt,'$.exitScope.maxShares') AS sale_limit,
                 json_extract(receipt,'$.exitScope.tokenId') AS sale_token,
                 coalesce(json_extract(receipt,'$.portfolioSale.targetShares'), json_extract(receipt,'$.capacity.targetShares')) AS target_shares,
                 json_extract(receipt,'$.participant.orderHash') AS order_hash,
                 json_extract(receipt,'$.participant.exchange') AS exchange"""
    next_cursor = None
    if export:
        rows = db.execute(f"SELECT {fields},receipt FROM public_decisions WHERE run_id=? ORDER BY revision", (run_id,))
    else:
        kinds = "AND kind IN ('entry','exit')" if trades else ""
        rows = db.execute(f"""SELECT {fields} FROM public_decisions WHERE run_id=? AND revision < ? {kinds}
                           ORDER BY revision DESC LIMIT ?""", (run_id, before or 2**63 - 1, PAGE + 1)).fetchall()
        if len(rows) > PAGE:
            rows = rows[:PAGE]
            next_cursor = rows[-1]["revision"]
    decisions = []
    for d in rows:
        decision = {"revision": d["revision"], "at": d["recorded"], "kind": d["kind"], "reason": d["reason"],
                    "shares": str(d["shares"]), "gross": units(d["gross"]), "fee": units(d["fee"]),
                    "market": d["market"], "outcome": d["outcome"], "tokenId": d["token_id"], "sourceOrder": d["source_order"]}
        if d["kind"] == "exit":
            decision.update(targetShares=d["target_shares"], releasedCost=units(d["released_cost"]), proceeds=units(d["gross"]-d["fee"]),
                            realized=_signed(d["gross"]-d["fee"]-d["released_cost"]))
        if d["source_order"] and d["source_order"].startswith("137:"):
            decision.update(sourceOrder=d["exchange"] + "/" + d["order_hash"], sourceFill=d["source_order"])
        if d["budget"] is not None or d["sale_limit"] is not None:
            decision["observation"] = {"windowStartSeconds": d["window_start"], "windowEndSeconds": d["window_end"],
                                       "eventTimeSeconds": d["event_time"], "bookReceivedMs": d["book_time"],
                                       "budget": d["budget"], "maxShares": d["sale_limit"],
                                       "outcomeToken": d["sale_token"], "side": "SELL" if d["sale_limit"] else "BUY"}
        if export:
            decision["receipt"] = json.loads(d["receipt"]) if d["receipt"] else None
        decisions.append(decision)
    result["decisions"] = decisions
    result["nextCursor"] = next_cursor
    return result


def _check_revision(row, revision):
    if type(revision) is not int or revision != row["revision"]:
        raise Conflict("The run changed. Reload the latest decisions before continuing.")


def require_revision(db, run_id, revision):
    _check_revision(_run(db, run_id), revision)


def _check_control(status, action):
    prior, after = CONTROLS[action]
    if status == "stopped" or (prior and status != prior):
        raise Conflict("This control is unavailable for the current run state.")
    return after


def _positions(db, run_id, token=None, *, include_closed=False):
    query = """SELECT condition_id, token_id, max(market) AS market, max(outcome) AS outcome,
               sum(CASE WHEN kind='exit' THEN -shares ELSE shares END) AS quantity,
               sum(CASE WHEN kind='exit' THEN -released_cost ELSE gross+fee END) AS cost,
               sum(CASE WHEN kind='exit' THEN shares ELSE 0 END) AS sold,
               sum(CASE WHEN kind='exit' THEN gross-fee ELSE 0 END) AS proceeds,
               sum(released_cost) AS released,
               max(CASE WHEN kind='entry' THEN recorded END) AS last_entry, max(recorded) AS last_change
               FROM public_decisions WHERE run_id=? AND kind IN ('entry','exit')"""
    args = [run_id]
    if token is not None:
        query += " AND token_id=?"
        args.append(token)
    query += " GROUP BY condition_id,token_id"
    if not include_closed:
        query += " HAVING quantity>0"
    return db.execute(query + " ORDER BY min(revision)", args).fetchall()


def position_basis(db, run_id, token, revision):
    _check_revision(_run(db, run_id), revision)
    positions = _positions(db, run_id, token)
    if len(positions) != 1:
        raise ValueError("Choose an existing position with an unambiguous market.")
    p = positions[0]
    return {"runId": run_id, "revision": revision, "conditionId": p["condition_id"], "tokenId": token,
            "shares": str(p["quantity"]), "cost": units(p["cost"]), "lastEntryAt": p["last_entry"], "lastChangeAt": p["last_change"]}


def valuation_basis(db, run_id, revision):
    row = _run(db, run_id)
    _check_revision(row, revision)
    summary = _summary(row, *_totals(db, run_id))
    positions = [{"conditionId": p["condition_id"], "tokenId": p["token_id"], "market": p["market"],
                  "outcome": p["outcome"], "shares": str(p["quantity"]), "cost": units(p["cost"]),
                  "lastEntryAt": p["last_entry"], "lastChangeAt": p["last_change"]} for p in _positions(db, run_id)]
    return {**summary, "positions": positions}


def control(db, run_id, revision, action):
    row = _run(db, run_id)
    _check_revision(row, revision)
    if action in BACKGROUND_REASONS:
        status, reason = row["status"], BACKGROUND_REASONS[action]
    elif action == "enable-exits":
        if row["status"] == "stopped" or _enabled(db, row):
            raise Conflict("This run cannot enable another exit policy.")
        status, reason = row["status"], ENABLE_REASON
    else:
        status, reason = _check_control(row["status"], action), CONTROL_REASONS[action]
    now = _recorded_time(row["updated"], timestamp())
    db.execute("""INSERT INTO public_decisions(run_id,revision,recorded,kind,reason,shares,gross,fee)
                  VALUES(?,?,?,?,?,0,0,0)""", (run_id, revision + 1, now, action, reason))
    db.execute("UPDATE public_runs SET revision=revision+1, status=?, updated=? WHERE id=?", (status, now, run_id))
    if action in ("pause", "stop"):
        db.execute("DELETE FROM background_runs WHERE run_id=?", (run_id,))
    return report(db, run_id)


def sampling_terms(db, run_id, revision):
    row = _run(db, run_id)
    _check_revision(row, revision)
    if row["status"] != "running":
        raise Conflict("Only a running public shadow portfolio can sample a BUY.")
    gross, fee, _, sales, _, _, deposits = _totals(db, run_id)
    budget = _next_budget(row["capital"] + deposits - gross - fee + sales, row["entry_cap"])
    if not budget:
        raise Conflict("Less than 1 pUSD of simulated cash remains. Review the open positions.")
    return row["wallet"], budget, json.loads(row["policy"]).get("checkSalesBeforeEntry", False)


def _cap_change(previous, cap, capital):
    amount = _budget(cap)
    if amount > capital:
        raise ValueError("The per-entry cap exceeds this run's starting cash.")
    return amount, f"Changed future simulated BUY cap from {units(previous)} to {units(amount)} pUSD."


def _deposit_terms(amount, funded):
    micros = _budget(amount)
    if funded + micros > 1_000_000_000:
        raise ValueError("Total simulated funding must stay within 1,000 pUSD.")
    return micros, f"Added {units(micros)} pUSD of simulated cash."


def deposit(db, run_id, revision, amount):
    row = _run(db, run_id)
    _check_revision(row, revision)
    if row["status"] == "stopped":
        raise Conflict("This portfolio has stopped.")
    micros, reason = _deposit_terms(amount, row["capital"] + _totals(db, run_id)[-1])
    now = _recorded_time(row["updated"], timestamp())
    receipt = {"amount": units(micros), "amountMicros": micros}
    db.execute("""INSERT INTO public_decisions(run_id,revision,recorded,kind,reason,shares,gross,fee,receipt)
                  VALUES(?,?,?,'deposit',?,0,0,0,?)""", (run_id, revision + 1, now, reason, json.dumps(receipt)))
    db.execute("UPDATE public_runs SET revision=revision+1, updated=? WHERE id=?", (now, run_id))
    return report(db, run_id)


def change_cap(db, run_id, revision, cap):
    row = _run(db, run_id)
    _check_revision(row, revision)
    if row["status"] == "stopped":
        raise Conflict("This portfolio has stopped.")
    amount, reason = _cap_change(row["entry_cap"], cap, row["capital"])
    if amount != row["entry_cap"]:
        now = _recorded_time(row["updated"], timestamp())
        change = {"previousCap": units(row["entry_cap"]), "nextCap": units(amount)}
        db.execute("""INSERT INTO public_decisions(run_id,revision,recorded,kind,reason,shares,gross,fee,receipt)
                      VALUES(?,?,?,'change-cap',?,0,0,0,?)""",
                   (run_id, revision + 1, now, reason, json.dumps(change)))
        db.execute("UPDATE public_runs SET entry_cap=?, revision=revision+1, updated=? WHERE id=?",
                   (amount, now, run_id))
    return report(db, run_id)


def _source_order(receipt, side):
    event, participant = receipt["event"], receipt["participant"]
    if (receipt["status"] != "observed" or receipt["asset"] != "pUSD"
            or event["side"] != side or participant["status"] != "matched"
            or participant["chainId"] != 137 or participant["transactionHash"] != event["transactionHash"]
            or not re.fullmatch("0x[0-9a-f]{64}", event["transactionHash"])
            or participant["exchange"] not in EXCHANGES or not re.fullmatch("0x[0-9a-f]{64}", participant["orderHash"])
            or not re.fullmatch("0x[0-9a-f]{64}", event["conditionId"])
            or not re.fullmatch("[0-9]{1,78}", event["tokenId"])):
        raise ValueError("Receipt identity mismatch")
    return participant["exchange"] + "/" + participant["orderHash"]


def _entry(receipt, budget):
    cap, event = receipt["capacity"], receipt["event"]
    source = _source_order(receipt, "BUY")
    if cap["asset"] != "pUSD" or cap["budget"] != budget:
        raise ValueError("Receipt budget mismatch")
    shares = cap["shares"]
    if not isinstance(shares, str) or not re.fullmatch("[1-9][0-9]{0,9}", shares):
        raise ValueError("Invalid modeled quantity")
    gross, fee, unspent = (_money(cap[key]) for key in ("gross", "feeEstimate", "unspent"))
    if not gross or gross + fee + unspent != _money(budget):
        raise ValueError("The modeled entry does not reconcile with its budget.")
    return (source, event["conditionId"], event["tokenId"],
            event.get("marketTitle"), event.get("outcomeLabel"), int(shares), gross, fee)


def _check_entry_policy(run, receipt, recorded):
    policy = json.loads(run["policy"])
    cap = receipt["capacity"]
    if any(cap[k] != policy[k] for k in capacity_policy(cap["budget"]) if k != "budget"):
        raise ValueError("The capacity assumptions changed since the run was created.")
    if (not 0 < decimal_value(receipt["event"]["price"]) <= 1
            or not 0 < len(receipt["book"]["bestAsks"]) <= policy["maxLevels"]
            or any(not isinstance(receipt["event"].get(key, ""), str) for key in ("marketTitle", "outcomeLabel"))):
        raise ValueError("Invalid source price, book depth or market labels.")
    if measure_depth(receipt, cap["budget"]) != cap:
        raise ValueError("The estimated entry differs from the retained book and market terms.")
    _check_window(run, receipt, recorded)


def _check_window(run, receipt, recorded):
    start = receipt["windowStartSeconds"]
    if (type(start) is not int or start < datetime.fromisoformat(run["created"]).timestamp()
            or receipt["windowEndSeconds"] != start + 1
            or receipt["bookReceivedMs"] > datetime.fromisoformat(recorded).timestamp() * 1000 + 1
            or not start <= receipt["event"]["eventTimeSeconds"] <= receipt["windowEndSeconds"]):
        raise ValueError("The source trade falls outside the run's observation period.")


NO_ENTRY = (None, None, None, None, None, 0, 0, 0)


def _sale_check_issue(receipt):
    check = receipt.get("saleCheck") or {}
    event = receipt["event"]
    coverage = check.get("coverage", {})
    uncertain = ("incomplete", "Later leader sales could not be ruled out from a complete, timely activity page.", NO_ENTRY)
    requested, received = check.get("requestedMs"), check.get("receivedMs")
    eligible = receipt["evidenceCheckedMs"] + DELAY_SECONDS * 1000 + receipt["market"]["takerDelayMs"]
    if (type(requested) is not int or type(received) is not int
            or not eligible <= requested <= received <= receipt["bookRequestedMs"]
            or check["startSeconds"] != event["eventTimeSeconds"] or check["endSeconds"] != requested // 1000):
        return uncertain
    returned = coverage.get("rowsReturned")
    matches = coverage.get("matchingSellRows")
    if type(returned) is not int or type(matches) is not int or not 0 <= matches <= returned or "firstSale" not in check:
        return uncertain
    sale = check["firstSale"]
    if sale is not None:
        if (matches < 1 or sale["side"] != "SELL" or sale["conditionId"] != event["conditionId"] or sale["tokenId"] != event["tokenId"]
                or not check["startSeconds"] <= sale["eventTimeSeconds"] <= check["endSeconds"]):
            return uncertain
        return "skipped", "Public activity showed a sale of this outcome at or after the reported BUY second. No entry was modeled.", NO_ENTRY
    if coverage.get("complete") is not True or matches != 0:
        return uncertain
    return None


def _decision(run, budget, receipt, recorded, seen):
    verify_retained_amounts(receipt, "BUY")
    if receipt["wallet"] != run["wallet"] or receipt["researchBudget"] != budget:
        raise ValueError("Receipt scope mismatch")
    capacity = receipt.get("capacity", {})
    kind = capacity.get("status", receipt["status"])
    if kind == "estimated":
        _check_entry_policy(run, receipt, recorded)
        candidate = _entry(receipt, budget)
        if seen(candidate[0]):
            return "duplicate", "This source order already has a modeled entry in this run.", NO_ENTRY
        if json.loads(run["policy"]).get("checkSalesBeforeEntry"):
            issue = _sale_check_issue(receipt)
            if issue:
                return issue
        return "entry", "Modeled a BUY against the delayed displayed asks.", candidate
    reason = capacity.get("reason") or receipt["reason"]
    if kind not in ("waiting", "incomplete", "unavailable", "skipped") or not isinstance(reason, str):
        raise ValueError("Unknown observation outcome")
    return kind, reason, NO_ENTRY


def record(db, run_id, revision, receipt):
    wallet, budget, _ = sampling_terms(db, run_id, revision)
    now = timestamp()

    def seen(source):
        return db.execute("SELECT 1 FROM public_decisions WHERE run_id=? AND source_order=?", (run_id, source)).fetchone()

    try:
        kind, reason, amounts = _decision(_run(db, run_id), budget, receipt, now, seen)
    except (AttributeError, ArithmeticError, IndexError, KeyError, TypeError, ValueError):
        kind, reason, amounts = "incomplete", "The observation could not be reconciled with this run and its budget.", NO_ENTRY
        receipt = {"wallet": wallet, "researchBudget": budget, "status": kind, "reason": reason}
    return _save(db, run_id, revision, now, kind, reason, amounts, receipt, 0)


def sale_terms(db, run_id, revision, token, limit):
    row = _run(db, run_id)
    _check_revision(row, revision)
    if row["status"] == "stopped" or not _enabled(db, row):
        raise Conflict("This run is closed to SELL observations.")
    basis = position_basis(db, run_id, token, revision)
    scope = sell_scope(basis["conditionId"], token, limit)
    if int(limit) > int(basis["shares"]):
        raise ValueError("The share limit exceeds the open position.")
    return row["wallet"], scope, basis


@dataclass
class SaleOrder:
    limit: int = 0
    source_micros: int = 0
    sold: int = 0
    last_exit: str | None = None

    def include(self, limit, source_micros, shares, recorded):
        self.limit = self.limit or int(limit)
        self.source_micros += int(source_micros)
        self.sold += shares
        if shares:
            self.last_exit = recorded


def _sale_progress(db, run_id, order):
    exchange, order_hash = order.split("/")
    progress = SaleOrder()
    for row in db.execute("""SELECT json_extract(receipt,'$.exitScope.maxShares'),
                             json_extract(receipt,'$.participant.sharesBaseUnits'), shares, recorded
                             FROM public_decisions WHERE run_id=? AND source_order LIKE '137:%'
                             AND json_extract(receipt,'$.participant.orderHash')=?
                             AND json_extract(receipt,'$.participant.exchange')=? ORDER BY revision""",
                          (run_id, order_hash, exchange)):
        progress.include(*row)
    return progress


def _sale_decision(run, scope, basis, receipt, recorded, seen, order_history):
    verify_retained_amounts(receipt, "SELL")
    if receipt["wallet"] != run["wallet"] or receipt["exitScope"] != scope:
        raise ValueError("SELL receipt scope mismatch")
    quote = receipt.get("capacity", {})
    kind = quote.get("status", receipt["status"])
    cumulative = json.loads(run["policy"]).get("saleSizing") == CUMULATIVE_SELL
    below_minimum = kind == "skipped" and quote.get("reason") == MINIMUM_SALE_REASON
    if kind != "estimated" and not (cumulative and below_minimum):
        reason = quote.get("reason") or receipt["reason"]
        if kind not in ("waiting", "incomplete", "unavailable", "skipped") or not isinstance(reason, str):
            raise ValueError("Unknown SELL observation outcome")
        return kind, reason, NO_ENTRY, 0
    order = _source_order(receipt, "SELL")
    source = order
    if cumulative:
        participant = receipt["participant"]
        index = participant["logIndex"]
        source = f"137:{participant['transactionHash']}:{index}"
        if type(index) is not int or not 0 <= index < 2**64 or participant["fillId"] != source:
            raise ValueError("SELL fill identity mismatch")
    _check_window(run, receipt, recorded)
    if measure_sale(receipt) != quote:
        raise ValueError("Sale evidence did not reconcile with the position.")
    if seen(source):
        reason = "This verified SELL fill was already recorded." if cumulative else "This source order already has a modeled decision in this run."
        return "duplicate", reason, NO_ENTRY, 0
    prior = order_history(order) if cumulative else None
    boundary = basis["lastChangeAt"]
    if prior and prior.last_exit == boundary:
        boundary = basis["lastEntryAt"]
    if receipt["windowStartSeconds"] < datetime.fromisoformat(boundary).timestamp():
        raise ValueError("The sale predates the current position.")
    if cumulative:
        observed = prior.source_micros + int(participant["sharesBaseUnits"])
        authorized = min(prior.limit or int(scope["maxShares"]), observed // 1_000_000)
        target = min(int(scope["maxShares"]), authorized - prior.sold)
        if target < 0:
            raise ValueError("Invalid cumulative SELL target")
        quote = measure_sale(receipt, remaining_target=target)
        receipt["portfolioSale"] = {"targetShares": str(target), "orderTargetShares": str(authorized),
                                    "sourceShareMicros": str(observed), "soldBefore": str(prior.sold)}
        if quote["status"] == "skipped":
            reason = "The source order reached its original share limit." if prior.sold == (prior.limit or int(scope["maxShares"])) else quote["reason"]
            return "skipped", reason, (source, *NO_ENTRY[1:]), 0
        if quote["status"] != "estimated":
            raise ValueError("Cumulative sale cannot be verified")
    count, held, cost = int(quote["shares"]), int(basis["shares"]), _money(basis["cost"])
    if not 0 < count <= int(scope["maxShares"]) <= held:
        raise ValueError("Sale exceeds its share limit")
    event = receipt["event"]
    gross, fee = _money(quote["gross"]), _money(quote["feeEstimate"])
    amounts = (source, scope["conditionId"], scope["tokenId"], event.get("marketTitle"), event.get("outcomeLabel"),
               count, gross, fee)
    released = cost * count // held
    if cumulative:
        # Use the same pooled basis until the next purchase, so intermediate floors cancel.
        base_shares, base_cost = basis["pool"]
        released = base_cost * (base_shares - held + count) // base_shares - (base_cost - cost)
    return "exit", "Modeled a SELL against the delayed displayed bids.", amounts, released


def record_sale(db, run_id, revision, token, limit, receipt):
    wallet, scope, basis = sale_terms(db, run_id, revision, token, limit)
    now = timestamp()

    def seen(source):
        return db.execute("SELECT 1 FROM public_decisions WHERE run_id=? AND source_order=?", (run_id, source)).fetchone()

    if isinstance(receipt, dict):
        receipt = receipt.copy()
    try:
        sold, released_since_buy = db.execute("""SELECT coalesce(sum(shares),0),coalesce(sum(released_cost),0)
            FROM public_decisions WHERE run_id=? AND token_id=? AND kind='exit' AND revision >
            (SELECT max(revision) FROM public_decisions WHERE run_id=? AND token_id=? AND kind='entry')""",
            (run_id, token, run_id, token)).fetchone()
        basis["pool"] = (int(basis["shares"]) + sold, _money(basis["cost"]) + released_since_buy)
        kind, reason, amounts, released = _sale_decision(_run(db, run_id), scope, basis, receipt, now, seen,
                                                          lambda order: _sale_progress(db, run_id, order))
    except (AttributeError, ArithmeticError, IndexError, KeyError, TypeError, ValueError):
        kind, reason, amounts, released = "incomplete", "The SELL observation could not be reconciled with this position.", NO_ENTRY, 0
        receipt = {"wallet": wallet, "exitScope": scope, "status": kind, "reason": reason}
    return _save(db, run_id, revision, now, kind, reason, amounts, receipt, released)


def _save(db, run_id, revision, now, kind, reason, amounts, receipt, released):
    now = _recorded_time(_run(db, run_id)["updated"], now)
    db.execute("INSERT INTO public_decisions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (run_id, revision + 1, now, kind, reason, *amounts, json.dumps(receipt, allow_nan=False), released))
    db.execute("UPDATE public_runs SET revision=revision+1, updated=? WHERE id=?", (now, run_id))
    state = report(db, run_id)
    if state["backgroundEnabled"] and not state["nextBudget"]:
        db.execute("DELETE FROM background_runs WHERE run_id=?", (run_id,))
        state["backgroundEnabled"] = False
    return state


def verify_archive(db, version=WORKSPACE_VERSION):
    """Replay persisted control and money decisions against their frozen receipts."""
    if db.execute("PRAGMA foreign_key_check").fetchone():
        raise ValueError("A public shadow decision has no run.")
    for run in db.execute("SELECT * FROM public_runs"):
        if (not re.fullmatch("[0-9a-f]{32}", run["id"]) or validate_address(run["wallet"]) != run["wallet"]
                or not isinstance(run["name"], str) or not 1 <= len(run["name"].strip()) <= 80
                or not 1_000_000 <= run["entry_cap"] <= run["capital"] <= 1_000_000_000
                or run["capital"] % 10_000 or run["entry_cap"] % 10_000):
            raise ValueError("Invalid public shadow configuration.")
        cash, status, revision, last = run["capital"], "running", 1, run["created"]
        funded = run["capital"]
        policy = json.loads(run["policy"])
        exit_enabled = policy.get("exitModel") is not None
        check_sales = policy.get("checkSalesBeforeEntry") is True
        cumulative = "saleSizing" in policy
        active_cap = _budget(policy["budget"])
        if ((exit_enabled and version < 3) or (check_sales and not exit_enabled) or (cumulative and (not exit_enabled or version < 5))
                or active_cap > run["capital"]
                or policy != _policy(_next_budget(active_cap, active_cap), exit_enabled, check_sales, cumulative)):
            raise ValueError("Invalid public shadow policy.")
        _journal_time(last)
        used = set()
        holdings = {}
        background_enabled = False
        pools = {}
        orders = {}
        for item in db.execute("SELECT * FROM public_decisions WHERE run_id=? ORDER BY revision", (run["id"],)):
            revision += 1
            kind, last = item["kind"], item["recorded"]
            _journal_time(last)
            if item["revision"] != revision or not isinstance(item["reason"], str):
                raise ValueError("Invalid public shadow journal sequence.")
            released = 0
            if kind == "deposit":
                transfer = json.loads(item["receipt"])
                micros, reason = _deposit_terms(transfer["amount"], funded)
                if (version < 7 or status == "stopped" or type(transfer.get("amountMicros")) is not int
                        or transfer != {"amount": units(micros), "amountMicros": micros}):
                    raise ValueError("Invalid simulated deposit.")
                funded += micros
                cash += micros
                expected = NO_ENTRY
            elif kind == "change-cap":
                change = json.loads(item["receipt"])
                amount, reason = _cap_change(active_cap, change["nextCap"], run["capital"])
                if (version < 6 or status == "stopped" or amount == active_cap
                        or change != {"previousCap": units(active_cap), "nextCap": units(amount)}):
                    raise ValueError("The budget change disagrees with the portfolio history.")
                active_cap, expected = amount, NO_ENTRY
            elif kind in CONTROLS or kind == "enable-exits" or kind in BACKGROUND_REASONS:
                if kind in BACKGROUND_REASONS:
                    requested = kind == "background-on"
                    if version < 5 or status != "running" or requested == background_enabled or (requested and cash < 1_000_000):
                        raise ValueError("Invalid background sampling change.")
                    background_enabled, reason = requested, BACKGROUND_REASONS[kind]
                elif kind == "enable-exits":
                    if version < 3 or exit_enabled or status == "stopped":
                        raise ValueError("Invalid change of exit policy.")
                    exit_enabled, reason = True, ENABLE_REASON
                else:
                    status, reason = _check_control(status, kind), CONTROL_REASONS[kind]
                    if kind in ("pause", "stop"):
                        background_enabled = False
                expected = NO_ENTRY
                if item["receipt"] is not None:
                    raise ValueError("Unexpected receipt on a public shadow control.")
            else:
                receipt = json.loads(item["receipt"])
                if "exitScope" in receipt:
                    scope = receipt["exitScope"]
                    token = scope["tokenId"]
                    if (not exit_enabled or status == "stopped" or scope != sell_scope(scope["conditionId"], token, scope["maxShares"])):
                        raise ValueError("SELL receipt outside the run's scope.")
                    held, cost, changed = holdings[(scope["conditionId"], token)]
                    if not 0 < int(scope["maxShares"]) <= held:
                        raise ValueError("The sale limit exceeds the attributed position.")
                    basis = {"shares": str(held), "cost": units(cost), "lastChangeAt": changed}
                    basis["pool"], basis["lastEntryAt"] = pools[(scope["conditionId"], token)]
                    saved_sale = receipt.pop("portfolioSale", None)
                    outcome, reason, expected, released = _sale_decision(run, scope, basis, receipt, last, used.__contains__,
                                                                          lambda key: orders.get(key, SaleOrder()))
                    if saved_sale != receipt.get("portfolioSale"):
                        raise ValueError("The cumulative SELL target differs from the retained fill evidence.")
                    if saved_sale is not None:
                        key = _source_order(receipt, "SELL")
                        orders.setdefault(key, SaleOrder()).include(scope["maxShares"], receipt["participant"]["sharesBaseUnits"], expected[5], last)
                        used.add(expected[0])
                else:
                    budget = _next_budget(cash, active_cap)
                    if status != "running" or budget is None:
                        raise ValueError("Receipt outside the run's scope.")
                    outcome, reason, expected = _decision(run, budget, receipt, last, used.__contains__)
                if kind != outcome:
                    raise ValueError("The public shadow decision differs from its receipt.")
                if kind in ("entry", "exit"):
                    source, condition, token, _, _, shares, gross, fee = expected
                    used.add(source)
                    held, cost, _ = holdings.get((condition, token), (0, 0, None))
                    if kind == "entry":
                        holdings[(condition, token)] = held + shares, cost + gross + fee, last
                        pools[(condition, token)] = ((held + shares, cost + gross + fee), last)
                    else:
                        holdings[(condition, token)] = held - shares, cost - released, last
            if version >= 3 and item["released_cost"] != released:
                raise ValueError("Sale cost basis does not reconcile.")
            if item["reason"] != reason:
                raise ValueError("The saved explanation differs from the public shadow decision.")
            actual = tuple(item[k] for k in ("source_order", "condition_id", "token_id", "market", "outcome",
                                             "shares", "gross", "fee"))
            if actual != expected:
                raise ValueError("The public shadow journal disagrees with its recorded amounts.")
            cash += (item["gross"] if kind == "exit" else -item["gross"]) - item["fee"]
            if cash < 1_000_000:
                background_enabled = False
        if version >= 5 and background_enabled != bool(db.execute(
                "SELECT 1 FROM background_runs WHERE run_id=?", (run["id"],)).fetchone()):
            raise ValueError("Background sampling permission disagrees with the journal.")
        if (revision, status, last, active_cap) != (run["revision"], run["status"], run["updated"], run["entry_cap"]):
            raise ValueError("The public shadow run disagrees with its journal.")
