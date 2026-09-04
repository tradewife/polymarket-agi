# AGENTS.md

Operating contract for humans and coding agents on **polymarket-agi**.

This repo is not a dashboard demo and not a 9B-token training stack. It is a small autonomous trader that **acts simply** and **remembers completely**, then only changes the live rule when memory proves the change beats fees.

Read this before editing `agent/polyagent/`, `LIVE_TRADING`, `judge()`, or anything that can spend paper or real capital.

**Active candidate (paper only):** [SPEC-path-ensemble.md](SPEC-path-ensemble.md) — independent `p_true` from a local price-path ensemble on crypto markets that resolve off a listed price. Implement that spec; do not clone Synth or flip `LIVE_TRADING` in the same patch.

---

## Doctrine

Two sources. Two layers. Do not mash them into one clever object.

| Layer | Teacher | Mandate |
| --- | --- | --- |
| **Live policy** | [Resilient Protocol](https://www.resilientprotocol.xyz/) | One short rule, fees in the sim, hard caps, gates before capital. Complexity belongs in validation, not in the tick. |
| **Memory** | [UV Labs — agentic trading](https://uvlabs.ai/agentic-trading/), [decision episodes](https://uvlabs.ai/blog/anatomy-of-decision-episode), [reasoning traces](https://uvlabs.ai/blog/reasoning-traces), [counterfactuals](https://uvlabs.ai/blog/counterfactual-learning) | Every cycle is an episode: what we saw, what we judged, what we did (including HOLD), how the path moved (MFE/MAE). Outcomes alone mix luck and skill. |

**AGI here** does not mean an LLM on every market. It means the system *judges* at runtime (not only a human-authored script with no record), *executes* the same loop end to end, and *improves* from process-labeled episodes rather than from a lucky PnL print.

If a change makes the live brain fatter without a gate, it is not AGI. It is bloat. The original fork still exists on GitHub; do not restore it.

---

## Live policy (current)

Canonical code: `agent/polyagent/reason.py` → `judge()`.

1. Default **HOLD**. The book *is* the public probability. Inventing `p_true` from volume, “favorite,” or vibes is not edge.
2. **ARB** only if `yes_fill + no_fill + taker_fees < 0.995` (locked $1 payout after V2 fees `shares × rate × p(1−p)`).
3. **Path-ensemble candidate** (SPEC-path-ensemble.md, paper): if the market parses as BTC/ETH/SOL/XRP/HYPE up-down or level, `p_true` is the share of simulated paths on the YES side of the strike. BUY_YES / BUY_NO only when that p beats the fill plus V2 fee plus `POLYAGENT_PATH_EDGE`. Unparsed markets stay HOLD.
4. Any non-HOLD is sized with **quarter-Kelly**, cash-capped, ticket-capped at **$5**, max **4** open. Paper bankroll **$100**. Ledger in `agent/data/agent.db`.
5. Paper fills are **takers** (pay the fee). Do not credit maker rebates.
6. **LIVE_TRADING** stays `false` until the deposit **funder** is funded *and* a gate (below) has passed. Signer EOA ≠ funder.

HOLDs are decisions. A cycle with 50 HOLDs and 0 fills is a successful episode, not an idle bug.

---

## Always

- Change live behavior only in `judge()` (and the sizing that consumes `Judgment`). One hook.
- After every cycle, persist: SQLite + `agent/data/snapshot.json` + append `agent/data/episodes.jsonl`.
- On every open ticket, update **MFE/MAE** (`trades.mfe` / `trades.mae`) from the live mark. Counterfactuals need the path, not just entry/exit.
- Label process independently of PnL: good HOLD that “missed” a favorite rally is still good process; lucky favorite-chase is still bad process.
- Price every proposal **net of the V2 fee curve** (`agent/polyagent/fees.py`). If it does not beat fees, it is not a candidate.
- Keep the dashboard a **viewer** of the snapshot. Do not give the UI a second book, a second bankroll, or a toy CLOB ABI.
- Prefer public Polymarket APIs (Gamma/CLOB, DNS-pinned). Do not put paid Polynode on the critical path.
- When adding evidence (paths, news, resolution clock, structure), timestamp it **at decision time** and store it on the episode. Post-hoc stories are not traces.
- Path ensembles are evidence for `judge()`, not a second product. Do not clone `synth-subnet` or subscribe to Synth API inside this repo until SPEC-path-ensemble.md says that phase is open.

---

## Never

- Never train or boast on outcome-only (“we made 2%”). Require the episode: reasoning + action + path + counterfactual.
- Never buy the favorite because it is expensive. That was deleted on purpose.
- Never call xAI/Grok (or any LLM) from the hot loop until `judge()` has a question the book does not already answer, and the call is traced (prompt, tools, confidence, action).
- Never add naive social sentiment (raw bullish/bearish counts). [UV on sentiment](https://uvlabs.ai/blog/social-sentiment): it lags, is gamed, and is useless without engagement, source class, and alignment to the decision timestamp. Skip until that bar is met.
- Never raise `LIVE_TRADING` to ship a hunch. Paper first, then the profit gate.
- Never create a parallel agent (dashboard Prisma, swarm Python, RainbowKit `createOrder`). One loop: `agent/polyagent`.
- Never restore skills/, docker swarm, WorldMonitor stubs, or Kelly-on-0.5-prior.
- Never bake directional drift into the path simulator so RTP or a hunch looks good. Zero-mean log-increments. SN50 CRPS will punish leftover drift later.

---

## Profit gate (mandatory before a policy change)

A new live rule is a **candidate**, not a deploy. Same spirit as RTP’s gate suite, scaled to this book.

1. **State the rule in one sentence** in `judge()` docstring / this file. If it needs a paragraph, it is not ready.
2. **Paper only.** Run until you have enough episodes that include both HOLDs and the new action (do not evaluate on a handful of lucky fills).
3. **Score process, not luck.** From `episodes.jsonl` + trade MFE/MAE:
   - Actual PnL net of fees
   - MFE left on the table / MAE risk taken
   - Would-have: favorite-buy, always-hold, pair-arb-only
   - Fraction of wins that were *also* labeled sound process
4. **Beat the incumbent.** Candidate must beat **always-HOLD** and **current `judge()`** on fee-adjusted expectancy *and* not explode MAE. If it only wins because 97¢ favorites drifted, reject it.
5. **Then** consider `LIVE_TRADING`, still $5 / 4 slots, funder funded.

No candidate skips steps 2–4 because “AGI should just know.”

---

## Learning loop (how we push toward AGI)

Do this on a cadence, not as a vibe.

| Cadence | Action |
| --- | --- |
| Every cycle | `judge()` → episode JSONL → snapshot. No silent cycles. |
| Daily | Read last day’s episodes. Count HOLD vs ARB vs path BUY. Note any ARB/path that fired or should have. |
| Weekly | Replay: for each filled (or hypothetical) ticket, compute MFE/MAE and “exit at MFE vs actual.” Write 5 lines in the next commit message or a dated note under `agent/data/` (gitignored) / chat — not a new markdown religion. |
| Before any `judge()` edit | Name the failure mode (no edge / bad size / bad exit / acting without evidence). Patch that class, not one market. |
| Before live | Profit gate above. |

**Process supervision:** reward a correct HOLD. Punish a well-PnL trade whose trace is “price was high so I bought.” That is the UV lesson applied with RTP brutality.

**Counterfactuals we always owe ourselves:** always-HOLD; pair-arb-only; and “what if we had bought the favorite.” The third exists to prove we were right *not* to.

---

## File map (do not grow this without cause)

| Path | Role |
| --- | --- |
| `SPEC-path-ensemble.md` | Implementation spec for the path `p_true` candidate. |
| `agent/polyagent/reason.py` | Judgment. **Only** place for p_true / HOLD / ARB / BUY_* / future LLM. |
| `agent/polyagent/price_markets.py` | Parse asset + horizon + strike (SPEC). |
| `agent/polyagent/paths.py` | Ensemble simulator (SPEC). |
| `agent/polyagent/fees.py` | V2 taker fee. Source of truth for “beats fees.” |
| `agent/polyagent/strategy.py` | Turns `Judgment` into sized intents (Kelly + caps). |
| `agent/polyagent/loop.py` | Scan → judge → MFE update → execute → episode. |
| `agent/polyagent/episode.py` | Episode writer. |
| `agent/data/agent.db` | Ledger + trades + judgments. |
| `agent/data/snapshot.json` | Dashboard. |
| `agent/data/episodes.jsonl` | Learning corpus. |
| `src/app/` | Thin viewer. No second brain. |

---

## Commands

```bash
systemctl --user status polyagent
cd agent && uv run python -m polyagent status
bash agent/start.sh --once
cd agent && uv run python -m unittest discover -s tests
bun run dev
```

Paper is the default. Live is a promotion, not a feature flag for convenience.
