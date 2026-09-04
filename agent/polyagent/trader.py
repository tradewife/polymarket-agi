from __future__ import annotations

from polyagent.config import Settings
from polyagent.db import AgentDB, utcnow
from polyagent.strategy import Intent


def execute_paper(db: AgentDB, intent: Intent) -> dict:
    db.begin()
    try:
        if db.open_count() >= 10_000:
            raise RuntimeError("open count overflow")
        db.debit_cash(intent.cash_debit, intent.fee)
        trade_id = db.record_trade(
            created_at=utcnow(),
            market_id=intent.market.market_id,
            condition_id=intent.market.condition_id,
            question=intent.market.question,
            side=intent.side,
            outcome=intent.outcome,
            price=intent.price,
            size=intent.size,
            notional=round(intent.price * intent.size, 6),
            token_id=intent.token_id,
            status="open",
            paper=1,
            order_id=f"paper-{intent.market.market_id}-{intent.outcome}",
            reason=intent.reason,
            fee=intent.fee,
            fill_role=intent.fill_role,
            cash_debit=intent.cash_debit,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {
        "id": trade_id,
        "mode": "paper",
        "status": "open",
        "fee": intent.fee,
        "cash_debit": intent.cash_debit,
    }


def execute_live(settings: Settings, db: AgentDB, intent: Intent) -> dict:
    from polymarket import SecureClient

    if not settings.private_key:
        raise RuntimeError("LIVE_TRADING is on but no private key is configured")

    kwargs = {"private_key": settings.private_key}
    if settings.funder_address:
        kwargs["wallet"] = settings.funder_address

    with SecureClient.create(**kwargs) as client:
        result = client.place_limit_order(
            asset_id=intent.token_id,
            price=intent.price,
            size=intent.size,
            side=intent.side,
            post_only=True,
        )

    order_id = getattr(result, "order_id", None) or getattr(result, "id", None)
    status = getattr(result, "status", None) or "pending"
    trade_id = db.record_trade(
        created_at=utcnow(),
        market_id=intent.market.market_id,
        condition_id=intent.market.condition_id,
        question=intent.market.question,
        side=intent.side,
        outcome=intent.outcome,
        price=intent.price,
        size=intent.size,
        notional=round(intent.price * intent.size, 4),
        token_id=intent.token_id,
        status=str(status).lower(),
        paper=0,
        order_id=str(order_id) if order_id else None,
        reason=intent.reason,
        fee=0.0,
        fill_role="maker",
        cash_debit=round(intent.price * intent.size, 6),
    )
    db.commit()
    return {"id": trade_id, "mode": "live", "status": status, "order_id": order_id}


def mark_to_market(db: AgentDB, markets_by_condition: dict[str, object]) -> int:
    """Close paper trades when price is effectively settled. Credits remaining cash."""
    closed = 0
    for trade in list(db.open_trades()):
        if not trade["paper"]:
            continue
        market = markets_by_condition.get(trade["condition_id"])
        if market is None:
            continue
        yes = getattr(market, "yes_price", None)
        if yes is None:
            continue
        if trade["outcome"] == "YES":
            current = yes
        else:
            current = getattr(market, "no_price", 1 - yes)
        if current >= 0.97 or current <= 0.03:
            win = current >= 0.97
            payout = trade["size"] * (1.0 if win else 0.0)
            fee = float(trade["fee"] or 0.0)
            pnl = payout - trade["notional"] - fee
            db.begin()
            try:
                db.mark_resolved(trade["id"], round(pnl, 6), round(payout, 6))
                db.credit_cash(payout, pnl)
                db.commit()
            except Exception:
                db.rollback()
                raise
            closed += 1
    return closed
