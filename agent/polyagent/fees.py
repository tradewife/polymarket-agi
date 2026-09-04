"""Polymarket V2 paper-fee model.

Official taker fee (USDC / pUSD):

    fee = shares × rate × p × (1 - p)

When a market publishes ``fee_schedule.exponent``, that exponent is applied
to the price curve: ``(p * (1-p)) ** exponent``. Exponent 1 matches the
published fee tables.

Makers are not charged. Paper fills are modeled as takers (immediate last/ask
print), so they pay the taker fee. Maker rebates are not credited — they are
paid later from a pool and are not guaranteed per fill.
"""

from __future__ import annotations

from dataclasses import dataclass

# Fallback rates from https://docs.polymarket.com/trading/fees when a market
# does not publish a schedule. Geopolitics is fee-free.
DEFAULT_TAKER_RATE = {
    "crypto": 0.07,
    "sports": 0.05,
    "finance": 0.04,
    "politics": 0.04,
    "economics": 0.05,
    "culture": 0.05,
    "weather": 0.05,
    "other": 0.05,
    "general": 0.05,
    "mentions": 0.04,
    "tech": 0.04,
    "geopolitics": 0.0,
}


@dataclass(frozen=True)
class FeeQuote:
    rate: float
    exponent: float
    taker_only: bool
    fees_enabled: bool
    role: str  # taker | maker
    fee: float
    fee_per_share: float
    fill_price: float
    shares: float
    notional: float
    cash_debit: float


def taker_rate_for_category(category: str | None) -> float:
    if not category:
        return 0.05
    return DEFAULT_TAKER_RATE.get(category.strip().lower(), 0.05)


def fee_per_share(price: float, rate: float, exponent: float = 1.0) -> float:
    p = min(max(price, 1e-6), 1 - 1e-6)
    curve = p * (1.0 - p)
    if exponent != 1.0:
        curve = curve**exponent
    return max(0.0, rate * curve)


def quote_taker(
    *,
    shares: float,
    price: float,
    rate: float,
    exponent: float = 1.0,
    fees_enabled: bool = True,
    taker_only: bool = True,
    role: str = "taker",
) -> FeeQuote:
    fill_price = min(max(price, 0.001), 0.999)
    notional = shares * fill_price
    per_share = 0.0
    fee = 0.0
    if fees_enabled and role == "taker":
        per_share = fee_per_share(fill_price, rate, exponent)
        fee = round(shares * per_share, 6)
    elif fees_enabled and role == "maker":
        # Makers are not charged protocol fees.
        per_share = 0.0
        fee = 0.0
    cash_debit = round(notional + fee, 6)
    return FeeQuote(
        rate=rate,
        exponent=exponent,
        taker_only=taker_only,
        fees_enabled=fees_enabled,
        role=role,
        fee=fee,
        fee_per_share=per_share,
        fill_price=fill_price,
        shares=shares,
        notional=round(notional, 6),
        cash_debit=cash_debit,
    )


def shares_for_budget(
    *,
    price: float,
    budget: float,
    rate: float,
    exponent: float = 1.0,
    fees_enabled: bool = True,
    min_shares: float = 1.0,
) -> float:
    """Largest share count whose notional + taker fee fits in budget."""
    if price <= 0 or budget <= 0:
        return 0.0
    per_share_fee = fee_per_share(price, rate, exponent) if fees_enabled else 0.0
    all_in = price + per_share_fee
    if all_in <= 0:
        return 0.0
    shares = round(budget / all_in, 2)
    if shares < min_shares:
        return 0.0
    quote = quote_taker(
        shares=shares,
        price=price,
        rate=rate,
        exponent=exponent,
        fees_enabled=fees_enabled,
    )
    if quote.cash_debit > budget + 1e-9:
        shares = round((budget / all_in) - 0.01, 2)
    return max(shares, 0.0)
