"""Emit Synth-lib prediction files for a short backtest window.

Uses polyagent.paths.simulate when present; otherwise a local zero-drift
Student-t fallback so the night-shift pipe runs before paths.py lands.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from polyagent.synth_io import HORIZON, write_prediction

try:
    from polyagent.paths import simulate as _simulate
except ImportError:
    _simulate = None  # type: ignore[assignment]


def _fallback_simulate(
    *,
    spot: float,
    n_points: int,
    dt_seconds: int,
    vol: float,
    n_paths: int = 1000,
    seed: int = 0,
    nu: float = 5.0,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    # scale t-draws so Var(increment) ≈ vol^2 * dt
    dt_year = dt_seconds / (365.25 * 24 * 3600)
    step_var = (vol**2) * dt_year
    t_var = nu / (nu - 2.0)
    scale = np.sqrt(step_var / t_var)
    shocks = rng.standard_t(nu, size=(n_paths, n_points - 1)) * scale
    log_paths = np.concatenate(
        [np.zeros((n_paths, 1)), np.cumsum(shocks, axis=1)], axis=1
    )
    return spot * np.exp(log_paths)


def _spot_binance(asset: str) -> float:
    import json
    import urllib.request

    symbol = {"BTC": "BTCUSDT", "ETH": "ETHUSDT", "SOL": "SOLUSDT", "XRP": "XRPUSDT"}[asset]
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        data = json.loads(resp.read().decode())
    return float(data["price"])


def emit(
    dest: Path,
    *,
    asset: str,
    horizon: str,
    days: int,
    end: datetime | None = None,
    spot: float | None = None,
    vol: float = 0.6,
    seed: int = 7,
) -> list[Path]:
    spec = HORIZON[horizon]
    end = end or datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    if horizon == "24h":
        step = timedelta(hours=1)
    else:
        step = timedelta(minutes=15)
    start0 = end - timedelta(days=days)
    if spot is None:
        spot = _spot_binance(asset)
    written: list[Path] = []
    t = start0
    i = 0
    while t < end:
        if _simulate is not None:
            ens = _simulate(
                asset=asset,
                horizon_seconds=spec["time_length"],
                n_paths=1000,
                dt_seconds=spec["time_increment"],
                spot=spot,
                vol=vol,
                seed=seed + i,
            )
            prices = np.asarray(ens.prices if hasattr(ens, "prices") else ens)
        else:
            prices = _fallback_simulate(
                spot=spot,
                n_points=spec["n_points"],
                dt_seconds=spec["time_increment"],
                vol=vol,
                seed=seed + i,
            )
        written.append(
            write_prediction(
                dest,
                start=t,
                asset=asset,
                horizon=horizon,
                paths=prices.tolist(),
            )
        )
        t += step
        i += 1
    return written


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--asset", default="BTC")
    p.add_argument("--horizon", choices=sorted(HORIZON), default="24h")
    p.add_argument("--days", type=int, default=2)
    p.add_argument("--spot", type=float, default=None)
    p.add_argument("--vol", type=float, default=0.6)
    p.add_argument("--seed", type=int, default=7)
    args = p.parse_args()
    files = emit(
        args.out,
        asset=args.asset.upper(),
        horizon=args.horizon,
        days=args.days,
        spot=args.spot,
        vol=args.vol,
        seed=args.seed,
    )
    print(f"wrote {len(files)} files -> {args.out}")


if __name__ == "__main__":
    main()
