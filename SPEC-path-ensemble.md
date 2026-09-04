# SPEC: Path-ensemble `p_true` for price markets

Status: **candidate**. Paper only. Does not change `LIVE_TRADING`.
Audience: coding agents working in this repo.
Doctrine: [AGENTS.md](AGENTS.md) still wins if this file and the code disagree.

One-sentence live rule this spec adds:

> On Polymarket markets that resolve off a listed crypto price, fair YES is the share of simulated paths that finish on the winning side of the strike; trade only if that `p_true` beats the book after V2 taker fees. Everything else stays HOLD (unless pair-arb).

---

## Why this exists

`polymarket-agi` was stripped on purpose. The live brain is `judge()` in `agent/polyagent/reason.py`: default HOLD; the only non-HOLD today is mechanical pair-arb (`YES + NO + taker fees < 0.995`). That is honest. It is also not an angle.

Inventing `p_true` from volume, favorites, sentiment, or an LLM on the hot loop is forbidden by AGENTS.md. The missing object is an **independent probability the book does not already contain**, timestamped at decision time, scored net of fees, and remembered as an episode.

That object is a **price-path ensemble** — the same commodity Bittensor SN50 (Synth) pays miners to produce. We do **not** start by mining. We implement the path function here, feed `judge()`, paper-trade, and only later wrap the same function for Synth CRPS / an axon.

Related product: RTP (`tradewife/resilient-token-protocol`) already runs a point signal + ATR on SOL. The same paths later answer P(touch SL) / P(touch TP). One generator, two books. Do not couple the repos in this ticket.

---

## Intent (read this before writing code)

| Layer | Job |
| --- | --- |
| This repo | Consumer. Parse price markets, simulate paths, set `p_true`, HOLD or BUY_YES/BUY_NO, write episodes. |
| `synth-lib` (later, not this ticket) | Offline CRPS / rank of the **same** `simulate()` vs historical prices. |
| `synth-subnet` (later, not this ticket) | Axon + `simulations.py` format. Only after paper gate **and** CRPS looks competitive. |

Do **not** clone `synth-subnet` in this ticket. Do **not** open a sibling paths repo. Do **not** pay for https://docs.synthdata.co/. Do **not** call Grok from `judge()`.

### External references (read, do not vendor)

- Synth site (miners / dashboard): https://synthdata.co/miners
- Subnet code: https://github.com/synthdataco/synth-subnet
- Miner tutorial: https://github.com/synthdataco/synth-subnet/blob/main/docs/miner_tutorial.md
- Miner response format / FAQ: https://github.com/synthdataco/synth-subnet/blob/main/docs/miner_reference.md
- README competitions + CRPS: https://github.com/synthdataco/synth-subnet/blob/main/README.md
- Hook miners edit: https://github.com/synthdataco/synth-subnet/blob/main/synth/miner/simulations.py
- Reference price feeds: https://github.com/synthdataco/synth-subnet/blob/main/synth/miner/price_simulation.py
- Backtester: https://github.com/synthdataco/synth-lib
- Public API docs (do not subscribe): https://docs.synthdata.co/
- OpenAPI: https://api.synthdata.co/docs
- SN50 metagraph: https://taostats.io/subnets/50/metagraph

Synth in one paragraph: miners return **1000 simulated price paths** for an asset. Validators score the ensemble with **CRPS** on price changes (basis points) across several increments. Competitions: Crypto 1h (Δt=1m, T=1h, **61 points/path**), Crypto 24h (Δt=5m, T=24h, **289 points/path**), Commodities/Equities 24h (same 289). Assets we care about first: **BTC, ETH, SOL, XRP, HYPE**. Feeds validators use: Binance spot for BTC/ETH/SOL/XRP, Hyperliquid for HYPE. Paths must be finite, ≤8 significant digits. Late or wrong shape is a penalty. Drift-on-purpose is how foundation models bleed; **zero mean drift** on log-returns.

Our `simulate()` should be able to emit those shapes later. This ticket only needs enough path length to cover the Polymarket horizon (15m / 1h / 4h / 24h).

---

## Scope of this ticket

In `agent/polyagent/` only, paper default unchanged:

1. Parse scan results into price-resolution markets (asset + horizon + strike + close-vs-touch).
2. Add `paths.py`: start from Binance last (Hyperliquid last for HYPE), zero-drift, EWMA vol, Student-t increments, 1000 paths.
3. `p_true = mean(terminal ? strike)` or `mean(max(path) ? strike)` if touch.
4. `judge()`: ARB first (unchanged), else path-priced BUY_YES / BUY_NO if edge survives fees, else HOLD.
5. Persist path summary on the episode. Tests. No live flag.

Out of scope: SN50 wallet, PM2, port 8091, `synth-subnet` clone, LoRA/Chronos, RTP import, paid Synth API, dashboard redesign, raising caps, `LIVE_TRADING`.

---

## Current hooks (do not invent a second loop)

| File | Role |
| --- | --- |
| `agent/polyagent/reason.py` | **Only** place `p_true` / HOLD / ARB / BUY_* may be decided. |
| `agent/polyagent/strategy.py` | Already sizes `BUY_YES` / `BUY_NO` via `quarter_kelly` when `p_true` is set. Do not reimplement Kelly. |
| `agent/polyagent/scan.py` | Gamma fetch. Add a filter helper; keep `ScoredMarket`. |
| `agent/polyagent/fees.py` | Source of truth for “beats fees.” |
| `agent/polyagent/loop.py` | Scan → judge → intents → paper execute → episode. Call parse + paths from `judge()` or immediately before it. |
| `agent/polyagent/episode.py` | Update `reasoning.policy` when path-priced actions exist. Store path fields on actionable rows. |
| `agent/tests/test_reason.py` | Keep existing HOLD/ARB tests. Add path tests with a **stubbed** simulator (no live Binance in CI). |

`Judgment` already has `p_true`, `action` in `{HOLD, BUY_YES, BUY_NO, ARB}`, `fill_yes`, `fill_no`, `edge_after_fees`, `kelly_fraction`. Extend the dataclass only if you must; prefer putting path diagnostics in `reasoning` text **and** in the episode JSON, not a parallel struct the dashboard does not need.

---

## 1. Price-market filter

New module: `agent/polyagent/price_markets.py`.

Parse `ScoredMarket.question` and any slug you can reach without new HTTP. If parse fails → not a price market → `judge()` HOLDs as today.

Accept only:

- Assets: `BTC`, `ETH`, `SOL`, `XRP`, `HYPE` (map Bitcoin/Ether/Solana/Ripple/Hyperliquid aliases).
- Horizons: 15m, 1h, 4h, 24h / daily. Skip 5m until we have evidence; fees + latency will eat it.
- Structure: binary up/down from a reference price, **or** above/below an explicit strike.
- Settlement: **close** (terminal price vs strike) default; **touch** only if the question clearly pays on high/low / “reach”.

Return a frozen dataclass, e.g.:

```text
PriceContract(
  asset: str,              # BTC
  venue: str,              # binance | hyperliquid
  horizon_seconds: int,
  strike: float | None,    # None → use spot at decision as ATM up/down reference
  reference_price: float | None,
  settlement: str,         # close | touch
  yes_means: str,          # up | down | above | below
  raw_question: str,
)
```

If `strike` is missing on an up/down contract, strike = spot at decision time (the usual “higher or lower than now”). Document that in the episode.

Politics, sports, “will X announce”, multi-outcome, and unparsed questions never get a `p_true`.

Optional: drop `min_volume_24h` for this subset only if crypto 15m/1h books are thinner than 8k — gate it behind a setting `POLYAGENT_PRICE_MIN_VOLUME_24H`, default keep 8000 until you see the scan miss every BTC 1h. Do not silently scan the whole world at 0 volume.

---

## 2. `paths.py`

New module: `agent/polyagent/paths.py`.

### `simulate(...)` contract

```text
simulate(
  asset: str,
  horizon_seconds: int,
  n_paths: int = 1000,
  dt_seconds: int | None = None,
  spot: float | None = None,   # inject in tests
  vol: float | None = None,    # inject in tests
  seed: int | None = None,
) -> PathEnsemble
```

`PathEnsemble.prices`: `ndarray` shape `(n_paths, n_steps)` inclusive of t0 so:

- 15m / 1h → `dt=60`, steps = horizon/60 + 1 (1h → **61**, matches Synth crypto-1h).
- 4h / 24h → `dt=300`, steps = horizon/300 + 1 (24h → **289**, matches Synth crypto-24h).

Prices: finite floats, clip to > 0, round/export with ≤8 significant digits when serialising.

### Dynamics (v1 — statistical, not a foundation model)

1. Spot: Binance last for BTC/ETH/SOL/XRP (`https://api.binance.com` bookTicker or equivalent). HYPE: Hyperliquid mid/mark. Cache in-process for the cycle so 20 markets do not hammer the venue.
2. Vol: EWMA of log-returns on recent 1m (short horizon) or 5m (long) bars. Fallback: a hard-coded per-asset prior if the fetch fails — then HOLD, do not trade on a stale invented vol unless tests inject it.
3. Log-increments: i.i.d. Student-t with ν ≈ 5, scale so per-step variance matches EWMA × dt. **Mean of the increment = 0** (no directional drift).
4. `S_{t+1} = S_t * exp(r)`. No jump module in v1.
5. Deterministic `seed` in unit tests.

Network failures → return `None` from the helper `judge()` calls → HOLD with reasoning “no spot/vol”. Never crash the loop.

Do not add GPU, Chronos, LoRA, or paid APIs.

### `p_yes(ensemble, contract) -> float`

- `settlement=close`: fraction of paths with `prices[:, -1]` on the YES side of strike.
- `settlement=touch`: fraction whose `max` (above) or `min` (below) crosses strike.
- Map `yes_means=down/below` by complement. Clamp to `(1e-6, 1-1e-6)`.

---

## 3. `judge()` change

Keep ARB block identical and first.

Then:

```text
contract = parse_price_market(market)
if contract is None:
    HOLD  # existing message
ensemble = simulate(...)          # or injected
if ensemble is None:
    HOLD  # no feed
p_true = p_yes(ensemble, contract)
# edge vs the fill we would actually pay
fee = fee_per_share(fill, ...)
if p_true > fill_yes + fee + EDGE_BUFFER:
    BUY_YES
elif (1 - p_true) > fill_no + fee + EDGE_BUFFER:
    BUY_NO
else:
    HOLD
```

`EDGE_BUFFER`: setting `POLYAGENT_PATH_EDGE`, default **0.03** (3¢ after fee). Too small and you churn. Do not Kelly on 0.4¢ of model dust.

`confidence`: something dumb and inspectable, e.g. `min(0.8, 0.4 + 10 * abs(p_true - implied_yes))` — not a fake 0.99.

Reasoning string must include asset, horizon, strike, settlement, n_paths, spot, vol, p_true, implied, fill, fee, edge. This is the trace.

`kelly_fraction`: leave to `strategy.py` (`quarter_kelly`). Set `Judgment.kelly_fraction` to that same value so the episode matches the intent.

Caps stay: $5 ticket, 4 open, $100 paper, taker fees on.

---

## 4. Episodes

Update `agent/polyagent/episode.py`:

- `reasoning.policy`: `hold-unless-pair-arb-or-path-edge` once path actions can fire.
- Each actionable row adds: `p_true`, `asset`, `horizon_seconds`, `strike`, `settlement`, `n_paths`, `spot`, `vol`, `edge_after_fees`.
- HOLD sample for parsed price markets should still show `implied_yes` (so weekly replay can see “we saw BTC 1h and stood down”).

Do not dump 1000×289 floats into JSONL.

---

## 5. Tests (required)

`agent/tests/test_price_markets.py`

- Parse a few realistic questions (BTC up/down 1h, ETH above $X, SOL 15m). Reject “Will the Fed cut?”.

`agent/tests/test_paths.py`

- Injected spot+vol+seed: shape `(1000, 61)` for 1h, all finite, all > 0.
- Zero-drift: mean log-return across paths ≈ 0 at loose tolerance.
- `p_yes` is 0.5-ish when strike == spot on a symmetric draw (seed-stable, loose).

`agent/tests/test_reason.py` (extend)

- Existing HOLD/ARB tests still pass with no path injection.
- Inject a fake ensemble (or monkeypatch `simulate`) with **all paths above strike** → BUY_YES when book is mid.
- Inject all paths below → BUY_NO.
- Buffer: p_true = 0.51 vs fill 0.50 + fee → HOLD.
- Unparsed question → HOLD, `p_true is None`.

No live HTTP in tests.

---

## Profit gate (do not skip)

A green test suite is not permission to go live.

From `agent/data/episodes.jsonl` + trades, the candidate must beat:

1. always-HOLD
2. current arb-only `judge()`

on **fee-adjusted expectancy**, without exploding MAE. If it only wins because 15m BTC favorites drifted, reject it (AGENTS.md).

If HOLD wins: the book is efficient on that horizon. Do **not** register SN50. Iterate `paths.py` offline or stop.

If the candidate wins: next specs (not this one) are (a) emit Synth-shaped files into `synth-lib` backtest, (b) copy `simulate()` into `synth-subnet` `simulations.py` on a VPS — never the laptop axon as the mainnet miner.

---

## Constraints for the coding agent

- One hook: `judge()`. No Prisma/dashboard book, no second Python agent, no restored fork features.
- Paper default. Do not touch `LIVE_TRADING`.
- Prefer stdlib + numpy. Add numpy in `agent/pyproject.toml` if missing. Do not add torch/bittensor.
- Fail closed: any parse/feed/shape error is HOLD.
- Keep `uv` tests runnable: `cd agent && uv run python -m unittest discover -s tests`.
- Commit message names the failure mode this patch addresses: **no independent p_true on price markets**.

---

## Suggested file list

```text
SPEC-path-ensemble.md          # this file (already landed)
agent/polyagent/price_markets.py
agent/polyagent/paths.py
agent/polyagent/reason.py      # edit
agent/polyagent/episode.py     # edit
agent/polyagent/scan.py        # optional filter helper only
agent/polyagent/config.py      # POLYAGENT_PATH_EDGE, optional volume override
agent/tests/test_price_markets.py
agent/tests/test_paths.py
agent/tests/test_reason.py     # extend
AGENTS.md                      # one paragraph pointing here; do not rewrite doctrine
```

When this ticket is done, the live policy sentence in AGENTS.md becomes:

> HOLD unless (1) pair-arb after fees or (2) parsed crypto price market whose path-ensemble `p_true` beats the fill by `POLYAGENT_PATH_EDGE` after V2 fees.
