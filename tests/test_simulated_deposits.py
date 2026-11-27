import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from apps.server import public_marks, public_shadow as paper
from apps.server.archive import copy_workspace
from apps.server.store import Conflict, Workspace
from apps.server.run_week import summary


class SimulatedDepositTests(unittest.TestCase):
    def test_clock_correction_preserves_pause_and_flags_old_out_of_order_history(self):
        with TemporaryDirectory() as directory, Workspace(Path(directory) / 'original.db').connection() as db:
            key = 'e' * 32
            with patch.object(paper, 'timestamp', return_value='2026-10-20T01:00:00Z'):
                paper.create(db, key, '0x' + 'ab' * 20, 'History', '20', '5')
            with patch.object(paper, 'timestamp', return_value='2026-10-19T01:00:00Z'):
                paused = paper.control(db, key, 1, 'pause')
            self.assertEqual(paused['createdAt'], paused['updatedAt'])
            paper.verify_archive(db)
            db.execute("UPDATE public_decisions SET recorded='2026-10-18T01:00:00Z'")
            with self.assertRaisesRegex(ValueError, 'clock moved backwards'):
                summary(db, key)
            db.execute("UPDATE public_runs SET created='2026-10-10'")
            with self.assertRaisesRegex(ValueError, 'UTC offset'):
                paper.verify_archive(db)

    def test_pause_duplicate_and_cash_benchmark_survive_restore(self):
        key = 'd' * 32
        with TemporaryDirectory() as directory:
            store = Workspace(Path(directory) / 'original.db')
            with store.connection() as db:
                paper.create(db, key, '0x' + 'ab' * 20, 'Personal', '10', '2')
                paper.control(db, key, 1, 'pause')
                state = paper.deposit(db, key, 2, '14.25')
                self.assertEqual((state['cash'], state['capital'], state['fundedCapital'], state['openCost'],
                                  state['realized'], state['status']), ('24.25', '10', '24.25', '0', '0', 'paused'))
                with self.assertRaises(Conflict):
                    paper.deposit(db, key, 2, '14.25')
                with self.assertRaises(ValueError):
                    paper.deposit(db, key, 3, '990')
                value = public_marks.portfolio_value(paper.valuation_basis(db, key, 3))
                self.assertEqual((value['cashBenchmark']['endValue'], value['cashBenchmark']['additionalFlows'],
                                  value['netResult'], value['cashBenchmark']['netReturnPct']), ('24.25','14.25','0','0'))
                paper.control(db, key, 3, 'stop')
                with self.assertRaises(Conflict):
                    paper.deposit(db, key, 4, '5')
            backup = Path(directory) / 'restored.db'
            copy_workspace(store.path, backup)
            with Workspace(backup).connection() as db:
                self.assertEqual(paper.report(db, key)['cash'], '24.25')
                db.execute("UPDATE public_decisions SET receipt=? WHERE kind='deposit'",
                           (json.dumps({'amount': '1', 'amountMicros': 14250000}),))
                with self.assertRaises(ValueError):
                    paper.verify_archive(db)
