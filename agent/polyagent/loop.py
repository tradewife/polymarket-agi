from __future__ import annotations

import time
import traceback

from polyagent.config import DATA_DIR, Settings, load_settings
from polyagent.db import AgentDB, utcnow
from polyagent.lock import ProcessLock
from polyagent.episode import append_episode
from polyagent.reason import judge
from polyagent.scan import fetch_candidates
from polyagent.snapshot import write_snapshot
from polyagent.strategy import pick_intents
from polyagent.trader import execute_live, execute_paper, mark_to_market

SNAPSHOT_PATH = DATA_DIR / "snapshot.json"
EPISODE_PATH = DATA_DIR / "episodes.jsonl"


def run_cycle(settings: Settings, db: AgentDB) -> dict:
    markets = fetch_candidates(
        limit=80, min_volume_24h=settings.min_volume_24h
    )
    by_condition = {m.condition_id: m for m in markets if m.condition_id}
    for trade in db.open_trades():
        mkt = by_condition.get(trade["condition_id"])
        if mkt is None:
            continue
        mark = mkt.yes_price if trade["outcome"] == "YES" else mkt.no_price
        db.update_excursion(trade["id"], mark)
    resolved = mark_to_market(db, by_condition)

    judgments = [judge(m) for m in markets]
    ts = utcnow()
    db.record_judgments(
        [
            {
                "ts": ts,
                "market_id": j.market_id,
                "condition_id": j.condition_id,
                "question": j.question,
                "action": j.action,
                "p_true": j.p_true,
                "confidence": j.confidence,
                "reasoning": j.reasoning,
                "implied_yes": j.implied_yes,
                "edge_after_fees": j.edge_after_fees,
                "kelly_fraction": j.kelly_fraction,
                "pair_cost": j.pair_cost,
            }
            for j in judgments
        ]
    )

    holds = sum(1 for j in judgments if j.action == "HOLD")
    arbs = [j for j in judgments if j.action == "ARB"]

    open_rows = db.open_trades()
    open_conditions = {row["condition_id"] for row in open_rows if row["condition_id"]}
    open_conditions.update({row["market_id"] for row in open_rows if row["market_id"]})
    remaining = max(0, settings.max_open - len(open_rows))
    cash = db.cash()
    intents = pick_intents(
        markets, judgments, settings, open_conditions, remaining, cash
    )

    placed = []
    for intent in intents:
        if db.open_count() >= settings.max_open:
            break
        if intent.cash_debit > db.cash() + 1e-9:
            continue
        if settings.live_trading and not settings.paper:
            placed.append(execute_live(settings, db, intent))
        else:
            placed.append(execute_paper(db, intent))

    snap = db.snapshot()
    note = (
        f"resolved={resolved} hold={holds}/{len(judgments)} arb={len(arbs)} "
        f"cash={snap['cash']:.2f} fees={snap['fees_paid']:.4f}"
    )
    db.heartbeat(
        mode="live" if settings.live_trading and not settings.paper else "paper",
        markets_scored=len(markets),
        trades_this_cycle=len(placed),
        open_positions=db.open_count(),
        note=note,
    )
    mode = "live" if settings.live_trading and not settings.paper else "paper"
    write_snapshot(
        db,
        SNAPSHOT_PATH,
        judgments=judgments,
        extra={
            "mode": mode,
            "signer": settings.signer_address,
            "funder": settings.funder_address,
            "holds": holds,
            "arbs_seen": len(arbs),
            "note": note,
        },
    )
    append_episode(
        EPISODE_PATH,
        judgments=judgments,
        markets=markets,
        placed=placed,
        ledger=snap,
        open_trades=db.open_trades(),
        mode=mode,
    )
    return {
        "markets": len(markets),
        "intents": len(intents),
        "placed": placed,
        "open": db.open_count(),
        "paper_pnl": db.paper_pnl(),
        "resolved": resolved,
        "ledger": snap,
        "holds": holds,
        "arbs": len(arbs),
        "mode": "live" if settings.live_trading and not settings.paper else "paper",
    }


def run_forever(once: bool = False) -> None:
    settings = load_settings()
    lock = ProcessLock(settings.db_path.with_suffix(".lock"))
    lock.acquire()
    try:
        db = AgentDB(settings.db_path, starting_cash=settings.paper_bankroll)
        snap = db.snapshot()
        print(
            f"[polyagent] mode={('live' if settings.live_trading and not settings.paper else 'paper')} "
            f"reasoner=local-hold-unless-arb scan={settings.scan_seconds}s "
            f"max_pos={settings.max_position} max_open={settings.max_open} "
            f"bankroll={settings.paper_bankroll:.2f} cash={snap['cash']:.2f} "
            f"signer={settings.signer_address or 'unset'} funder={settings.funder_address or 'unset'}",
            flush=True,
        )
        while True:
            try:
                result = run_cycle(settings, db)
                led = result["ledger"]
                print(
                    f"[polyagent] cycle markets={result['markets']} hold={result['holds']} "
                    f"arb={result['arbs']} placed={len(result['placed'])} "
                    f"open={result['open']}/{settings.max_open} cash={led['cash']:.2f} "
                    f"reserved={led['reserved_notional']:.2f} fees={led['fees_paid']:.4f} "
                    f"pnl={led['realized_pnl']:.2f} mode={result['mode']}",
                    flush=True,
                )
                for item in result["placed"]:
                    print(f"  trade {item}", flush=True)
            except Exception as exc:
                print(f"[polyagent] cycle error: {exc}", flush=True)
                traceback.print_exc()
            if once:
                return
            time.sleep(max(15, settings.scan_seconds))
    finally:
        lock.release()
