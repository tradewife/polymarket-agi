"""V2 taker-fee quotes used by paper fills."""

from __future__ import annotations

import unittest

from polyagent.fees import fee_per_share, quote_taker, shares_for_budget, taker_rate_for_category


class FeeTests(unittest.TestCase):
    def test_fee_per_share_is_rate_times_p_one_minus_p(self) -> None:
        # shares × 0.05 × 0.5 × 0.5 = 0.0125 per share at 50¢, sports default
        self.assertAlmostEqual(fee_per_share(0.5, 0.05), 0.0125)

    def test_fee_zero_when_price_near_boundary(self) -> None:
        self.assertLess(fee_per_share(0.99, 0.05), fee_per_share(0.5, 0.05))

    def test_geopolitics_is_fee_free(self) -> None:
        self.assertEqual(taker_rate_for_category("geopolitics"), 0.0)

    def test_quote_taker_adds_fee_to_cash_debit(self) -> None:
        q = quote_taker(shares=10, price=0.5, rate=0.05)
        self.assertAlmostEqual(q.notional, 5.0)
        self.assertAlmostEqual(q.fee, 0.125)
        self.assertAlmostEqual(q.cash_debit, 5.125)

    def test_maker_role_pays_no_protocol_fee(self) -> None:
        q = quote_taker(shares=10, price=0.5, rate=0.05, role="maker")
        self.assertEqual(q.fee, 0.0)
        self.assertAlmostEqual(q.cash_debit, 5.0)

    def test_shares_for_budget_fits_including_fee(self) -> None:
        shares = shares_for_budget(price=0.5, budget=5.0, rate=0.05)
        q = quote_taker(shares=shares, price=0.5, rate=0.05)
        self.assertLessEqual(q.cash_debit, 5.0 + 1e-9)
        self.assertGreater(shares, 0.0)

    def test_zero_budget_yields_zero_shares(self) -> None:
        self.assertEqual(shares_for_budget(price=0.4, budget=0.0, rate=0.05), 0.0)


if __name__ == "__main__":
    unittest.main()
