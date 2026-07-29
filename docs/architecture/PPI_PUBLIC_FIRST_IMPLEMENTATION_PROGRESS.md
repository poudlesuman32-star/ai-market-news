# PPI Public-First Implementation Progress

**Status date:** 2026-07-29  
**Repository:** `poudlesuman32-star/ai-market-news`  
**Architecture reference:** `docs/architecture/PPI_PUBLIC_FIRST_3000_6000_TICKER_EXECUTION_PLAN.md`  
**Tracking issue:** [#104](https://github.com/poudlesuman32-star/ai-market-news/issues/104)

## 1. Executive status

The public-first architecture has advanced from a documentation-only plan to a complete, review-gated 500-candidate public pipeline scaffold.

Installed stages now cover:

```text
Universe foundation validation
        ↓
SEC 500-candidate collection
        ↓
SEC artifact review
        ↓
OpenFIGI identity mapping
        ↓
OpenFIGI artifact review
        ↓
Stable public instrument-ID allocation
        ↓
Stable-ID artifact review
        ↓
Immutable universe snapshot assembly
        ↓
Immutable snapshot artifact review
```

A separate public readiness scheduler now evaluates objective source support for future common-stock versus ADR classification.

The implementation is installed but the live end-to-end chain has not been proven successful. The first external gate remains a monitored SEC contact configured through the non-secret repository variable `PPI_SEC_CONTACT_EMAIL` or an eligible public GitHub profile email.

No successful live SEC 500-candidate artifact, OpenFIGI mapping artifact, stable-ID artifact, or immutable universe snapshot is claimed by this document.

## 2. Architecture boundaries preserved

The implementation continues to enforce the following split.

### Public repositories

Public runners perform universe ingestion, source retrieval, normalization, retries, quota handling, identity mapping, objective validation, artifact hashing, manifests, receipts, deterministic allocation, and operational diagnostics.

### Private repository

`musksuman3/ai-signal-engine` remains limited to one compact final-analysis job for semantic curation, private calculations, final scoring, countability, checkpointing, and final reporting.

The private repository must not discover sources, call providers, hold provider credentials, retry external requests, rebuild public packages, or process the broad 3,000–6,000-instrument universe.

### Prohibited authority

The new public workflows do not authorize:

- automatic private dispatch;
- private provider retrieval;
- billing-budget mutation;
- registry mutation;
- production publication;
- broker or trading actions;
- broad-universe market screening without an approved source contract.

## 3. Merged implementation history

| PR | Merge commit | Implementation result |
|---|---|---|
| [#101](https://github.com/poudlesuman32-star/ai-market-news/pull/101) | `5714ec0c8518821cfe481a5a2ec81dfdf1a64837` | Canonical public-first 3,000–6,000 ticker execution plan. |
| [#102](https://github.com/poudlesuman32-star/ai-market-news/pull/102) | `53ea3931d23290dab1eaa032dd7f3216b11206be` | Public-only universe foundation scheduler, source inventory, foundation contract, schemas, validator, and tests. |
| [#103](https://github.com/poudlesuman32-star/ai-market-news/pull/103) | `fd7eb1fc9e4ca38addd96c089e183232316ca106` | Public SEC bulk-universe pilot for exactly 500 deterministic provisional candidates. |
| [#105](https://github.com/poudlesuman32-star/ai-market-news/pull/105) | `6c8b4439bb19854497a6bf2ff98cee1fdbcf18cd` | Automatic SEC pilot artifact review gate. |
| [#106](https://github.com/poudlesuman32-star/ai-market-news/pull/106) | `4bbc468b9c291f5d6387cd9b659ddd779eedf7e4` | Gate-bound public OpenFIGI mapping pilot for the reviewed 500-candidate snapshot. |
| [#107](https://github.com/poudlesuman32-star/ai-market-news/pull/107) | `92e75e19e632d59b18dc131964280a2beea73b0d` | Automatic OpenFIGI mapping artifact review gate. |
| [#108](https://github.com/poudlesuman32-star/ai-market-news/pull/108) | `86f43ca79ac0e4153a0df42736fc4cf41ad26394` | Deterministic stable public instrument-ID allocation for exact FIGI mappings. |
| [#109](https://github.com/poudlesuman32-star/ai-market-news/pull/109) | `065f81738f17a9ce8e5ba7cb04ce6f2479614c4f` | Automatic stable-ID allocation artifact review gate. |
| [#110](https://github.com/poudlesuman32-star/ai-market-news/pull/110) | `f04fb53dc677cb6ad83837f4b07cb0c51ed66457` | Automated SEC declared-user-agent resolution with fail-closed contact validation. |
| [#111](https://github.com/poudlesuman32-star/ai-market-news/pull/111) | `d32e3666917dfe0dd0aaa9f3cc2a2ceea446266a` | Immutable 500-candidate universe and deferred-disposition snapshot assembler. |
| [#112](https://github.com/poudlesuman32-star/ai-market-news/pull/112) | `00c2186adf5f2436e55c894ab53da024272d2a43` | Automatic immutable universe snapshot artifact review gate. |
| [#113](https://github.com/poudlesuman32-star/ai-market-news/pull/113) | `b21225019f7168e96b78931129d41e0ca80ec2be` | Operational SEC pilot retry with a visible workflow run name; no authority change. |
| [#114](https://github.com/poudlesuman32-star/ai-market-news/pull/114) | `50f9160edfc77bb5648feaf76060b4c6be81bb19` | Public source-readiness gate for objective common-stock versus ADR evidence. |

Issue #104 is the configuration and artifact-review tracker; it is not an implementation pull request.

## 4. Installed workflows

### Foundation

`ppi-public-universe-foundation.yml`

- Runs manually, on relevant `main` changes, and weekly.
- Performs no network requests.
- Validates source inventory, foundation contracts, schemas, and frozen Batch 3 identities.
- Keeps screening blocked until provider and terms approval.

### SEC collection

`ppi-sec-universe-pilot.yml`

- Uses only `https://www.sec.gov/files/company_tickers_exchange.json`.
- Normalizes NYSE, Nasdaq, and NYSE American listings.
- Selects exactly 500 candidates through deterministic SHA-256 ranking.
- Generates provisional candidate identities.
- Retains no raw SEC payload.
- Requires a valid declared SEC user agent.
- Fails closed before SEC access when no monitored contact is resolved.

Successful artifact paths:

```text
sec-universe-pilot-500.jsonl
manifest.json
receipt.json
report.md
```

Candidate state remains:

```text
identity_status       = provisional_sec_seed
classification_status = unresolved
```

### SEC artifact review

`ppi-sec-universe-artifact-review.yml`

- Downloads one exact SEC pilot run artifact.
- Verifies exact paths, 500 canonical records, candidate uniqueness, source identity, and bound hashes.
- Rejects raw-payload retention, unexpected files, tampering, private access, and registry authority.
- Emits only `review.json` and `review.md`.

OpenFIGI may proceed only when the review receipt records:

```json
{
  "gate_passed": true,
  "artifact_mode": "success",
  "candidate_count": 500
}
```

### OpenFIGI mapping

`ppi-openfigi-mapping-pilot.yml`

- Runs only after a passing SEC review receipt.
- Re-downloads and re-verifies the exact SEC artifact.
- Uses the unauthenticated public OpenFIGI mapping endpoint.
- Batches 10 jobs per request for exactly 50 requests.
- Normalizes each candidate to `exact`, `ambiguous`, or `unmatched`.
- Retains no raw OpenFIGI response.

Successful artifact paths:

```text
openfigi-mapping-500.jsonl
manifest.json
receipt.json
report.md
```

### OpenFIGI artifact review

`ppi-openfigi-mapping-artifact-review.yml`

- Verifies exactly 500 mapping records and exactly 50 requests.
- Recalculates mapping state consistency and all snapshot hashes.
- Rejects API-key use, raw-response retention, unexpected paths, and authority expansion.
- Emits only `review.json` and `review.md`.

Stable-ID allocation may proceed only after an exact passing mapping review receipt.

### Stable instrument-ID allocation

`ppi-stable-instrument-id-allocation-pilot.yml`

- Performs zero network requests.
- Allocates IDs only for reviewed exact FIGI mappings.
- Defers ambiguous and unmatched candidates without guessing.
- Rejects duplicate exact FIGIs.
- Does not mutate any registry.

Identity rule:

```text
namespace input:
PPI-STABLE-INSTRUMENT-ID-V1|FIGI|<FIGI>

instrument ID:
ppi-us-equity-<first 24 lowercase hex characters of SHA-256>
```

Disposition rule:

```text
exact       → allocated
ambiguous   → deferred_ambiguous
unmatched   → deferred_unmatched
```

### Stable-ID artifact review

`ppi-stable-instrument-id-allocation-artifact-review.yml`

- Recalculates deterministic IDs.
- Verifies that deferred candidates have no instrument ID.
- Verifies unique IDs, counts, hashes, source-run identity, and zero network use.
- Emits only `review.json` and `review.md`.

### Immutable universe snapshot

`ppi-immutable-universe-snapshot-pilot.yml`

- Runs only after a passing stable-ID review receipt.
- Places allocated exact mappings in `universe-instruments.jsonl`.
- Places ambiguous and unmatched candidates in `universe-deferred.jsonl`.
- Binds SEC, mapping, allocation, instrument, deferred, and combined snapshot hashes.
- Performs zero network requests.
- Does not classify common stock versus ADR.

Allocated records remain:

```text
identity_status       = verified_exact_figi
lifecycle_state       = universe_member
classification_status = unresolved_asset_subtype
```

### Immutable snapshot review

`ppi-immutable-universe-snapshot-artifact-review.yml`

- Verifies the exact success or blocked path set.
- Verifies unique and non-overlapping candidate and instrument identities.
- Requires exactly 500 total candidate dispositions.
- Verifies unresolved asset-subtype preservation and complete hash lineage.
- Emits only `review.json` and `review.md`.

### Asset-classification source readiness

`ppi-asset-classification-source-readiness.yml`

- Performs one allowlisted OpenFIGI `securityType2` enum probe.
- Verifies objective metadata values including `Common Stock` and `Depositary Receipt`.
- Records SEC F-6 and F-6EF as positive ADR evidence only when linked to the exact subject issuer.
- Leaves Nasdaq symbol-directory classification pending terms and semantic approval.
- Classifies zero instruments.

Explicitly prohibited shortcuts:

```text
Security-name substring classification
Ticker-suffix classification
Issuer-country-only classification
Treating absence of F-6 as common-stock proof
```

## 5. Current live status

| Stage | Implementation | Live evidence |
|---|---|---|
| Public-first architecture | Complete | Merged and documented. |
| Universe foundation scheduler | Complete | Installed on `main`; no hosted success assertion is required for downstream live evidence. |
| SEC 500-candidate collector | Complete | Successful live artifact not confirmed. |
| SEC artifact reviewer | Complete | Passing live review receipt not confirmed. |
| OpenFIGI mapper | Complete and held | No live OpenFIGI mapping claimed. |
| OpenFIGI artifact reviewer | Complete and held | No passing live mapping review claimed. |
| Stable-ID allocator | Complete and held | No live stable IDs claimed. |
| Stable-ID reviewer | Complete and held | No passing live stable-ID review claimed. |
| Immutable universe assembler | Complete and held | No live immutable snapshot claimed. |
| Immutable snapshot reviewer | Complete and held | No passing live snapshot review claimed. |
| Asset-classification source readiness | Complete | Source policy installed; zero instruments classified. |
| 3,000-instrument expansion | Not started | Requires proven 500-candidate chain and a new contract. |
| Public screening | Blocked | Provider and terms approval unresolved. |
| Private analysis | Held | Automatic private execution remains disabled. |

## 6. Remaining operator configuration

A monitored SEC contact must be available through one of these paths:

1. non-secret repository variable `PPI_SEC_CONTACT_EMAIL`; or
2. the repository owner's eligible public GitHub profile email.

The variable value must be a real monitored address. It must not be committed into the public repository, placed in workflow outputs, or treated as a password or provider credential.

The workflow constructs:

```text
PPI Universe Research <validated-contact-email>
```

When contact resolution fails, the workflow performs no SEC request and emits a blocked artifact.

## 7. Private execution hold

The private execution hold remains unchanged.

- Recovery run: `30188784601`
- Job: `89758014837`
- Classification: `pre_step_failure_without_runner_assignment`
- Runner assignment: none
- Workflow steps executed: zero
- Automatic private dispatch: disabled
- Billing-budget mutation: prohibited

A private recovery must not be triggered unless billing/account review is complete and the operator provides the exact confirmation:

```text
RECOVER-PPI-PRIVATE-AFTER-BILLING-REVIEW
```

## 8. Frozen Batch 3 preservation

The existing Batch 3 scope remains immutable:

```text
AAPL
MU
NVDA
AMD
AVGO
INTC
TSM
ARM
QCOM
MRVL
GFS
TXN
```

The 500-candidate pilot and future 3,000-instrument contracts do not add tickers to Batch 3 or alter its 50-path handoff contract.

## 9. Validation status

Focused local test suites were reported passing for every implemented unit, including deterministic selection, field-drift rejection, exact path enforcement, source-run binding, tamper detection, request-count validation, duplicate-ID rejection, deferred-record preservation, unresolved-classification preservation, and workflow authority checks.

No GitHub-hosted end-to-end success is asserted here because a complete live artifact chain has not been independently observed and reviewed.

## 10. Next safe execution sequence

1. Configure the non-secret `PPI_SEC_CONTACT_EMAIL` repository variable with a monitored address.
2. Run the SEC 500-candidate pilot.
3. Confirm the exact four-file artifact and passing SEC review receipt.
4. Allow the automatic OpenFIGI, stable-ID, and immutable-snapshot workflow chain to continue.
5. Record the exact run IDs, attempts, artifact IDs, counts, and hashes in issue #104.
6. Review exact, ambiguous, and unmatched mapping rates before expanding scope.
7. Implement an objective asset-classification evidence collector only after a passing immutable-snapshot review.
8. Define a new 3,000-instrument import contract rather than modifying Batch 3 or the frozen 500-candidate pilot.
9. Keep public screening blocked until a legal, free, high-volume source is approved.
10. Keep private execution held until the separate billing-reviewed recovery gate is satisfied.

## 11. Definition of the next milestone

The 500-candidate public foundation milestone is complete only when one live chain produces and verifies:

```text
500 SEC candidate records
        ↓
500 OpenFIGI mapping dispositions
        ↓
500 stable-ID allocation dispositions
        ↓
500 immutable universe/deferred dispositions
        ↓
passing review receipt at every stage
```

Until that evidence exists, the implementation state is **installed and fail-closed**, not live-complete.
