# SPEC: Synth-lib night shift (no TAO)

Status: **open now**. Runs on the laptop. No wallet, no axon, no SN50 burn.
Doctrine: [AGENTS.md](AGENTS.md). Price-market consumer: [SPEC-path-ensemble.md](SPEC-path-ensemble.md).
Cadence teacher: [4d-chess-sequential](https://github.com/tradewife/night-shift-security/blob/main/.agents/skills/4d-chess-sequential/SKILL.md) + RTP [promotion_criteria.py](https://github.com/tradewife/resilient-token-protocol/blob/main/research/promotion_criteria.py).

One-sentence job:

> Generate Synth-shaped path files from the same simulator `judge()` will use, score them with the official backtester against real prices, and only promote a variant that beats the incumbent on CRPS *and* still looks like a fee-positive `p_true` on paper Polymarket.

---

## Why this, why not the miner

https://synthdata.co/miners and the [miner tutorial](https://github.com/synthdataco/synth-subnet/blob/main/docs/miner_tutorial.md) say: clone → implement model → **backtest with synth-lib** → then fund TAO and register.

That middle step is the night shift. RTP already learned this: research/orchestration + promotion gates *before* the live binary. NSS 4d-chess-sequential is the same loop pointed at invariants instead of vibes — sequential, one thread, human gates, failure preserved.

Do **not** clone `synth-subnet` in this ticket. Do **not** register netuid 50/247. Do **not** pay https://docs.synthdata.co/.

### Repos and docs

| What | URL |
| --- | --- |
| Backtester | https://github.com/synthdataco/synth-lib |
| Subnet (later) | https://github.com/synthdataco/synth-subnet |
| Tutorial | https://github.com/synthdataco/synth-subnet/blob/main/docs/miner_tutorial.md |
| Response format | https://github.com/synthdataco/synth-subnet/blob/main/docs/miner_reference.md |
| Competitions / CRPS | https://github.com/synthdataco/synth-subnet/blob/main/README.md |
| `simulations.py` hook (later copy) | https://github.com/synthdataco/synth-subnet/blob/main/synth/miner/simulations.py |
| Price feeds | https://github.com/synthdataco/synth-subnet/blob/main/synth/miner/price_simulation.py |
| Miners page | https://synthdata.co/miners |
| RTP research | https://github.com/tradewife/resilient-token-protocol/tree/main/research |
| RTP live | https://www.resilientprotocol.xyz/ |
| 4d-chess-sequential | https://github.com/tradewife/night-shift-security/blob/main/.agents/skills/4d-chess-sequential/SKILL.md |

---

## Map 4D onto this problem

This is not a Solana bounty hunt. Reuse the *sequence*, not the fuzz tooling.

| 4D layer | Here |
| --- | --- |
| **0 Ingest** | synth-lib + this spec + SPEC-path-ensemble. System map: path shape, CRPS increments, three competitions, fee curve on the other book. |
| **1 Invariants** | Living table below. Things that should never break. |
| **2.1 Static** | Filename, JSON layout, 61 vs 289 points, 1000 paths, ≤8 sig digits, t0 = spot. |
| **2.2 Dynamic** | `simulate()` vs realized Binance/HL path. CRPS per increment. |
| **2.3 Economic** | Softmax weight / estimated α. Separately: Polymarket edge after V2 fees. SN50-optimal ≠ PM-PnL-optimal — log the tension, do not bake drift into the miner. |
| **2.4 Temporal** | 5d (1h) / 10d (24h) rolling score. Regime (quiet vs spike). Missed hours = 90th-percentile poison later on the axon. |
| **3 Human gate** | Kate reads rank + CRPS vs incumbent before any `judge()` or miner copy. |
| **4 Synthesis** | Promote / reject / retire using RTP-shaped gates, not a screenshot. |
| **5 Loop** | Keep the losing variant and the note. Fresh-context rerun of the same window. |

### Invariants (v1 table)

| ID | Invariant | Status |
| --- | --- | --- |
| I1 | Zero mean drift on log-increments | required |
| I2 | Paths start at venue spot at `start_timestamp` | required |
| I3 | Shape is 1000 × (T/Δt + 1); 1h=61, 24h=289 | required |
| I4 | Finite, positive, ≤8 sig digits when written | required |
| I5 | Candidate CRPS beats `random_walk` / `gbm_agent` baseline on the same window | gate |
| I6 | Candidate does not explode 24h tail mass vs realized (visual + CRPS-at-T) | gate |
| I7 | `p_true` from the same files, net of V2 fees, must still beat always-HOLD on paper PM before `LIVE_TRADING` | gate (other book) |
| I8 | No directional drift added “to help RTP” | never break |

---

## Promotion (RTP spirit, Synth numbers)

Reuse the *stages*, not Sharpe-on-perps.

| Status | Meaning |
| --- | --- |
| RESEARCH | emit files + synth-lib only |
| PAPER | also wired into `judge()` (SPEC-path-ensemble) |
| LIVE | SN50 UID and/or `LIVE_TRADING` — **not this ticket** |
| RETIRED | lost I5 or I7; keep the files |

Research → paper gate for the *miner-shaped* model:

1. Window starts **on or after 2026-06-23** (3-competition split). Do not backtest across the split.
2. crypto-1h windows start **on or after 2026-03-16** if you touch 1h (CRPS formula change).
3. Same `--days` / `--eval-end` / assets for incumbent vs candidate.
4. Candidate must beat the checked-in baseline (`zero_drift_t` vs `gbm_baseline`) on mean CRPS **and** not collapse estimated earnings to floor.
5. Human reads the charts in `miner_outputs/{name}/charts/`.
6. Then, and only then, copy `simulate()` into `judge()` path (if not already) and run the PM profit gate in AGENTS.md.

---

## Laptop commands (do this first, tonight)

Python ≥ 3.12, `uv` on PATH. Sibling clone next to this repo is fine.

```bash
# 0. toolchain
cd ~
git clone https://github.com/synthdataco/synth-lib.git
cd synth-lib
uv sync

# 1. prices (BTC, 3 days is enough to prove the pipe)
uv run synth_lib/preparation/market_data.py --asset BTC --days 3

# 2. prove synth-lib itself (it will synthesise a random-walk if no files exist)
uv run synth_lib/backtester/scripts/run_backtest.py \
  --miner-name gbm_agent --competition crypto-24h --asset BTC --days 2
```

If step 2 prints rank / CRPS / chart paths, the pipe works. No TAO was used.

```bash
# 3. emit OUR files from polymarket-agi (this repo)
cd /path/to/polymarket-agi/agent
uv run python -m polyagent.emit_synth \
  --out /path/to/synth-lib/miner_outputs/zero_drift_t/predictions \
  --asset BTC --horizon 24h --days 2

# 4. score us on the same window
cd /path/to/synth-lib
uv run synth_lib/backtester/scripts/run_backtest.py \
  --miner-name zero_drift_t \
  --competition crypto-24h \
  --asset BTC \
  --days 2 \
  --predictions-dir miner_outputs/zero_drift_t/predictions
```

Then compare `zero_drift_t` vs `gbm_agent` on that window. That is Phase 0 of 4D: baseline vs candidate, failure preserved.

Hyperliquid assets (HYPE, equities) only have ~3.5 days of 1m history in-lib. Stay on **BTC/ETH/SOL/XRP + crypto-24h** until the pipe is boring.

---

## File format we emit

Directory: `miner_outputs/{miner_name}/predictions/`

Name: `YYYY-MM-DD_HH:MM:SSZ_{ASSET}_{time_length}.json`  
Example: `2026-09-04_00:00:00Z_BTC_86400.json`

Flat layout:

```json
{
  "start_timestamp": "2026-09-04T00:00:00Z",
  "asset": "BTC",
  "time_increment": 300,
  "time_length": 86400,
  "paths": [[s0, s1, ...], ...]
}
```

| horizon | time_length | time_increment | points/path |
| --- | --- | --- | --- |
| 1h | 3600 | 60 | 61 |
| 24h | 86400 | 300 | 289 |

1000 paths. Point 0 = spot at start. Implementation: `agent/polyagent/synth_io.py` + `python -m polyagent.emit_synth`.

---

## What the coding agent implements in *this* repo

Already expected from SPEC-path-ensemble: `paths.py` `simulate()`.

This ticket adds:

- `agent/polyagent/synth_io.py` — write one flat JSON, 8-sig-digit positives.
- `agent/polyagent/emit_synth.py` — CLI: walk hourly (24h) or ~15min (1h) timestamps over `--days`, call `simulate()`, write files. If `paths.simulate` is not ready, use the local GBM/Student-t fallback in `emit_synth` so the pipe runs tonight.
- `agent/tests/test_synth_io.py` — one fake ensemble → filename + shape 1000×289 + t0.

Do not vendor synth-lib into this repo. Do not add bittensor.

---

## Night-shift loop (sequential, one variant at a time)

1. **Ingest** — pipe runs on BTC 24h, 2 days.
2. **Propose one change** — e.g. Student-t ν, EWMA span, separate 1h dt. One sentence.
3. **Emit + backtest** same window as incumbent.
4. **Record** in `agent/data/synth_lab.jsonl` (gitignored is fine): variant, window, mean CRPS, rank note, I5 pass/fail, charts path.
5. **Human** — keep or reject. Do not stack three un-scored ideas.
6. **Only after I5** — feed the same `simulate()` into `judge()` and run the PM gate.

That is 4d-chess-sequential without Crucible: depth via one-thread iteration, not a swarm.

---

## Out of scope

- `synth-subnet` clone, PM2, 8091, testnet/mainnet register
- Paid Synth API
- Chronos / LoRA on the 4050 (later research branch, after I5 is green on the statistical model)
- Wiring RTP `rtp-trader` in the same PR
- Backtests that start before 2026-06-23

---

## Done when

- [ ] `synth-lib` cloned and `run_backtest.py --miner-name gbm_agent --asset BTC --competition crypto-24h --days 2` completes
- [ ] `emit_synth` writes valid files for BTC 24h
- [ ] `zero_drift_t` has a CRPS number next to `gbm_agent` on the same window
- [ ] one row in the lab log with I5 pass/fail
- [ ] no TAO moved
