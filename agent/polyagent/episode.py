"""Decision episodes — UV Labs shape, RTP simplicity.

Live policy stays dumb (HOLD unless pair-arb). Memory is rich: every cycle
we record what we saw, what we judged, what we did, and (on open trades)
MFE/MAE so later we can tell skill from luck without changing the strategy.
"""

from __future__ import annotations

import json
from pathlib import Path

from polyagent.db import utcnow
from polyagent.reason import Judgment
from polyagent.scan import ScoredMarket


def append_episode(
    path: Path,
    *,
    judgments: list[Judgment],
    markets: list[ScoredMarket],
    placed: list[dict],
    ledger: dict,
    open_trades: list,
    mode: str,
) -> None:
    by_id = {m.market_id: m for m in markets}
    actionable = [j for j in judgments if j.action != "HOLD"]
    holds = len(judgments) - len(actionable)

    # Compact HOLDs: we still log them (a HOLD is a decision) without 50 essays.
    hold_sample = [
        {
            "market_id": j.market_id,
            "implied_yes": round(j.implied_yes, 4),
            "pair_cost": round(j.pair_cost, 4),
            "question": j.question,
        }
        for j in judgments
        if j.action == "HOLD"
    ][:20]

    journeys = []
    for t in open_trades:
        mark = t["last_mark"]
        entry = t["price"]
        size = t["size"]
        u_pnl = None
        if mark is not None:
            u_pnl = round(size * (float(mark) - float(entry)), 6)
        journeys.append(
            {
                "trade_id": t["id"],
                "question": t["question"],
                "entry": t["price"],
                "mark": mark,
                "mfe": t["mfe"],
                "mae": t["mae"],
                "unrealized_pnl": u_pnl,
                "counterfactual": {
                    "exit_at_mfe_pnl": (
                        round(size * float(t["mfe"]), 6) if t["mfe"] is not None else None
                    ),
                    "exit_at_mae_pnl": (
                        round(size * float(t["mae"]), 6) if t["mae"] is not None else None
                    ),
                },
            }
        )

    episode = {
        "ts": utcnow(),
        "mode": mode,
        "reasoning": {
            "policy": "hold-unless-pair-arb",
            "explicit": (
                "No independent p_true. HOLD unless YES+NO+taker fees < 0.995."
            ),
            "holds": holds,
            "actionable": [
                {
                    "action": j.action,
                    "question": j.question,
                    "reasoning": j.reasoning,
                    "confidence": j.confidence,
                    "edge_after_fees": j.edge_after_fees,
                    "kelly_fraction": j.kelly_fraction,
                    "pair_cost": j.pair_cost,
                    "implied_yes": j.implied_yes,
                }
                for j in actionable
            ],
            "hold_sample": hold_sample,
        },
        "market_context": {
            "n": len(markets),
            "names": [by_id[j.market_id].question for j in actionable if j.market_id in by_id],
        },
        "execution": placed,
        "position_journey": journeys,
        "ledger": ledger,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(episode, default=str) + "\n")
