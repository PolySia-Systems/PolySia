import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from apps.server import public_fill

# Public Polygon receipt from the fourth observation in docs/provider.md.
RECEIPT = json.loads((Path(__file__).parent / "fixtures/polygon-buy-receipt.json").read_text())
WALLET = "0xc69bd5567b40ef4d11922eaa57e1f9be1c642076"
EVENT = {"transactionHash": RECEIPT["transactionHash"], "price": "0.002", "shares": "5.0",
         "tokenId": "33339798372916037220786136133406478491116150628220441951753426683441228279665"}


class ParticipantTests(unittest.TestCase):
    def identify(self, receipt, wallet=WALLET, event=EVENT):
        with patch.object(public_fill, "_receipt", return_value=receipt):
            return public_fill.identify_buy(wallet, event)

    def test_real_receipt_counts_only_the_wallet_owned_order(self):
        result = self.identify(RECEIPT)
        self.assertEqual((result["status"], result["role"], result["logIndex"]), ("matched", "taker", 136))
        self.assertEqual(result["fillId"], f"137:{EVENT['transactionHash']}:136")
        self.assertEqual((result["collateralBaseUnits"], result["sharesBaseUnits"], result["feeBaseUnits"]),
                         ("10000", "5000000", "490"))
        self.assertEqual(result["orderHash"], RECEIPT["logs"][4]["topics"][1])
        self.assertEqual(result["amountMatchBasis"], "exact-price-and-shares")
        self.assertEqual((result["grossCollateral"], result["chargedFee"], result["totalCollateral"]),
                         ("0.01", "0.00049", "0.01049"))
        with_debit = self.identify(RECEIPT, event=dict(EVENT, reportedCollateral="0.01049"))
        self.assertEqual(with_debit["amountMatchBasis"], "exact-price-and-shares")
        self.assertEqual(self.identify(RECEIPT, event=dict(EVENT, reportedCollateral="0.01"))["status"], "unresolved")
        seller = RECEIPT["logs"][2]["topics"][2][-40:]
        self.assertEqual(self.identify(RECEIPT, "0x" + seller)["status"], "unresolved")

    def test_owner_side_survives_complementary_order_matching(self):
        receipt = copy.deepcopy(RECEIPT)
        maker_fill = next(log for log in receipt["logs"] if log["logIndex"] == "0x86")
        maker_fill["data"] = receipt["logs"][4]["data"]
        owner = "0x" + maker_fill["topics"][2][-40:]
        result = self.identify(receipt, owner)
        self.assertEqual((result["role"], result["logIndex"]), ("maker", 134))
        self.assertNotIn("totalCollateral", result)
        self.assertEqual(self.identify(receipt)["role"], "taker")

    @staticmethod
    def receipt_with_amounts(paid, shares, fee):
        receipt = copy.deepcopy(RECEIPT)
        own = receipt["logs"][4]
        data = own["data"]
        own["data"] = data[:130] + f"{paid:064x}{shares:064x}{fee:064x}" + data[322:]
        receipt["logs"][5]["data"] = own["data"][:258]
        return receipt

    def test_rounded_prices_from_two_public_taker_settlements(self):
        # Reuse the receipt envelope with the public amounts from Polygon block
        # 97958031, logs 646 and 605. Each activity debit includes the charged fee.
        for price, quantity, amount, gross, shares, fee, gross_text, fee_text in [
            ("0.649999974", "9.615385", "6.35937", 6250000, 9615385, 109370, "6.25", "0.10937"),
            ("0.5899999543", "5.254236", "3.163539", 3099999, 5254236, 63540, "3.099999", "0.06354"),
        ]:
            with self.subTest(price=price):
                event = dict(EVENT, price=price, shares=quantity, reportedCollateral=amount)
                result = self.identify(self.receipt_with_amounts(gross, shares, fee), event=event)
                self.assertEqual(result["amountMatchBasis"], "fee-inclusive-collateral-and-rounded-price")
                self.assertEqual((result["grossCollateral"], result["chargedFee"], result["totalCollateral"]),
                                 (gross_text, fee_text, amount))

    def test_rounded_price_requires_exact_debit_size_price_and_paired_taker(self):
        event = dict(EVENT, price="0.649999974", shares="9.615385", reportedCollateral="6.35937")
        receipt = self.receipt_with_amounts(6250000, 9615385, 109370)
        for changes in [{"reportedCollateral": None}, {"reportedCollateral": "6.25"},
                        {"reportedCollateral": "6.46874"}, {"reportedCollateral": "6.3593701"},
                        {"reportedCollateral": "NaN"}, {"reportedCollateral": True},
                        {"price": "0.65"}, {"price": "0.64999997400001"}, {"shares": "9.615386"}]:
            with self.subTest(changes=changes):
                self.assertNotIn("fillId", self.identify(receipt, event=event | changes))
        self.assertNotIn("fillId", self.identify(receipt, event={k: v for k, v in event.items() if k != "reportedCollateral"}))
        wrong_summary = copy.deepcopy(receipt)
        wrong_summary["logs"][5]["address"] = next(a for a in public_fill.EXCHANGES if a != receipt["logs"][4]["address"])
        self.assertNotIn("fillId", self.identify(wrong_summary, event=event))
        maker = copy.deepcopy(receipt)
        maker["logs"][4]["topics"][3] = "0x" + "00" * 12 + "af" * 20
        self.assertNotIn("fillId", self.identify(maker, event=event))

    def test_half_quantum_price_ties_remain_unresolved_and_zero_fee_is_exact(self):
        # 1 / 20,000,000,000 over 0.5 puts the chain price exactly on a tie.
        tied = self.receipt_with_amounts(10000000001, 20000000000, 0)
        event = dict(EVENT, shares="20000", reportedCollateral="10000.000001")
        for price in ("0.5", "0.5000000001"):
            self.assertNotIn("fillId", self.identify(tied, event=dict(event, price=price)))
        exact = self.identify(tied, event=dict(event, price="0.50000000005"))
        self.assertEqual((exact["chargedFee"], exact["totalCollateral"]), ("0", exact["grossCollateral"]))

    def test_ambiguous_wrong_amount_removed_or_untrusted_receipts_cannot_match(self):
        for case in ("two-orders", "duplicate-index", "wrong-amount", "removed", "unknown-exchange",
                     "wrong-summary", "wrong-block", "failed", "missing", "wrong-tx", "counterparty-only"):
            with self.subTest(case=case):
                r = copy.deepcopy(RECEIPT)
                event = EVENT.copy()
                own = next(log for log in r["logs"] if log["logIndex"] == "0x88")
                if case == "two-orders":
                    r["logs"].append(dict(own, logIndex="0xff"))
                elif case == "duplicate-index":
                    r["logs"].append(own)
                elif case == "wrong-amount":
                    event["price"] = "0.002000000000000000000000000000001"
                elif case == "removed":
                    own["removed"] = True
                elif case == "unknown-exchange":
                    own["address"] = "0x" + "af"*20
                elif case == "wrong-summary":
                    r["logs"] = [log for log in r["logs"] if log["logIndex"] != "0x89"]
                elif case == "wrong-block":
                    own["blockHash"] = "0x" + "dd"*32
                elif case == "failed":
                    r["status"] = "0x0"
                elif case == "wrong-tx":
                    event["transactionHash"] = "0x" + "cb"*32
                elif case == "counterparty-only":
                    r["logs"].remove(own)
                else:
                    r = None
                result = self.identify(r, event=event)
                self.assertNotEqual(result["status"], "matched")
                self.assertNotIn("fillId", result)

    def test_only_network_identity_and_receipt_are_requested(self):
        chain = {"id": 1, "jsonrpc": "2.0", "result": "0x89"}
        receipt = {"id": 2, "jsonrpc": "2.0", "result": RECEIPT}
        with patch.object(public_fill, "read_json_response", return_value=[receipt, chain]) as read:
            self.assertEqual(public_fill.identify_buy(WALLET, EVENT)["status"], "matched")
        request = read.call_args.args[0]
        self.assertEqual(request.full_url, public_fill.RPC)
        self.assertEqual([(r["method"], r["params"]) for r in json.loads(request.data)],
                         [("eth_chainId", []), ("eth_getTransactionReceipt", [EVENT["transactionHash"]])])
        for reply in ([dict(chain, result="0x1"), receipt], [receipt, receipt], [chain], None):
            with patch.object(public_fill, "read_json_response", return_value=reply):
                self.assertEqual(public_fill.identify_buy(WALLET, EVENT)["status"], "unavailable")
