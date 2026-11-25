import json
import unittest
from decimal import Decimal
from unittest.mock import patch

from apps.server import shadow


def steps(run, count):
    for _ in range(count):
        run = shadow.apply_action(run, "step")
    return run


class ShadowReplayTests(unittest.TestCase):
    def test_distinct_profiles_and_period_basis(self):
        items = shadow.leaders()
        self.assertEqual(len(items), len({p["id"] for p in items}))
        for p in items:
            self.assertEqual(Decimal(p["pnl"]), p["history"][-1] - p["history"][0])
            self.assertEqual(p["source"], "scenario")
            self.assertEqual(shadow.create_run(p["id"])["market"], p["market"])

    def test_gate_unknown_inputs(self):
        with self.assertRaises(ValueError):
            shadow.create_run("live")
        for allocation, size in [("NaN", "1"), ("0.001", "1"), ("10001", "1"),
                                 ("9.99", "10"), ("100", "1001"), ("1e3", "3"),
                                 ("100", "-1"), (100, "1"), ("100", None)]:
            with self.subTest(allocation=allocation, size=size), self.assertRaises(ValueError):
                shadow.create_run("atlas", allocation, size)

    def test_floor_target_walk_prices_and_account_for_fees(self):
        initial = shadow.create_run("atlas")
        first = steps(initial, 1)
        event = first["events"][0]
        self.assertEqual(initial["events"], [])
        self.assertEqual(event["source_order"], "entry-1")  # Pre-run trade never replayed.
        self.assertEqual((event["quantity"], event["filled"], event["fee"]), ("19", "9.57", "0.10"))
        self.assertEqual(first["cash"], "90.33")
        self.assertEqual(first["cost_basis"], "9.67")
        self.assertGreater(Decimal(event["price"]), Decimal(event["leader_price"]))
        self.assertGreater(event["book_at"], event["observed_at"])
        self.assertEqual(event["decided_at"], event["book_at"])
        second = steps(first, 1)
        self.assertEqual(second["events"][-1]["status"], "partial")
        self.assertEqual(second["events"][-1]["quantity"], "4")
        self.assertEqual(second["quantity"], "23")
        self.assertEqual(second["pending_commitments"], "0.00")
        self.assertEqual(second["fees"], "0.13")

    def test_paused_entries_are_consumed_reductions_remain_authorized(self):
        first = steps(shadow.create_run("atlas"), 1)
        paused = shadow.apply_action(first, "pause")
        restored = json.loads(json.dumps(paused))
        paused = steps(restored, 4)
        self.assertEqual(paused["status"], "paused")
        self.assertEqual([e["status"] for e in paused["events"]], ["filled", "skipped", "skipped", "skipped", "filled"])
        self.assertEqual(paused["quantity"], "10")
        resumed = shadow.apply_action(paused, "resume")
        final = steps(resumed, resumed["remaining_steps"])
        self.assertEqual(final["quantity"], "10")
        self.assertEqual(final["status"], "completed")

    def test_stop_preserves_open_exposure_and_ledger(self):
        first = steps(shadow.create_run("atlas"), 1)
        stopped = shadow.apply_action(first, "stop")
        self.assertEqual(stopped, {**first, "status": "stopped"})
        for action in ("resume", "step", "pause", "stop"):
            with self.assertRaises(ValueError):
                shadow.apply_action(stopped, action)

    def test_partial_coverage_stale_signals_and_unattributed_exits(self):
        run = steps(shadow.create_run("atlas"), 2)
        original_cash = run["cash"]
        gap = steps(run, 1)
        self.assertIsNone(gap["marked_value"])
        self.assertIsNone(gap["liquidation_value"])
        delayed = steps(gap, 1)
        self.assertEqual(delayed["cash"], original_cash)
        self.assertIn("10 seconds", delayed["events"][-1]["reason"])
        reduction = steps(delayed, 1)
        self.assertEqual(reduction["quantity"], "12")
        self.assertEqual(reduction["realized_pnl"], "-0.06")
        done = steps(reduction, 2)
        self.assertEqual(done["cash"], reduction["cash"])
        self.assertIn("Duplicate", done["events"][-2]["reason"])
        self.assertIn("inventory", done["events"][-1]["reason"])
        self.assertGreater(Decimal(done["marked_value"]), Decimal(done["liquidation_value"]))

    def test_small_allocation_never_overdraws_even_when_a_share_will_not_fit(self):
        for p in shadow.leaders():
            for allocation, size in [("1", "1"), ("10.09", "10.08"), ("10000", "1000")]:
                run = shadow.create_run(p["id"], allocation, size)
                for _ in range(run["total_steps"]):
                    run = steps(run, 1)
                    e = run["events"][-1]
                    self.assertGreaterEqual(Decimal(run["cash"]), 0)
                    self.assertEqual(Decimal(run["cash"]) + Decimal(run["cost_basis"]),
                                     Decimal(allocation) + Decimal(run["realized_pnl"]))
                    if e["side"] == "BUY":
                        self.assertLessEqual(Decimal(e["filled"]) + Decimal(e["fee"]), Decimal(size))

    def test_deeper_positions_have_unknown_whole_liquidation(self):
        run = shadow.create_run("atlas", "10000.00", "1000.00")
        run = steps(run, run["total_steps"])
        self.assertGreater(int(run["quantity"]), 23)
        self.assertIsNotNone(run["marked_value"])
        self.assertIsNone(run["liquidation_value"])

    def test_no_lookahead_or_fill_outside_price_limit(self):
        run = shadow.create_run("atlas")
        early = shadow.Signal("test", "BUY", 10, 11, 49)
        future = shadow.Book(14, ((50, 20),), ((49, 20),))
        too_expensive = shadow.Book(13, ((53, 20),), ((49, 20),))
        for book in (future, too_expensive):
            with patch.object(shadow, "_tape", return_value=[(early, book)]):
                result = steps(run, 1)
            self.assertEqual(result["quantity"], "0")
            self.assertEqual(result["events"][0]["status"], "skipped")

    def test_valuation_after_consuming_an_entire_side(self):
        run = steps(shadow.create_run("atlas"), 2)
        self.assertIsNone(run["marked_value"])  # All displayed asks at this step consumed.
        self.assertEqual(run["liquidation_value"], "10.96")
        book = shadow.Book(11, ((50, 10),), ((49, 5), (48, 8)))
        residual = shadow._residual_book(book, "SELL", 5)
        self.assertEqual(residual.bids, ((48, 8),))
        shadow._mark(run, residual)
        self.assertEqual(run["marked_value"], "11.27")
        self.assertIsNone(run["liquidation_value"])  # Eight bid shares for 23 open shares.

    def test_exported_decisions_reconcile_without_a_provider_or_the_tape(self):
        run = steps(shadow.create_run("atlas"), 7)
        artifact = json.loads(json.dumps(run))
        cash, shares, fees = Decimal(artifact["capital"]), 0, Decimal(0)
        for event in artifact["events"]:
            if event["status"] == "skipped":
                continue
            buying = event["side"] == "BUY"
            levels = event["book"]["asks" if buying else "bids"]
            size, gross = int(event["quantity"]), Decimal(0)
            for level in levels:
                take = min(size, level["shares"])
                gross += take * Decimal(level["price"])
                size -= take
            self.assertEqual(size, 0)
            self.assertEqual(gross, Decimal(event["filled"]))
            fee = Decimal(event["fee"])
            fees += fee
            cash += (-gross if buying else gross) - fee
            shares += (1 if buying else -1) * int(event["quantity"])
        self.assertEqual((cash, shares, fees), (Decimal(artifact["cash"]),
                         int(artifact["quantity"]), Decimal(artifact["fees"])))

    def test_policy_version_mismatch_cannot_resume_with_different_terms(self):
        run = shadow.create_run("atlas")
        run["policy"]["fee_bps"] = 0
        with self.assertRaises(ValueError):
            steps(run, 1)
        self.assertEqual(shadow.apply_action(run, "stop")["status"], "stopped")
