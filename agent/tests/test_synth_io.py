from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from polyagent.emit_synth import (
    _fallback_simulate,
    annual_vol_to_per_second,
    emit,
)
from polyagent.synth_io import write_prediction


class SynthIoTests(unittest.TestCase):
    def test_24h_file_shape(self) -> None:
        start = datetime(2026, 9, 4, tzinfo=timezone.utc)
        paths = _fallback_simulate(
            spot=100_000.0, n_points=289, dt_seconds=300, vol=0.5, seed=1
        )
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            path = write_prediction(
                dest, start=start, asset="BTC", horizon="24h", paths=paths.tolist()
            )
            self.assertEqual(path.name, "2026-09-04_00:00:00Z_BTC_86400.json")
            payload = json.loads(path.read_text())
            self.assertEqual(payload["time_length"], 86400)
            self.assertEqual(payload["time_increment"], 300)
            self.assertEqual(len(payload["paths"]), 1000)
            self.assertEqual(len(payload["paths"][0]), 289)
            self.assertAlmostEqual(payload["paths"][0][0], 100_000.0, delta=1.0)
            self.assertTrue(all(p > 0 for p in payload["paths"][0][:8]))

    def test_emit_one_hour_injected_spot(self) -> None:
        end = datetime(2026, 9, 4, 1, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            files = emit(
                dest,
                asset="BTC",
                horizon="24h",
                days=1 / 24,
                end=end + timedelta(hours=1),
                spot=50_000.0,
                vol=0.5,
                seed=2,
            )
            self.assertEqual(len(files), 1)
            payload = json.loads(files[0].read_text())
            self.assertEqual(payload["asset"], "BTC")
            self.assertEqual(len(payload["paths"]), 1000)
            self.assertEqual(len(payload["paths"][0]), 289)
            self.assertAlmostEqual(payload["paths"][0][0], 50_000.0, delta=1.0)

    def test_annual_vol_converts_to_small_per_second(self) -> None:
        ps = annual_vol_to_per_second(0.6)
        self.assertGreater(ps, 0)
        self.assertLess(ps, 0.01)


if __name__ == "__main__":
    unittest.main()

