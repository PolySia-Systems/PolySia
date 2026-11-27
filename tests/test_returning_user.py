import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from apps.server import public_shadow as paper
from apps.server.archive import copy_workspace
from apps.server.run_week import export_week, summary
from apps.server.store import Conflict, Workspace
from test_public_shadow import ID, WALLET, observed_buy, observed_sell


END = datetime(2026, 7, 9, 12, 0, tzinfo=timezone.utc)
START = END - timedelta(days=7)


class ReturningUserTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store = Workspace(Path(temp.name) / "weekly.db")

    def at(self, when, operation, *args):
        with self.store.connection() as db, patch.object(paper, "timestamp", return_value=when.isoformat(timespec="milliseconds")):
            return operation(db, ID, *args)

    def week(self):
        with self.store.connection(write=False) as db:
            return summary(db, ID, now=END)

    def test_starting_cash_deposit_skipped_action_pause_and_open_exposure(self):
        self.at(START - timedelta(days=2), paper.create, WALLET, "Scoped test", "25", "10")
        self.at(START - timedelta(milliseconds=1), paper.deposit, 1, "2")
        self.at(START, paper.deposit, 2, "5")
        buy_time = START + timedelta(days=2)
        buy = observed_buy(WALLET, "10.00", start=int(buy_time.timestamp()) - 6)
        state = self.at(buy_time, paper.record, 3, buy)
        self.assertEqual(state["positions"][0]["shares"], "19")
        self.at(END - timedelta(minutes=5), paper.record, 4, {"wallet": WALLET, "researchBudget": "10.00",
                "status": "skipped", "reason": "The market minimum exceeded this budget."})
        state = self.at(END, paper.control, 5, "pause")
        report = self.week()
        self.assertEqual((report["openingCash"], report["funding"], report["closingCash"]), ("27", "5", state["cash"]))
        self.assertEqual((report["purchases"], report["sales"], report["fees"]), ("9.62", "0", "0.23744"))
        self.assertEqual((report["realizedOnSales"], report["netResult"]), ("0", None))
        self.assertEqual(report["observations"], 2)
        self.assertEqual(report["counts"], {"entry": 1, "skipped": 1, "deposit": 1, "pause": 1})
        self.assertEqual(report["latestObservation"]["kind"], "skipped")
        self.assertEqual(datetime.fromisoformat(report["from"]), START)
        self.assertEqual(datetime.fromisoformat(report["through"]), END)

    def test_new_quiet_run_and_future_rows(self):
        self.at(START, paper.create, WALLET, "Quiet run", "25", "10")
        self.at(END, paper.record, 1, {"wallet": WALLET, "researchBudget": "10.00", "status": "waiting",
                                      "reason": "No qualifying visible BUY."})
        self.at(END + timedelta(milliseconds=1), paper.deposit, 2, "3")
        report = self.week()
        self.assertEqual((report["openingCash"], report["funding"], report["closingCash"]), ("0", "25", "25"))
        self.assertEqual((report["observations"], report["counts"], report["netResult"]), (1, {"waiting": 1}, "0"))
        self.assertEqual(report["latestObservation"]["reason"], "No qualifying visible BUY.")

    def test_restored_iso_basic_and_submillisecond_boundaries(self):
        self.at(START - timedelta(days=1), paper.create, WALLET, "Imported history", "10", "2")
        with self.store.connection() as db:
            for revision, time_text in enumerate(("20260702T115959.999999+0000", "20260702T130000+0100",
                                                   "20260709T120000.000001+0000"), 1):
                with patch.object(paper, "timestamp", return_value=time_text):
                    paper.deposit(db, ID, revision, "5")
        restored = self.store.path.with_name("restored.db")
        copy_workspace(self.store.path, restored)
        with Workspace(restored).connection(write=False) as db:
            week = summary(db, ID, now=END)
            self.assertEqual((week["openingCash"], week["funding"], week["closingCash"]), ("15", "5", "20"))
            self.assertEqual(paper.report(db, ID)["cash"], "25")

    def test_position_from_before_period_sold_inside_period(self):
        self.at(START - timedelta(days=3), paper.create, WALLET, "Inherited position", "25", "10")
        before = START - timedelta(days=1)
        state = self.at(before, paper.record, 1, observed_buy(WALLET, "10.00", start=int(before.timestamp()) - 6))
        with self.store.connection(write=False) as db:
            _, scope, _ = paper.sale_terms(db, ID, 2, "734", "19")
        sale = observed_sell(WALLET, scope, start=int(END.timestamp()) - 6, depth="25")
        final = self.at(END, paper.record_sale, 2, "734", "19", sale)
        self.assertEqual(final["positions"], [])
        report = self.week()
        self.assertEqual((report["openingCash"], report["funding"], report["closingCash"]), (state["cash"], "0", final["cash"]))
        self.assertEqual(report["netResult"], None)
        self.assertEqual(report["realizedOnSales"], final["realized"])
        self.assertEqual(report["sales"], final["sales"])

    def test_complete_round_trip_excludes_funding_and_includes_both_fees(self):
        self.at(START, paper.create, WALLET, "Round trip", "25", "10")
        self.at(START + timedelta(days=1), paper.deposit, 1, "5")
        before = END - timedelta(days=1)
        self.at(before, paper.record, 2, observed_buy(WALLET, "10.00", start=int(before.timestamp()) - 6))
        with self.store.connection(write=False) as db:
            _, scope, _ = paper.sale_terms(db, ID, 3, "734", "19")
        sale = observed_sell(WALLET, scope, start=int(END.timestamp()) - 6, depth="25")
        final = self.at(END, paper.record_sale, 3, "734", "19", sale)
        report = self.week()
        self.assertEqual(report["funding"], "30")
        self.assertEqual(report["netResult"], final["realized"])
        self.assertEqual(report["fees"], final["fees"])

    def test_export_reconciles_exact_interval_and_rejects_newer_state(self):
        from decimal import Decimal
        self.at(START - timedelta(days=1), paper.create, WALLET, "Audited week", "25", "10")
        self.at(START - timedelta(microseconds=1000), paper.deposit, 1, "2")
        self.at(START, paper.deposit, 2, "5")
        purchase = END - timedelta(days=1)
        self.at(purchase, paper.record, 3, observed_buy(WALLET, "10.00", start=int(purchase.timestamp()) - 6))
        with self.store.connection(write=False) as db:
            _, scope, _ = paper.sale_terms(db, ID, 4, "734", "19")
        self.at(END, paper.record_sale, 4, "734", "19", observed_sell(WALLET, scope, start=int(END.timestamp()) - 6))
        self.at(END, paper.change_cap, 5, "8")
        self.at(END, paper.control, 6, "pause")
        shown = self.week()
        with self.store.connection(write=False) as db:
            exported = export_week(db, ID, 7, shown["through"])
        self.assertEqual(exported["period"], shown)
        self.assertEqual(exported["run"]["wallet"], WALLET)
        self.assertEqual(exported["run"]["status"], "paused")
        self.assertEqual(exported["run"]["positions"][0]["shares"], "11")
        decisions = exported["decisions"]
        self.assertEqual([d["revision"] for d in decisions], [3, 4, 5, 6, 7])
        deposit, buy, sale, cap, pause = decisions
        self.assertEqual((deposit["funding"], cap["previousCap"], cap["nextCap"], pause["kind"]), ("5", "10", "8", "pause"))
        self.assertEqual((buy["tokenId"], sale["tokenId"]), ("734", "734"))
        self.assertEqual(sale["realizedOnSale"], shown["realizedOnSales"])
        D = Decimal
        self.assertEqual(D(shown["openingCash"]) + D(deposit["funding"]) - D(buy["gross"]) - D(buy["fee"])
                         + D(sale["gross"]) - D(sale["fee"]), D(shown["closingCash"]))
        self.assertIsNone(shown["netResult"])
        self.at(END + timedelta(milliseconds=1), paper.deposit, 7, "1")
        with self.store.connection(write=False) as db:
            with self.assertRaises(Conflict):
                export_week(db, ID, 7, shown["through"])
            for invalid in (None, 42, "no date", "2026-11-28", "0001-01-01T00:00:00Z"):
                with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                    export_week(db, ID, 8, invalid)
