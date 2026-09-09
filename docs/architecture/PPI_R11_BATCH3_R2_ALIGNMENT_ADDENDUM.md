# PPI R11 Batch-3 R2 Contract Alignment Addendum

**Status:** implemented alignment; counted batch-3 completion remains pending  
**Originally approved:** July 29, 2026  
**Status refreshed:** September 8, 2026  
**Applies to:** `poudlesuman32-star/ai-market-news`, `MarketMakingLFG/ppi-data-acquisition` (repository ID `1312286476`), and `musksuman3/ai-signal-engine`

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

`MarketMakingLFG/ppi-data-acquisition` (repository ID `1312286476`) is the only provider-execution plane. It may collect, retry, validate objective structure, package, hash, attest, and hand off evidence. It may not score, approve, publish trading signals, mutate the private registry, or start private analysis automatically.

`musksuman3/ai-signal-engine` may accept an R2 package only after a fail-closed trust gate verifies repository and workflow identity, materialized run identity, exact provider operations, exact package shape, hashes, attestation, safe extraction, and disabled downstream authorities.

Passing the transport trust gate does not approve evidence, authorize scoring, establish countability, or permit registry changes.

## Implemented and verified controls

As of September 8, 2026, the following architecture items are implemented in the reviewed code paths:

- R2 public provider mapping and exact 49-operation ledger;
- exact 48-bundle and 50-path success-package enforcement;
- four deterministic three-ticker public shards with resumable private checkpoints;
- final-package provenance attestation generation;
- private verification of producer run identity and attestation before extraction;
- safe ZIP extraction with path, member-type, duplicate-entry, and size protections;
- integrated R2 trust validation before private scoring;
- network-disabled private analysis with no provider credentials or GitHub token;
- corrected bounded private scoring output root;
- replay and duplicate-credit protection;
- review-only registry proposal generation rather than automatic pilot registry merge;
- full pilot evidence-dossier validation before registration;
- public package secret scanning and a dedicated producer job-log leak-scan stage;
- separate success/failure retention and cleanup paths; and
- adversarial validation coverage across the public/private trust boundary.

The authoritative private R11 registry remains unchanged until a complete batch-3 pilot passes all gates and the separate governance step accepts the proposal.

## Current pilot state

The first R2 acquisition remains manual-only and requires the exact confirmation:

`COLLECT-R11-BATCH-3`

The latest inspected manual public run, GitHub Actions run `34265097209` on producer head `2bbef4dc81c65ab2ee2b723f1bd4de5e34a90e88`, completed the main `collect-and-handoff` job successfully. That job completed collection/reuse of all four shards, package secret scanning, package provenance generation, private publication of the attested package, public safe-receipt construction, checkpoint cleanup, and the public raw-upload assertion.

The workflow nevertheless concluded `failure` because the separate `scan completed producer job log` job failed while downloading the completed job log. The GitHub CLI rejected terminal escape sequences in the downloaded log before the credential-leak scanner ran. The safe success metadata artifact was still retained, but the mandatory job-log leak-scan proof was not produced.

Therefore this run is **not countable** and must not advance the private registry.

## Current blocker and required correction

The immediate producer-side correction is to make the job-log download step robust to terminal escape sequences while retaining fail-closed leak scanning. The current failure text indicates that the GitHub CLI log download needs explicit escape-sequence handling or an equivalent binary-safe download path.

After that correction, a new manual R2 run must complete with:

1. a successful collection/handoff job;
2. a successful completed-job-log leak scan and retained safe receipt;
3. a complete public success receipt and private handoff;
4. private materialization, attestation, trust-gate, safe-extraction, semantic-review, scoring, and countability evidence;
5. a complete pilot evidence dossier; and
6. a separate review-only registry proposal and governance decision.

## Remaining documentation and configuration work

The following items remain open even though the corresponding runtime architecture is substantially implemented:

- `MarketMakingLFG/ppi-data-acquisition/README.md` is stale: it still names the former repository owner, declares the R1 public acquisition/collector lineage, and describes the obsolete three-shard layout. It must be updated to the canonical repository name, R2 lineage, and current four-shard/resumable/attested workflow.
- The producer-bearing job does not currently declare a protected GitHub `environment:` in the workflow. A protected credential environment therefore remains not proven as a live runtime control and should be added/reviewed before treating that control as satisfied.
- The batch-3 pilot must obtain one complete successful end-to-end evidence dossier after the producer log-scan defect is fixed.

## R11 program state

The authoritative private registry remains:

- accepted countable batches: `2 / 20`;
- approved active tickers: `8 / 80`;
- approved tickers: `AAPL, MU, NVDA, AMD, AVGO, INTC, TSM, ARM`.

Batch 3 will move the program toward `3 / 20` and `12 / 80` only after the full countability and governance sequence succeeds. No partial credit is granted.

## Required acquisition secrets

The acquisition repository requires these GitHub Actions secrets:

- `PPI_ALPHA_VANTAGE_API_KEY`
- `PPI_MARKETDATA_TOKEN`
- `PPI_PRIVATE_HANDOFF_TOKEN`

The required secrets are configured for the current acquisition path. Secret values must never be committed, copied into issues, or stored as repository variables.

`PPI_SEC_CONTACT_EMAIL` is not part of the R2 acquisition contract because the active acquisition collector does not call SEC endpoints. It remains scoped to components that actually use it.

## Authority boundary

The pilot is not production authorization. Production, publication, broker, order, trading, MMM/raw-data, and R12 authority remain disabled.