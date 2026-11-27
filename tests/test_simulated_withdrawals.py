import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from apps.server import background, public_depth, public_marks, public_shadow as paper
from apps.server.archive import copy_workspace
from apps.server.run_week import export_week, summary
from apps.server.store import Conflict, Workspace
from test_public_shadow import ID, WALLET, observed_buy, observed_sell


class WithdrawalTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store = Workspace(Path(temp.name) / "state.db")
        self.start = datetime(2026, 11, 18, tzinfo=UTC)

    def at(self, offset, action, *args):
        when = (self.start + timedelta(seconds=offset)).isoformat()
        with self.store.connection() as db, patch.object(paper, "timestamp", return_value=when):
            return action(db, ID, *args)

    def test_insufficient_cash_rejects_entire_change_and_invalidates_worker_on_transfer(self):
        self.at(0, paper.create, WALLET, "Budget", "100", "10")
        tick = int(self.start.timestamp())
        before = self.at(10, paper.record, 1, observed_buy(WALLET, "10.00", start=tick + 4))
        self.assertEqual(before["cash"], "90.14256")
        self.at(20, background.configure, 2, True)
        for invalid in ("91", "90.142561", "0", "-1", "1e1", "0.0000001", 90):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.at(30, paper.withdraw, 3, invalid)
        after = self.at(30, paper.withdraw, 3, before["cash"])
        self.assertEqual((after["cash"], after["openCost"], after["realized"], after["positions"]),
                         ("0", before["openCost"], before["realized"], before["positions"]))
        self.assertFalse(after["backgroundEnabled"])
        self.assertIsNone(after["nextBudget"])
        with self.assertRaises(Conflict):
            self.at(31, paper.record, 3, observed_buy(WALLET, "10.00", start=tick + 24))
        with self.assertRaises(Conflict):
            self.at(31, paper.withdraw, 3, before["cash"])
        funded = self.at(40, paper.deposit, 4, "3")
        self.assertEqual(funded["nextBudget"], "3.00")
        self.assertFalse(funded["backgroundEnabled"])
        self.at(50, paper.control, 5, "pause")
        paused = self.at(60, paper.withdraw, 6, "1")
        self.assertEqual((paused["status"], paused["entryCap"], paused["cash"]), ("paused", "10", "2"))
        self.at(70, paper.control, 7, "stop")
        with self.assertRaises(Conflict):
            self.at(71, paper.withdraw, 8, "1")
        restored = self.store.path.with_name("restored.db")
        copy_workspace(self.store.path, restored)
        with Workspace(restored).connection() as db:
            state = paper.report(db, ID, export=True)
            self.assertEqual((state["cash"], state["withdrawals"], state["positions"]), ("2", "91.14256", before["positions"]))
            with self.assertRaises(ValueError):
                paper.verify_archive(db, version=7)
            db.execute("UPDATE public_decisions SET receipt=? WHERE kind='withdraw' AND revision=4",
                       (json.dumps({"amount": "95", "amountMicros": 95000000}),))
            with self.assertRaisesRegex(ValueError, "available simulated cash"):
                paper.verify_archive(db)

    def test_withdrawing_profit_and_repeated_deposits_preserve_return_and_cash_comparison(self):
        self.at(0, paper.create, WALLET, "Capital and gains", "25", "10")
        tick = int(self.start.timestamp())
        bought = self.at(10, paper.record, 1, observed_buy(WALLET, "10.00", start=tick + 4))
        with self.store.connection(write=False) as db:
            wallet, scope, _ = paper.sale_terms(db, ID, 2, "734", "19")
        sale = observed_sell(wallet, scope, start=tick + 14, depth="25")
        bid = {"price": "0.80", "shares": "25"}
        sale["book"].update(bestBids=[bid], bestBid=bid, bestAsks=[{"price": "0.81", "shares": "25"}], spreadPerShare="0.01")
        sale["capacity"] = public_depth.measure_sale(sale)
        sold = self.at(20, paper.record_sale, 2, "734", "19", sale)
        profit = Decimal(sold["realized"])
        self.assertGreater(profit, 0)
        self.assertEqual(Decimal(sold["cash"]), 25 + profit)
        all_cash = self.at(30, paper.withdraw, 3, sold["cash"])
        self.assertEqual(Decimal(all_cash["netContributions"]), -profit)
        for rev, delta, operation in ((4, "1000", paper.deposit), (5, "1000", paper.withdraw), (6, "1000", paper.deposit)):
            self.at(rev * 10, operation, rev, delta)
        with self.assertRaises(ValueError):
            self.at(70, paper.deposit, 7, "1000")
        with self.store.connection() as db:
            state = paper.report(db, ID)
            self.assertEqual((state["fundedCapital"], state["cash"], state["realized"]), ("2025", "1000", sold["realized"]))
            value = public_marks.portfolio_value(paper.valuation_basis(db, ID, 7))
            self.assertEqual(value["netResult"], sold["realized"])
            self.assertIsNone(value["cashBenchmark"]["endValue"])
            self.assertIsNone(value["cashBenchmark"]["netReturnPct"])
            after = self.start + timedelta(hours=1)
            period = summary(db, ID, now=after)
            self.assertEqual((period["netResult"], period["closingCash"], period["withdrawals"]),
                             (sold["realized"], "1000", state["withdrawals"]))
            file = export_week(db, ID, 7, period["through"])
            self.assertEqual(file["period"], period)
            self.assertEqual([d["withdrawal"] for d in file["decisions"] if d["kind"] == "withdraw"], [sold["cash"], "1000"])
            old = summary(db, ID, now=after + timedelta(days=7))
            self.assertEqual((old["openingCash"], old["closingCash"], old["withdrawals"], old["netResult"]), ("1000", "1000", "0", "0"))
            paper.verify_archive(db)

    def test_zero_net_contribution_with_no_positions_is_flat(self):
        self.at(0, paper.create, WALLET, "Flat", "1000", "5")
        self.at(5, paper.withdraw, 1, "1000")
        with self.store.connection(write=False) as db:
            value = public_marks.portfolio_value(paper.valuation_basis(db, ID, 2))
            self.assertEqual((value["cashBenchmark"]["endValue"], value["cashBenchmark"]["netReturnPct"], value["netResult"]),
                             ("0", None, "0"))
