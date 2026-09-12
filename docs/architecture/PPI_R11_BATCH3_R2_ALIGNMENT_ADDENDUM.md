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

`MarketMakingLFG/ppi-data-acquisition` (repository ID `1312286476`) is the only approved producer-execution plane. All producer contracts, configuration, receipts, handoff metadata, attestation policy, and documentation used for a fresh countable pilot must identify that canonical repository consistently. The historical `spoudel2010-ux/ppi-data-acquisition` slug must not appear in fresh producer-generated identity metadata.

The producer may collect, retry, validate objective structure, package, hash, attest, and hand off evidence. It may not score, approve, publish trading signals, mutate the private registry, or start private analysis automatically.

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
- public package secret scanning and a dedicated producer completed-job-log leak-scan stage;
- separate success/failure retention and cleanup paths; and
- adversarial validation coverage across the public/private trust boundary.

The authoritative private R11 registry remains unchanged until a complete batch-3 pilot passes all gates and the separate governance step accepts the proposal.

## Current pilot state and exact blocker evidence

The R2 acquisition remains manual-only and requires the exact confirmation:

`COLLECT-R11-BATCH-3`

The latest inspected manual public run is GitHub Actions run `34265097209` on producer head `2bbef4dc81c65ab2ee2b723f1bd4de5e34a90e88`.

Its main `collect-and-handoff` job, job ID `102192347121`, completed successfully. It completed collection/reuse of all four shards, retained-package secret scanning, exact-package provenance generation, private publication of the attested package, public safe-receipt construction, checkpoint cleanup, and the public raw-upload assertion.

The run retained safe-success artifact `ppi-r11-public-success-34265097209-1`, artifact ID `10071593777`, with GitHub artifact digest `sha256:8721f7ce848bb75be653f602ae1eb2ebf8f967bdbb8ee211ac14516fbbd4a9d5`.

The overall workflow concluded `failure` because the separate `scan completed producer job log` job, job ID `102193467150`, failed at `Download completed collect job log`. The current workflow uses:

```text
gh api "repos/${GITHUB_REPOSITORY}/actions/jobs/${job_id}/logs" > "$RUNNER_TEMP/collect-and-handoff.log"
```

GitHub CLI exited with:

```text
the response contains terminal escape sequences; pass --allow-escape-sequences to output it anyway
```

The credential scanner was skipped and no job-log-scan receipt was retained. Therefore run `34265097209` is **not countable** and must not advance private analysis or the registry as a pilot result.

## Required producer correction

The immediate producer-side change must remain fail closed. The reviewable correction should:

1. enable binary/escape-bearing log output from the GitHub CLI, such as `gh api --allow-escape-sequences .../actions/jobs/${job_id}/logs`;
2. feed the resulting file directly to the scanner rather than echoing it back into workflow output;
3. scan both raw log bytes and a safely ANSI-normalized byte view so formatting bytes cannot split and conceal a credential;
4. reject unsupported escape material or otherwise prove normalization cannot suppress credential evidence;
5. retain exact, encoded, authorization-header, and credential-query leak detection;
6. add adversarial regressions for safe ANSI formatting, an ANSI-fragmented secret, an ANSI-fragmented authorization header, and the workflow download flag; and
7. require a later authorized manual R2 run to produce a passing retained job-log-scan receipt before this blocker is considered finished.

A fresh remediation branch was attempted from exact failing producer head `2bbef4dc81c65ab2ee2b723f1bd4de5e34a90e88` as `codex/ppi-r11-log-scan-ansi-20260908`. The connected GitHub App returned HTTP 403 `Resource not accessible by integration` on ref creation. The older producer review branch `codex/ppi-r11-r2-producer-evidence-20260801` was then rechecked live; it remains at August commit `451d442f4b16768ba77050cf7026300813ca9a6d`. A non-force fast-forward of that branch to current producer `main` `2bbef4dc81c65ab2ee2b723f1bd4de5e34a90e88` was attempted and also returned HTTP 403 `Resource not accessible by integration`. No producer code was written directly to `main`, and the stale branch must not be used as-is.

## Required producer identity correction before fresh pilot

Current producer `main` still contains the former repository slug `spoudel2010-ux/ppi-data-acquisition` in identity-bearing surfaces despite the canonical repository being `MarketMakingLFG/ppi-data-acquisition` with stable repository ID `1312286476`:

- `contracts/PPI-R11-PUBLIC-ACQUISITION-003-R2.json` field `repository`;
- `contracts/PPI-PUBLIC-COLLECTOR-003-R2.json` field `repository`;
- `config/provider_licensing_dispositions.json` field `public_repository`;
- `src/publish_private_handoff.py` private-release body text; and
- `README.md`.

These references must be corrected together on a reviewable producer change, with focused tests that fail if canonical producer identity diverges across frozen contracts, licensing configuration, generated handoff metadata, and documentation relevant to operator execution. This correction is required before a fresh countable pilot; updating the README alone is insufficient.

## Remaining sequence after log-scan repair

The remediation queue remains sequential:

1. validate the producer log-scan correction in focused tests and then in a later successful manual R2 workflow run;
2. bind the provider-bearing acquisition job to a reviewed protected GitHub environment and verify the environment protections, without changing repository secrets/environments absent explicit approval;
3. correct all stale producer identity surfaces listed above, including the README, and prove identity consistency;
4. obtain a fresh completely successful manual R2 acquisition evidence set;
5. perform private exact-run materialization and analysis only when explicitly authorized;
6. validate the complete immutable pilot evidence dossier;
7. generate/review the one-file registry proposal without automatic merge; and
8. register batch 3 only if every countability and governance gate passes.

## Protected credential environment remains unproven

The provider-bearing producer job does not currently declare a protected GitHub `environment:`. A protected credential environment therefore remains not proven as a live runtime control. Adding or changing the repository environment itself requires explicit approval; no such mutation is authorized by this addendum.

## Live R11 registry state

The authoritative registry `musksuman3/ai-signal-engine/audit/r11_shadow_validation_registry.json` remains:

- status `collecting`;
- accepted countable batches `2 / 20`;
- approved active tickers `8 / 80`;
- approved tickers `AAPL, MU, NVDA, AMD, AVGO, INTC, TSM, ARM`;
- only batch sequences 1 and 2 registered;
- formal closure not committed; and
- `r12_authorized: false`.

QCOM, MRVL, GFS, and TXN have not received batch-3 registry credit. No partial credit is granted.

## Required acquisition secrets

The acquisition repository requires these GitHub Actions secrets:

- `PPI_ALPHA_VANTAGE_API_KEY`
- `PPI_MARKETDATA_TOKEN`
- `PPI_PRIVATE_HANDOFF_TOKEN`

The required secrets are configured for the current acquisition path. Secret values must never be committed, copied into issues, or stored as repository variables.

`PPI_SEC_CONTACT_EMAIL` is not part of the R2 acquisition contract because the active acquisition collector does not call SEC endpoints. It remains scoped to components that actually use it.

## Authority boundary

The pilot is not production authorization. Production, publication, broker, order, trading, MMM/raw-data, and R12 authority remain disabled.
