import unittest
from unittest.mock import patch

from apps.server import public_history

ADDRESS = "0x" + "ad" * 20


def series(**changes):
    return {"data": {
        "proxy_wallet": ADDRESS, "interval": "1w", "fidelity": "1d", "source_fidelity": "1h",
        "points": [{"timestamp": 1, "realized_pnl": "100.000000001"},
                   {"timestamp": 86401, "realized_pnl": None},
                   {"timestamp": 172801, "realized_pnl": "140.000000001"}], **changes,
    }}


class PublicHistoryTest(unittest.TestCase):
    def test_cumulative_observations_are_preserved_without_summing_or_imputing(self):
        with patch.object(public_history, "read_public_json", return_value=series()) as fetch:
            result = public_history.pnl_history(ADDRESS)
        fetch.assert_called_once_with(public_history.ENDPOINT, {"user": ADDRESS, "interval": "1w", "fidelity": "1d"})
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["sourceGrid"], "1h")
        self.assertEqual([p["value"] for p in result["points"]], ["100.000000001", None, "140.000000001"])

    def test_empty_failed_and_mismatched_series(self):
        for payload in [series(proxy_wallet="0x" + "aa" * 20), series(interval="all"), series(fidelity="1h"),
                        series(points=[{"timestamp": 0, "realized_pnl": 1}]),
                        series(points=[{"timestamp": 1, "realized_pnl": 1}] * 2)]:
            with self.subTest(payload=payload), patch.object(public_history, "read_public_json", return_value=payload):
                self.assertEqual(public_history.pnl_history(ADDRESS)["status"], "unavailable")
        with patch.object(public_history, "read_public_json", return_value={"data": None}):
            empty = public_history.pnl_history(ADDRESS)
        self.assertEqual((empty["status"], empty["points"]), ("available", []))
