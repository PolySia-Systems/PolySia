import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

from apps.server import background, capital_pool, public_depth, public_shadow as paper
from apps.server.archive import copy_workspace
from apps.server.store import Conflict, Workspace
from test_public_shadow import STARTED, observed_buy


POOL = "c" * 32
IDS = ["1" * 32, "2" * 32]
WALLETS = ["0x" + "11" * 20, "0x" + "22" * 20]


class CapitalPoolTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = Workspace(Path(directory.name) / "pool.db")
        with self.store.connection() as db, patch.object(paper, "timestamp", return_value=STARTED):
            for run, wallet in zip(IDS, WALLETS):
                paper.create(db, run, wallet, "Leader", "50", "10")
                background.configure(db, run, 1, True)
            self.start = db.execute("SELECT max(due) FROM background_runs").fetchone()[0]

    def create(self, capital="25"):
        with self.store.connection() as db:
            return capital_pool.create(db, POOL, "Shared buys", capital, IDS)

    def state(self, through=None):
        with self.store.connection(write=False) as db:
            return capital_pool.report(db, POOL, through=through)

    def receipt(self, wallet, budget, **options):
        self.assertEqual(options, {"retry_empty": True, "check_sales": True})
        receipt = observed_buy(wallet, budget, start=int(time.time()) - 8)
        receipt["book"]["bestAsks"] = [{"price": "0.50", "shares": "25"}]
        receipt["capacity"] = public_depth.measure_depth(receipt, budget)
        return receipt

    def test_parallel_callbacks_share_capital_and_visible_depth_across_restart(self):
        self.assertEqual(self.create()["windows"], 0)
        with self.store.connection() as db:
            capital_pool.create(db, "a" * 32, "Ten only", "10", IDS)
        barrier = Barrier(2)
        def simultaneous(*args, **kwargs):
            barrier.wait(timeout=5)
            return self.receipt(*args, **kwargs)
        with ThreadPoolExecutor(2) as workers:
            futures = [workers.submit(background.tick, self.store, simultaneous, self.start) for _ in IDS]
            for future in futures:
                future.result(timeout=10)
        self.store = Workspace(self.store.path)
        pooled = self.state()
        shares = sorted(run["sharesByToken"]["734"] for run in pooled["runs"])
        self.assertEqual((pooled["windows"], shares, pooled["cost"], pooled["fees"], pooled["cash"]),
                         (2, [6, 19], "12.8125", "0.3125", "12.1875"))
        with self.store.connection() as db:
            limited = capital_pool.report(db, "a" * 32)
            self.assertEqual((limited["cash"], limited["limitedBuys"]), ("0.2625", 1))
            for run_id in IDS:
                self.assertEqual(paper.report(db, run_id)["positions"][0]["shares"], "19")
        through = datetime.fromisoformat(pooled["week"]["through"])
        self.assertEqual(self.state(through), pooled)
        destination = self.store.path.with_suffix(".backup")
        copy_workspace(self.store.path, destination)
        with Workspace(destination).connection(write=False) as db:
            self.assertEqual(capital_pool.report(db, POOL, through=through), pooled)
        with self.store.connection() as db:
            db.execute("UPDATE pool_members SET start_revision=3 WHERE pool_id=? AND run_id=?", (POOL, IDS[0]))
        with self.assertRaisesRegex(ValueError, "shared BUY window"):
            copy_workspace(self.store.path, self.store.path.with_suffix(".invalid"))

    def test_pause_resume_or_stop_during_window_cannot_admit_old_callback(self):
        self.create()
        def after_resume(*args, **kwargs):
            with self.store.connection() as db:
                capital_pool.control(db, POOL, 1, "paused")
                capital_pool.control(db, POOL, 2, "running")
            return self.receipt(*args, **kwargs)
        background.tick(self.store, after_resume, self.start)
        self.assertEqual(self.state()["windows"], 0)
        def after_stop(*args, **kwargs):
            with self.store.connection() as db:
                capital_pool.control(db, POOL, 3, "stopped")
            return self.receipt(*args, **kwargs)
        background.tick(self.store, after_stop, self.start)
        self.assertEqual((self.state()["status"], self.state()["cash"]), ("stopped", "25"))
        with self.store.connection() as db:
            with self.assertRaises(Conflict):
                capital_pool.control(db, POOL, 4, "running")
            self.assertTrue(all(paper.report(db, run)["backgroundEnabled"] for run in IDS))

    def test_week_preserves_shared_depth_and_separates_funding_from_result(self):
        through = datetime(2025, 3, 15, 12, tzinfo=UTC)
        start = through - timedelta(days=7)
        with patch.object(capital_pool, "timestamp", return_value=(start - timedelta(days=1)).isoformat()):
            self.create()
        for recorded in (start - timedelta(microseconds=1), start):
            with patch.object(paper, "timestamp", return_value=recorded.isoformat()), patch.object(time, "time", return_value=recorded.timestamp()):
                background.tick(self.store, self.receipt, self.start)
        pooled = self.state(through)
        week = pooled["week"]
        self.assertTrue(week["available"])
        self.assertEqual((week["openingCash"], week["funding"], week["buys"], week["purchaseCost"],
                          week["includedFees"], week["closingCash"], week["netResult"]),
                         ("15.2625", "0", 1, "3.075", "0.075", pooled["cash"], None))
        self.assertEqual(week["counts"], {"entry": 1})
        with self.store.connection() as db:
            # Deliberately reverse the wall clocks across two different source runs.
            db.execute("UPDATE public_decisions SET recorded=? WHERE run_id=? AND kind='entry'",
                       ((start - timedelta(minutes=1)).isoformat(), IDS[1]))
        changed = self.state(through)
        self.assertFalse(changed["week"]["available"])
        self.assertEqual(changed["cash"], pooled["cash"])

    def test_week_counts_overlapping_complete_pages_once_per_wallet_and_shows_gaps(self):
        through = datetime(2025, 3, 15, 12, tzinfo=UTC)
        created = through - timedelta(seconds=100)
        begin = int(created.timestamp())
        with patch.object(capital_pool, "timestamp", return_value=created.isoformat()):
            self.create()
        def quiet(wallet, budget, **options):
            return {"wallet": wallet, "researchBudget": budget, "status": "waiting", "reason": "Quiet window.",
                    "windowStartSeconds": begin + 10, "windowEndSeconds": begin + 11,
                    "activityCoverage": {"complete": wallet == WALLETS[0]}, "activityReceivedMs": (begin + 12) * 1000}
        for offset in (0, 0, 15):
            with patch.object(paper, "timestamp", return_value=(created + timedelta(seconds=20 + offset)).isoformat()):
                background.tick(self.store, quiet, self.start + offset)
        week = self.state(through)["week"]
        self.assertEqual((week["funding"], week["openingCash"], week["closingCash"], week["netResult"]),
                         ("25", "0", "25", "0"))
        covered, unknown = [week["coverage"][run] for run in IDS]
        self.assertEqual((covered["receipts"], covered["completePageSeconds"], covered["periodSeconds"]), (2, 2, 100))
        self.assertEqual(covered["longestGap"], {"from": (created + timedelta(seconds=12)).isoformat(), "through": through.isoformat()})
        self.assertEqual((unknown["receipts"], unknown["completePageSeconds"], unknown["longestGap"]["from"]),
                         (1, 0, created.isoformat()))
        # Pricing evidence and activity-page evidence are independent. A failed
        # final activity read, however, clears the complete page from the receipt.
        def missing_book(wallet, budget, **options):
            receipt = quiet(wallet, budget, **options)
            receipt.update(status="incomplete", reason="Book unavailable.", activityCoverage={"complete": True},
                           windowStartSeconds=begin + 40, windowEndSeconds=begin + 41,
                           activityReceivedMs=(begin + 43) * 1000)
            return receipt
        with patch.object(paper, "timestamp", return_value=(created + timedelta(seconds=50)).isoformat()):
            background.tick(self.store, missing_book, self.start + 15)
        week = self.state(through)["week"]
        self.assertEqual(week["counts"]["incomplete"], 1)
        self.assertEqual(week["coverage"][IDS[1]]["completePageSeconds"], 2)

    def test_new_subscriber_excludes_inflight_and_manual_decisions_and_reports_outage(self):
        def subscribe(*args, **kwargs):
            self.create()
            return self.receipt(*args, **kwargs)
        background.tick(self.store, subscribe, self.start)
        with self.store.connection() as db:
            paper.record(db, IDS[1], 2, self.receipt(WALLETS[1], "10.00", retry_empty=True, check_sales=True))
        self.assertEqual(self.state()["windows"], 0)
        def offline(*args, **kwargs):
            raise OSError("Unavailable")
        background.tick(self.store, offline, self.start)
        pooled = self.state()
        self.assertEqual((pooled["windows"], pooled["cash"], pooled["otherRecordedDecisions"]), (1, "25", {"unavailable": 1}))
        with self.store.connection() as db:
            paper.control(db, IDS[1], 4, "stop")
            self.assertFalse(capital_pool.report(db, POOL)["runs"][1]["sourceBackgroundEnabled"])
            with self.assertRaises(ValueError):
                capital_pool.create(db, "a" * 32, "Missing source", "10", IDS)
            with self.assertRaises(Conflict):
                capital_pool.create(db, POOL, "Different funding", "12", IDS)

    def test_restore_matches_worker_provenance_control_generation_and_commit_order(self):
        self.create()
        # One genuine background entry in each running generation. The two
        # controls intentionally have the same timestamp, as after a clock correction.
        background.tick(self.store, self.receipt, self.start)
        with self.store.connection() as db, patch.object(capital_pool, "timestamp", return_value=STARTED):
            capital_pool.control(db, POOL, 1, "paused")
            capital_pool.control(db, POOL, 2, "running")
        background.tick(self.store, self.receipt, self.start)
        with self.store.connection() as db:
            receipt = self.receipt(WALLETS[1], "10.00", retry_empty=True, check_sales=True)
            receipt["participant"]["orderHash"] = "0x" + "af" * 32
            manual = paper.record(db, IDS[1], 3, receipt)
            self.assertEqual(manual["decisions"][0]["kind"], "entry")
        valid = self.store.path.with_suffix(".valid")
        copy_workspace(self.store.path, valid)
        with Workspace(valid).connection(write=False) as db:
            through = datetime.now(UTC)
            self.assertEqual(capital_pool.report(db, POOL, through=through), self.state(through))
        modifications = [
            # Substitute a valid manual decision from the same active source.
            "UPDATE pool_windows SET revision=4 WHERE sequence=2",
            "UPDATE pool_windows SET generation=1 WHERE sequence=2",
            "DELETE FROM pool_windows WHERE sequence=2",
            "UPDATE public_decisions SET receipt=json_remove(receipt,'$.serverWorker') WHERE run_id=? AND revision=3",
            "UPDATE worker_windows SET opened=1 WHERE ordinal=2",
        ]
        for i, sql in enumerate(modifications):
            tampered = self.store.path.with_suffix(f".trial{i}")
            copy_workspace(valid, tampered)
            with Workspace(tampered).connection() as db:
                db.execute(sql, (IDS[1],) if "?" in sql else ())
            with self.subTest(sql=sql), self.assertRaisesRegex(ValueError, "worker|background|authorized"):
                copy_workspace(tampered, self.store.path.with_suffix(f".reject{i}"))
        with self.store.connection() as db:
            # Reverse sequence in a single generation without manipulating the
            # source receipts, which retain their independent commit ordinals.
            capital_pool.create(db, "d" * 32, "New pool", "25", IDS)
        for offset in (15, 16):
            background.tick(self.store, self.receipt, self.start + offset)
        with self.store.connection() as db:
            db.execute("UPDATE pool_windows SET sequence=-sequence WHERE pool_id=?", ("d" * 32,))
        with self.assertRaisesRegex(ValueError, "commit order"):
            copy_workspace(self.store.path, self.store.path.with_suffix(".bad-order"))
