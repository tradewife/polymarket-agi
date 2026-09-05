from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
AGENT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.environ.get("POLYAGENT_DATA_DIR", AGENT_DIR / "data"))
ENV_PATH = ROOT / ".env.local"
CLI_CONFIG = Path.home() / ".config" / "polymarket" / "config.json"

load_dotenv(ENV_PATH, override=False)
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


@dataclass(frozen=True)
class Settings:
    paper: bool
    live_trading: bool
    scan_seconds: int
    paper_bankroll: float
    max_position: float
    max_open: int
    max_trades_per_cycle: int
    min_volume_24h: float
    min_yes_favorite: float
    max_yes_underdog: float
    min_liquidity: float
    path_edge: float
    price_min_volume_24h: float
    db_path: Path

    @property
    def private_key(self) -> str:
        return (
            os.environ.get("POLYGON_PRIVATE_KEY")
            or os.environ.get("POLYMARKET_PRIVATE_KEY")
            or ""
        ).strip()

    @property
    def funder_address(self) -> str:
        return (os.environ.get("POLYMARKET_FUNDER_ADDRESS") or "").strip()

    @property
    def signer_address(self) -> str:
        return (os.environ.get("POLYMARKET_SIGNER_ADDRESS") or "").strip()


def load_settings() -> Settings:
    live = _bool("LIVE_TRADING", False)
    paper_env = os.environ.get("PAPER_TRADE")
    if paper_env is None:
        paper = not live
    else:
        paper = _bool("PAPER_TRADE", True)
    if live:
        paper = False
    return Settings(
        paper=paper,
        live_trading=live,
        scan_seconds=_int("POLYAGENT_SCAN_SECONDS", 120),
        paper_bankroll=_float("POLYAGENT_PAPER_BANKROLL", 100.0),
        max_position=_float("POLYAGENT_MAX_POSITION", 5.0),
        max_open=_int("POLYAGENT_MAX_OPEN", 4),
        max_trades_per_cycle=_int("POLYAGENT_MAX_TRADES_PER_CYCLE", 2),
        min_volume_24h=_float("POLYAGENT_MIN_VOLUME_24H", 8000.0),
        min_yes_favorite=_float("POLYAGENT_MIN_YES_FAVORITE", 0.72),
        max_yes_underdog=_float("POLYAGENT_MAX_YES_UNDERDOG", 0.22),
        min_liquidity=_float("POLYAGENT_MIN_LIQUIDITY", 500.0),
        path_edge=_float("POLYAGENT_PATH_EDGE", 0.03),
        # 8000 24h vol never surfaces 15m/1h BTC up/down. Price subset only.
        price_min_volume_24h=_float("POLYAGENT_PRICE_MIN_VOLUME_24H", 500.0),
        db_path=DATA_DIR / "agent.db",
    )
