"""Reasoning slot for the trading loop.

HOLD unless (1) pair-arb after fees or (2) a parsed crypto price market
whose path-ensemble p_true beats the fill by POLYAGENT_PATH_EDGE after V2
fees. Inventing p_true from volume or favorites is still not edge.

LIVE_TRADING is not flipped here. Path trades are a paper candidate.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from polyagent.config import _float
from polyagent.fees import fee_per_share
from polyagent.paths import PathEnsemble, p_yes, simulate
from polyagent.price_markets import parse_price_market
from polyagent.scan import ScoredMarket

SimulateFn = Callable[..., PathEnsemble | None]


@dataclass(frozen=True)
class PathTrace:
    asset: str
    horizon_seconds: int
    strike: float
    settlement: str
    n_paths: int
    spot: float
    vol: float
    yes_means: str


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
    path: PathTrace | None = None


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


def judge(
    market: ScoredMarket,
    *,
    simulate_fn: SimulateFn | None = None,
    path_edge: float | None = None,
) -> Judgment:
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

    contract = parse_price_market(market)
    if contract is None:
        return _hold(
            market,
            fill_yes,
            fill_no,
            pair_cost,
            "No independent p_true. Market price is the public estimate; "
            "buying the favorite is paying the book plus taker fee. HOLD.",
        )

    sim = simulate_fn or simulate
    try:
        ensemble = sim(
            asset=contract.asset,
            horizon_seconds=contract.horizon_seconds,
        )
    except TypeError:
        ensemble = sim(contract.asset, contract.horizon_seconds)
    except Exception:
        ensemble = None
    if ensemble is None:
        return _hold(
            market,
            fill_yes,
            fill_no,
            pair_cost,
            f"Parsed {contract.asset} {contract.horizon_seconds}s "
            f"{contract.settlement} but no spot/vol. HOLD.",
        )

    strike = contract.strike if contract.strike is not None else ensemble.spot
    try:
        p_true = p_yes(ensemble, contract)
    except Exception:
        return _hold(
            market,
            fill_yes,
            fill_no,
            pair_cost,
            "Path ensemble failed to score. HOLD.",
        )

    buffer = _float("POLYAGENT_PATH_EDGE", 0.03) if path_edge is None else path_edge

    yes_cost = fill_yes + fee_yes
    no_cost = fill_no + fee_no
    yes_edge = p_true - yes_cost
    no_edge = (1.0 - p_true) - no_cost
    trace = PathTrace(
        asset=contract.asset,
        horizon_seconds=contract.horizon_seconds,
        strike=strike,
        settlement=contract.settlement,
        n_paths=ensemble.n_paths,
        spot=ensemble.spot,
        vol=ensemble.vol,
        yes_means=contract.yes_means,
    )
    conf = min(0.8, 0.4 + 10.0 * abs(p_true - yes))
    base = (
        f"{contract.asset} {contract.horizon_seconds}s {contract.settlement} "
        f"yes_means={contract.yes_means} strike={strike:.6g} n_paths={ensemble.n_paths} "
        f"spot={ensemble.spot:.8g} vol={ensemble.vol:.6g} p_true={p_true:.4f} "
        f"implied={yes:.4f} fill_yes={fill_yes:.4f} fee_yes={fee_yes:.4f} "
        f"fill_no={fill_no:.4f} fee_no={fee_no:.4f} buffer={buffer:.4f}"
    )

    if p_true > yes_cost + buffer:
        kf = quarter_kelly(p_true, fill_yes)
        return Judgment(
            market_id=market.market_id,
            condition_id=market.condition_id,
            question=market.question,
            action="BUY_YES",
            p_true=p_true,
            confidence=conf,
            reasoning=f"{base} edge_yes={yes_edge:.4f}. BUY_YES.",
            implied_yes=yes,
            fill_yes=fill_yes,
            fill_no=fill_no,
            edge_after_fees=yes_edge,
            kelly_fraction=kf,
            pair_cost=pair_cost,
            path=trace,
        )
    if (1.0 - p_true) > no_cost + buffer:
        kf = quarter_kelly(1.0 - p_true, fill_no)
        return Judgment(
            market_id=market.market_id,
            condition_id=market.condition_id,
            question=market.question,
            action="BUY_NO",
            p_true=p_true,
            confidence=conf,
            reasoning=f"{base} edge_no={no_edge:.4f}. BUY_NO.",
            implied_yes=yes,
            fill_yes=fill_yes,
            fill_no=fill_no,
            edge_after_fees=no_edge,
            kelly_fraction=kf,
            pair_cost=pair_cost,
            path=trace,
        )
    return Judgment(
        market_id=market.market_id,
        condition_id=market.condition_id,
        question=market.question,
        action="HOLD",
        p_true=p_true,
        confidence=conf,
        reasoning=f"{base} neither side beats fill+fee+buffer. HOLD.",
        implied_yes=yes,
        fill_yes=fill_yes,
        fill_no=fill_no,
        edge_after_fees=0.0,
        kelly_fraction=0.0,
        pair_cost=pair_cost,
        path=trace,
    )


def _hold(
    market: ScoredMarket,
    fill_yes: float,
    fill_no: float,
    pair_cost: float,
    reasoning: str,
) -> Judgment:
    return Judgment(
        market_id=market.market_id,
        condition_id=market.condition_id,
        question=market.question,
        action="HOLD",
        p_true=None,
        confidence=0.0,
        reasoning=reasoning,
        implied_yes=market.yes_price,
        fill_yes=fill_yes,
        fill_no=fill_no,
        edge_after_fees=0.0,
        kelly_fraction=0.0,
        pair_cost=pair_cost,
    )
