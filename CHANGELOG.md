# Changelog

## [0.8.4.0] - 2026-09-05

### Added
- One Python paper loop (`agent/polyagent`) with a HOLD-unless-pair-arb reasoner, V2 taker fees, cash/slot caps, and decision-episode logs.
- Thin dashboard that only reads `agent/data/snapshot.json` and public Gamma markets.
- Unit tests for fee quotes and HOLD/ARB judgment.

### Changed
- Operating contract lives in `AGENTS.md` (live policy, profit gate, learning loop).

### Removed
- Fork bloat that was not wired: fake Grok/Kelly/news/wallet APIs, Prisma trading UI, skills pack, docker swarm, screenshots, agent-ctx.
