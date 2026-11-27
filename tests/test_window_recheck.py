from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from apps.server import public_shadow, study
from apps.server.store import Workspace


class HistoricalWindowTests(unittest.TestCase):
    def test_later_activity_cannot_change_old_decision(self):
        with TemporaryDirectory() as tmp:
            store = Workspace(Path(tmp) / "state.sqlite")
            wallet, run = "0x" + "ab" * 20, "a" * 32
            with store.connection() as db:
                public_shadow.create(db, run, wallet, "Quiet", "20", "5")
                receipt = {"wallet": wallet, "researchBudget": "5.00", "status": "waiting",
                           "reason": "No visible buy.", "windowStartSeconds": 101, "windowEndSeconds": 102}
                public_shadow.record(db, run, 1, receipt)
                before = public_shadow.report(db, run, export=True)
            with patch.object(study, "_reference_page", return_value=([{"side": "BUY"}], {"complete": True}, 200000)) as read:
                result = study.review_waiting_window(store, run, 2)
                self.assertEqual((result["visibleBuys"], result["complete"]), (1, True))
                read.assert_called_once_with(wallet, 101, 102)
            with patch.object(study, "_reference_page", side_effect=TimeoutError()):
                self.assertIsNone(study.review_waiting_window(store, run, 2)["visibleBuys"])
            with store.connection() as db:
                self.assertEqual(before, public_shadow.report(db, run, export=True))
