"""Price-market parser: listed crypto only, fail closed."""

from __future__ import annotations

import unittest

from polyagent.price_markets import parse_price_market
from polyagent.scan import ScoredMarket


def mkt(question: str) -> ScoredMarket:
    return ScoredMarket(
        market_id="1",
        condition_id="c",
        question=question,
        yes_price=0.5,
        no_price=0.5,
        yes_token="y",
        no_token="n",
        volume_24h=10_000,
        liquidity=1_000,
        version="2",
        accepting=True,
    )


class ParseTests(unittest.TestCase):
    def test_btc_updown_1h(self) -> None:
        c = parse_price_market(mkt("Bitcoin Up or Down - 1 hour"))
        self.assertIsNotNone(c)
        assert c is not None
        self.assertEqual(c.asset, "BTC")
        self.assertEqual(c.venue, "binance")
        self.assertEqual(c.horizon_seconds, 3600)
        self.assertEqual(c.yes_means, "up")
        self.assertEqual(c.settlement, "close")
        self.assertIsNone(c.strike)

    def test_eth_above_strike_1h(self) -> None:
        c = parse_price_market(
            mkt("Will Ethereum be above $4,000 in the next 1h?")
        )
        self.assertIsNotNone(c)
        assert c is not None
        self.assertEqual(c.asset, "ETH")
        self.assertEqual(c.yes_means, "above")
        self.assertEqual(c.strike, 4000.0)
        self.assertEqual(c.horizon_seconds, 3600)

    def test_sol_15m_updown(self) -> None:
        c = parse_price_market(mkt("Solana Up or Down 15 minutes"))
        self.assertIsNotNone(c)
        assert c is not None
        self.assertEqual(c.asset, "SOL")
        self.assertEqual(c.horizon_seconds, 15 * 60)

    def test_clock_range_is_1h(self) -> None:
        c = parse_price_market(
            mkt("Bitcoin Up or Down - September 5, 2:00AM-3:00AM ET")
        )
        self.assertIsNotNone(c)
        assert c is not None
        self.assertEqual(c.horizon_seconds, 3600)

    def test_reach_is_touch(self) -> None:
        c = parse_price_market(
            mkt("Will Bitcoin reach $150k in the next 24h?")
        )
        self.assertIsNotNone(c)
        assert c is not None
        self.assertEqual(c.settlement, "touch")
        self.assertEqual(c.yes_means, "above")
        self.assertEqual(c.strike, 150_000.0)
        self.assertEqual(c.horizon_seconds, 24 * 3600)

    def test_rejects_fed(self) -> None:
        self.assertIsNone(parse_price_market(mkt("Will the Fed cut?")))

    def test_rejects_5m(self) -> None:
        self.assertIsNone(
            parse_price_market(mkt("Bitcoin Up or Down - 5 minutes"))
        )

    def test_rejects_sports(self) -> None:
        self.assertIsNone(
            parse_price_market(mkt("Will Liverpool FC win on 2026-09-04?"))
        )


if __name__ == "__main__":
    unittest.main()
