from __future__ import annotations

import json
from pathlib import Path

from polyagent.db import AgentDB, utcnow
from polyagent.reason import Judgment


def _row(row) -> dict:
    return {k: row[k] for k in row.keys()}


def write_snapshot(
    db: AgentDB,
    path: Path,
    *,
    judgments: list[Judgment],
    extra: dict | None = None,
) -> None:
    snap = db.snapshot()
    payload = {
        "ts": utcnow(),
        "ledger": snap,
        "open_trades": [_row(r) for r in db.open_trades()],
        "recent_trades": [_row(r) for r in db.recent_trades(40)],
        "judgments": [
            {
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
        ],
        "recent_stored_judgments": [_row(r) for r in db.recent_judgments(40)],
        **(extra or {}),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, default=str))
    tmp.replace(path)
