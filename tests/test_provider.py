import io
import json
import unittest
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from apps.server import provider


WALLET = "0x" + "ab" * 20


def row(**changes):
    return {
        "proxy_wallet": WALLET, "token_id": "212", "condition_id": "0x" + "cd" * 32,
        "status": "OPEN", "current_size": "100.000001", "title": "Sample market?",
        "outcome": "Yes", **changes,
    }


def envelope(rows, more=False):
    return {"data": rows, "pagination": {"has_more": more, "next_cursor": "opaque" if more else None}}


class AccountReadTests(unittest.TestCase):
    def test_optional_market_date_preserves_missing_evidence(self):
        for value, expected in (("2028-02-29", "2028-02-29"), ("2027-02-29", None), (None, None)):
            with self.subTest(value=value):
                snapshot = self.read(envelope([row(end_date=value)]))
                self.assertEqual(snapshot["status"], "available")
                self.assertEqual(snapshot["positions"][0].get("endDate"), expected)

    def test_wallet_aggregate_keeps_reported_precision_and_real_zero(self):
        for raw in ("248434.9443", "100000000000000000000000.0001", "0.00"):
            with self.subTest(raw=raw), patch.object(provider, "build_opener") as opener:
                response = '{"data":{"proxy_wallet":"' + WALLET + '","value":' + raw + '}}'
                opener.return_value.open.return_value = io.BytesIO(response.encode())
                result = provider.holdings_value(WALLET)
                request = opener.return_value.open.call_args.args[0]
                self.assertEqual(request.full_url, provider.VALUE_ENDPOINT + "?user=" + WALLET)
                self.assertEqual((result["status"], result["value"], result["unit"]), ("available", raw, "USDC"))
                self.assertEqual(result["observedAt"], result["checkedAt"])

    def test_wallet_aggregate_failure_preserves_unknown(self):
        valid = {"proxy_wallet": WALLET, "value": "10"}
        for response in (None, [], {"data": []}, {"data": None}, {"data": valid, "pagination": {}},
                         {"data": {**valid, "proxy_wallet": "0x" + "cd" * 20}},
                         *({"data": {**valid, "value": v}} for v in (None, True, "-1", "NaN", "3.00001"))):
            with self.subTest(response=response), patch.object(provider, "read_public_json", return_value=response):
                result = provider.holdings_value(WALLET)
                self.assertEqual(result["status"], "unavailable")
                self.assertIsNone(result["value"])
                self.assertIsNone(result["observedAt"])
                self.assertTrue(result["checkedAt"])
        with patch.object(provider, "read_public_json", side_effect=TimeoutError()):
            self.assertIn("Could not reach", provider.holdings_value(WALLET)["message"])

    def read(self, payload):
        with patch.object(provider, "_read_page", return_value=payload):
            return provider.inspect_account(WALLET)

    def test_network_contract_and_precision(self):
        # Insert an unquoted JSON decimal to exercise parsing before any float conversion.
        body = json.dumps(envelope([row(condition_id="0x" + "CD" * 32)])).replace('"100.000001"', '100.000000000000000001')
        with patch.object(provider, "build_opener") as opener:
            opener.return_value.open.return_value = io.BytesIO(body.encode())
            result = provider.inspect_account("0x" + "AB" * 20)
        request = opener.return_value.open.call_args.args[0]
        url = urlsplit(request.full_url)
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(request.get_header("User-agent"), provider.USER_AGENT)
        self.assertEqual(url.scheme, "https")
        self.assertEqual((url.netloc, url.path), ("data-api.polymarket.com", "/v2/positions"))
        self.assertEqual(parse_qs(url.query), {"user": [WALLET], "status": ["OPEN"], "limit": ["20"]})
        self.assertEqual(result["positions"], [
            {"conditionId": "0x" + "cd" * 32, "market": "Sample market?", "outcome": "Yes", "shares": "100.000000000000000001", "status": "OPEN"}])
        self.assertEqual(result["status"], "available")
        self.assertTrue(result["complete"])
        self.assertEqual(result["observedAt"], result["checkedAt"])

    def test_empty_and_partial_are_distinct(self):
        empty = self.read(envelope([]))
        self.assertTrue(empty["complete"])
        self.assertEqual(empty["positions"], [])
        partial = self.read(envelope([row(title=None, outcome=None, status="REDEEMABLE")], more=True))
        self.assertEqual(partial["positions"][0]["status"], "REDEEMABLE")
        self.assertEqual(partial["status"], "available")
        self.assertFalse(partial["complete"])
        self.assertEqual(partial["nextCursor"], "opaque")
        self.assertEqual(partial["positions"][0]["outcome"], "Outcome unavailable")

    def test_invalid_calls_never_reach_network(self):
        with patch.object(provider, "_read_page") as fetch:
            for invalid in (None, 2, " ", "bad", WALLET + "/?x", "0x" + "z" * 40):
                with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                    provider.inspect_account(invalid)
            fetch.assert_not_called()

    def test_incompatible_or_ambiguous_data_does_not_become_a_zero_balance(self):
        invalid = [
            [], {}, {"data": []}, {"data": [], "pagination": {"has_more": False}},
            {"data": [], "pagination": {"has_more": True, "next_cursor": None}},
            envelope([row(), row()]), envelope([row(proxy_wallet="0x" + "00" * 20)]),
            envelope([row(condition_id="same market title")]), envelope([row(status="CLOSED")]), envelope([row(current_size=True)]),
            envelope([row(current_size="1e500000000")]), envelope([row(current_size="-1")]),
            envelope([row(current_size="malformed")]), envelope([row(current_size="NaN")]),
        ]
        for data in invalid:
            with self.subTest(data=data):
                failed = self.read(data)
                self.assertEqual(failed["status"], "unavailable")
                self.assertIsNone(failed["observedAt"])
                self.assertFalse(failed["complete"])

    def test_failure_detail_is_bounded_and_redacted(self):
        errors = [(URLError(WALLET), "Could not reach"), (TimeoutError(WALLET), "Could not reach"),
                  (HTTPError(WALLET, 429, "retry", {}, None), "rate-limited"),
                  (HTTPError(WALLET, 403, "forbidden", {}, None), "HTTP 403")]
        for error, reason in errors:
            with self.subTest(error=error), patch.object(provider, "_read_page", side_effect=error):
                result = provider.inspect_account(WALLET)
                self.assertIn(reason, result["message"])
                self.assertNotIn(WALLET, result["message"])
                self.assertFalse(result["complete"])

    def test_oversized_body_is_rejected(self):
        with patch.object(provider, "build_opener") as opener:
            opener.return_value.open.return_value = io.BytesIO(b" " * (provider.MAX_BODY_BYTES + 1))
            result = provider.inspect_account(WALLET)
        self.assertEqual(result["status"], "unavailable")
        self.assertIn("contract", result["message"])


if __name__ == "__main__":
    unittest.main()
