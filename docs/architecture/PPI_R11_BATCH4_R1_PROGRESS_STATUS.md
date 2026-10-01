# PPI R11 Batch-4 Progress Status

**Status date:** October 1, 2026 UTC  
**Program:** PPI R11 cumulative shadow validation  
**Batch-4 state:** **IN PROGRESS — provider credit window blocked; fail-closed checkpoint retained**  
**Authoritative R11 registry:** **12 / 80 approved tickers and 3 / 20 countable batches**

## Frozen batch-4 scope

Batch 4 is the next exact frozen queue cohort:

`STM, ON, NXPI, MCHP`

The cumulative batch-4 cohort is 16 tickers:

`AAPL, MU, NVDA, AMD, AVGO, INTC, TSM, ARM, QCOM, MRVL, GFS, TXN, STM, ON, NXPI, MCHP`

The reviewed batch-4 boundary preserves:

- public acquisition contract `PPI-R11-PUBLIC-ACQUISITION-004-R1`;
- collector release `PPI-PUBLIC-COLLECTOR-004-R1`;
- private analytical contract `PPI-R11-BATCH-EVIDENCE-004-R1`;
- 64 evidence bundles;
- 66 retained package paths;
- 65 provider operations;
- 16 Alpha Vantage `NEWS_SENTIMENT` operations;
- 16 Yahoo/yfinance expectation-history operations;
- 17 MarketData daily-candle operations including `QQQ`;
- 16 MarketData option-chain operations;
- four deterministic shards of four tickers each;
- public raw storage disabled;
- all production/publication/broker/order/trading/MMM/R12 authority disabled.

## Implementation and trust boundary

Producer batch-4 implementation merged through `MarketMakingLFG/ppi-data-acquisition#24` at `84e25ef834d9986aef404cfeff6ffe4b3621c17a`.

Private batch-4 contract was reviewed separately and merged before implementation. The private implementation then merged through `musksuman3/ai-signal-engine#273` at `bdb10cb247c0080a0ed0320c8947588dc51e4901`.

The independently hosted deployment-protection service was updated to the exact batch-4 protected workflow allowlist. Render deployment `dep-dauv5841nsns73fs4fc0` is live. Its startup self-test passed with policy `r11-autonomous-v3`, App ID `5112236`, installation `165898080`, repository ID `1312286476`, protection rule `67004141`, and main-only branch policy `60290047`.

No protection bypass was used.

## Producer pilot evidence so far

The protected producer run is `36821116213`, head:

`d362e635054bd6b7a313d41e8c2236cd20ac2122`

Attempt 1 was independently approved by `r11-autonomous-v3` and failed closed during provider collection after MarketData returned HTTP 429 on bounded retries. The safe failure receipt recorded:

- `provider_calls_this_attempt: 24`;
- `resumed_from_attempt: null`;
- `reused_shards: []`;
- no package publication;
- no private analysis;
- no registry action.

A private authenticated checkpoint was persisted.

Attempt 2 was independently approved again, restored the prior checkpoint, and reused verified shard 0. It also failed closed at the first new MarketData request because the provider credit window remained exhausted. Its safe failure receipt recorded:

- `provider_calls_this_attempt: 8`;
- `resumed_from_attempt: 1`;
- `reused_shards: [0]`;
- no package publication;
- no private analysis;
- no registry action.

The completed attempt-2 job log was scanned successfully:

- exact secret matches: 0;
- encoded-secret matches: 0;
- authorization-header matches: 0;
- credential-query matches: 0.

## Provider-limit remediation

Market Data documents daily credit windows for Free/Starter/Trader-class plans and a reset at 9:30 AM Eastern Time. The next retry is intentionally deferred until after that reset instead of burning repeated provider attempts inside the exhausted credit window.

The existing authenticated checkpoint remains the only allowed reuse source. On the next attempt, only complete verified shards may be reused; incomplete shards must be recomputed. Any identity drift, protection failure, credential leak, provider failure, package mismatch, private-analysis failure, or duplicate-credit condition remains fail closed.

## Registry effect

**None yet.**

Batch 4 has not earned registry credit. The authoritative registry remains:

- accepted countable batches: **3 / 20**;
- approved tickers: **12 / 80**;
- status: `collecting`;
- `r12_authorized: false`.

Only a completed protected producer run, passing private exact-run analysis, countable-candidate disposition, immutable dossier validation, and CI-gated one-file registry governance may advance batch 4 to 4/20 and 16/80.
