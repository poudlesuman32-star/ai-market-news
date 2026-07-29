# PPI R11 Batch-3 R2 Contract Alignment Addendum

**Status:** proposed alignment for review  
**Date:** July 29, 2026  
**Applies to:** `poudlesuman32-star/ai-market-news`, `spoudel2010-ux/ppi-data-acquisition`, and `musksuman3/ai-signal-engine`

## Decision

For the R11 batch-3 public acquisition pilot, the approved runtime lineage is:

- Private analytical contract: `PPI-R11-BATCH-EVIDENCE-003-R1`
- Public acquisition contract: `PPI-R11-PUBLIC-ACQUISITION-003-R2`
- Public collector release: `PPI-PUBLIC-COLLECTOR-003-R2`

R2 supersedes only the public acquisition and collector R1 identities. The private analytical contract remains R1. Existing R1 receipts and historical records remain immutable and must not be relabeled as R2.

This addendum supersedes R1-only wording in the Version 1.2 architecture document wherever that wording conflicts with the active, frozen R2 public collector.

## Why R2 is required

The R1 public design could exhaust Alpha Vantage quota before the complete twelve-ticker package was collected. R2 keeps provider execution public while changing expectation-history retrieval to the pinned `yfinance==1.5.1` helper and limiting Alpha Vantage to twelve `NEWS_SENTIMENT` operations.

The R2 provider mapping is:

| Evidence category | Frozen provider operation |
|---|---|
| Expectation history | `yahoo_finance_via_yfinance:1.5.1` |
| Independent recognition | `alpha_vantage:NEWS_SENTIMENT` |
| Market time series | `marketdata:daily_candles` |
| Specialized contract data | `marketdata:option_chain` |

The benchmark remains `QQQ`.

## Frozen public package

A valid R2 batch-3 package must contain exactly:

- 12 cumulative tickers;
- 4 evidence categories per ticker;
- 48 evidence bundles;
- 1 cumulative manifest;
- 1 collection receipt;
- 50 total retained package paths; and
- 49 provider operations, including exactly 12 Alpha Vantage operations.

The cumulative tickers are:

`AAPL, MU, NVDA, AMD, AVGO, INTC, TSM, ARM, QCOM, MRVL, GFS, TXN`

The new batch-3 candidates remain:

`QCOM, MRVL, GFS, TXN`

## Trust boundary

`spoudel2010-ux/ppi-data-acquisition` remains the only provider-execution plane. It may collect, retry, validate objective structure, package, hash, and hand off evidence. It may not score, approve, publish trading signals, mutate the private registry, or start private analysis automatically.

`musksuman3/ai-signal-engine` may accept an R2 package only after a fail-closed trust gate verifies:

1. repository name and numeric repository ID;
2. approved workflow path and manual event;
3. workflow run ID, attempt, and 40-character head SHA;
4. public R2 contract and collector identities;
5. private R1 analytical contract identity;
6. queue receipt identity;
7. exact 50-path package shape;
8. exact ticker/category coverage;
9. manifest and bundle hashes;
10. public-storage and downstream-authority flags remain disabled; and
11. no synthetic content is marked as used.

Passing this transport trust gate does not approve evidence, authorize scoring, establish countability, or permit registry changes.

## Pilot gate

The first R2 run remains manual-only. Use the exact confirmation:

`COLLECT-R11-BATCH-3`

Do not treat the run as authoritative until:

- the acquisition repository README acknowledges this R2 lineage;
- the private repository contains and tests the R2 trust gate;
- the three required acquisition secrets are configured;
- the public run succeeds with exactly 48 bundles and 50 paths;
- the private prerelease asset is present;
- no automatic private-analysis trigger occurs; and
- the public receipt and private package pass independent verification.

## Required acquisition secrets

The acquisition repository requires these GitHub Actions secrets:

- `PPI_ALPHA_VANTAGE_API_KEY`
- `PPI_MARKETDATA_TOKEN`
- `PPI_PRIVATE_HANDOFF_TOKEN`

Secret values must never be committed, copied into issues, or stored as repository variables.

`PPI_SEC_CONTACT_EMAIL` is not part of the R2 acquisition contract because the active acquisition collector does not call SEC endpoints. It remains scoped to components that actually use it.

## Remaining hardening

The pilot is not production authorization. Before an official counted run, complete and review:

- a protected GitHub environment for provider credentials;
- provenance attestation generation and private verification;
- sharded or resumable public acquisition;
- package-size, retention, and cleanup enforcement;
- safe archive extraction;
- a network-disabled private analytical invocation;
- duplicate-credit and registry-race protection; and
- a separate human-reviewed append-only registry proposal.

Production, publication, broker, order, trading, MMM/raw-data, and R12 authority remain disabled.
