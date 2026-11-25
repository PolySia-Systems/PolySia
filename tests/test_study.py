import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from apps.server.observe import RETRY_AFTER_WINDOW_MS
from apps.server.study import REFERENCE_TIMEOUT_SECONDS, _recheck_activity, record_study


class StudyTests(unittest.TestCase):
    def test_all_windows_recorded_and_related_fills_counted_once(self):
        wallet = "0x" + "aa"*20
        observed = {"status": "observed", "participant": {"status": "matched", "fillId": "a",
                    "exchange": "example", "orderHash": "shared"}, "capacity": {"status": "estimated"}}
        trials = [observed, observed, {"status": "waiting"}, TimeoutError()]
        with tempfile.TemporaryDirectory() as tmp, patch("apps.server.study.sample_once", side_effect=trials) as sample:
            path = Path(tmp) / "study.jsonl"
            summary = record_study(path, wallet, "10", 2, 4)
            self.assertEqual(summary, {"windows": 4, "outcomes": {"estimated": 2, "waiting": 1, "unavailable": 1},
                                       "distinctParticipantFills": 1, "distinctSourceOrders": 1})
            data = path.read_bytes()
            records = [json.loads(line) for line in data.splitlines()]
            self.assertEqual(records[0]["schemaVersion"], 2)
            self.assertNotIn("retryEmpty", records[0])
            self.assertEqual(records[0]["budget"], "10.00")
            self.assertEqual([r["type"] for r in records], ["plan"] + ["attempt", "window"]*4 + ["summary"])
            self.assertEqual([r["number"] for r in records if r["type"] == "window"], [1, 2, 3, 4])
            self.assertTrue(all(call.args == (wallet, 2, "10.00") for call in sample.call_args_list))
            with self.assertRaises(FileExistsError):
                record_study(path, wallet, "10", 2, 4)
            self.assertEqual(path.read_bytes(), data)
            self.assertEqual(sample.call_count, 4)

    def test_later_activity_is_paired_without_backfilling_a_decision(self):
        wallet = "0x" + "aa" * 20
        trials = [{"status": "waiting", "windowStartSeconds": n, "windowEndSeconds": n + 1}
                  for n in (100, 110, 120, 130)]
        reads = [([{"shares": "5"}], {"complete": False}, 201000),
                 ([], {"complete": True}, 202000), ([], {"complete": False}, 203000), TimeoutError()]
        with (tempfile.TemporaryDirectory() as tmp,
              patch("apps.server.study.sample_once", side_effect=[*trials, TimeoutError()]),
              patch("apps.server.study.time.sleep") as wait,
              patch("apps.server.study._reference_page", side_effect=reads) as read):
            path = Path(tmp) / "paired.jsonl"
            summary = record_study(path, wallet, "10", 2, 5, recheck_after=30)
            wait.assert_called_once_with(30)
            self.assertEqual([c.args for c in read.call_args_list],
                             [(wallet, n, n + 1) for n in (100, 110, 120, 130)])
            self.assertEqual(summary["outcomes"], {"waiting": 4, "unavailable": 1})
            self.assertEqual(summary["waitingWindowsWithLaterBuy"], 1)
            self.assertEqual(summary["waitingWindowsCompared"], 2)
            records = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(records[0]["recheckAfterSeriesSeconds"], 30)
            rechecks = records[-6:-1]
            self.assertEqual([r["type"] for r in rechecks], ["activityRecheck"] * 5)
            self.assertEqual(rechecks[0]["visibleBuys"], [{"shares": "5"}])
            self.assertIn("reason", rechecks[-1])
            self.assertIn("reason", rechecks[-2])

    def test_retry_counts_follow_actual_reads_and_compare_initially_empty_windows(self):
        wallet = "0x" + "ab" * 20

        def read(ordinary, complete=True):
            return {"requestedMs": 103000, "receivedMs": 103100,
                    "activityCoverage": {"ordinaryBuyRows": ordinary, "rowsReturned": ordinary,
                                         "complete": complete}}

        def receipt(reads, status, *, detected=None, capacity=None):
            result = {"schemaVersion": 3, "windowStartSeconds": 101, "windowEndSeconds": 102,
                      "activityReads": reads, "status": status}
            if detected:
                result["detectionRead"] = detected
            if capacity:
                result["capacity"] = {"status": capacity}
            return result

        trials = [receipt([read(1)], "observed", detected=1, capacity="estimated"),
                  receipt([read(0), read(1)], "observed", detected=2, capacity="estimated"),
                  receipt([read(0), read(2, False)], "incomplete", detected=2, capacity="incomplete"),
                  receipt([read(0), {"requestedMs": 106000, "reason": "unavailable"}], "unavailable"),
                  receipt([read(0), read(0, False)], "incomplete"),
                  receipt([read(0), read(0)], "waiting"),
                  receipt([read(0, False)], "incomplete"), TimeoutError()]
        positive = ([{"shares": "1"}], {"complete": False}, 130000)
        negative = ([], {"complete": True}, 130000)
        unknown = ([], {"complete": False}, 130000)
        references = [positive, positive, unknown, TimeoutError(), negative, positive, positive]
        with (tempfile.TemporaryDirectory() as tmp,
              patch("apps.server.study.sample_once", side_effect=trials) as sample,
              patch("apps.server.study._reference_page", side_effect=references) as reference,
              patch("apps.server.study.time.sleep")):
            path = Path(tmp) / "study.jsonl"
            summary = record_study(path, wallet, "5", 2, len(trials), recheck_after=10, retry_empty=True)
            self.assertTrue(all(c.kwargs == {"retry_empty": True} for c in sample.call_args_list))
            records = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(records[0]["schemaVersion"], 3)
            self.assertEqual(records[0]["maxActivityReadsPerWindow"], 2)
            self.assertEqual(records[0]["retryAfterWindowMs"], RETRY_AFTER_WINDOW_MS)
            self.assertTrue(records[0]["retryEmpty"])
            self.assertEqual(records[-1], {"type": "summary", **summary})
            self.assertEqual(reference.call_count, len(trials) - 1)
            self.assertEqual(summary, {
                "windows": 8, "outcomes": {"estimated": 2, "incomplete": 3, "unavailable": 2, "waiting": 1},
                "distinctParticipantFills": 0, "distinctSourceOrders": 0,
                "firstReadDetections": 1, "initiallyEmptyWindows": 5, "retriesAttempted": 5,
                "secondReadDetections": 2, "secondReadCapacityEstimates": 1,
                "secondReadsUnavailable": 1, "secondReadsPartial": 2, "windowsWithoutReadEvidence": 1,
                "initiallyEmptyWindowsCompared": 3, "initiallyEmptyWindowsWithLaterBuy": 2,
            })

    def test_retry_requires_two_seconds_before_creating_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "study.jsonl"
            with self.assertRaisesRegex(ValueError, "--seconds 2"):
                record_study(path, "0x" + "aa" * 20, "5", 3, 2, retry_empty=True)
            self.assertFalse(path.exists())

    def test_recheck_has_a_wall_clock_deadline_and_keeps_window_on_timeout(self):
        wallet = "0x" + "ab" * 20
        receipt = {"windowStartSeconds": 101, "windowEndSeconds": 102}
        with patch("apps.server.study.subprocess.run", side_effect=subprocess.TimeoutExpired("read", 12)) as child:
            result = _recheck_activity(wallet, receipt)
        self.assertEqual(child.call_args.kwargs["timeout"], REFERENCE_TIMEOUT_SECONDS)
        self.assertEqual(child.call_args.args[0][-3:], [wallet, "101", "102"])
        self.assertEqual(result["windowStartSeconds"], 101)
        self.assertIn("reason", result)
        self.assertNotIn("activityCoverage", result)

    def test_interrupted_series_retains_attempt_and_omits_completion(self):
        with tempfile.TemporaryDirectory() as tmp, patch("apps.server.study.sample_once", side_effect=KeyboardInterrupt):
            path = Path(tmp) / "study.jsonl"
            with self.assertRaises(KeyboardInterrupt):
                record_study(path, "0x" + "aa"*20, "5", 2, 2)
            records = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual([r["type"] for r in records], ["plan", "attempt"])
            self.assertEqual(records[0]["windows"], 2)
