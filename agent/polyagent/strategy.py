from __future__ import annotations

from dataclasses import dataclass

from polyagent.config import Settings
from polyagent.fees import quote_taker, shares_for_budget
from polyagent.reason import Judgment, quarter_kelly
from polyagent.scan import ScoredMarket


@dataclass
class Intent:
    market: ScoredMarket
    outcome: str
    side: str
    price: float
    size: float
    token_id: str
    reason: str
    score: float
    fee: float = 0.0
    cash_debit: float = 0.0
    fill_role: str = "taker"
    kelly_fraction: float = 0.0


def _intent_for_leg(
    *,
    market: ScoredMarket,
    outcome: str,
    price: float,
    token_id: str,
    reason: str,
    settings: Settings,
    cash: float,
    kelly_fraction: float,
    score: float,
) -> Intent | None:
    if not token_id:
        return None
    kelly_budget = cash * kelly_fraction if kelly_fraction > 0 else 0.0
    budget = min(settings.max_position, max(0.0, cash), kelly_budget if kelly_budget > 0 else settings.max_position)
    if budget <= 0:
        return None
    shares = shares_for_budget(
        price=price,
        budget=budget,
        rate=market.fee_rate,
        exponent=market.fee_exponent,
        fees_enabled=market.fees_enabled,
        min_shares=1.0,
    )
    if shares <= 0:
        return None
    quote = quote_taker(
        shares=shares,
        price=price,
        rate=market.fee_rate,
        exponent=market.fee_exponent,
        fees_enabled=market.fees_enabled,
        taker_only=market.taker_only,
        role="taker",
    )
    return Intent(
        market=market,
        outcome=outcome,
        side="BUY",
        price=round(quote.fill_price, 4),
        size=quote.shares,
        token_id=token_id,
        reason=reason,
        score=score,
        fee=quote.fee,
        cash_debit=quote.cash_debit,
        fill_role="taker",
        kelly_fraction=kelly_fraction,
    )


def intents_from_judgment(
    market: ScoredMarket,
    judgment: Judgment,
    settings: Settings,
    cash: float,
) -> list[Intent]:
    if judgment.action == "HOLD":
        return []
    if judgment.action == "ARB":
        # Size each leg so both fit in remaining cash; Kelly on locked edge.
        half = cash * max(judgment.kelly_fraction, 0.02) / 2
        out: list[Intent] = []
        yes = _intent_for_leg(
            market=market,
            outcome="YES",
            price=judgment.fill_yes,
            token_id=market.yes_token or "",
            reason=judgment.reasoning,
            settings=settings,
            cash=min(cash, half * 2),
            kelly_fraction=judgment.kelly_fraction,
            score=judgment.edge_after_fees,
        )
        if yes:
            out.append(yes)
            cash -= yes.cash_debit
        no = _intent_for_leg(
            market=market,
            outcome="NO",
            price=judgment.fill_no,
            token_id=market.no_token or "",
            reason=judgment.reasoning,
            settings=settings,
            cash=cash,
            kelly_fraction=judgment.kelly_fraction,
            score=judgment.edge_after_fees,
        )
        if no:
            out.append(no)
        return out if len(out) == 2 else []

    if judgment.action == "BUY_YES" and judgment.p_true is not None:
        kf = quarter_kelly(judgment.p_true, judgment.fill_yes)
        intent = _intent_for_leg(
            market=market,
            outcome="YES",
            price=judgment.fill_yes,
            token_id=market.yes_token or "",
            reason=judgment.reasoning,
            settings=settings,
            cash=cash,
            kelly_fraction=kf,
            score=judgment.edge_after_fees,
        )
        return [intent] if intent else []

    if judgment.action == "BUY_NO" and judgment.p_true is not None:
        kf = quarter_kelly(1.0 - judgment.p_true, judgment.fill_no)
        intent = _intent_for_leg(
            market=market,
            outcome="NO",
            price=judgment.fill_no,
            token_id=market.no_token or "",
            reason=judgment.reasoning,
            settings=settings,
            cash=cash,
            kelly_fraction=kf,
            score=judgment.edge_after_fees,
        )
        return [intent] if intent else []

    return []


def pick_intents(
    markets: list[ScoredMarket],
    judgments: list[Judgment],
    settings: Settings,
    open_conditions: set[str],
    remaining_slots: int,
    cash: float,
) -> list[Intent]:
    by_id = {m.market_id: m for m in markets}
    ranked = sorted(judgments, key=lambda j: j.edge_after_fees, reverse=True)
    picked: list[Intent] = []
    remaining_cash = cash
    slots = remaining_slots
    for judgment in ranked:
        if slots <= 0 or remaining_cash <= 0:
            break
        if judgment.action == "HOLD":
            continue
        if judgment.condition_id in open_conditions or judgment.market_id in open_conditions:
            continue
        market = by_id.get(judgment.market_id)
        if market is None:
            continue
        batch = intents_from_judgment(market, judgment, settings, remaining_cash)
        if not batch:
            continue
        if len(batch) > slots:
            continue
        cost = sum(i.cash_debit for i in batch)
        if cost > remaining_cash + 1e-9:
            continue
        picked.extend(batch)
        remaining_cash -= cost
        slots -= len(batch)
        open_conditions.add(judgment.condition_id)
        open_conditions.add(judgment.market_id)
        if len(picked) >= settings.max_trades_per_cycle:
            break
    return picked
