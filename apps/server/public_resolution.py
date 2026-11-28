"""Read binary CTF settlement for an identified simulated holding. No journal writes."""

import re
from datetime import UTC, datetime
from http.client import HTTPException

from . import polygon
from .provider import units_from_micros


CTF = "0x4d97dcd97ec945f40cf65f87097ace5ea0476045"
AUTO_REDEEMER = "0xa1200000d0002264c9a1698e001292d00e1b00af"


def _word(value):
    return f"{value:064x}"


def _reads(block_hash, calls):
    block = {"blockHash": block_hash, "requireCanonical": True}
    responses = polygon._read_many([("eth_call", [{"to": contract, "data": "0x" + data}, block])
                                    for contract, data in calls])
    if any(not isinstance(r, str) or not re.fullmatch("0x[0-9a-fA-F]{64}", r) for r in responses):
        raise ValueError("Incomplete contract word")
    return [int(r, 16) for r in responses]


def finalized_head():
    try:
        return polygon._read("eth_getBlockByNumber", ["finalized", False])
    except (OSError, HTTPException, TypeError, ValueError, RecursionError):
        return None


def read(basis):
    return read_at(basis, finalized_head())


def read_at(basis, head):
    condition, token = basis["conditionId"], basis["tokenId"]
    result = {**basis, "source": polygon.RPC, "chainId": 137, "contract": CTF, "blockNumber": None,
              "blockHash": None, "blockTime": None, "status": "unavailable", "numerator": None,
              "denominator": None, "payout": None, "unit": "USDC.e equivalent"}
    try:
        digest = head["hash"]
        if not re.fullmatch("0x[0-9a-fA-F]{64}", digest) or not re.fullmatch("0x[0-9a-fA-F]{64}", condition):
            raise ValueError("Invalid block or condition ID")
        block_time = int(head["timestamp"], 16)
        if not 0 <= datetime.now(UTC).timestamp() - block_time <= 3600:
            raise ValueError("Stale finalized block")
        result.update(blockHash=digest, blockNumber=int(head["number"], 16),
                      blockTime=datetime.fromtimestamp(block_time, UTC).isoformat(timespec="seconds"))
        key = condition[2:]
        # The official adapter exposes the two collateral identities used in CTF position derivation.
        # Read the CTF vector and both root collection IDs at the same finalized block.
        count, denominator, first, second, yes, no, standard, wrapped = _reads(digest, [
            (CTF, "d42dc0c2" + key), (CTF, "dd34de67" + key),
            (CTF, "0504c814" + key + _word(0)), (CTF, "0504c814" + key + _word(1)),
            (CTF, "856296f7" + _word(0) + key + _word(1)), (CTF, "856296f7" + _word(0) + key + _word(2)),
            (AUTO_REDEEMER, "195187e1"), (AUTO_REDEEMER, "2d277260")])
        if count != 2 or denominator != first + second or yes == no or standard == wrapped or not all(
                0 < address < 2**160 for address in (standard, wrapped)):
            raise ValueError("Inconsistent binary CTF data")
        candidates = _reads(digest, [(CTF, "39dd7530" + _word(collateral) + _word(collection))
                                     for collateral in (standard, wrapped) for collection in (yes, no)])
        if len(set(candidates)) != 4 or int(token) not in candidates:
            raise ValueError("Unsupported token identity")
        index = candidates.index(int(token))
        result.update(slot=index % 2, collateral="0x" + f"{(standard, wrapped)[index // 2]:040x}",
                      denominator=str(denominator))
        if denominator == 0:
            result.update(status="unresolved", reason="No final payout is recorded on this contract. A delay or dispute can remain unresolved.")
        else:
            numerator = (first, second)[index % 2]
            amount = int(basis["shares"]) * 1_000_000 * numerator // denominator
            result.update(status="resolved", numerator=str(numerator), payout=units_from_micros(amount),
                          reason="Final payout for the simulated shares, before any redemption costs.")
    except (KeyError, OSError, HTTPException, TypeError, ValueError, OverflowError, RecursionError):
        result["reason"] = "Could not verify this binary CTF outcome on Polygon. Its payout is unknown."
    result["checkedAt"] = datetime.now(UTC).isoformat(timespec="seconds")
    return result
