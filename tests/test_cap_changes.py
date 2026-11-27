import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from apps.server import public_shadow as paper
from apps.server.archive import copy_workspace
from apps.server.store import Conflict, Workspace
from test_public_shadow import ID, STARTED, WALLET, observed_buy


class CapChanges(unittest.TestCase):
    def test_cutover_and_rollback_preserve_old_receipts_and_pause(self):
        with TemporaryDirectory() as directory:
            store = Workspace(Path(directory) / "workspace.db")
            with store.connection() as db:
                with patch.object(paper, "timestamp", return_value=STARTED):
                    paper.create(db, ID, WALLET, "Personal", "60", "10")
                first = paper.record(db, ID, 1, observed_buy(WALLET, "10.00"))
                paper.control(db, ID, 2, "pause")
                changed = paper.change_cap(db, ID, 3, "5")
                self.assertEqual((changed["cash"], changed["positions"], changed["status"]),
                                 (first["cash"], first["positions"], "paused"))
                self.assertEqual(paper.change_cap(db, ID, 4, "5.00")["revision"], 4)
                self.assertEqual(paper.create(db, ID, WALLET, "Personal", "60", "10")["entryCap"], "5")
                with self.assertRaises(Conflict):
                    paper.create(db, ID, WALLET, "Personal", "60", "5")
                with self.assertRaises(Conflict):
                    paper.change_cap(db, ID, 3, "40")
                with self.assertRaises(ValueError):
                    paper.change_cap(db, ID, 4, "61")
                paper.control(db, ID, 4, "resume")
                self.assertEqual(paper.sampling_terms(db, ID, 5)[1], "5.00")
                paper.record(db, ID, 5, observed_buy(WALLET, "5.00", order="08"))
                paper.change_cap(db, ID, 6, "10")
                with self.assertRaises(Conflict):
                    paper.record(db, ID, 6, observed_buy(WALLET, "5.00", order="09"))
                paper.control(db, ID, 7, "stop")
                with self.assertRaises(Conflict):
                    paper.change_cap(db, ID, 8, "6")
                exported = paper.report(db, ID, export=True)
                self.assertEqual([d["receipt"]["researchBudget"] for d in exported["decisions"] if d["kind"]=="entry"],
                                 ["10.00", "5.00"])
                self.assertEqual([d["receipt"] for d in exported["decisions"] if d["kind"]=="change-cap"],
                                 [{"previousCap": "10", "nextCap": "5"}, {"previousCap": "5", "nextCap": "10"}])
            backup = Path(directory) / "backup.db"
            copy_workspace(store.path, backup)
            with Workspace(backup).connection() as db:
                self.assertEqual(paper.report(db, ID, export=True), exported)
                db.execute("UPDATE public_decisions SET receipt=? WHERE run_id=? AND revision=4",
                           (json.dumps({"previousCap": "99", "nextCap": "5"}), ID))
                with self.assertRaises(ValueError):
                    paper.verify_archive(db)
