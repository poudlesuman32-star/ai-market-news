# PPI R11 Batch-3 R2 Progress Status

**Status date:** September 8, 2026  
**Program:** PPI R11 cumulative shadow validation  
**Current authoritative progress:** `8 / 80` approved tickers and `2 / 20` countable batches

This file is the operational status companion to the R2 alignment addendum. It distinguishes controls that are finished in reviewed code from controls that are still blocked, not proven in a successful pilot, or stale in documentation.

## Finished in reviewed code

| Area | Status | Evidence/state |
|---|---|---|
| Three-repository responsibility split | Finished | Public source/contract plane, public acquisition plane, private analysis/governance plane are separated. |
| Canonical producer identity | Finished as architecture decision | Canonical runtime identity is `MarketMakingLFG/ppi-data-acquisition`, repository ID `1312286476`; stale producer files listed below still require correction before a fresh pilot. |
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

## Current live blocker: completed-job-log scan plumbing

The latest inspected manual producer run is GitHub Actions run `34265097209`, producer head `2bbef4dc81c65ab2ee2b723f1bd4de5e34a90e88`.

The main `collect-and-handoff` job, job ID `102192347121`, succeeded. It completed:

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

The successful job retained artifact `ppi-r11-public-success-34265097209-1`, artifact ID `10071593777`, with GitHub artifact digest `sha256:8721f7ce848bb75be653f602ae1eb2ebf8f967bdbb8ee211ac14516fbbd4a9d5`.

The overall workflow failed in the separate `scan completed producer job log` job, job ID `102193467150`. Its `Download completed collect job log` step executed:

```text
gh api "repos/${GITHUB_REPOSITORY}/actions/jobs/${job_id}/logs" > "$RUNNER_TEMP/collect-and-handoff.log"
```

GitHub CLI then terminated with:

```text
the response contains terminal escape sequences; pass --allow-escape-sequences to output it anyway
```

The credential scanner did not execute, and the retention step reported that no job-log-scan receipt existed. Therefore the run lacks mandatory completed-job-log credential-leak evidence.

**Disposition:** the acquisition payload is not accepted as a counted pilot because the evidence dossier is incomplete. A red workflow conclusion is correct under the fail-closed policy even though provider collection/handoff itself succeeded.

### Prepared remediation and acceptance tests

The reviewable producer correction should be based on exact failing head `2bbef4dc81c65ab2ee2b723f1bd4de5e34a90e88` and must preserve fail-closed scanning:

1. download the log with GitHub CLI escape-sequence output explicitly enabled, for example `gh api --allow-escape-sequences .../actions/jobs/${job_id}/logs`;
2. retain the downloaded bytes as scanner input rather than rendering them back into the workflow log;
3. scan the raw bytes and an ANSI-normalized byte view so terminal formatting cannot split a credential and evade matching;
4. reject unsupported/unhandled escape sequences or otherwise prove normalization cannot hide credential material;
5. keep exact, base64, URL-encoded, authorization-header, and credential-query detection fail closed;
6. add focused regressions for an ordinary ANSI-formatted safe log, a secret fragmented by ANSI CSI bytes, an ANSI-fragmented authorization header, and the workflow `--allow-escape-sequences` wiring; and
7. require a later manual R2 run to retain a passing `job-log-scan-receipt.json` before this item moves to finished.

A fresh producer branch from the exact failing head was attempted as `codex/ppi-r11-log-scan-ansi-20260908`, but the connected GitHub App returned HTTP 403 `Resource not accessible by integration` on ref creation. The older manually created producer branch is based on August code and must not be reused without first aligning it to current `main`, because doing so could discard merged resumability/log-evidence hardening.

## Remaining before a countable batch-3 result

| Priority | Remaining item | Completion condition |
|---:|---|---|
| 1 | Repair producer job-log download/scanning plumbing | Escape-bearing logs download safely; raw + normalized credential scanning remains fail closed; focused negative tests pass; a later authorized manual run retains a passing safe scan receipt. |
| 2 | Bind provider-bearing job to a protected GitHub environment | Workflow contains the reviewed protected `environment:` boundary and repository environment protections are verified. No secret/environment mutation occurs without explicit approval. |
| 3 | Correct all stale producer identity/documentation references | Before a fresh pilot, replace the former `spoudel2010-ux/ppi-data-acquisition` slug with canonical `MarketMakingLFG/ppi-data-acquisition` wherever producer runtime/contracts emit or govern identity, including both R2 contract JSON files, provider licensing dispositions, handoff release-body generation, and README; add focused identity-consistency coverage. |
| 4 | Execute a fresh manual public R2 run | Entire producer workflow, including job-log scan, concludes success and retains the required safe metadata. |
| 5 | Execute private final analysis for that exact successful public run | Materialization, attestation, R2 trust gate, safe extraction, semantic review, no-network scoring, and countability all pass for the same immutable run identity. |
| 6 | Complete the immutable pilot evidence dossier | All required public/private receipts, hashes, run identities, scans, attestation, score, countability and replay proofs validate together. |
| 7 | Review the one-file registry proposal | Human/review governance confirms exact append-only change. Do not auto-merge from the analysis job. |
| 8 | Register batch 3 only if countable | Registry moves from `2 / 20`, `8 / 80` to `3 / 20`, `12 / 80`; otherwise remains unchanged with explicit non-counting disposition. |

## Producer identity drift requiring correction

The canonical producer is `MarketMakingLFG/ppi-data-acquisition`, repository ID `1312286476`, but current producer `main` still contains the former slug `spoudel2010-ux/ppi-data-acquisition` in multiple authoritative/runtime-facing locations:

- `contracts/PPI-R11-PUBLIC-ACQUISITION-003-R2.json` field `repository`;
- `contracts/PPI-PUBLIC-COLLECTOR-003-R2.json` field `repository`;
- `config/provider_licensing_dispositions.json` field `public_repository`;
- `src/publish_private_handoff.py` private-release body text; and
- `README.md` documentation.

This is not merely README drift. A fresh countable pilot must not proceed until these identity-bearing surfaces consistently name the canonical producer and focused tests prove that the generated contract/handoff metadata agrees with the trusted repository identity. The repository ID remains stable at `1312286476`, but slug consistency is still required by the trust contract.

The R2 alignment addendum in this repository is refreshed alongside this status file so controls already merged in August are no longer listed as unfinished.

## Live registry verification

The private registry at `musksuman3/ai-signal-engine/audit/r11_shadow_validation_registry.json` remains `status: collecting` with:

- `accepted_run_count: 2`;
- `accepted_ticker_count: 8`;
- approved tickers `AAPL, MU, NVDA, AMD, AVGO, INTC, TSM, ARM`;
- only batch sequences 1 and 2 in `accepted_runs`; and
- `formal_closure.committed: false` and `r12_authorized: false`.

No batch-3 registry mutation has occurred.

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
