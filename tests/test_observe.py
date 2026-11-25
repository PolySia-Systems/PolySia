import unittest
from unittest.mock import patch

from apps.server import observe


WALLET = "0x" + "aa" * 20
START = 1_790_000_001


def activity(**changes):
    return {
        "proxy_wallet": WALLET, "timestamp": START, "condition_id": "0x" + "12" * 32,
        "type": "TRADE", "size": "14.285715", "price": "0.9300000035", "token_id": "734",
        "transaction_hash": "0x" + "fe" * 32, "side": "BUY", **changes,
    }


def page(rows, cursor=None):
    return {"data": rows, "pagination": {"has_more": cursor is not None, "next_cursor": cursor}}


def book(**changes):
    return {
        "market": "0x" + "12" * 32, "asset_id": "734", "timestamp": str((START + 2) * 1000),
        "min_order_size": "5", "tick_size": "0.01",
        "asks": [{"price": "0.97", "size": "19"}, {"price": "0.95", "size": "2.3"}],
        **changes,
    }


class ObservationTests(unittest.TestCase):
    def probe(self, *responses):
        with (
            patch.object(observe.time, "time", return_value=START - 0.2),
            patch.object(observe.time, "sleep"),
            patch.object(observe.time, "time_ns", return_value=(START + 2) * 1_000_000_000),
            patch.object(observe, "read_public_json", side_effect=responses) as reader,
        ):
            result = observe.observe(WALLET, 2)
        return result, reader.call_args_list

    def test_delayed_read_preserves_the_predeclared_window(self):
        with (
            patch.object(observe.time, "time", return_value=START - 1),
            patch.object(observe.time, "sleep") as wait,
            patch.object(observe, "read_public_json", return_value=page([])) as fetch,
        ):
            result = observe.observe(WALLET, 4, index_wait_seconds=60)
        self.assertEqual(result["indexWaitSeconds"], 60)
        self.assertEqual(result["status"], "waiting")
        self.assertEqual(fetch.call_args.args[1]["end"], START + 3)
        wait.assert_called_once_with(65)
        with self.assertRaises(ValueError):
            observe.observe(WALLET, 4, index_wait_seconds=301)

    def test_new_observation_followed_by_matching_book(self):
        result, calls = self.probe(page([activity(is_combo=True), activity(title="Market question?", outcome="Yes")]), book())
        endpoint, query = calls[0].args
        self.assertEqual(endpoint, observe.ACTIVITY)
        self.assertEqual((query["start"], query["end"]), (START, START + 1))
        self.assertEqual(query["user"], WALLET)
        self.assertEqual(calls[1].args, (observe.BOOK, {"token_id": "734"}))
        self.assertEqual(result["status"], "observed")
        self.assertIsNone(result["event"]["fillId"])
        self.assertEqual(result["event"]["price"], "0.9300000035")
        self.assertEqual((result["event"]["marketTitle"], result["event"]["outcomeLabel"]), ("Market question?", "Yes"))
        self.assertEqual(result["book"]["bestAsks"][0], {"price": "0.95", "shares": "2.3"})
        self.assertEqual(result["book"]["minimumOrderShares"], "5")
        self.assertEqual(result["book"]["priceTick"], "0.01")
        self.assertEqual(result["book"]["sourceAgeAtDetectionMs"], 0)
        self.assertEqual(result["book"]["bestAskMinusLeaderPrice"], "0.0199999965")
        self.assertLessEqual(result["activityReceivedMs"], result["bookRequestedMs"])
        self.assertLessEqual(result["bookRequestedMs"], result["bookReceivedMs"])

    def test_no_catchup_or_guessing(self):
        for response, status in [
            (page([activity(timestamp=START-1)]), "unavailable"),
            (page([activity(proxy_wallet="0x" + "bb"*20)]), "unavailable"),
            (page([activity(side="SELL")]), "unavailable"),
            (page([activity(is_combo=True)]), "waiting"), (page([]), "waiting"),
            (page([activity(is_combo=True)], "more"), "incomplete"), (TimeoutError(), "unavailable"),
        ]:
            with self.subTest(status=status, response=response):
                result, calls = self.probe(response)
                self.assertEqual(result["status"], status)
                self.assertEqual(len(calls), 1)
                self.assertNotIn("book", result)

    def test_capped_page_keeps_pairable_evidence_without_claiming_complete_coverage(self):
        rows = [activity()] * observe.LIMIT
        result, reads = self.probe(page(rows, "more"), book())
        self.assertEqual(len(reads), 2)
        self.assertEqual(reads[1].args, (observe.BOOK, {"token_id": "734"}))
        self.assertEqual(result["activityCoverage"], {
            "rowsReturned": 20, "ordinaryBuyRows": 20, "complete": False,
        })
        self.assertEqual(result["status"], "incomplete")
        self.assertIn("book", result)
        self.assertIsNone(result["event"]["fillId"])

    def test_book_failure_preserves_observation_without_executable_result(self):
        for response in [book(asset_id="735"), book(market="0x" + "ab"*32),
                         book(timestamp=None), TimeoutError()]:
            with self.subTest(response=response):
                result, _ = self.probe(page([activity()]), response)
                self.assertEqual(result["status"], "incomplete")
                self.assertIn("event", result)
                self.assertNotIn("book", result)

    def test_missing_or_stale_offers_preserve_partial_evidence(self):
        for response in [book(asks=[]), book(timestamp=str((START-10)*1000)),
                         book(timestamp=str((START+1)*1000)), book(timestamp=str((START+3)*1000))]:
            with self.subTest(response=response):
                result, _ = self.probe(page([activity()]), response)
                self.assertEqual(result["status"], "incomplete")
                self.assertIn("book", result)

    def test_measurements_remain_descriptive_on_stale_depth(self):
        older = book(timestamp=str((START + 2) * 1000 - 245))
        result, _ = self.probe(page([activity(price="0.95")]), older)
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["book"]["sourceAgeAtDetectionMs"], 245)
        self.assertEqual(result["book"]["bestAskMinusLeaderPrice"], "0.00")
        empty, _ = self.probe(page([activity()]), book(asks=[]))
        self.assertIsNone(empty["book"]["bestAskMinusLeaderPrice"])
