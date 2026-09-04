from __future__ import annotations

import json
import os
from pathlib import Path

from eth_account import Account

from polyagent.config import CLI_CONFIG, ENV_PATH, ROOT


def upsert_env(updates: dict[str, str], path: Path = ENV_PATH) -> None:
    if path.exists():
        text = path.read_text()
    else:
        example = ROOT / ".env.local.example"
        text = example.read_text() if example.exists() else ""
    for key, value in updates.items():
        line = f'{key}="{value}"'
        pattern = f"{key}="
        lines = text.splitlines(keepends=True)
        found = False
        out: list[str] = []
        for existing in lines:
            if existing.startswith(pattern) or existing.startswith(f"export {pattern}"):
                out.append(line + "\n")
                found = True
            else:
                out.append(existing)
        if not found:
            if out and not out[-1].endswith("\n"):
                out.append("\n")
            out.append(line + "\n")
        text = "".join(out)
    path.write_text(text)
    os.chmod(path, 0o600)


def load_cli_private_key() -> str | None:
    if not CLI_CONFIG.exists():
        return None
    data = json.loads(CLI_CONFIG.read_text())
    key = (data.get("private_key") or "").strip()
    return key or None


def generate_or_load_key() -> tuple[str, bool]:
    existing = (
        os.environ.get("POLYGON_PRIVATE_KEY")
        or os.environ.get("POLYMARKET_PRIVATE_KEY")
        or ""
    ).strip()
    if existing:
        if not existing.startswith("0x"):
            existing = "0x" + existing
        return existing, False
    cli_key = load_cli_private_key()
    if cli_key:
        if not cli_key.startswith("0x"):
            cli_key = "0x" + cli_key
        return cli_key, False
    acct = Account.create()
    return acct.key.to_0x_hex(), True


def signer_address(private_key: str) -> str:
    return Account.from_key(private_key).address


def derive_deposit_wallet(private_key: str) -> str:
    from polymarket._internal.environment import get_environment_config
    from polymarket._internal.wallet import derive_beacon_deposit_wallet_address
    from polymarket.environments import PRODUCTION

    config = get_environment_config(PRODUCTION)
    eoa = signer_address(private_key)
    return derive_beacon_deposit_wallet_address(eoa, config.wallet_derivation)


def bootstrap_wallet() -> dict[str, str]:
    key, generated = generate_or_load_key()
    eoa = signer_address(key)
    funder = derive_deposit_wallet(key)
    upsert_env(
        {
            "POLYGON_PRIVATE_KEY": key,
            "POLYMARKET_PRIVATE_KEY": key,
            "POLYMARKET_SIGNER_ADDRESS": eoa,
            "POLYMARKET_FUNDER_ADDRESS": funder,
            "PAPER_TRADE": os.environ.get("PAPER_TRADE", "true"),
            "LIVE_TRADING": os.environ.get("LIVE_TRADING", "false"),
            "DATABASE_URL": os.environ.get("DATABASE_URL", "file:./dev.db"),
        }
    )
    os.environ["POLYGON_PRIVATE_KEY"] = key
    os.environ["POLYMARKET_PRIVATE_KEY"] = key
    os.environ["POLYMARKET_SIGNER_ADDRESS"] = eoa
    os.environ["POLYMARKET_FUNDER_ADDRESS"] = funder
    return {
        "generated": str(generated).lower(),
        "signer": eoa,
        "funder": funder,
        "source": "cli-config" if load_cli_private_key() and not generated else "local",
    }
