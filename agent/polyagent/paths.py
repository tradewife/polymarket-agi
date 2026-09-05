"""Zero-drift Student-t price-path ensemble.

Statistical v1: spot from Binance (HYPE from Hyperliquid), EWMA vol,
i.i.d. t_5 log-increments, mean 0. Network failure → None (judge HOLDs).
Tests inject spot/vol/seed and never hit the network.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

import numpy as np

from polyagent.price_markets import PriceContract

NU = 5.0
N_PATHS_DEFAULT = 1000
_CACHE_TTL = 90.0
_UA = {"User-Agent": "polyagent/0.1"}

_BINANCE_SYMBOL = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "SOL": "SOLUSDT",
    "XRP": "XRPUSDT",
}

_cache: dict[str, tuple[float, Any]] = {}


@dataclass(frozen=True)
class PathEnsemble:
    asset: str
    horizon_seconds: int
    dt_seconds: int
    spot: float
    vol: float
    prices: np.ndarray  # (n_paths, n_steps), includes t0

    @property
    def n_paths(self) -> int:
        return int(self.prices.shape[0])

    @property
    def n_steps(self) -> int:
        return int(self.prices.shape[1])


def dt_for_horizon(horizon_seconds: int) -> int:
    if horizon_seconds <= 60 * 60:
        return 60
    return 300


def n_steps_for(horizon_seconds: int, dt_seconds: int | None = None) -> int:
    dt = dt_seconds or dt_for_horizon(horizon_seconds)
    if dt <= 0 or horizon_seconds <= 0:
        raise ValueError("horizon and dt must be positive")
    return horizon_seconds // dt + 1


def simulate(
    asset: str,
    horizon_seconds: int,
    n_paths: int = N_PATHS_DEFAULT,
    dt_seconds: int | None = None,
    spot: float | None = None,
    vol: float | None = None,
    seed: int | None = None,
) -> PathEnsemble | None:
    asset = asset.upper()
    dt = dt_seconds or dt_for_horizon(horizon_seconds)
    steps = n_steps_for(horizon_seconds, dt)
    if n_paths < 1 or steps < 2:
        return None
    if spot is None:
        spot = fetch_spot(asset)
    if vol is None:
        vol = fetch_vol(asset, dt_seconds=dt)
    if spot is None or vol is None or spot <= 0 or vol < 0:
        return None
    try:
        prices = _walk(float(spot), float(vol), n_paths, steps, dt, seed)
    except (ValueError, FloatingPointError):
        return None
    if not np.all(np.isfinite(prices)) or np.any(prices <= 0):
        return None
    return PathEnsemble(
        asset=asset,
        horizon_seconds=horizon_seconds,
        dt_seconds=dt,
        spot=float(spot),
        vol=float(vol),
        prices=prices,
    )


def p_yes(ensemble: PathEnsemble, contract: PriceContract) -> float:
    strike = contract.strike if contract.strike is not None else ensemble.spot
    prices = ensemble.prices
    if contract.settlement == "touch":
        if contract.yes_means in {"up", "above"}:
            hits = np.max(prices, axis=1) >= strike
        else:
            hits = np.min(prices, axis=1) <= strike
    else:
        terminal = prices[:, -1]
        if contract.yes_means in {"up", "above"}:
            hits = terminal >= strike
        else:
            hits = terminal <= strike
    p = float(np.mean(hits))
    return min(max(p, 1e-6), 1.0 - 1e-6)


def fetch_spot(asset: str) -> float | None:
    key = f"spot:{asset}"
    hit = _cached(key)
    if hit is not None:
        return float(hit)
    try:
        if asset == "HYPE":
            data = _http_json(
                "https://api.hyperliquid.xyz/info",
                payload={"type": "allMids"},
            )
            if not isinstance(data, dict) or "HYPE" not in data:
                return None
            spot = float(data["HYPE"])
        else:
            symbol = _BINANCE_SYMBOL.get(asset)
            if not symbol:
                return None
            data = _http_json(
                f"https://api.binance.com/api/v3/ticker/bookTicker?symbol={symbol}"
            )
            bid = float(data["bidPrice"])
            ask = float(data["askPrice"])
            if bid <= 0 or ask <= 0:
                return None
            spot = (bid + ask) / 2.0
    except (KeyError, TypeError, ValueError, urllib.error.URLError, TimeoutError, OSError):
        return None
    if not np.isfinite(spot) or spot <= 0:
        return None
    _store(key, spot)
    return spot


def fetch_vol(asset: str, dt_seconds: int) -> float | None:
    """Per-second log-return stdev from EWMA of matching bars. None on failure."""
    key = f"vol:{asset}:{dt_seconds}"
    hit = _cached(key)
    if hit is not None:
        return float(hit)
    interval = "1m" if dt_seconds <= 60 else "5m"
    bar_seconds = 60 if interval == "1m" else 300
    try:
        closes = _closes(asset, interval)
    except (KeyError, TypeError, ValueError, urllib.error.URLError, TimeoutError, OSError):
        return None
    if closes is None or len(closes) < 20:
        return None
    log_rets = np.diff(np.log(closes))
    log_rets = log_rets[np.isfinite(log_rets)]
    if log_rets.size < 10:
        return None
    var_bar = _ewma_var(log_rets)
    if var_bar <= 0 or not np.isfinite(var_bar):
        return None
    vol = float(np.sqrt(var_bar / bar_seconds))
    _store(key, vol)
    return vol


def clear_feed_cache() -> None:
    _cache.clear()


def _walk(
    spot: float,
    vol_per_second: float,
    n_paths: int,
    n_steps: int,
    dt_seconds: int,
    seed: int | None,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    raw = rng.standard_t(NU, size=(n_paths, n_steps - 1))
    unit = raw / np.sqrt(NU / (NU - 2.0))
    sigma = vol_per_second * np.sqrt(dt_seconds)
    increments = sigma * unit  # mean 0 by construction
    log_levels = np.concatenate(
        [np.zeros((n_paths, 1)), np.cumsum(increments, axis=1)],
        axis=1,
    )
    prices = spot * np.exp(log_levels)
    prices = np.maximum(prices, 1e-12)
    return prices


def _ewma_var(log_rets: np.ndarray, lam: float = 0.94) -> float:
    v = 0.0
    for r in log_rets:
        v = lam * v + (1.0 - lam) * float(r) * float(r)
    return v


def _closes(asset: str, interval: str) -> np.ndarray | None:
    if asset == "HYPE":
        now_ms = int(time.time() * 1000)
        lookback = 6 * 60 * 60 * 1000
        data = _http_json(
            "https://api.hyperliquid.xyz/info",
            payload={
                "type": "candleSnapshot",
                "req": {
                    "coin": "HYPE",
                    "interval": interval,
                    "startTime": now_ms - lookback,
                    "endTime": now_ms,
                },
            },
        )
        if not isinstance(data, list) or not data:
            return None
        closes = np.array([float(c["c"]) for c in data], dtype=float)
    else:
        symbol = _BINANCE_SYMBOL.get(asset)
        if not symbol:
            return None
        data = _http_json(
            "https://api.binance.com/api/v3/klines"
            f"?symbol={symbol}&interval={interval}&limit=120"
        )
        if not isinstance(data, list) or not data:
            return None
        closes = np.array([float(row[4]) for row in data], dtype=float)
    closes = closes[np.isfinite(closes) & (closes > 0)]
    return closes if closes.size else None


def _http_json(url: str, payload: dict | None = None) -> Any:
    if payload is None:
        req = urllib.request.Request(url, headers=_UA)
    else:
        body = json.dumps(payload).encode()
        headers = {**_UA, "Content-Type": "application/json"}
        req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode())


def _cached(key: str) -> Any | None:
    item = _cache.get(key)
    if item is None:
        return None
    ts, value = item
    if time.monotonic() - ts > _CACHE_TTL:
        _cache.pop(key, None)
        return None
    return value


def _store(key: str, value: Any) -> None:
    _cache[key] = (time.monotonic(), value)
