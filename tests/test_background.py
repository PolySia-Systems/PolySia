import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from apps.server import background, public_shadow
from apps.server.archive import copy_workspace
from apps.server.store import Conflict, Workspace


ID = "2" * 32
WALLET = "0x" + "ab" * 20


class BackgroundTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "workspace.db"
        self.store = Workspace(self.path)
        with self.store.connection() as db:
            public_shadow.create(db, ID, WALLET, "Background test", "25", "5")
        self.waiting = {"status": "waiting", "reason": "No public BUY in this window.",
                        "wallet": WALLET, "researchBudget": "5.00"}

    def enable(self):
        with self.store.connection() as db:
            state = background.configure(db, ID, 1, True)
            self.assertTrue(state["backgroundEnabled"])
            return db.execute("SELECT due FROM background_runs").fetchone()[0]

    def test_explicit_enable_survives_restart_and_outage_backs_off(self):
        sampler = Mock(return_value=self.waiting)
        background.tick(self.store, sampler)
        sampler.assert_not_called()
        start = self.enable()
        self.store = Workspace(self.path)
        background.tick(self.store, Mock(side_effect=TimeoutError()), start)
        background.tick(self.store, sampler, start + 59)
        sampler.assert_not_called()
        backup = self.path.with_suffix(".backup")
        copy_workspace(self.path, backup)
        self.store = Workspace(backup)
        background.tick(self.store, sampler, start + 60)
        sampler.assert_called_once_with(WALLET, "5.00", retry_empty=True, check_sales=True)
        with self.store.connection() as db:
            state = public_shadow.report(db, ID)
            self.assertEqual([d["kind"] for d in state["decisions"]], ["waiting", "unavailable", "background-on"])
            self.assertEqual(state["cash"], "25")
            public_shadow.control(db, ID, 4, "pause")
            state = public_shadow.control(db, ID, 5, "resume")
            self.assertFalse(state["backgroundEnabled"])

    def test_stop_during_read_discards_receipt_and_only_one_worker_claims(self):
        now = self.enable()
        rival = Mock()

        def interrupt(*args, **kwargs):
            background.tick(Workspace(self.path), rival, now)
            with self.store.connection() as db:
                public_shadow.control(db, ID, 2, "stop")
            return self.waiting

        background.tick(self.store, interrupt, now)
        rival.assert_not_called()
        with self.store.connection(write=False) as db:
            state = public_shadow.report(db, ID)
            self.assertEqual((state["status"], state["backgroundEnabled"], state["cash"]), ("stopped", False, "25"))
            self.assertEqual([d["kind"] for d in state["decisions"]], ["stop", "background-on"])

    def test_invalid_provider_output_and_far_future_claim_recover(self):
        start = self.enable()
        with self.store.connection() as db:
            db.execute("UPDATE background_runs SET due=?", (2**63 - 1,))
        background.tick(self.store, Mock(return_value=[]), start)
        background.tick(self.store, Mock(return_value=self.waiting), start + 60)
        with self.store.connection(write=False) as db:
            state = public_shadow.report(db, ID)
            self.assertTrue(state["backgroundEnabled"])
            self.assertEqual([d["kind"] for d in state["decisions"]], ["waiting", "unavailable", "background-on"])

    def test_reenabled_run_rejects_old_claim_and_recovers_interrupted_claim(self):
        now = self.enable()

        def change_permission(*args, **kwargs):
            with self.store.connection() as db:
                background.configure(db, ID, 2, False)
                with self.assertRaises(Conflict):
                    background.configure(db, ID, 1, True)
                background.configure(db, ID, 3, True)
            return self.waiting

        background.tick(self.store, change_permission, now)
        with self.store.connection() as db:
            self.assertEqual([d["kind"] for d in public_shadow.report(db, ID)["decisions"]],
                             ["background-on", "background-off", "background-on"])
            db.execute("UPDATE background_runs SET due=?, claim=?", (now + 120, "b" * 32))
        sampler = Mock(return_value=self.waiting)
        background.tick(self.store, sampler, now + 119)
        sampler.assert_not_called()
        background.tick(self.store, sampler, now + 120)
        sampler.assert_called_once()
