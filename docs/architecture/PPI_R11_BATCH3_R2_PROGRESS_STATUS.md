# PPI R11 Batch-3 R2 Progress Status

**Status date:** September 8, 2026  
**Program:** PPI R11 cumulative shadow validation  
**Current authoritative progress:** `8 / 80` approved tickers and `2 / 20` countable batches

This file is the operational status companion to the R2 alignment addendum. It distinguishes controls that are finished in reviewed code from controls that are still blocked, not proven in a successful pilot, or stale in documentation.

## Finished in reviewed code

| Area | Status | Evidence/state |
|---|---|---|
| Three-repository responsibility split | Finished | Public source/contract plane, public acquisition plane, private analysis/governance plane are separated. |
| Canonical producer identity | Finished | `MarketMakingLFG/ppi-data-acquisition`, repository ID `1312286476`. |
| R2 public acquisition lineage | Finished | `PPI-R11-PUBLIC-ACQUISITION-003-R2`. |
| R2 collector lineage | Finished | `PPI-PUBLIC-COLLECTOR-003-R2`. |
| Private analytical lineage | Finished | Remains `PPI-R11-BATCH-EVIDENCE-003-R1`. |
| Exact public success shape | Finished | 48 bundles + manifest + receipt = 50 paths. |
| Provider mapping and request ledger | Finished | Yahoo/yfinance expectations, Alpha Vantage recognition, MarketData candles/options; 49 total operations, 12 Alpha Vantage. |
| Public acquisition sharding | Finished | Four deterministic three-ticker shards. |
| Resumability | Finished | Private checkpoint persistence, integrity verification, reuse, and cleanup. |
| Package provenance | Finished | Final public ZIP provenance attestation generated before private handoff. |
| Public package secret scan | Finished | Package checked before handoff; public raw upload remains prohibited. |
| Private materialization identity | Finished | Exact producer repository/run/head/release/asset identity is verified. |
| Attestation verification | Finished | Producer run/package attestation is checked before extraction. |
| Safe extraction | Finished | Traversal, absolute paths, links, duplicates, unexpected members, and size limits fail closed. |
| R2 trust gate | Finished | Integrated before semantic review/scoring; validates actual provider/request material and disabled authorities. |
| Private network isolation | Finished | Final analysis uses network namespace isolation with no GitHub token/provider credentials. |
| Private scoring output boundary | Finished | Corrected to bounded `runtime/shadow/r11-private-final-analysis` output root. |
| Countability/replay protection | Finished | Duplicate-credit and registry-race/no-op controls are present. |
| Registry governance model | Finished | Pilot produces a review-only registry proposal; analysis does not automatically merge registry credit. |
| Pilot evidence-dossier validator | Finished | Complete evidence classes must agree before registration. |
| Adversarial trust-boundary tests | Finished | Exact-head private suite reached 70 passing tests; public hardening suites reached 97/103 passing tests in the merged producer PRs. |

## Current live blocker

The latest inspected manual producer run is GitHub Actions run `34265097209`, producer head `2bbef4dc81c65ab2ee2b723f1bd4de5e34a90e88`.

The main `collect-and-handoff` job succeeded. It completed:

- public boundary/secret checks;
- checkpoint restoration;
- all four deterministic shards;
- resumability checkpoint persistence;
- retained-package secret scanning;
- exact-package provenance generation;
- private publication of the attested package;
- public safe-success receipt generation;
- checkpoint cleanup; and
- the public raw-upload prohibition assertion.

The overall workflow failed only in the separate `scan completed producer job log` job. Its `Download completed collect job log` step called the GitHub CLI log endpoint and GitHub CLI exited because the response contained terminal escape sequences. The scanner itself was therefore skipped, and no successful job-log leak-scan proof was retained.

**Disposition:** the acquisition payload is not accepted as a counted pilot because the evidence dossier is incomplete. A red workflow conclusion is correct under the fail-closed policy even though provider collection/handoff itself succeeded.

## Remaining before a countable batch-3 result

| Priority | Remaining item | Completion condition |
|---:|---|---|
| 1 | Repair producer job-log download plumbing | Log download handles terminal escape sequences/binary log content safely; credential scanner executes; safe scan receipt is retained; negative leak tests still fail closed. |
| 2 | Correct the stale producer README | README names `MarketMakingLFG/ppi-data-acquisition`, R2 contracts, four shards, resumability, attestation, and current retention behavior. |
| 3 | Bind provider-bearing job to a protected GitHub environment | Workflow contains the reviewed protected `environment:` boundary and repository environment protections are verified. |
| 4 | Execute a fresh manual public R2 run | Entire producer workflow, including job-log scan, concludes success and retains the required safe metadata. |
| 5 | Execute private final analysis for that exact successful public run | Materialization, attestation, R2 trust gate, safe extraction, semantic review, no-network scoring, and countability all pass for the same immutable run identity. |
| 6 | Complete the immutable pilot evidence dossier | All required public/private receipts, hashes, run identities, scans, attestation, score, countability and replay proofs validate together. |
| 7 | Review the one-file registry proposal | Human/review governance confirms exact append-only change. Do not auto-merge from the analysis job. |
| 8 | Register batch 3 if countable | Registry moves from `2 / 20`, `8 / 80` to `3 / 20`, `12 / 80`; otherwise remains unchanged with explicit non-counting disposition. |

## Documentation drift requiring correction

`MarketMakingLFG/ppi-data-acquisition/README.md` is currently inconsistent with runtime reality. It still records the former `spoudel2010-ux/ppi-data-acquisition` owner, R1 public/collector identities, and an old three-shard design. This connector cannot currently create a review branch in that producer repository, so the correction remains an owner-side/repository-permission action rather than a direct `main` edit.

The R2 alignment addendum in this repository has been refreshed alongside this status file so that controls already merged in August are no longer listed as unfinished.

## Program state and end goal

The R11 closure contract still requires:

- 80 unique approved active tickers;
- 20 countable cumulative batches;
- exactly four new approved tickers per countable run;
- cumulative scoring of the complete cohort for each batch;
- at least 10 distinct trading dates, with 20 preferred; and
- separate formal closure after all gates are satisfied.

The authoritative registry remains `8 / 80` and `2 / 20`. QCOM, MRVL, GFS, and TXN have not yet received batch-3 registry credit.

Production, publication, broker, order, trading, MMM/raw-data, and R12 authority remain outside the R11 batch-3 pilot and remain disabled.