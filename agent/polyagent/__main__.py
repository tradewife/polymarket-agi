from __future__ import annotations

import argparse
import json
import sys

from polyagent import dnsfix

dnsfix.install()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="polyagent")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("bootstrap", help="Create/load wallet and write .env.local")
    sub.add_parser("status", help="Show wallet and latest heartbeat")
    run = sub.add_parser("run", help="Start the trading loop")
    run.add_argument("--once", action="store_true", help="Single cycle then exit")

    args = parser.parse_args(argv)

    if args.cmd == "bootstrap":
        from polyagent.wallet import bootstrap_wallet

        info = bootstrap_wallet()
        print("Wallet ready (key stored in gitignored .env.local)")
        print(f"  signer EOA:  {info['signer']}")
        print(f"  funder:      {info['funder']}")
        print(f"  generated:   {info['generated']}")
        print("Fund the funder address with PolyUSD before setting LIVE_TRADING=true.")
        return 0

    if args.cmd == "status":
        from polyagent.config import load_settings
        from polyagent.db import AgentDB

        settings = load_settings()
        db = AgentDB(settings.db_path, starting_cash=settings.paper_bankroll)
        snap = db.snapshot()
        print(
            json.dumps(
                {
                    "mode": "live" if settings.live_trading and not settings.paper else "paper",
                    "signer": settings.signer_address,
                    "funder": settings.funder_address,
                    "bankroll": settings.paper_bankroll,
                    "max_position": settings.max_position,
                    "max_open": settings.max_open,
                    **snap,
                    "db": str(settings.db_path),
                },
                indent=2,
            )
        )
        return 0

    if args.cmd == "run":
        from polyagent.loop import run_forever
        from polyagent.wallet import bootstrap_wallet

        bootstrap_wallet()
        run_forever(once=args.once)
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
