import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from apps.server import background, public_shadow
from apps.server.store import Conflict, Workspace, verify_saved_wallets
from test_public_shadow import ID, STARTED, WALLET, observed_buy


class SavedWalletTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "workspace.sqlite"
        self.store = Workspace(self.path)
        self.first = "0x" + "a1" * 20
        self.second = "0x" + "b2" * 20

    def select(self, address, revision):
        self.store.save_account({"address": address, "status": "available"}, revision)

    def test_addresses_and_names_survive_switch_disconnect_and_restart(self):
        self.select(self.first, 0)
        self.store.update_saved_wallet(self.first, 1, label="First")
        self.select(self.second, 2)
        self.store.update_saved_wallet(self.second, 3, label="Second")
        self.store.save_account(None, 4)
        self.store = Workspace(self.path)
        expected = [{"address": self.first, "label": "First"}, {"address": self.second, "label": "Second"}]
        state = self.store.read()
        self.assertIsNone(state["account"])
        self.assertEqual(state["savedWallets"], expected)
        self.select(self.first, 5)
        self.store.update_saved_wallet(self.first.upper().replace("0X", "0x"), 6, label=" Renamed ")
        self.assertEqual(self.store.read()["savedWallets"][0]["label"], "Renamed")
        self.store.update_saved_wallet(self.first, 7, remove=True)
        state = self.store.read()
        self.assertEqual(state["savedWallets"], expected[1:])
        self.assertEqual(state["account"]["address"], self.first)

    def test_stale_selection_and_invalid_names_cannot_mutate_saved_wallets(self):
        self.select(self.first, 0)
        self.select(self.second, 1)
        for address, revision in [(self.first, 1), (self.first, 2), (self.second, 1)]:
            with self.subTest(address=address, revision=revision), self.assertRaises(Conflict):
                self.store.update_saved_wallet(address, revision, label="Wrong wallet")
        for label in (None, 7, "x" * 65, "line\nbreak"):
            with self.subTest(label=label), self.assertRaises(ValueError):
                self.store.update_saved_wallet(self.second, 2, label=label)
        with self.assertRaises(ValueError):
            self.store.update_saved_wallet(self.second, True, label="")
        state = self.store.read()
        self.assertEqual((state["savedWallets"], state["accountRevision"]), ([], 2))

    def test_archive_rejects_invalid_stored_addresses_and_names(self):
        with self.store.connection() as db:
            for address, label in [(self.first, " Hidden space"), ("invalid", "First")]:
                with self.subTest(address=address):
                    db.execute("INSERT INTO saved_wallets VALUES (?, ?)", (address, label))
                    with self.assertRaises(ValueError):
                        verify_saved_wallets(db)
                    db.execute("DELETE FROM saved_wallets")

    def test_overview_lists_current_window_issues_and_stopped_exposure(self):
        with self.store.connection() as db, patch.object(public_shadow, "timestamp", return_value=STARTED):
            run = public_shadow.create(db, ID, WALLET, "Study", "25", "10")
            run = background.configure(db, ID, run["revision"], True)
        summary = self.store.overview()
        self.assertEqual((summary["running"], summary["background"], summary["issues"]), (1, 1, []))
        for kind in ("unavailable", "incomplete", "waiting"):
            with self.store.connection() as db:
                run = public_shadow.record(db, ID, run["revision"], {
                    "status": kind, "reason": "Window " + kind, "wallet": WALLET, "researchBudget": "10.00"})
            items = self.store.overview()["issues"]
            self.assertEqual([item["kind"] for item in items], [] if kind == "waiting" else [kind])
            if kind == "unavailable":
                with self.store.connection() as db:
                    run = public_shadow.deposit(db, ID, run["revision"], "1")
                self.assertEqual(self.store.overview()["issues"], items)
        with self.store.connection() as db:
            run = public_shadow.record(db, ID, run["revision"], observed_buy(WALLET, "10.00"))
            self.assertEqual(run["decisions"][0]["kind"], "entry")
            public_shadow.control(db, ID, run["revision"], "stop")
        summary = self.store.overview()
        self.assertEqual((summary["running"], summary["background"], summary["stopped"]), (0, 0, 1))
        self.assertEqual([(item["id"], item["kind"]) for item in summary["issues"]], [(ID, "exposure")])
