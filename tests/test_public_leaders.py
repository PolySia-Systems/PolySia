import unittest
from decimal import Decimal
from urllib.error import HTTPError
from unittest.mock import patch

from apps.server import public_leaders


def row(n=1, **changes):
    return {"user_id": f"0x{n:040x}", "rank": n, "pnl": Decimal("-0.0000001"),
            "volume": "200.000001", "user_name": f"Trader {n}", **changes}


def page(rows, more=False):
    return {"data": rows, "pagination": {"next_cursor": "opaque" if more else None, "has_more": more}}


class PublicLeaderboardTests(unittest.TestCase):
    def test_finite_window_keeps_provider_units_ranks_and_scope(self):
        response = page([row(), row(2, rank=1), row(3, user_name=None)], more=True)
        with patch.object(public_leaders, "read_public_json", return_value=response) as reader:
            result = public_leaders.leaderboard("month")
        reader.assert_called_once_with("https://data-api.polymarket.com/v2/leaderboard",
                                       {"time_period": "month", "sort_by": "PNL", "limit": 10})
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["observedAt"], result["checkedAt"])
        self.assertFalse(result["complete"])
        self.assertEqual(result["nextCursor"], "opaque")
        self.assertEqual([x["rank"] for x in result["leaders"]], [1, 1, 3])
        self.assertEqual(result["leaders"][0]["pnl"], "-0.0000001")
        self.assertEqual(result["leaders"][0]["volumeShares"], "200.000001")
        self.assertEqual(result["leaders"][2]["name"], row(3)["user_id"])

    def test_continuation_preserves_sort_and_period_and_requires_progress(self):
        cursor = "next+/="
        with patch.object(public_leaders, "read_public_json", return_value=page([row(11)])) as read:
            result = public_leaders.leaderboard("week", cursor)
        read.assert_called_once_with(public_leaders.ENDPOINT, {"time_period": "week", "sort_by": "PNL", "cursor": cursor})
        self.assertEqual((result["leaders"][0]["rank"], result["nextCursor"], result["complete"]), (11, None, True))
        with patch.object(public_leaders, "read_public_json", return_value=page([row(11)], more=True)):
            self.assertEqual(public_leaders.leaderboard("week", "opaque")["status"], "unavailable")
        with patch.object(public_leaders, "read_public_json") as read:
            for invalid in ("", "x" * 4097):
                with self.assertRaises(ValueError):
                    public_leaders.leaderboard("week", invalid)
            read.assert_not_called()

    def test_unavailable_and_empty_do_not_return_scenario_data(self):
        for fixture in (page([row(volume=-1)]), page([row(), row()]), page([row(rank=0)]),
                        page([row(2), row()]), page([row(pnl=None)]), page([row(user_name=[])])):
            with self.subTest(fixture=fixture), patch.object(public_leaders, "read_public_json", return_value=fixture):
                result = public_leaders.leaderboard()
                self.assertIsNone(result["observedAt"])
                self.assertEqual((result["status"], result["leaders"], result["complete"]),
                                 ("unavailable", [], False))
        with patch.object(public_leaders, "read_public_json", return_value=page([])):
            result = public_leaders.leaderboard("all")
            self.assertEqual((result["status"], result["leaders"], result["complete"]), ("available", [], True))
        with patch.object(public_leaders, "read_public_json", side_effect=HTTPError("", 403, "", {}, None)):
            self.assertIn("403", public_leaders.leaderboard()["message"])
        with patch.object(public_leaders, "read_public_json") as reader, self.assertRaises(ValueError):
            public_leaders.leaderboard("tomorrow")
        reader.assert_not_called()
