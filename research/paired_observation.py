"""Compare a Polygon notification plus public corroboration with interval-end polling.

Research only. Run with PYTHONPATH pointing at the source or installed release.
Requires websockets 15.0.1 in the research environment, outside the application.
"""

import argparse
import asyncio
from http.client import HTTPException
import json
import os
from pathlib import Path
import re
import time

from apps.server.observe import ACTIVITY, measure_trade, read_buy_page
from apps.server.public_depth import capacity_policy
from apps.server.public_fill import EXCHANGES, ORDER_FILLED, RPC
from apps.server.provider import validate_address


SOCKET = RPC.replace("https:", "wss:", 1)
SECONDS = 2
SERIES = 3
BUDGET = "10.00"
LOOKBACK = 10
RECHECK = 30
HASH = re.compile(r"0x[0-9a-f]{64}")


def now_ms():
    return time.time_ns() // 1_000_000


def candidate(log, owner):
    topics = log["topics"]
    if (not isinstance(topics, list) or len(topics) != 4 or topics[0] != ORDER_FILLED
            or topics[2] != owner or log["address"] not in EXCHANGES
            or not all(HASH.fullmatch(item) for item in topics[1:])
            or not HASH.fullmatch(log["transactionHash"]) or not HASH.fullmatch(log["blockHash"])
            or not re.fullmatch(r"0x(?:0|[1-9a-f][0-9a-f]{0,63})", log["logIndex"])
            or not re.fullmatch(r"0x[0-9a-f]{448}", log["data"])
            or type(log["removed"]) is not bool):
        raise ValueError("Invalid subscription evidence")
    data = log["data"][2:]
    side = int(data[:64], 16)
    if side not in (0, 1):
        raise ValueError("Unknown side")
    if side == 1:
        return None
    return {"transactionHash": log["transactionHash"], "tokenId": str(int(data[64:128], 16)),
            "logIndex": int(log["logIndex"], 16), "blockHash": log["blockHash"],
            "exchange": log["address"], "orderHash": topics[1], "removed": log["removed"]}


def check(wallet, start, end, trigger=None):
    try:
        trades, coverage, received = read_buy_page(wallet, start, end)
        result = {"wallet": wallet, "windowStartSeconds": start, "windowEndSeconds": end,
                  "activitySource": ACTIVITY, "activityCoverage": coverage, "activityReceivedMs": received}
        if trigger:
            matches = [trade for trade in trades if all(trade[k] == trigger[k] for k in ("transactionHash", "tokenId"))]
            if len(matches) != 1 or not coverage["complete"]:
                return dict(result, status="unconfirmed", matchCount=len(matches))
            chosen = matches[0]
        elif trades:
            chosen = min(trades, key=lambda trade: trade["eventTimeSeconds"])
        else:
            return dict(result, status="waiting" if coverage["complete"] else "incomplete")
        result = measure_trade(result, trades, chosen, BUDGET)
        if trigger and any(result["participant"].get(key) != trigger[key]
                           for key in ("logIndex", "blockHash", "exchange", "orderHash")):
            result.pop("capacity", None)
            result.update(status="unconfirmed", reason="Notification identity differed from the receipt.")
        return result
    except (KeyError, ValueError, HTTPException, OSError, ArithmeticError, TypeError, RecursionError) as exc:
        return {"status": "unavailable", "error": type(exc).__name__}


async def setup(sock, number, method, params):
    await sock.send(json.dumps(dict(jsonrpc="2.0", id=number, method=method, params=params)))
    reply = json.loads(await asyncio.wait_for(sock.recv(), 5))
    if reply.get("jsonrpc") != "2.0" or reply.get("id") != number or "error" in reply:
        raise ValueError("Invalid acknowledgment")
    return reply["result"]


async def window(wallet):
    from websockets.asyncio.client import connect
    from websockets.exceptions import WebSocketException

    owner = "0x" + "0" * 24 + wallet[2:]
    out = {"wallet": wallet, "streamStatus": "unavailable"}
    work = None
    try:
        async with connect(SOCKET, open_timeout=5, close_timeout=1, max_size=262144, max_queue=8) as sock:
            if await setup(sock, 1, "eth_chainId", []) != "0x89":
                raise ValueError("Wrong chain")
            filt = {"address": list(EXCHANGES), "topics": [ORDER_FILLED, None, owner]}
            subscription = await setup(sock, 2, "eth_subscribe", ["logs", filt])
            if not isinstance(subscription, str) or not re.fullmatch(r"0x[0-9a-f]{1,128}", subscription):
                raise ValueError("Invalid subscription")
            start = int(time.time()) + 1
            finish = start + SECONDS
            out.update(start=start, end=finish-1, notes=[])
            deadline = asyncio.get_running_loop().time() + max(0, finish-time.time())
            while (remaining := deadline - asyncio.get_running_loop().time()) > 0:
                try:
                    msg = json.loads(await asyncio.wait_for(sock.recv(), remaining))
                except TimeoutError:
                    break
                received = now_ms()
                if not start*1000 <= received < finish*1000:
                    continue
                if (msg.get("method") != "eth_subscription" or msg["params"]["subscription"] != subscription):
                    raise ValueError("Invalid notification")
                note = candidate(msg["params"]["result"], owner)
                if note:
                    out["notes"].append(dict(note, receivedMs=received))
                    if len(out["notes"]) >= 50:
                        raise ValueError("Notification limit")
                    if work is None and not note["removed"]:
                        when = received // 1000
                        work = asyncio.create_task(asyncio.to_thread(check, wallet, when-LOOKBACK, when, note))
            # Start the baseline at interval close without waiting for the connector to shut down.
            baseline = asyncio.create_task(asyncio.to_thread(check, wallet, start, finish-1))
            out["streamStatus"] = "complete"
        out["baseline"] = await baseline
    except (WebSocketException, OSError, ValueError, KeyError, TypeError, RecursionError) as exc:
        out["streamError"] = type(exc).__name__
    if work is not None:
        out["triggered"] = await work
    return out


def identity(event):
    return tuple(event[key] for key in ("transactionHash", "tokenId", "eventTimeSeconds", "price", "shares"))


def counts(row, later):
    if (row["streamStatus"] != "complete" or not later["coverage"]["complete"]
            or not row.get("baseline", {}).get("activityCoverage", {}).get("complete")
            or ("triggered" in row and not row["triggered"].get("activityCoverage", {}).get("complete"))
            or any(note["removed"] for note in row["notes"])):
        return None
    keys = [identity(event) for event in later["events"]]
    result = {"laterBuys": len(keys)}
    for arm in ("triggered", "baseline"):
        check_result = row.get(arm, {})
        estimated = check_result.get("capacity", {}).get("status") == "estimated"
        paired = estimated and keys.count(identity(check_result["event"])) == 1
        result[arm] = int(paired)
    return result


async def study(path, wallets):
    with path.open("x", encoding="utf-8") as output:
        def write(kind, **fields):
            output.write(json.dumps({"type": kind, **fields}, allow_nan=False) + "\n")
            output.flush()
            os.fsync(output.fileno())

        write("plan", wallets=wallets, recordedMs=now_ms(), comparison="first ordinary BUY at interval close vs first owned Polygon BUY notification with immediate public corroboration",
              windowsPerWallet=SERIES, secondsPerWindow=SECONDS, lookbackSeconds=LOOKBACK,
              recheckAfterSeriesSeconds=RECHECK, socket=SOCKET, exchanges=list(EXCHANGES),
              adoptionGate="Trigger-only paired estimates on two distinct source orders in two windows, no baseline-only usable window, and complete comparable evidence for every window. Otherwise keep polling.",
              **capacity_policy(BUDGET))
        rows = []
        for number in range(1, SERIES+1):
            for wallet in wallets:
                write("attempt", number=number, wallet=wallet, startedMs=now_ms())
                row = await window(wallet)
                write("window", number=number, **row)
                rows.append(row)
        await asyncio.sleep(RECHECK)
        paired = []
        gained_orders = set()
        for row in rows:
            if "start" not in row:
                continue
            try:
                events, coverage, received = await asyncio.to_thread(read_buy_page, row["wallet"], row["start"], row["end"])
                later = dict(events=events, coverage=coverage, receivedMs=received)
                result = counts(row, later)
                if result is not None:
                    paired.append(result)
                    if result["triggered"] and not result["baseline"]:
                        part = row["triggered"]["participant"]
                        gained_orders.add((part["exchange"], part["orderHash"]))
            except (OSError, HTTPException, KeyError, TypeError, ValueError, ArithmeticError, RecursionError) as exc:
                later, result = {"error": type(exc).__name__}, None
            write("laterReference", wallet=row["wallet"], start=row["start"], end=row["end"], comparison=result, **later)
        adopt = (len(paired) == len(rows) and len(gained_orders) >= 2
                 and all(p["baseline"] <= p["triggered"] for p in paired))
        summary = dict(windows=len(rows), comparable=len(paired), laterBuyRows=sum(p["laterBuys"] for p in paired),
                       pairedPollingEstimates=sum(p["baseline"] for p in paired),
                       pairedTriggeredEstimates=sum(p["triggered"] for p in paired),
                       distinctGainedOrders=len(gained_orders), decision="candidate for controlled integration" if adopt else "retain polling")
        write("summary", **summary)
        print(json.dumps(summary))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wallet", nargs=2, type=validate_address)
    parser.add_argument("--to", required=True, type=Path)
    args = parser.parse_args()
    if len(set(args.wallet)) != 2:
        parser.error("Choose distinct public wallets.")
    async def run():
        await asyncio.wait_for(study(args.to, args.wallet), timeout=240)

    asyncio.run(run())
