# FIRST-RUN — laptop agent prompt

Paste everything under **PROMPT** into the coding agent on the Ubuntu laptop.
Working directory should be a code folder you own (e.g. `~/src`). Do not start from a Drive sync copy of night-shift-security.

---

## PROMPT

```text
You are the night-shift coding agent on this Ubuntu laptop.

Read, in order, and obey:
1. AGENTS.md
2. PROGRAM-night-shift.md
3. SPEC-synth-lib-night-shift.md
4. SPEC-path-ensemble.md

This session is FIRST PIPE only. Not mining. Not LIVE_TRADING. Not Chronos.
Not cloning synth-subnet. Not creating a Synth API key. Not editing judge()
beyond what already exists. Not restoring Atlas desks or RTP S01–S15.

Goal: prove synth-lib + emit_synth run on THIS machine and write one lab row.

Do the work. Do not stop at a plan.

## Layout

Use ~/src if it exists, else create it.

~/src/polymarket-agi     # this repo (git pull)
~/src/synth-lib          # clone https://github.com/synthdataco/synth-lib

Install uv if missing: curl -LsSf https://astral.sh/uv/install.sh | sh
Need Python >= 3.12.

## Commands to run for real

cd ~/src/polymarket-agi && git pull

cd ~/src
git clone https://github.com/synthdataco/synth-lib.git || true
cd ~/src/synth-lib && git pull && uv sync

# prices — 5 days BTC 1m
cd ~/src/synth-lib
uv run synth_lib/preparation/market_data.py --asset BTC --days 5

# If that 451s on api.binance.com, do NOT give up. Ingest from
# https://api.binance.us/api/v3/klines symbol=BTCUSDT interval=1m into
# market_data/prices/BTC/1m/date=YYYY-MM-DD.parquet
# columns: timestamp, close, source, ingested_at, is_final
# 1440 minute rows per settled day. Days needed: 2026-08-31 through 2026-09-05.

# official baseline
cd ~/src/synth-lib
MPLBACKEND=Agg uv run synth_lib/backtester/scripts/run_backtest.py \
  --miner-name gbm_agent --competition crypto-24h --asset BTC \
  --days 2 --eval-end 2026-09-04

# If /rewards/scores 404s on a same-day tail chunk, treat 404 as empty list
# in synth_lib/backtester/loading.py get_rewards_history (local patch only,
# do not PR it to synthdataco). Then rerun the same command.

# emit our files
cd ~/src/polymarket-agi/agent
uv run python -m polyagent.emit_synth \
  --out ~/src/synth-lib/miner_outputs/zero_drift_t/predictions \
  --asset BTC --horizon 24h --days 2

# score ours
cd ~/src/synth-lib
MPLBACKEND=Agg uv run synth_lib/backtester/scripts/run_backtest.py \
  --miner-name zero_drift_t --competition crypto-24h --asset BTC \
  --days 2 --eval-end 2026-09-04 \
  --predictions-dir miner_outputs/zero_drift_t/predictions

## Lab row

Create agent/data/synth_lab.tsv in polymarket-agi if missing. Append one row
with: ts, variant, window, mean_crps, smoothed, rank, i5, note.
Window label: BTC-24h-eval-2026-09-04-2d
i5=fail unless mean CRPS beats the gbm_agent number from THIS run.
Do not git-add bulky miner_outputs or parquet. Lab tsv is fine to commit.

## Stop conditions (success)

Print a short report:
- gbm_agent: prompts, mean CRPS, smoothed, rank, chart paths
- zero_drift_t: same
- where parquets live and which venue (binance.com vs .us)
- any local synth-lib patch you made
- tsv path

Then STOP. Do not start EWMA, judge() wiring, or a second asset tonight
until the human says the pipe is boring.

If a step fails, fix that step. Do not skip the backtest and claim done.
```
