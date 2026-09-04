# PolyAgent

Agents and contributors: **[AGENTS.md](AGENTS.md)** is the operating contract (live policy, profit gate, learning loop).

One autonomous paper trader for Polymarket, plus a thin dashboard that only shows that book.

There is no Grok/xAI call, no copy-trading, no Kelly-on-a-fake-probability, and no Polynode requirement. The reasoner HOLDs unless buying YES and NO together still costs less than $1 after taker fees.

## Run the agent

```bash
bash agent/start.sh --once    # one scan
bash agent/start.sh           # loop
# already enabled:
systemctl --user status polyagent
```

Paper bankroll is $100. Live CLOB stays off until `LIVE_TRADING=true` **and** the deposit wallet is funded.

```bash
cd agent && uv run python -m polyagent status
```

## Dashboard

```bash
bun install
bun run dev
```

`GET /api/agent` reads `agent/data/snapshot.json` written each cycle.
`GET /api/markets` is Gamma (DNS-pinned).

## What the reasoner does

`agent/polyagent/reason.py` is the judgment slot:

- Default: **HOLD**. Market price is the public p. Inventing another p without evidence is not edge.
- Exception: **ARB** if `yes_fill + no_fill + taker_fees < 0.995` (locked $1 payout).
- Sizing for any non-HOLD is quarter-Kelly, capped at $5, deducted from cash including V2 fees (`shares × rate × p(1−p)`).

When you add `XAI_API_KEY` later, that function is the only place to plug it in.

## How we think about this (UV Labs × RTP)

[UV Labs](https://uvlabs.ai/agentic-trading/) is right that *judgment* needs memory: reasoning traces, MFE/MAE, counterfactuals — not just P&L. [Resilient Protocol](https://www.resilientprotocol.xyz/) is right that the *live* engine should be a short, gated rule with fees in the sim (score + ATR stops, not an LLM on every tick).

We take both, cheaply:

- **Act like RTP:** one rule, fees on, hard cash/slot caps. No social-sentiment firehose (UV themselves say raw sentiment lags and is gamed).
- **Remember like UV:** every cycle appends `agent/data/episodes.jsonl` (what we saw, HOLD vs ARB, fills, MFE/MAE on open tickets). HOLDs are decisions. Lucky wins with bad process stay labeled.

That is how this stays `polymarket-agi` without becoming a 9B-token training stack.

## Wallet

Official CLI wallet if present (`~/.config/polymarket/config.json`), else a new EOA. Fund **funder** (deposit wallet), not the signer EOA.
