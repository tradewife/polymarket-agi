"""Write Synth-lib / SN50 flat prediction JSON.

Format: https://github.com/synthdataco/synth-lib
Points: 1h -> 61 (dt=60), 24h -> 289 (dt=300). Always 1000 paths.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

HORIZON = {
    "1h": {"time_length": 3600, "time_increment": 60, "n_points": 61},
    "24h": {"time_length": 86400, "time_increment": 300, "n_points": 289},
}


def _ts_token(start: datetime) -> str:
    utc = start.astimezone(timezone.utc).replace(microsecond=0)
    return utc.strftime("%Y-%m-%d_%H:%M:%SZ")


def _iso(start: datetime) -> str:
    utc = start.astimezone(timezone.utc).replace(microsecond=0)
    return utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def filename(start: datetime, asset: str, time_length: int) -> str:
    return f"{_ts_token(start)}_{asset.upper()}_{time_length}.json"


def _sig8(value: float) -> float:
    if value <= 0 or value != value:  # NaN / non-positive
        raise ValueError(f"non-finite or non-positive price: {value!r}")
    return float(f"{value:.8g}")


def write_prediction(
    dest_dir: Path,
    *,
    start: datetime,
    asset: str,
    horizon: str,
    paths: Sequence[Sequence[float]],
) -> Path:
    spec = HORIZON[horizon]
    n_points = spec["n_points"]
    if len(paths) != 1000:
        raise ValueError(f"need 1000 paths, got {len(paths)}")
    cleaned: list[list[float]] = []
    for i, row in enumerate(paths):
        if len(row) != n_points:
            raise ValueError(f"path {i} has {len(row)} points, want {n_points}")
        cleaned.append([_sig8(float(x)) for x in row])
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / filename(start, asset, spec["time_length"])
    payload = {
        "start_timestamp": _iso(start),
        "asset": asset.upper(),
        "time_increment": spec["time_increment"],
        "time_length": spec["time_length"],
        "paths": cleaned,
    }
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    return path
