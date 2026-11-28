import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
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

    def state(self):
        with self.store.connection(write=False) as db:
            return capital_pool.report(db, POOL)

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
                capital_pool.capture(db, run_id, 3, capital_pool.authorized(db, run_id))
        self.assertEqual(self.state(), pooled)
        destination = self.store.path.with_suffix(".backup")
        copy_workspace(self.store.path, destination)
        with Workspace(destination).connection(write=False) as db:
            self.assertEqual(capital_pool.report(db, POOL), pooled)
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
            self.assertEqual(capital_pool.authorized(db, IDS[0]), [])
            with self.assertRaises(Conflict):
                capital_pool.control(db, POOL, 4, "running")
            self.assertTrue(all(paper.report(db, run)["backgroundEnabled"] for run in IDS))

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
