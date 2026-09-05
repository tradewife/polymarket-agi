from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from polyagent.emit_synth import _fallback_simulate
from polyagent.synth_io import write_prediction


class SynthIoTests(unittest.TestCase):
    def test_24h_file_shape(self) -> None:
        start = datetime(2026, 9, 4, tzinfo=timezone.utc)
        paths = _fallback_simulate(spot=100_000.0, n_points=289, dt_seconds=300, vol=0.5, seed=1)
        dest = Path("/tmp/polyagent-synth-io")
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


if __name__ == "__main__":
    unittest.main()
