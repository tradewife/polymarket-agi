"""Path ensemble shape and zero-drift. No live HTTP."""

from __future__ import annotations

import unittest

import numpy as np

from polyagent.paths import p_yes, simulate
from polyagent.price_markets import PriceContract


class PathTests(unittest.TestCase):
    def test_1h_shape_finite_positive(self) -> None:
        ens = simulate(
            "BTC",
            3600,
            n_paths=1000,
            spot=100.0,
            vol=0.0002,
            seed=7,
        )
        self.assertIsNotNone(ens)
        assert ens is not None
        self.assertEqual(ens.prices.shape, (1000, 61))
        self.assertTrue(np.all(np.isfinite(ens.prices)))
        self.assertTrue(np.all(ens.prices > 0))
        self.assertTrue(np.allclose(ens.prices[:, 0], 100.0))

    def test_24h_shape_matches_synth(self) -> None:
        ens = simulate(
            "ETH",
            24 * 3600,
            n_paths=200,
            spot=50.0,
            vol=0.0002,
            seed=1,
        )
        self.assertIsNotNone(ens)
        assert ens is not None
        self.assertEqual(ens.prices.shape, (200, 289))

    def test_zero_mean_log_return(self) -> None:
        ens = simulate(
            "SOL",
            3600,
            n_paths=2000,
            spot=100.0,
            vol=0.0003,
            seed=42,
        )
        assert ens is not None
        log_ret = np.log(ens.prices[:, -1] / ens.prices[:, 0])
        self.assertLess(abs(float(np.mean(log_ret))), 0.02)

    def test_p_yes_atm_is_halfish(self) -> None:
        ens = simulate(
            "BTC",
            3600,
            n_paths=2000,
            spot=100.0,
            vol=0.0002,
            seed=3,
        )
        assert ens is not None
        contract = PriceContract(
            asset="BTC",
            venue="binance",
            horizon_seconds=3600,
            strike=100.0,
            reference_price=100.0,
            settlement="close",
            yes_means="up",
            raw_question="test",
        )
        p = p_yes(ens, contract)
        self.assertGreater(p, 0.45)
        self.assertLess(p, 0.55)

    def test_injected_only_never_returns_none(self) -> None:
        ens = simulate("HYPE", 15 * 60, spot=10.0, vol=0.001, seed=0)
        self.assertIsNotNone(ens)
        assert ens is not None
        self.assertEqual(ens.prices.shape[1], 16)


if __name__ == "__main__":
    unittest.main()
