"""Parse Polymarket questions into listed-crypto price contracts.

Fail closed: if the question is not a BTC/ETH/SOL/XRP/HYPE close-or-touch
market on an accepted horizon, return None and judge() HOLDs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from polyagent.scan import ScoredMarket

ASSETS = ("BTC", "ETH", "SOL", "XRP", "HYPE")
VENUE = {
    "BTC": "binance",
    "ETH": "binance",
    "SOL": "binance",
    "XRP": "binance",
    "HYPE": "hyperliquid",
}
ALIASES = {
    "bitcoin": "BTC",
    "btc": "BTC",
    "ethereum": "ETH",
    "ether": "ETH",
    "eth": "ETH",
    "solana": "SOL",
    "sol": "SOL",
    "ripple": "XRP",
    "xrp": "XRP",
    "hyperliquid": "HYPE",
    "hype": "HYPE",
}
HORIZON_SECONDS = {
    "15m": 15 * 60,
    "1h": 60 * 60,
    "4h": 4 * 60 * 60,
    "24h": 24 * 60 * 60,
}

_SKIP_5M = re.compile(
    r"\b(5\s*-?\s*m(?:in(?:ute)?s?)?|five\s+minutes?)\b", re.I
)
_ASSET = re.compile(
    r"\b(bitcoin|btc|ethereum|ether|eth|solana|sol|ripple|xrp|hyperliquid|hype)\b",
    re.I,
)
_STRIKE = re.compile(
    r"(?:\$|usd\s*)?\s*(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(k|m|thousand|million)?\b",
    re.I,
)
_CLOCK_RANGE = re.compile(
    r"(\d{1,2}):(\d{2})\s*(am|pm)?\s*[-–to]+\s*(\d{1,2}):(\d{2})\s*(am|pm)?",
    re.I,
)
_ABOVE = re.compile(r"\b(above|over|higher than|at least|greater than)\b", re.I)
_BELOW = re.compile(r"\b(below|under|lower than|less than|dip to)\b", re.I)
_UP = re.compile(r"\b(up or down|go up|goes up|finish up|end up|higher)\b", re.I)
_DOWN = re.compile(r"\b(go down|goes down|finish down|end down|lower)\b", re.I)
_TOUCH = re.compile(
    r"\b(reach|hit|touch|high|low|ath|all[- ]time high|intraday)\b", re.I
)


@dataclass(frozen=True)
class PriceContract:
    asset: str
    venue: str
    horizon_seconds: int
    strike: float | None
    reference_price: float | None
    settlement: str  # close | touch
    yes_means: str  # up | down | above | below
    raw_question: str


def parse_price_market(
    market: ScoredMarket | str, slug: str | None = None
) -> PriceContract | None:
    if isinstance(market, ScoredMarket):
        text = " ".join(
            p for p in (market.question, slug, market.category) if p
        )
    else:
        text = " ".join(p for p in (market, slug) if p)
    if not text.strip():
        return None
    if _SKIP_5M.search(text):
        return None

    asset = _asset(text)
    if asset is None:
        return None
    horizon = _horizon(text)
    if horizon is None:
        return None

    settlement = "touch" if _TOUCH.search(text) else "close"
    yes_means, strike = _side_and_strike(text)
    if yes_means is None:
        return None
    if yes_means in {"above", "below"} and strike is None:
        return None
    return PriceContract(
        asset=asset,
        venue=VENUE[asset],
        horizon_seconds=horizon,
        strike=strike,
        reference_price=None,
        settlement=settlement,
        yes_means=yes_means,
        raw_question=text if isinstance(market, str) else market.question,
    )


def _asset(text: str) -> str | None:
    found: list[str] = []
    for match in _ASSET.finditer(text):
        found.append(ALIASES[match.group(1).lower()])
    uniq = list(dict.fromkeys(found))
    if len(uniq) != 1:
        return None
    return uniq[0]


def _horizon(text: str) -> int | None:
    lower = text.lower()
    # Explicit first so "15m" is not eaten by a 1h clock phrase elsewhere.
    if re.search(r"\b15\s*-?\s*m(?:in(?:ute)?s?)?\b", lower) or re.search(
        r"\bfifteen\s+minutes?\b", lower
    ):
        return HORIZON_SECONDS["15m"]
    if re.search(r"\b4\s*-?\s*h(?:ours?)?\b", lower) or re.search(
        r"\bfour\s+hours?\b", lower
    ):
        return HORIZON_SECONDS["4h"]
    if re.search(
        r"\b(24\s*-?\s*h(?:ours?)?|daily|1\s*day|one\s+day|end of (the )?day|eod)\b",
        lower,
    ):
        return HORIZON_SECONDS["24h"]
    if re.search(r"\b(1\s*-?\s*h(?:our)?|one\s+hour|hourly|60\s*m(?:in)?s?)\b", lower):
        return HORIZON_SECONDS["1h"]
    ranged = _horizon_from_clock(text)
    if ranged is not None:
        return ranged
    return None


def _horizon_from_clock(text: str) -> int | None:
    match = _CLOCK_RANGE.search(text)
    if not match:
        return None
    h1, m1, ap1, h2, m2, ap2 = match.groups()
    t1 = _minutes(int(h1), int(m1), ap1)
    t2 = _minutes(int(h2), int(m2), ap2 or ap1)
    if t1 is None or t2 is None:
        return None
    delta = (t2 - t1) % (24 * 60)
    if delta == 0:
        delta = 24 * 60
    seconds = delta * 60
    if seconds == 15 * 60:
        return HORIZON_SECONDS["15m"]
    if seconds == 60 * 60:
        return HORIZON_SECONDS["1h"]
    if seconds == 4 * 60 * 60:
        return HORIZON_SECONDS["4h"]
    if seconds == 24 * 60 * 60:
        return HORIZON_SECONDS["24h"]
    return None


def _minutes(hour: int, minute: int, ampm: str | None) -> int | None:
    if minute < 0 or minute > 59 or hour < 0 or hour > 23:
        return None
    h = hour
    if ampm:
        ap = ampm.lower()
        h = hour % 12
        if ap == "pm":
            h += 12
    return h * 60 + minute


def _side_and_strike(text: str) -> tuple[str | None, float | None]:
    strike = _first_strike(text)
    if _BELOW.search(text) and strike is not None:
        return "below", strike
    if _ABOVE.search(text) and strike is not None:
        return "above", strike
    if re.search(r"\bup or down\b", text, re.I):
        return "up", strike
    if _DOWN.search(text) and not _UP.search(text):
        return "down", strike
    if _UP.search(text):
        return "up", strike
    if strike is not None and _TOUCH.search(text):
        # "reach $X" / "hit $X" is a touch-from-below unless the question says dip/low.
        if re.search(r"\b(dip|low)\b", text, re.I):
            return "below", strike
        return "above", strike
    if strike is not None:
        # Bare "BTC $X in 1h" is not a side. Fail closed.
        return None, strike
    return None, None


def _first_strike(text: str) -> float | None:
    # Skip clock-like numbers already consumed as times by requiring $ or k/m
    # or a price word nearby. Also accept comma-grouped USD.
    for match in _STRIKE.finditer(text):
        raw, suffix = match.group(1), (match.group(2) or "").lower()
        start = match.start()
        window = text[max(0, start - 12) : match.end() + 8].lower()
        looks_price = (
            "$" in window
            or "usd" in window
            or suffix in {"k", "m", "thousand", "million"}
            or "," in raw
        )
        if not looks_price:
            continue
        try:
            value = float(raw.replace(",", ""))
        except ValueError:
            continue
        if suffix in {"k", "thousand"}:
            value *= 1_000
        elif suffix in {"m", "million"}:
            value *= 1_000_000
        if value <= 0:
            continue
        return value
    return None
