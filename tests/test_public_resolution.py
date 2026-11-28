import copy
import json
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from apps.server import polygon, public_resolution as resolution


FIXTURES = json.loads((Path(__file__).parent / "fixtures/polygon-resolution.json").read_text())


def replay(record, *, token=None, age=10):
    batches = []
    def rpc(request):
        calls = json.loads(request.data)
        assert request.full_url == polygon.RPC
        assert calls[0]["method"] == "eth_chainId"
        values = ["0x89", *record["responses"][len(batches)]]
        assert len(values) == len(calls)
        batches.append(calls[1:])
        return list(reversed([{"jsonrpc": "2.0", "id": c["id"], "result": value} for c, value in zip(calls, values)]))
    now = int(record["responses"][0][0]["timestamp"], 16) + age
    basis = dict(record["basis"])
    if token is not None:
        basis["tokenId"] = token
    with patch.object(polygon, "read_json_response", side_effect=rpc), patch.object(resolution, "datetime", wraps=datetime) as clock:
        clock.now.return_value = datetime.fromtimestamp(now, UTC)
        result = resolution.read(basis)
    return result, batches


class ResolutionTests(unittest.TestCase):
    def test_recorded_standard_and_negative_risk_words_pin_chain_block_and_token(self):
        for record in FIXTURES:
            result, batches = replay(record)
            self.assertEqual({k: result[k] for k in record["expected"]}, record["expected"])
            self.assertEqual([[c["method"] for c in b] for b in batches],
                             [["eth_getBlockByNumber"], ["eth_call"] * 8, ["eth_call"] * 4])
            self.assertEqual(batches[0][0]["params"], ["finalized", False])
            for call in [*batches[1], *batches[2]]:
                self.assertEqual(call["params"][1], {"blockHash": result["blockHash"], "requireCanonical": True})
                self.assertIn(call["params"][0]["to"], (resolution.CTF, resolution.AUTO_REDEEMER))
            self.assertEqual([c["params"][0]["data"][:10] for c in batches[1]],
                             ["0xd42dc0c2", "0xdd34de67", "0x0504c814", "0x0504c814", "0x856296f7", "0x856296f7",
                              "0x195187e1", "0x2d277260"])
            self.assertEqual([c["params"][0]["data"][:10] for c in batches[2]], ["0x39dd7530"] * 4)
        losing = FIXTURES[0]
        other = str(int(losing["responses"][2][1], 16))
        winner, _ = replay(losing, token=other)
        self.assertEqual((winner["numerator"], winner["denominator"], winner["payout"]), ("1", "1", "19"))

    def test_partial_payout_rounds_down_to_collateral_precision_and_uncertainty_stays_unknown(self):
        record = copy.deepcopy(FIXTURES[0])
        word = lambda n: f"0x{n:064x}"
        record["responses"][1][1:4] = [word(3), word(1), word(2)]
        partial, _ = replay(record)
        self.assertEqual((partial["status"], partial["payout"]), ("resolved", "6.333333"))
        for token, age in (("734", 0), (None, 3601), (None, -1)):
            unknown, _ = replay(record, token=token, age=age)
            self.assertEqual((unknown["status"], unknown["payout"]), ("unavailable", None))
        record["responses"][1][1] = word(1)
        unknown, _ = replay(record)
        self.assertEqual((unknown["status"], unknown["numerator"]), ("unavailable", None))
