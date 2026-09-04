"""HOLD unless pair-arb after V2 taker fees."""

from __future__ import annotations

import unittest

from polyagent.reason import judge, quarter_kelly
from polyagent.scan import ScoredMarket


def market(**kwargs: object) -> ScoredMarket:
    base = dict(
        market_id="m1",
        condition_id="c1",
        question="Will X happen?",
        yes_price=0.52,
        no_price=0.48,
        yes_token="yes-tok",
        no_token="no-tok",
        volume_24h=10_000.0,
        liquidity=5_000.0,
        version="2",
        accepting=True,
        fees_enabled=True,
        fee_rate=0.05,
        fee_exponent=1.0,
    )
    base.update(kwargs)
    return ScoredMarket(**base)  # type: ignore[arg-type]


class ReasonTests(unittest.TestCase):
    def test_default_is_hold_when_book_sums_to_one(self) -> None:
        j = judge(market())
        self.assertEqual(j.action, "HOLD")
        self.assertIsNone(j.p_true)
        self.assertEqual(j.kelly_fraction, 0.0)

    def test_arb_when_both_legs_cheap_after_fees(self) -> None:
        # 0.40 + 0.40 + 2 * (0.05 * 0.4 * 0.6) = 0.80 + 0.024 = 0.824 < 0.995
        j = judge(market(yes_price=0.40, no_price=0.40, best_ask=0.40))
        self.assertEqual(j.action, "ARB")
        self.assertGreater(j.edge_after_fees, 0.0)
        self.assertLess(j.pair_cost, 0.995)

    def test_hold_when_fees_eat_the_apparent_arb(self) -> None:
        # 0.49 + 0.50 = 0.99 before fees; sports 5% curve at ~0.5 is 0.0125 each
        j = judge(market(yes_price=0.49, no_price=0.50, best_ask=0.49, fee_rate=0.05))
        self.assertEqual(j.action, "HOLD")

    def test_hold_without_both_tokens(self) -> None:
        j = judge(market(yes_price=0.30, no_price=0.30, no_token=None))
        self.assertEqual(j.action, "HOLD")

    def test_quarter_kelly_zero_without_edge(self) -> None:
        self.assertEqual(quarter_kelly(0.5, 0.5), 0.0)

    def test_quarter_kelly_positive_when_p_exceeds_price(self) -> None:
        k = quarter_kelly(0.8, 0.5)
        self.assertGreater(k, 0.0)
        self.assertLessEqual(k, 0.25)


if __name__ == "__main__":
    unittest.main()
