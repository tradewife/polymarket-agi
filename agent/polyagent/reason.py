"""Reasoning slot for the trading loop.

Without an xAI key this module is honest: the market price *is* the public
probability. Inventing a different p_true from volume or "favorites" is not
edge. Default action is HOLD.

The only trade it will approve without extra information is a mechanical
pair mispricing: buying YES and NO together still costs less than $1 after
taker fees (locked $1 payout).
"""

from __future__ import annotations

from dataclasses import dataclass

from polyagent.fees import fee_per_share, quote_taker
from polyagent.scan import ScoredMarket


@dataclass(frozen=True)
class Judgment:
    market_id: str
    condition_id: str
    question: str
    action: str  # HOLD | BUY_YES | BUY_NO | ARB
    p_true: float | None
    confidence: float
    reasoning: str
    implied_yes: float
    fill_yes: float
    fill_no: float
    edge_after_fees: float
    kelly_fraction: float
    pair_cost: float


def quarter_kelly(p_true: float, price: float) -> float:
    if price <= 0 or price >= 1:
        return 0.0
    b = (1.0 / price) - 1.0
    if b <= 0:
        return 0.0
    q = 1.0 - p_true
    full = (b * p_true - q) / b
    return max(0.0, min(full, 1.0)) * 0.25


def _fill(market: ScoredMarket, last: float, side: str) -> float:
    if side == "YES" and market.best_ask is not None:
        return float(market.best_ask)
    return last


def judge(market: ScoredMarket) -> Judgment:
    yes = market.yes_price
    no = market.no_price
    fill_yes = _fill(market, yes, "YES")
    fill_no = max(0.001, min(0.999, no if market.best_ask is None else no))

    fee_yes = (
        fee_per_share(fill_yes, market.fee_rate, market.fee_exponent)
        if market.fees_enabled
        else 0.0
    )
    fee_no = (
        fee_per_share(fill_no, market.fee_rate, market.fee_exponent)
        if market.fees_enabled
        else 0.0
    )
    pair_cost = fill_yes + fill_no + fee_yes + fee_no

    # Mechanical lock: buy both legs, payout is $1.
    if pair_cost < 0.995 and market.yes_token and market.no_token:
        edge = 1.0 - pair_cost
        return Judgment(
            market_id=market.market_id,
            condition_id=market.condition_id,
            question=market.question,
            action="ARB",
            p_true=None,
            confidence=0.9,
            reasoning=(
                f"Pair costs {pair_cost:.4f} after taker fees vs $1 payout "
                f"(YES {fill_yes:.3f}+fee {fee_yes:.4f}, NO {fill_no:.3f}+fee {fee_no:.4f})."
            ),
            implied_yes=yes,
            fill_yes=fill_yes,
            fill_no=fill_no,
            edge_after_fees=edge,
            kelly_fraction=min(0.25, edge),
            pair_cost=pair_cost,
        )

    # No independent probability. A 50% prior vs an 80¢ favorite is negative Kelly.
    # Saying the favorite "should" win because it is expensive is not analysis.
    return Judgment(
        market_id=market.market_id,
        condition_id=market.condition_id,
        question=market.question,
        action="HOLD",
        p_true=None,
        confidence=0.0,
        reasoning=(
            "No independent p_true. Market price is the public estimate; "
            "buying the favorite is paying the book plus taker fee. HOLD."
        ),
        implied_yes=yes,
        fill_yes=fill_yes,
        fill_no=fill_no,
        edge_after_fees=0.0,
        kelly_fraction=0.0,
        pair_cost=pair_cost,
    )
