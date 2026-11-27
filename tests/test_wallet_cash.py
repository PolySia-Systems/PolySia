import json
import unittest
from unittest.mock import patch

from apps.server import polygon


ADDRESS = '0x' + 'ab' * 20
CHAIN = {"jsonrpc": "2.0", "id": 1, "result": "0x89"}


class WalletCashTests(unittest.TestCase):
    def test_exact_balance_and_zero_use_the_fixed_polygon_token(self):
        for amount, expected in [(0, "0"), (1, "0.000001"), (12_345_678, "12.345678")]:
            token = {"jsonrpc": "2.0", "id": 2, "result": f"0x{amount:064x}"}
            with self.subTest(amount=amount), patch.object(polygon, "read_json_response", return_value=[token, CHAIN]) as read:
                result = polygon.cash_balance(ADDRESS)
                req = read.call_args.args[0]
                self.assertEqual(req.full_url, polygon.RPC)
                self.assertEqual([(r["method"], r["params"]) for r in json.loads(req.data)], [
                    ("eth_chainId", []),
                    ("eth_call", [{"to": "0xc011a7e12a19f7b1f670d46f03b03f3342e82dfb",
                                   "data": "0x70a08231" + "00" * 12 + ADDRESS[2:]}, "latest"])])
                self.assertEqual((result["address"], result["status"], result["value"], result["unit"]),
                                 (ADDRESS, "available", expected, "pUSD"))
                self.assertEqual(result["checkedAt"], result["observedAt"])

    def test_unverified_balance_stays_unknown(self):
        zero = {"jsonrpc": "2.0", "id": 2, "result": "0x" + "0" * 64}
        for reply in ([dict(CHAIN, result="0x1"), zero], [CHAIN, dict(zero, result="0x0")],
                      [CHAIN, dict(zero, result=None)], [CHAIN, dict(zero, error={})], [CHAIN, CHAIN]):
            with self.subTest(reply=reply), patch.object(polygon, "read_json_response", return_value=reply):
                result = polygon.cash_balance(ADDRESS)
                self.assertEqual((result["status"], result["value"], result["observedAt"]), ("unavailable", None, None))
        with patch.object(polygon, "read_json_response", side_effect=TimeoutError()):
            self.assertIsNone(polygon.cash_balance(ADDRESS)["value"])
        with patch.object(polygon, "read_json_response") as read, self.assertRaises(ValueError):
            polygon.cash_balance("invalid")
        read.assert_not_called()
