"""HOLD unless pair-arb after V2 taker fees, or path-edge on parsed crypto."""

from __future__ import annotations

import unittest

import numpy as np

from polyagent.paths import PathEnsemble
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

    def test_unparsed_stays_hold_without_p_true(self) -> None:
        j = judge(market(question="Will the Fed cut?"))
        self.assertEqual(j.action, "HOLD")
        self.assertIsNone(j.p_true)

    def test_all_paths_above_buys_yes(self) -> None:
        prices = np.full((32, 61), 110.0)
        prices[:, 0] = 100.0

        def sim(asset, horizon_seconds, **_k):
            return PathEnsemble(
                asset=asset,
                horizon_seconds=horizon_seconds,
                dt_seconds=60,
                spot=100.0,
                vol=0.001,
                prices=prices,
            )

        j = judge(
            market(
                question="Will Bitcoin be above $100 in the next 1 hour?",
                yes_price=0.50,
                no_price=0.50,
            ),
            simulate_fn=sim,
            path_edge=0.03,
        )
        self.assertEqual(j.action, "BUY_YES")
        self.assertIsNotNone(j.p_true)
        self.assertGreater(j.p_true or 0, 0.9)
        self.assertGreater(j.kelly_fraction, 0.0)
        self.assertIsNotNone(j.path)

    def test_all_paths_below_buys_no(self) -> None:
        prices = np.full((32, 61), 90.0)
        prices[:, 0] = 100.0

        def sim(asset, horizon_seconds, **_k):
            return PathEnsemble(
                asset=asset,
                horizon_seconds=horizon_seconds,
                dt_seconds=60,
                spot=100.0,
                vol=0.001,
                prices=prices,
            )

        j = judge(
            market(
                question="Will Bitcoin be above $100 in the next 1 hour?",
                yes_price=0.50,
                no_price=0.50,
            ),
            simulate_fn=sim,
            path_edge=0.03,
        )
        self.assertEqual(j.action, "BUY_NO")
        self.assertIsNotNone(j.p_true)

    def test_buffer_blocks_dust_edge(self) -> None:
        n = 100
        prices = np.full((n, 61), 99.0)
        prices[:51, -1] = 101.0
        prices[:, 0] = 100.0

        def sim(asset, horizon_seconds, **_k):
            return PathEnsemble(
                asset=asset,
                horizon_seconds=horizon_seconds,
                dt_seconds=60,
                spot=100.0,
                vol=0.001,
                prices=prices,
            )

        j = judge(
            market(
                question="Bitcoin Up or Down - 1 hour",
                yes_price=0.50,
                no_price=0.50,
            ),
            simulate_fn=sim,
            path_edge=0.03,
        )
        self.assertEqual(j.action, "HOLD")
        self.assertIsNotNone(j.p_true)

    def test_arb_still_wins_on_a_price_market(self) -> None:
        j = judge(
            market(
                question="Bitcoin Up or Down - 1 hour",
                yes_price=0.40,
                no_price=0.40,
                best_ask=0.40,
            )
        )
        self.assertEqual(j.action, "ARB")
        self.assertIsNone(j.p_true)


if __name__ == "__main__":
    unittest.main()

