import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from apps.server import public_depth, public_marks, public_shadow as paper
from apps.server.archive import copy_workspace
from apps.server.store import Conflict, Workspace, create_schema_v1
from test_public_depth import MS, sample
from test_observe import book


WALLET = "0x" + "ab" * 20
ID = "c" * 32
STARTED = "2020-01-01T00:00:00.000Z"


def observed_buy(wallet, budget, *, order="07", start=None):
    # Use the provider adapter's normalized inputs and its actual depth/fee engine.
    data = sample()
    if start is None:
        start = int(time.time()) - 6
    shift = start * 1000 - MS
    for source in (data, data["book"], data["participant"], data["market"]):
        for key in source:
            if key in ("activityReceivedMs", "evidenceCheckedMs", "bookRequestedMs", "bookReceivedMs",
                       "checkedMs", "sourceTimeMs"):
                source[key] += shift
    tx = "0x" + "de" * 32
    data["event"] = dict(data["event"], side="BUY", eventTimeSeconds=start, transactionHash=tx,
                         marketTitle="Fixture opening day?", outcomeLabel="Yes")
    data["participant"].update(chainId=137, transactionHash=tx, orderHash="0x" + order * 32)
    data.update(schemaVersion=2, windowStartSeconds=start, windowEndSeconds=start + 1,
                status="observed", reason="Controlled public BUY.", wallet=wallet, asset="pUSD", researchBudget=budget)
    data["capacity"] = public_depth.measure_depth(data, budget)
    return data


class PublicPortfolioTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.store = Workspace(self.root / "work.db")

    def create(self, capital="25", cap="10"):
        with self.store.connection() as db, patch.object(paper, "timestamp", return_value=STARTED):
            return paper.create(db, ID, WALLET, "Public wallet", capital, cap)

    def test_duplicate_create_source_order_and_frozen_portfolio_survive_restore(self):
        original = self.create()
        self.assertEqual(self.create(), original)
        with self.assertRaises(Conflict):
            self.create(capital="26")
        with self.store.connection() as db:
            first = paper.record(db, ID, 1, observed_buy(WALLET, "10.00"))
            self.assertEqual((first["cash"], first["gross"], first["fees"]), ("15.14256", "9.62", "0.23744"))
            again = paper.record(db, ID, 2, observed_buy(WALLET, "10.00"))
            self.assertEqual(again["decisions"][0]["kind"], "duplicate")
            self.assertEqual(again["positions"], first["positions"])
            second = paper.record(db, ID, 3, observed_buy(WALLET, "10.00", order="08"))
            self.assertEqual((second["nextBudget"], second["positions"][0]["shares"]), ("5.28", "38"))
            paper.control(db, ID, 4, "pause")
            with self.assertRaises(Conflict):
                paper.sampling_terms(db, ID, 5)
            paper.control(db, ID, 5, "resume")
            paper.control(db, ID, 6, "stop")
            with self.assertRaises(Conflict):
                paper.control(db, ID, 7, "resume")
            before = paper.report(db, ID, export=True)
        copy_workspace(self.store.path, self.root / "copy.db")
        with Workspace(self.root / "copy.db").connection(write=False) as db:
            self.assertEqual(before, paper.report(db, ID, export=True))
        self.assertEqual([d["kind"] for d in before["decisions"]], ["entry", "duplicate", "entry", "pause", "resume", "stop"])

    def test_subcent_cash_floor_and_invalid_or_insufficient_evidence(self):
        self.create(capital="10")
        with self.store.connection() as db:
            for rev, defect in enumerate(("wrong-wallet", "unbalanced", "dishonest-book", "null-capacity"), 1):
                r = observed_buy(WALLET, "10.00")
                if defect == "wrong-wallet":
                    r["wallet"] = "0x" + "cd" * 20
                elif defect == "unbalanced":
                    r["capacity"]["gross"] = "0.01"
                elif defect == "dishonest-book":
                    r["book"]["bestAsks"][0]["shares"] = "0.1"
                else:
                    r["capacity"] = None
                item = paper.record(db, ID, rev, r)
                self.assertEqual((item["cash"], item["decisions"][0]["kind"]), ("10", "incomplete"))
            report = paper.record(db, ID, 5, observed_buy(WALLET, "10.00"))
            self.assertEqual((report["cash"], report["nextBudget"]), ("0.14256", None))
            with self.assertRaises(Conflict):
                paper.record(db, ID, 6, observed_buy(WALLET, "10.00"))
            paper.verify_archive(db)

    def test_non_entries_history_and_tampered_ledger(self):
        self.create()
        with self.store.connection() as db:
            for rev in range(1, 26):
                kind = ("waiting", "unavailable", "incomplete", "skipped")[rev % 4]
                paper.record(db, ID, rev, dict(wallet=WALLET, researchBudget="10.00", status=kind, reason="Fixture window."))
            result = paper.record(db, ID, 26, observed_buy(WALLET, "10.00"))
            older = paper.report(db, ID, before=result["nextCursor"])
            self.assertEqual([d["revision"] for d in result["decisions"] + older["decisions"]], list(range(27, 1, -1)))
            db.execute("UPDATE public_decisions SET fee=0 WHERE kind='entry'")
        with self.assertRaisesRegex(ValueError, "recorded amounts"):
            copy_workspace(self.store.path, self.root / "invalid.db")
        self.assertFalse((self.root / "invalid.db").exists())

    def test_legacy_archive_restores_and_migrates(self):
        old = self.root / "legacy.db"
        with sqlite3.connect(old) as db:
            create_schema_v1(db)
            db.execute("UPDATE workspace SET theme='dark', settings_revision=4")
        target = self.root / "restored.db"
        copy_workspace(old, target)
        migrated = Workspace(target)
        self.assertEqual(migrated.read()["settings"], {"version": 1, "theme": "dark", "revision": 4})
        with migrated.connection() as db:
            self.assertEqual(paper.listing(db), {"runs": [], "nextCursor": None})

    def test_position_mark_is_revision_scoped_with_fresh_two_sided_identity(self):
        self.create()
        with self.store.connection() as db:
            paper.record(db, ID, 1, observed_buy(WALLET, "10.00"))
            with self.assertRaises(Conflict):
                paper.position_basis(db, ID, "734", 1)
            with self.assertRaises(ValueError):
                paper.position_basis(db, ID, "735", 2)
            basis = paper.position_basis(db, ID, "734", 2)
        now = time.time_ns() // 1_000_000
        fixture = book(timestamp=str(now), bids=[{"price": "0.49", "size": "12"}],
                       asks=[{"price": "0.50", "size": "1"}])
        for override in ({}, {"bids": []}, {"asks": []}, {"market": "wrong"},
                         {"timestamp": str(now - 10_000)},
                         {"timestamp": str(now - 60_001)}, {"timestamp": str(now + 1000)},
                         {"bids": [{"price": "0.50", "size": "3"}]}):
            with self.subTest(override=override), patch.object(public_marks, "read_public_json", return_value=fixture | override), patch.object(public_marks.time, "time_ns", return_value=now * 1_000_000):
                result = public_marks.read_mark(basis)
                if override:
                    self.assertIsNone(result["value"])
                    self.assertIsNone(result["changeFromCost"])
                else:
                    self.assertEqual((result["midpoint"], result["value"], result["changeFromCost"]),
                                     ("0.495", "9.405", "-0.45244"))
