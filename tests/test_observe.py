import subprocess
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

    def test_activity_collateral_preserves_missing_or_exact_provider_value(self):
        for row, expected in [(activity(usdc_size="6.359370"), "6.359370"), (activity(usdc_size=None), None)]:
            result, _ = self.probe(page([row]), book())
            self.assertEqual(result["event"]["reportedCollateral"], expected)
        result, _ = self.probe(page([activity()]), book())
        self.assertNotIn("reportedCollateral", result["event"])
        for invalid in ("not-an-amount", True, "1e1000"):
            with self.subTest(invalid=invalid):
                result, calls = self.probe(page([activity(usdc_size=invalid)]))
                self.assertEqual(result["status"], "unavailable")
                self.assertEqual(len(calls), 1)

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


class SecondReadTests(unittest.TestCase):
    def sample(self, *pages):
        start_ms = START * 1000
        now = start_ms - 500
        lookups = []
        responses = iter(pages)

        def sleep(seconds):
            nonlocal now
            now += round(seconds * 1000)

        def fetch(endpoint, params):
            nonlocal now
            if endpoint == observe.BOOK:
                return book(timestamp=str(now), neg_risk=False, asks=[{"price": "0.51", "size": "25"}],
                            bids=[{"price": "0.49", "size": "15"}])
            self.assertEqual(endpoint, observe.ACTIVITY)
            lookups.append((now, params["start"], params["end"]))
            duration_ms, response = next(responses)
            now += duration_ms
            if isinstance(response, Exception):
                raise response
            return response

        def market(event):
            return {"status": "available", "checkedMs": now, "acceptingOrders": True, "takerDelayMs": 0,
                    "negativeRisk": False, "priceTick": "0.01", "minimumOrderSize": "5", "takerRate": "0.05"}

        def participant(wallet, event):
            standard = next(k for k, negative in observe.public_fill.EXCHANGES.items() if not negative)
            return {"status": "matched", "checkedMs": now, "exchange": standard}

        with (patch.object(observe.time, "time", side_effect=lambda: now / 1000),
              patch.object(observe.time, "time_ns", side_effect=lambda: now * 1_000_000),
              patch.object(observe.time, "sleep", side_effect=sleep),
              patch.object(observe, "read_public_json", side_effect=fetch),
              patch.object(observe.public_depth, "market_terms", side_effect=market) as terms,
              patch.object(observe.public_fill, "identify_buy", side_effect=participant) as identity):
            receipt = observe.observe(WALLET, 2, budget="10", retry_empty=True)
        self.assertEqual(terms.call_count, identity.call_count)
        self.assertEqual(len(lookups), len(pages))
        self.assertEqual([(lower, upper) for _, lower, upper in lookups], [(START, START + 1)] * len(lookups))
        self.assertEqual([r["requestedMs"] for r in receipt["activityReads"]], [ms for ms, _, _ in lookups])
        return receipt, identity.call_count

    def test_newly_visible_buy_uses_the_second_receipt_for_the_full_delayed_check(self):
        result, checks = self.sample((650, page([])), (400, page([activity(price="0.50")])))
        self.assertEqual(result["schemaVersion"], 3)
        self.assertEqual(result["retryAfterWindowMs"], 3000)
        self.assertEqual(result["detectionRead"], 2)
        first, second = result["activityReads"]
        start_ms = START * 1000
        self.assertEqual((first["requestedMs"], first["receivedMs"]), (start_ms + 2000, start_ms + 2650))
        self.assertEqual((second["requestedMs"], second["receivedMs"]), (start_ms + 5000, start_ms + 5400))
        self.assertEqual(first["activityCoverage"]["ordinaryBuyRows"], 0)
        self.assertEqual(result["activityCoverage"], second["activityCoverage"])
        self.assertEqual(result["activityReceivedMs"], second["receivedMs"])
        self.assertEqual(checks, 1)
        self.assertEqual(result["bookRequestedMs"], start_ms + 7400)
        self.assertEqual(result["capacity"]["status"], "estimated")

    def test_visible_initial_buy_does_not_trigger_another_read(self):
        result, checks = self.sample((420, page([activity(price="0.50")])))
        self.assertEqual(result["detectionRead"], 1)
        self.assertEqual(result["capacity"]["status"], "estimated")
        self.assertEqual(checks, 1)

    def test_slow_first_response_rechecks_immediately_and_skips_expired_buy(self):
        result, checks = self.sample((4000, page([])), (2001, page([activity()])))
        self.assertEqual(result["activityReads"][1]["requestedMs"], result["activityReads"][0]["receivedMs"])
        self.assertEqual(result["detectionRead"], 2)
        self.assertEqual(result["event"]["eventTimeSeconds"], START)
        self.assertEqual(result["capacity"]["status"], "skipped")
        self.assertNotIn("bookRequestedMs", result)
        self.assertEqual(checks, 0)

    def test_expired_empty_window_is_distinct_from_two_successful_empty_reads(self):
        expired, checks = self.sample((7001, page([])))
        self.assertEqual(expired["status"], "incomplete")
        self.assertIn("skipped", expired["reason"])
        self.assertEqual(checks, 0)
        # Latest possible source second still has exactly the declared delay left.
        empty, checks = self.sample((7000, page([])), (100, page([])))
        self.assertEqual(empty["status"], "waiting")
        self.assertNotIn("detectionRead", empty)
        self.assertEqual(checks, 0)

    def test_unusable_pages_never_gain_complete_coverage(self):
        partial = page([activity(is_combo=True)], "more")
        for pages, status in [([(100, partial)], "incomplete"), ([(100, TimeoutError())], "unavailable"),
                              ([(100, page([])), (200, partial)], "incomplete"),
                              ([(100, page([])), (200, TimeoutError())], "unavailable"),
                              ([(100, page([])), (200, page([activity(timestamp=START-1)]))], "unavailable")]:
            with self.subTest(status=status, pages=pages):
                result, checks = self.sample(*pages)
                self.assertEqual(result["status"], status)
                self.assertNotIn("detectionRead", result)
                self.assertEqual(checks, 0)
                if status == "unavailable":
                    self.assertIn("reason", result["activityReads"][-1])
                    self.assertNotIn("activityCoverage", result)
                    self.assertNotIn("activityReceivedMs", result)
                if len(pages) == 2:
                    self.assertEqual(result["activityReads"][0]["activityCoverage"]["ordinaryBuyRows"], 0)

    def test_backward_receipt_clock_keeps_coverage_but_cannot_establish_timeliness(self):
        result, checks = self.sample((100, page([])), (-1, page([activity()])))
        self.assertEqual(result["status"], "incomplete")
        self.assertIn("preceded", result["activityReads"][-1]["reason"])
        self.assertEqual(result["activityCoverage"]["ordinaryBuyRows"], 1)
        self.assertNotIn("detectionRead", result)
        self.assertEqual(checks, 0)

    def test_cli_opt_in_has_a_bounded_deadline_and_rejects_incompatible_windows(self):
        for seconds, budget, wait, retry in [(1, "10", 0, True), (2, None, 0, True),
                                             (2, "10", 1, True), (2, "10", 0, 1)]:
            with self.subTest(seconds=seconds, budget=budget, wait=wait, retry=retry), self.assertRaises(ValueError):
                observe.observe(WALLET, seconds, wait, budget=budget, retry_empty=retry)
        with patch.object(observe.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, b"{}")) as run:
            observe.sample_once(WALLET, 2, "10", retry_empty=True)
            self.assertIn("--retry-empty", run.call_args.args[0])
            self.assertEqual(run.call_args.kwargs["timeout"], 39)
