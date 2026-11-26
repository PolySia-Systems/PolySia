"""Keep incomplete, removed or ambiguously matched observations out of paired evidence."""

import unittest

from research.paired_observation import counts


class PairedEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.trade = {"transactionHash": "tx", "tokenId": "7", "eventTimeSeconds": 100,
                      "price": "0.2", "shares": "5"}
        self.reference = {"events": [self.trade], "coverage": {"complete": True}}
        self.row = {"streamStatus": "complete", "notes": [],
                    "baseline": {"event": self.trade, "capacity": {"status": "estimated"},
                                 "activityCoverage": {"complete": True}},
                    "triggered": {"status": "unconfirmed", "activityCoverage": {"complete": True}}}

    def test_only_unique_later_source_rows_pair_with_prospective_estimates(self):
        self.assertEqual(counts(self.row, self.reference), {"laterBuys": 1, "baseline": 1, "triggered": 0})
        for rows in ([dict(self.trade, tokenId="8")], [self.trade, self.trade], []):
            with self.subTest(rows=rows):
                result = counts(self.row, dict(self.reference, events=rows))
                self.assertEqual(result["baseline"], 0)

    def test_partial_and_unavailable_reads_and_removed_logs_leave_unknown_comparison(self):
        for row in (dict(self.row, triggered={"status": "unavailable"}),
                    dict(self.row, baseline={"activityCoverage": {"complete": False}}),
                    dict(self.row, notes=[{"removed": True}]), dict(self.row, streamStatus="unavailable")):
            with self.subTest(row=row):
                self.assertIsNone(counts(row, self.reference))
        self.assertIsNone(counts(self.row, dict(self.reference, coverage={"complete": False})))
