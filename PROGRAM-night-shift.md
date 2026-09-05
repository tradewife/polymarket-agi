# PROGRAM: night shift on the laptop

This is the Karpathy `program.md` for this repo. A coding agent on the laptop
reads it, edits **one** research file, scores, keeps or reverts, repeats.

Doctrine for the live tick still lives in [AGENTS.md](AGENTS.md).
Consumer spec: [SPEC-path-ensemble.md](SPEC-path-ensemble.md).
Scoring spec: [SPEC-synth-lib-night-shift.md](SPEC-synth-lib-night-shift.md).

---

## Lineage (do not flatten this)

Night shift here is not a new idea. It is the same machine, pointed at a
sharper object.

| Source | What we keep | What we already paid for and do not bring back |
| --- | --- | --- |
| [Karpathy autoresearch](https://github.com/karpathy/autoresearch) | One editable file. One metric. Fixed eval. Keep or revert. `results.tsv`. You wake up to a log, not a redesign. | Editing the live loop every experiment. |
| [Atlas-GIC](https://github.com/chrisworsey55/atlas-gic) | Overnight search. Darwinian keep/kill. Prompts/params as weights. Simulation before capital. | 25–31 live agents debating on the tick. CIO layer. Copy-trading theatre. |
| RTP `research/` | `promotion_criteria.py` stages. Strategy library as *seeds*, not 15 live brains. Dead ends preserved. | Shipping S01–S15 into `judge()`. |
| NSS 4d-chess-sequential | Single thread. Invariants first. Human gate. Failure preserved. | Treating Synth like a Solana bounty (Crucible, CPIs). |

The old “30,000 strategies a night” number was a **search budget on a cheap
eval** (bar-based backtests / swarm sims). It was never 30,000 live policies.

Putting 30,000 named strategies into `judge()` would be the step backwards.
Atlas already showed what a fat live brain costs. This repo was stripped on
purpose.

**Evolution:** search volume stays in the night. The live hook stays one
sentence. The object of search is no longer “a new entry rule.” It is the
**path ensemble** — one `simulate()` that must win on two books.

```text
                    night (search)
            ┌──────────────────────────┐
            │  mutate simulate()       │
            │  score A: CRPS (Synth)   │
            │  score B: PM fees paper  │
            │  keep or revert          │
            │  results.tsv             │
            └────────────┬─────────────┘
                         │ promote only if A and B
                         v
              day (one hook: judge())
           HOLD | pair-arb | path p_true
                         │
              later: SN50 axon / LIVE_TRADING
```

Two metrics, one generator:

- **A — Synth / SN50:** mean CRPS on a frozen window (official `synth-lib`). Lower better. Gate I5 vs the incumbent in `results.tsv`.
- **B — Polymarket paper:** fee-adjusted expectancy vs always-HOLD and arb-only. Gate I7. No live flag.

A without B is a miner that cannot feed the agent.
B without A is a story the validator will not pay.
Neither metric alone is promotion.

---

## What the agent may edit

Fair game (the `train.py` analog):

- `agent/polyagent/paths.py` once it exists
- the fallback in `agent/polyagent/emit_synth.py` until `paths.py` exists
- vol estimator, Student-t ν, EWMA span, dt, jump on/off — **one change per experiment**

Not fair game in the same experiment:

- `judge()` control flow beyond wiring `p_true`
- `LIVE_TRADING`
- a second agent, dashboard book, LLM on the tick
- `synth-subnet`, wallets, 8091
- paid Synth `/insights` or `/v2/prediction/*`
- RTP trader import
- “restore the 15 strategies”

---

## Frozen eval (do not move the goalposts)

Until a human changes this block:

- asset: `BTC`
- competition: `crypto-24h`
- `--days 2 --eval-end 2026-09-04`
- miner names: incumbent `gbm_agent` (lib random-walk), candidate `zero_drift_t` then dated variants
- prices: local `synth-lib/market_data/prices/BTC/1m/`
- if `api.binance.com` returns 451, ingest from `api.binance.us` into the same parquet layout (already proven)
- `/rewards/scores` may 404 on the unfinished same-day tail — treat as empty, do not widen the window

Baseline already measured in lab (same window):

| name | prompts | mean CRPS | smoothed | rank |
| --- | --- | --- | --- | --- |
| gbm_agent random-walk | 45 | 3479.14 | 97.19 | 255/257 |
| zero_drift_t vol=0.55 ν=5 | 72 | 3352.86 | 200.73 | 256/257 |

I5 is **not** cleared. First laptop experiment: replace constant 0.55 with EWMA vol from the 1m store. Same window. One line in `results.tsv`.

---

## Laptop — first session (human or agent)

Python ≥ 3.12, `uv` on PATH. Sibling clones under `~/src` or `$HOME`.

```bash
# 0. tools
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env

# 1. this repo
cd ~/src   # or wherever you keep code
git clone https://github.com/tradewife/polymarket-agi.git
cd polymarket-agi && git pull

# 2. official backtester (do not vendor into this repo)
cd ~/src
git clone https://github.com/synthdataco/synth-lib.git
cd synth-lib && uv sync

# 3. prices — prefer Binance.com; fall back to .us if 451
uv run synth_lib/preparation/market_data.py --asset BTC --days 5 || echo "binance.com blocked — ingest .us into market_data/prices/BTC/1m/"

# 4. prove their pipe
MPLBACKEND=Agg uv run synth_lib/backtester/scripts/run_backtest.py \
  --miner-name gbm_agent --competition crypto-24h --asset BTC \
  --days 2 --eval-end 2026-09-04

# 5. emit ours
cd ~/src/polymarket-agi/agent
uv run python -m polyagent.emit_synth \
  --out ~/src/synth-lib/miner_outputs/zero_drift_t/predictions \
  --asset BTC --horizon 24h --days 2

# 6. score ours on the frozen window
cd ~/src/synth-lib
MPLBACKEND=Agg uv run synth_lib/backtester/scripts/run_backtest.py \
  --miner-name zero_drift_t --competition crypto-24h --asset BTC \
  --days 2 --eval-end 2026-09-04 \
  --predictions-dir miner_outputs/zero_drift_t/predictions
```

Append one row to `agent/data/synth_lab.tsv` (create if missing):

```text
ts	variant	window	mean_crps	smoothed	rank	i5	note
2026-09-05	zero_drift_t_vol0.55	BTC-24h-eval-2026-09-04-2d	3352.86	200.73	256/257	fail	lab sandbox; const vol
```

Public sniff (no key):

```bash
curl -sS 'https://api.synthdata.co/validation/scores/latest?asset=BTC' | head
```

---

## Overnight ratchet (after the pipe is boring)

Karpathy loop, translated:

1. Read this file + last 20 rows of `agent/data/synth_lab.tsv`.
2. Propose **one** mutation to `simulate()` in a single sentence.
3. Emit + official backtest on the **frozen** window. Do not change `--eval-end`.
4. If mean CRPS < incumbent *and* rank does not collapse worse than noise: keep, append TSV, commit the param change only.
5. Else: revert the file, append TSV with `i5=fail`, next mutation.
6. Never promote to `judge()` in the same night as a CRPS win. I7 is a separate paper week.

Throughput honesty: a full official backtest is ~20s scoring + API + writing 72×1000×289 JSON files. That is **not** 30,000 official runs per night.

To recover search volume without lying:

- Cache scores / rewards / realized path for the frozen window once.
- Score mutations **in memory** against that cache (local CRPS).
- Call `run_backtest.py` only for survivors (top 3 of the night).
- 30k cheap in-memory draws is the old budget. 3 official confirmations is the new honesty.

Do not implement the in-memory cache in the same PR as “first laptop pipe.” First make steps 0–6 finish on this machine.

---

## Promotion (RTP stages, this object)

| Stage | Evidence |
| --- | --- |
| RESEARCH | TSV rows. Official CRPS on frozen window. |
| PAPER | Same `simulate()` wired in `judge()`. Episodes beat HOLD and arb-only net of V2 fees. |
| LIVE-MINER | Testnet axon then one mainnet UID. Only if RESEARCH is top-pack, not floor. |
| LIVE-PM | `LIVE_TRADING` after PAPER gate. $5 / 4 slots. |

Killing a variant is success. Restoring Atlas desks into this repo is not.

---

## Done when (this session)

- [ ] `synth-lib` cloned on the laptop, `uv sync` works
- [ ] BTC 1m parquets exist for the frozen window
- [ ] `gbm_agent` backtest prints rank / CRPS
- [ ] `emit_synth` writes files
- [ ] `zero_drift_t` has a row in `synth_lab.tsv`
- [ ] no TAO, no API key, no `LIVE_TRADING`
