import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from apps.server.study import record_study


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
            self.assertEqual(records[0]["budget"], "10.00")
            self.assertEqual([r["type"] for r in records], ["plan"] + ["attempt", "window"]*4 + ["summary"])
            self.assertEqual([r["number"] for r in records if r["type"] == "window"], [1, 2, 3, 4])
            self.assertTrue(all(call.args == (wallet, 2, "10.00") for call in sample.call_args_list))
            with self.assertRaises(FileExistsError):
                record_study(path, wallet, "10", 2, 4)
            self.assertEqual(path.read_bytes(), data)
            self.assertEqual(sample.call_count, 4)

    def test_interrupted_series_retains_attempt_and_omits_completion(self):
        with tempfile.TemporaryDirectory() as tmp, patch("apps.server.study.sample_once", side_effect=KeyboardInterrupt):
            path = Path(tmp) / "study.jsonl"
            with self.assertRaises(KeyboardInterrupt):
                record_study(path, "0x" + "aa"*20, "5", 2, 2)
            records = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual([r["type"] for r in records], ["plan", "attempt"])
            self.assertEqual(records[0]["windows"], 2)
