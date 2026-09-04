from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class AgentDB:
    def __init__(self, path: Path, starting_cash: float = 100.0) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), timeout=30)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self._init(starting_cash)

    def _init(self, starting_cash: float) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                market_id TEXT,
                condition_id TEXT,
                question TEXT,
                side TEXT NOT NULL,
                outcome TEXT NOT NULL,
                price REAL NOT NULL,
                size REAL NOT NULL,
                notional REAL NOT NULL,
                token_id TEXT,
                status TEXT NOT NULL,
                paper INTEGER NOT NULL,
                order_id TEXT,
                reason TEXT,
                pnl REAL,
                resolved_at TEXT
            );
            CREATE TABLE IF NOT EXISTS heartbeats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                mode TEXT NOT NULL,
                markets_scored INTEGER,
                trades_this_cycle INTEGER,
                open_positions INTEGER,
                note TEXT
            );
            CREATE TABLE IF NOT EXISTS judgments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                market_id TEXT,
                condition_id TEXT,
                question TEXT,
                action TEXT NOT NULL,
                p_true REAL,
                confidence REAL,
                reasoning TEXT,
                implied_yes REAL,
                edge_after_fees REAL,
                kelly_fraction REAL,
                pair_cost REAL
            );
            CREATE TABLE IF NOT EXISTS ledger (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                cash REAL NOT NULL,
                starting_cash REAL NOT NULL,
                fees_paid REAL NOT NULL DEFAULT 0,
                realized_pnl REAL NOT NULL DEFAULT 0,
                updated_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_trades_condition ON trades(condition_id, status);
            """
        )
        self._ensure_trade_columns()
        self._ensure_ledger(starting_cash)
        self.conn.commit()

    def _ensure_trade_columns(self) -> None:
        existing = {
            row["name"]
            for row in self.conn.execute("PRAGMA table_info(trades)")
        }
        for name, ddl in (
            ("fee", "REAL NOT NULL DEFAULT 0"),
            ("fill_role", "TEXT"),
            ("cash_debit", "REAL"),
            ("payout", "REAL"),
            ("mfe", "REAL"),
            ("mae", "REAL"),
            ("last_mark", "REAL"),
        ):
            if name not in existing:
                self.conn.execute(f"ALTER TABLE trades ADD COLUMN {name} {ddl}")

    def _ensure_ledger(self, starting_cash: float) -> None:
        row = self.conn.execute("SELECT * FROM ledger WHERE id = 1").fetchone()
        realized = self.conn.execute(
            """
            SELECT COALESCE(SUM(pnl), 0) FROM trades
            WHERE paper = 1 AND status = 'resolved' AND pnl IS NOT NULL
            """
        ).fetchone()[0]
        fees = self.conn.execute(
            "SELECT COALESCE(SUM(fee), 0) FROM trades WHERE paper = 1"
        ).fetchone()[0]
        open_cost = self.conn.execute(
            """
            SELECT COALESCE(SUM(notional + COALESCE(fee, 0)), 0)
            FROM trades WHERE paper = 1 AND status IN ('open', 'pending')
            """
        ).fetchone()[0]
        reconstructed = round(max(0.0, starting_cash - float(open_cost) + float(realized)), 6)
        if row is None:
            self.conn.execute(
                """
                INSERT INTO ledger (id, cash, starting_cash, fees_paid, realized_pnl, updated_at)
                VALUES (1, ?, ?, ?, ?, ?)
                """,
                (reconstructed, starting_cash, float(fees), float(realized), utcnow()),
            )
            return
        # Repair the pre-ledger snapshot once: cash should be bankroll - open cost + realized.
        identity = float(row["cash"]) + float(open_cost)
        if abs(identity - (starting_cash + float(realized))) > 0.02:
            self.conn.execute(
                """
                UPDATE ledger
                SET cash = ?, fees_paid = ?, realized_pnl = ?, updated_at = ?
                WHERE id = 1
                """,
                (reconstructed, float(fees), float(realized), utcnow()),
            )

    def begin(self) -> None:
        self.conn.execute("BEGIN IMMEDIATE")

    def commit(self) -> None:
        self.conn.commit()

    def rollback(self) -> None:
        self.conn.rollback()

    def ledger(self) -> sqlite3.Row:
        return self.conn.execute("SELECT * FROM ledger WHERE id = 1").fetchone()

    def cash(self) -> float:
        return float(self.ledger()["cash"])

    def reserved_notional(self) -> float:
        row = self.conn.execute(
            """
            SELECT COALESCE(SUM(notional), 0) AS s
            FROM trades WHERE paper = 1 AND status IN ('open', 'pending')
            """
        ).fetchone()
        return float(row["s"])

    def snapshot(self) -> dict[str, float | int | str]:
        led = self.ledger()
        open_n = self.open_count()
        reserved = self.reserved_notional()
        return {
            "cash": round(float(led["cash"]), 4),
            "starting_cash": round(float(led["starting_cash"]), 4),
            "reserved_notional": round(reserved, 4),
            "equity": round(float(led["cash"]) + reserved, 4),
            "fees_paid": round(float(led["fees_paid"]), 4),
            "realized_pnl": round(float(led["realized_pnl"]), 4),
            "open": open_n,
        }

    def open_count(self) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) AS n FROM trades WHERE status IN ('open', 'pending')"
        ).fetchone()
        return int(row["n"])

    def record_trade(self, **kwargs: Any) -> int:
        cols = [
            "created_at",
            "market_id",
            "condition_id",
            "question",
            "side",
            "outcome",
            "price",
            "size",
            "notional",
            "token_id",
            "status",
            "paper",
            "order_id",
            "reason",
            "fee",
            "fill_role",
            "cash_debit",
        ]
        values = [kwargs.get(c) for c in cols]
        cur = self.conn.execute(
            f"INSERT INTO trades ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
            values,
        )
        return int(cur.lastrowid)

    def debit_cash(self, amount: float, fee: float) -> None:
        led = self.ledger()
        cash = float(led["cash"])
        if amount > cash + 1e-9:
            raise RuntimeError(f"insufficient paper cash: need {amount:.4f} have {cash:.4f}")
        self.conn.execute(
            """
            UPDATE ledger
            SET cash = cash - ?, fees_paid = fees_paid + ?, updated_at = ?
            WHERE id = 1
            """,
            (amount, fee, utcnow()),
        )

    def credit_cash(self, amount: float, realized_pnl: float) -> None:
        self.conn.execute(
            """
            UPDATE ledger
            SET cash = cash + ?, realized_pnl = realized_pnl + ?, updated_at = ?
            WHERE id = 1
            """,
            (amount, realized_pnl, utcnow()),
        )

    def open_trades(self) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                "SELECT * FROM trades WHERE status IN ('open', 'pending') ORDER BY id"
            )
        )

    def update_excursion(self, trade_id: int, mark: float) -> None:
        """Track MFE/MAE in price space for a long outcome token."""
        row = self.conn.execute(
            "SELECT price, mfe, mae FROM trades WHERE id = ?",
            (trade_id,),
        ).fetchone()
        if row is None:
            return
        entry = float(row["price"])
        excursion = mark - entry
        mfe = row["mfe"]
        mae = row["mae"]
        mfe = excursion if mfe is None else max(float(mfe), excursion)
        mae = excursion if mae is None else min(float(mae), excursion)
        self.conn.execute(
            "UPDATE trades SET last_mark = ?, mfe = ?, mae = ? WHERE id = ?",
            (mark, mfe, mae, trade_id),
        )
        self.conn.commit()

    def mark_resolved(self, trade_id: int, pnl: float, payout: float) -> None:
        self.conn.execute(
            """
            UPDATE trades
            SET status = 'resolved', pnl = ?, payout = ?, resolved_at = ?
            WHERE id = ?
            """,
            (pnl, payout, utcnow(), trade_id),
        )

    def paper_pnl(self) -> float:
        led = self.ledger()
        return float(led["realized_pnl"])

    def record_judgments(self, rows: list[dict[str, Any]]) -> None:
        self.conn.executemany(
            """
            INSERT INTO judgments (
                ts, market_id, condition_id, question, action, p_true, confidence,
                reasoning, implied_yes, edge_after_fees, kelly_fraction, pair_cost
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    r["ts"],
                    r.get("market_id"),
                    r.get("condition_id"),
                    r.get("question"),
                    r["action"],
                    r.get("p_true"),
                    r.get("confidence"),
                    r.get("reasoning"),
                    r.get("implied_yes"),
                    r.get("edge_after_fees"),
                    r.get("kelly_fraction"),
                    r.get("pair_cost"),
                )
                for r in rows
            ],
        )
        self.conn.commit()

    def recent_judgments(self, limit: int = 40) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                "SELECT * FROM judgments ORDER BY id DESC LIMIT ?",
                (limit,),
            )
        )

    def recent_trades(self, limit: int = 50) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                "SELECT * FROM trades ORDER BY id DESC LIMIT ?",
                (limit,),
            )
        )

    def heartbeat(self, **kwargs: Any) -> None:
        self.conn.execute(
            """
            INSERT INTO heartbeats (ts, mode, markets_scored, trades_this_cycle, open_positions, note)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                utcnow(),
                kwargs.get("mode"),
                kwargs.get("markets_scored", 0),
                kwargs.get("trades_this_cycle", 0),
                kwargs.get("open_positions", 0),
                kwargs.get("note"),
            ),
        )
        self.conn.commit()
