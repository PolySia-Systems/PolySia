import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from apps.server import public_depth, public_shadow, shared_replay
from apps.server.archive import copy_workspace
from apps.server.store import Workspace
from test_public_shadow import STARTED, observed_buy


class SharedReplayTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = Workspace(Path(directory.name) / "original.db")
        self.ids = ["a" * 32, "b" * 32]
        self.wallets = ["0x" + "01" * 20, "0x" + "02" * 20]
        with self.store.connection() as db, patch.object(public_shadow, "timestamp", return_value=STARTED):
            for run_id, wallet in zip(self.ids, self.wallets):
                public_shadow.create(db, run_id, wallet, "Example", "50", "10")

    def record(self, db, index, order, *, start=1700000000, token="734", shares=25):
        receipt = observed_buy(self.wallets[index], "10.00", order=order, start=start)
        receipt["event"]["tokenId"] = token
        receipt["book"]["bestAsks"] = [{"price": "0.50", "shares": str(shares)}]
        receipt["capacity"] = public_depth.measure_depth(receipt, "10.00")
        run_id = self.ids[index]
        run = public_shadow.report(db, run_id)
        updated = public_shadow.record(db, run_id, run["revision"], receipt)
        self.assertEqual(updated["decisions"][0]["kind"], "entry")

    def test_tied_receipts_share_depth_restore_and_repeat(self):
        with self.store.connection() as db:
            self.record(db, 1, "08")
            self.record(db, 0, "07")
            original = [public_shadow.report(db, key, export=True) for key in self.ids]
            result = shared_replay.replay(db, list(reversed(self.ids)), "50")
            self.assertEqual([run["sharesByToken"] for run in result["runs"]], [{"734": 19}, {"734": 6}])
            self.assertEqual((result["cost"], result["fees"], result["cash"]), ("12.8125", "0.3125", "37.1875"))
            self.assertEqual(result["firstBookMs"], result["lastBookMs"])
            self.assertEqual(result, shared_replay.replay(db, self.ids, "50"))
            self.assertEqual(original, [public_shadow.report(db, key, export=True) for key in self.ids])
        copied = self.store.path.with_name("restored.db")
        copy_workspace(self.store.path, copied)
        with Workspace(copied).connection(write=False) as db:
            self.assertEqual(result, shared_replay.replay(db, self.ids, "50"))

    def test_shared_cash_prioritizes_receipt_time_across_outcomes(self):
        with self.store.connection() as db:
            self.record(db, 0, "07", start=1700000001)
            self.record(db, 1, "08", token="735")
            result = shared_replay.replay(db, self.ids, "10")
            first, second = result["runs"]
            self.assertEqual((first["modeledBuys"], second["sharesByToken"]), (0, {"735": 19}))
            self.assertEqual((result["limitedBuys"], result["cash"], result["fees"]), (1, "0.2625", "0.2375"))
            bigger = shared_replay.replay(db, self.ids, "50")
            self.assertEqual([run["sharesByToken"] for run in bigger["runs"]], [{"734": 19}, {"735": 19}])

    def test_duplicate_orders_old_sale_checks_and_unsuccessful_trials(self):
        with self.store.connection() as db:
            db.execute("UPDATE public_runs SET wallet=? WHERE id=?", (self.wallets[0], self.ids[1]))
            self.wallets[1] = self.wallets[0]
            self.record(db, 0, "07")
            self.record(db, 1, "07")
            self.record(db, 1, "08", start=1700000010)
            # A supported older policy could record a BUY without an intervening sale check.
            old = db.execute("SELECT receipt FROM public_decisions WHERE run_id=? AND revision=3", (self.ids[1],)).fetchone()[0]
            receipt = json.loads(old)
            del receipt["saleCheck"]
            db.execute("UPDATE public_decisions SET receipt=? WHERE run_id=? AND revision=3", (json.dumps(receipt), self.ids[1]))
            result = shared_replay.replay(db, self.ids, "50")
            self.assertEqual((result["duplicateOrders"], result["missingSaleChecks"]), (1, 1))
            self.assertEqual([run["modeledBuys"] for run in result["runs"]], [1, 0])

        receipt = observed_buy(self.wallets[0], "10.00")
        consumed = {500000: 5, 510000: 100}
        self.assertEqual(public_depth._estimate(receipt, "10.00", receipt["market"], consumed)["status"], "skipped")
        self.assertEqual(consumed, {500000: 5, 510000: 100})

    def test_empty_input_and_validation(self):
        with self.store.connection(write=False) as db:
            result = shared_replay.replay(db, self.ids, "25")
            self.assertEqual((result["cash"], result["firstBookMs"], result["lastBookMs"]), ("25", None, None))
            for ids, capital in ((self.ids, "NaN"), ([], "10"), (self.ids[:1], "10"),
                                 ([self.ids[0]] * 2, "10"), ([self.ids[0], "c" * 32], "10")):
                with self.subTest(ids=ids, capital=capital), self.assertRaises(ValueError):
                    shared_replay.replay(db, ids, capital)
