from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from polymarket import PublicClient

from polyagent.fees import taker_rate_for_category


def _dec(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)


@dataclass
class ScoredMarket:
    market_id: str
    condition_id: str
    question: str
    yes_price: float
    no_price: float
    yes_token: str | None
    no_token: str | None
    volume_24h: float
    liquidity: float
    version: str | None
    accepting: bool
    category: str | None = None
    best_bid: float | None = None
    best_ask: float | None = None
    fees_enabled: bool = True
    fee_rate: float = 0.05
    fee_exponent: float = 1.0
    taker_only: bool = True


def fetch_candidates(limit: int = 80, min_volume_24h: float = 8000.0) -> list[ScoredMarket]:
    out: list[ScoredMarket] = []
    with PublicClient() as client:
        page = client.list_markets(
            closed=False,
            volume_num_min=min_volume_24h,
            order="volume24hr",
            ascending=False,
            page_size=min(limit, 50),
        ).first_page()
        for market in page.items:
            state = market.state
            if state.closed or state.archived:
                continue
            if state.accepting_orders is False or state.enable_order_book is False:
                continue
            yes = _dec(market.outcomes.yes.price)
            no = _dec(market.outcomes.no.price)
            if yes is None or no is None:
                continue
            vol = _dec(market.metrics.volume_24hr) or _dec(market.metrics.volume_num) or 0.0
            liq = _dec(market.metrics.liquidity_num) or _dec(market.metrics.liquidity) or 0.0
            yes_token = market.outcomes.yes.token_id or market.outcomes.yes.position_id
            no_token = market.outcomes.no.token_id or market.outcomes.no.position_id
            schedule = market.trading.fee_schedule
            fees_enabled = bool(market.trading.fees_enabled) if market.trading.fees_enabled is not None else True
            if schedule is not None:
                fee_rate = float(schedule.rate)
                fee_exponent = float(schedule.exponent)
                taker_only = bool(schedule.taker_only)
            else:
                fee_rate = taker_rate_for_category(market.category)
                fee_exponent = 1.0
                taker_only = True
            if not fees_enabled:
                fee_rate = 0.0
            out.append(
                ScoredMarket(
                    market_id=str(market.id),
                    condition_id=str(market.condition_id or ""),
                    question=market.question or market.slug or str(market.id),
                    yes_price=yes,
                    no_price=no,
                    yes_token=str(yes_token) if yes_token else None,
                    no_token=str(no_token) if no_token else None,
                    volume_24h=vol,
                    liquidity=liq,
                    version=str(market.version) if market.version else None,
                    accepting=True,
                    category=market.category,
                    best_bid=_dec(market.prices.best_bid),
                    best_ask=_dec(market.prices.best_ask),
                    fees_enabled=fees_enabled,
                    fee_rate=fee_rate,
                    fee_exponent=fee_exponent,
                    taker_only=taker_only,
                )
            )
    return out
