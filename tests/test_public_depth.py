from decimal import Decimal
import unittest
from unittest.mock import patch

from apps.server import observe, public_depth
from test_observe import START, WALLET, activity, book, page


MS = START * 1000
EVENT = {"eventTimeSeconds": START, "conditionId": "0x" + "12" * 32, "tokenId": "734", "price": "0.50"}
EXCHANGE = "0xe111180000d2663c0091e4f400237545b87b996b"
TERMS = {"c": EVENT["conditionId"], "t": [{"t": "734"}, {"t": "735"}], "ao": True, "nr": False,
         "mos": 5, "mts": "0.01", "fd": {"r": "0.05", "e": 1, "to": True}}


def sample():
    return {"activityReceivedMs": MS + 1000, "evidenceCheckedMs": MS + 2000,
            "activityCoverage": {"complete": True}, "participant": {"status": "matched", "checkedMs": MS + 1600, "exchange": EXCHANGE},
            "bookRequestedMs": MS + 4000, "bookReceivedMs": MS + 4200, "event": EVENT,
            "book": {"sourceTimeMs": MS + 3800, "minimumOrderShares": "5", "priceTick": "0.01",
                     "spreadPerShare": "0.02", "bidLevelCount": 1, "negativeRisk": False,
                     "bestAsks": [{"price": "0.50", "shares": "7.9"},
                                  {"price": "0.51", "shares": "100"}, {"price": "0.54", "shares": "50"}]},
            "market": {**public_depth._terms(TERMS, EVENT), "status": "available", "checkedMs": MS + 1800}}


class DepthTests(unittest.TestCase):
    def test_whole_shares_across_levels_reserve_budget_and_fee(self):
        quote = public_depth.measure_depth(sample(), "10.00")
        self.assertEqual((quote["status"], quote["shares"], quote["gross"]), ("estimated", "19", "9.62"))
        self.assertEqual(quote["feeEstimate"], "0.23744")
        self.assertEqual(sum(Decimal(quote[k]) for k in ("gross", "feeEstimate", "unspent")), 10)

    def test_ceiling_fee_and_exact_one_micro_budget_boundary(self):
        s = sample()
        s["market"].update(minimumShares="1", priceTick="0.000001", takerRate="0.000001")
        s["book"].update(minimumOrderShares="1", priceTick="0.000001",
                         bestAsks=[{"price": "0.5", "shares": "5"}])
        quote = public_depth.measure_depth(s, "1.00")
        self.assertEqual((quote["shares"], quote["feeEstimate"], quote["unspent"]), ("1", "0.000001", "0.499999"))

    def test_no_estimate_with_missing_or_late_evidence(self):
        for case, status in (("unmatched", "incomplete"), ("partial", "incomplete"), ("pre-check", "incomplete"),
                             ("early", "incomplete"), ("late", "incomplete"), ("future", "incomplete"),
                             ("expired", "skipped"), ("closed", "skipped"), ("minimum", "skipped"),
                             ("price-cap", "skipped"), ("empty", "skipped"), ("off-tick", "incomplete"),
                             ("tick-mismatch", "incomplete"), ("duplicate", "incomplete"), ("no-terms", "incomplete")):
            with self.subTest(case=case):
                s = sample()
                if case == "unmatched":
                    s["participant"] = {"status": "unresolved"}
                elif case == "partial":
                    s["activityCoverage"]["complete"] = False
                elif case == "pre-check":
                    s["book"]["sourceTimeMs"] = s["evidenceCheckedMs"] - 1
                elif case == "early":
                    s["bookRequestedMs"] -= 1
                elif case == "late":
                    s["bookReceivedMs"] = s["evidenceCheckedMs"] + 5001
                elif case == "future":
                    s["book"]["sourceTimeMs"] = s["bookReceivedMs"] + 1
                elif case == "expired":
                    s["event"] = dict(EVENT, eventTimeSeconds=START-8)
                elif case == "closed":
                    s["market"]["acceptingOrders"] = False
                elif case == "minimum":
                    s["book"]["minimumOrderShares"] = s["market"]["minimumShares"] = "20"
                elif case == "price-cap":
                    s["event"] = dict(EVENT, price="0.46")
                elif case == "empty":
                    s["book"]["bestAsks"] = []
                elif case == "off-tick":
                    s["book"]["bestAsks"][0]["price"] = "0.501"
                elif case == "tick-mismatch":
                    s["book"]["priceTick"] = "0.02"
                elif case == "duplicate":
                    s["book"]["bestAsks"][1]["price"] = "0.50"
                else:
                    s["market"] = {"status": "unavailable", "reason": "Market unavailable."}
                quote = public_depth.measure_depth(s, "10.00")
                self.assertEqual(quote["status"], status)
                self.assertNotIn("shares", quote)

    def test_unrecognized_fee_curves_and_instrument_ids_stay_unknown(self):
        for change in ({"c": "another"}, {"t": []}, {"fd": None}, {"fd": {"r": 0, "e": 2, "to": True}},
                       {"fd": {"r": "0.01", "e": 1, "to": False}}, {"ao": "true"}, {"mts": 0}):
            with self.subTest(change=change), patch.object(public_depth, "read_public_json", return_value={**TERMS, **change}):
                self.assertEqual(public_depth.market_terms(EVENT)["status"], "unavailable")

    def test_crossed_missing_or_different_instrument_books_never_estimate_capacity(self):
        for change in ({"spreadPerShare": "-0.01"}, {"spreadPerShare": "0"}, {"bidLevelCount": None},
                       {"negativeRisk": True}):
            s = sample()
            s["book"].update(change)
            self.assertEqual(public_depth.measure_depth(s, "10.00")["status"], "incomplete")
        s = sample()
        s["market"]["takerDelayEnabled"] = True
        self.assertEqual(public_depth.measure_depth(s, "10.00")["status"], "incomplete")

    def test_multiple_rows_for_one_token_and_transaction_remain_unresolved(self):
        with (patch.object(observe.time, "time", return_value=START - 1),
              patch.object(observe.time, "sleep"),
              patch.object(observe, "read_public_json", side_effect=[
                  page([activity(size="5"), activity(size="5.00")]), book()]),
              patch.object(public_depth, "market_terms", return_value=sample()["market"]),
              patch.object(observe.public_fill, "identify_buy") as identify):
            receipt = observe.observe(WALLET, 1, budget="10")
        identify.assert_not_called()
        self.assertEqual(receipt["participant"]["status"], "unresolved")
        self.assertEqual(receipt["capacity"]["status"], "incomplete")

    def test_complete_probe_checks_inputs_before_starting_the_delay(self):
        calls = []
        now = [MS + 1000]
        def sleep(seconds):
            now[0] += round(seconds * 1000)
        def fetch(endpoint, params):
            calls.append(endpoint)
            if endpoint == observe.ACTIVITY:
                return page([activity(price="0.50", size="5")])
            self.assertIn("identity", calls)
            self.assertIn("market", calls)
            return book(timestamp=str(now[0]), asks=[{"price": "0.51", "size": "25"}],
                        neg_risk=False, bids=[{"price": "0.49", "size": "5"}])
        def terms(event):
            calls.append("market")
            return dict(sample()["market"], checkedMs=now[0])
        def identify(wallet, event):
            calls.append("identity")
            return {"status": "matched", "checkedMs": now[0], "exchange": EXCHANGE}
        with (patch.object(observe.time, "time", return_value=START - 1),
              patch.object(observe.time, "time_ns", side_effect=lambda: now[0] * 1_000_000),
              patch.object(observe.time, "sleep", side_effect=sleep),
              patch.object(observe, "read_public_json", side_effect=fetch),
              patch.object(public_depth, "market_terms", side_effect=terms),
              patch.object(observe.public_fill, "identify_buy", side_effect=identify)):
            receipt = observe.observe(WALLET, 1, budget="10")
        self.assertEqual(receipt["capacity"]["status"], "estimated")
        self.assertEqual(receipt["bookRequestedMs"] - receipt["evidenceCheckedMs"], 2000)
        self.assertEqual(receipt["schemaVersion"], 2)
        self.assertEqual(receipt["book"]["spreadPerShare"], "0.02")
