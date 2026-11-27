import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from apps.server import public_marks, public_shadow as paper
from apps.server.archive import copy_workspace
from apps.server.store import Conflict, Workspace


class SimulatedDepositTests(unittest.TestCase):
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
