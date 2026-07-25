# PPI Three-Repository Architecture, Trust Boundary, and Migration Plan

**Two public repositories perform all long-running, retry-heavy, network-dependent, validation-heavy, and artifact-building work. The private repository performs only the final analytical and governance pass.**

**Decision document • Version 1.2 • July 25, 2026**

## Status and operating rule

**Architecture status:** approved.  
**Implementation status:** blocked until the no-go checklist in this document is satisfied.

> `poudlesuman32-star/ai-market-news` owns public source intelligence, schemas, reusable collector code, compatibility checks, and versioned public contracts.  
> `spoudel2010-ux/ppi-data-acquisition` owns provider execution, retries, objective validation, sanitization, hashing, packaging, receipts, attestations, and artifact retention.  
> `musksuman3/ai-signal-engine` receives one completed public artifact and performs only exact-artifact verification, final semantic curation, analytical normalization, private calculations, scoring, independent countability, final reporting, and a separate short registry-governance review.

The batch-2 private provider collector is architecture drift. It must not be copied for batch 3 or later batches.

The open private batch-3 evidence-path PR that contains provider collection must not be merged in its current form. It must be closed or replaced by a private artifact-consumer implementation.

## Stable repository identities

Trust decisions bind both repository names and numeric repository IDs so a rename cannot silently change the boundary.

| Repository | Repository ID | Visibility | Role |
|---|---:|---|---|
| `poudlesuman32-star/ai-market-news` | `1290414659` | Public | Source intelligence, reusable code, schemas, source health, licensing policy, and public collector releases |
| `spoudel2010-ux/ppi-data-acquisition` | `1312286476` | Public | Provider execution, retries, objective checks, packaging, receipts, attestations, and public artifacts |
| `musksuman3/ai-signal-engine` | `1290626648` | Private | Final curation, analytical normalization, calculations, scoring, countability, reporting, and registry governance |

`jansuman200001-prog/MMM` remains an audit/documentation repository outside the three-repository runtime pipeline. It may receive sanitized status only after the authoritative private registry changes.

## Repository responsibilities

### 1. `poudlesuman32-star/ai-market-news` — public source intelligence and reusable code

This repository owns public source knowledge and reusable implementation.

Allowed responsibilities:

- Maintain provider and source definitions, endpoint maps, field maps, ticker aliases, category mappings, and source allowlists.
- Maintain schemas, test fixtures, provider adapters, transport rules, sanitization policies, and licensing classifications.
- Run long source discovery, public-news retrieval, source-health checks, compatibility tests, and licensing metadata checks.
- Publish versioned collector releases, source catalogs, schemas, and compatibility receipts.
- Bootstrap or update `ppi-data-acquisition` through reviewed pull requests while direct connector access is unavailable.
- Define which public payload fields may be retained, sanitized, hashed only, encrypted, or prohibited from public storage.

Not allowed:

- Final semantic evidence approval.
- Private analytical normalization or proprietary feature engineering.
- Scoring, countability, ticker approval, or registry mutation.
- Production, publication, broker, order, trading, MMM/raw-data, or R12 authority.

### 2. `spoudel2010-ux/ppi-data-acquisition` — public acquisition execution plane

This repository owns every expensive provider-execution task.

Allowed responsibilities:

- Provider API requests, pagination, batching, bounded retries, exponential backoff with jitter, timeout handling, and rate-limit handling.
- Retrieval for the complete frozen ticker cohort and every required evidence category.
- Resumable or sharded collection so one transient failure does not require repeating all successful requests.
- Raw payload retention only when the provider policy explicitly permits public redistribution.
- Licensing-safe sanitization, hash-and-metadata-only evidence, or encrypted handoff when raw public retention is not permitted.
- Transport-level canonicalization: deterministic JSON, stable field ordering, canonical UTC timestamps, and exact-duplicate removal.
- Objective category-specific validation, coverage checks, future-date rejection, response-size limits, and provider-status checks.
- Credential-leak scanning, response hashes, bundle hashes, manifest hashes, package hashes, immutable receipts, and artifact attestations.
- Separate success and failure artifacts, artifact compression, retention, cleanup, lineage, and public run summaries.
- Every recollection, provider retry, and public artifact rebuild.

Not allowed:

- Final semantic evidence curation.
- Analytical normalization or private feature construction.
- Calculations, scoring, countability, ticker approval, or registry mutation.
- Automatic private-repository dispatch during the migration and pilot.
- Production, publication, broker, order, trading, MMM/raw-data, or R12 authority.

### 3. `musksuman3/ai-signal-engine` — private final analysis only

The private repository receives one completed, immutable public artifact.

Allowed private stages:

1. Materialize exactly one public artifact and verify its provenance.
2. Safely extract it and verify its exact manifest and file hashes.
3. Perform final semantic curation.
4. Perform analytical normalization and corrections required for private calculations.
5. Calculate private derived features.
6. Score the cumulative cohort.
7. Perform independent countability validation.
8. Produce one final private report.
9. After countability passes, use a separate short governance review for an append-only registry proposal.

The private repository must not:

- Call Alpha Vantage, MarketData, Yahoo Finance, yfinance, news providers, or any other external evidence provider.
- Retry provider requests or silently substitute a different provider.
- Recollect stale, missing, incomplete, or invalid evidence.
- Rebuild, repair, or silently replace a public artifact.
- Run public source discovery or long public acquisition validation.
- Perform long packaging or public artifact retention.
- Start a cascade of workflow-run, issue-comment, observer, reconciliation, and issue-writer workflows.
- Grant production, publication, broker, order, trading, MMM/raw-data, or R12 authority.

## Correct data flow

```text
ai-market-news
Public source definitions, licensing policy, schemas, adapters, tests, source health,
and versioned collector releases
        ↓ immutable public code release and contract identity
ppi-data-acquisition
Provider retrieval, retries, objective validation, sanitization, hashes,
50-path success package, receipt, attestation, and public artifact
        ↓ one explicitly selected immutable artifact
ai-signal-engine
Trust gate → safe extraction → final curation → analytical normalization
→ private calculations → scoring → independent countability → final report
        ↓ separate short governance review
Append-only private registry proposal
```

No missing or stale public evidence may be recollected inside `ai-signal-engine`. The private workflow fails closed and requests a new public acquisition.

## Frozen contract lineage

Use one explicit versioned lineage. Do not mix unversioned and `-R1` identities.

- Private analytical contract: `PPI-R11-BATCH-EVIDENCE-003-R1`
- Public acquisition contract: `PPI-R11-PUBLIC-ACQUISITION-003-R1`
- Public collector release: `PPI-PUBLIC-COLLECTOR-003-R1`

Each contract must include:

- Its own SHA-256.
- The exact SHA-256 of every upstream contract it depends on.
- The exact public collector release commit SHA and release digest.
- The stable repository IDs and expected workflow path.
- The queue receipt SHA-256.
- `authorized_actions: []`.
- Explicit false values for private dispatch, registry mutation, production, publication, broker, order, trading, MMM/raw-data, and R12 authority.

Changing a contract, schema, collector release, ticker cohort, category definition, or provider operation requires a new revision. Existing receipts are never rewritten.

## Batch-3 public acquisition scope

Cumulative tickers:

`AAPL, MU, NVDA, AMD, AVGO, INTC, TSM, ARM, QCOM, MRVL, GFS, TXN`

New batch-3 candidates:

`QCOM, MRVL, GFS, TXN`

Required categories:

- Expectation history
- Independent recognition
- Market time series
- Specialized contract data

All twelve tickers require fresh current-batch evidence. Historical accepted evidence remains immutable, but it does not replace fresh cumulative scoring input.

## Exact public success package

A successful batch-3 package contains exactly 50 retained paths:

- 48 evidence bundles
- 1 cumulative twelve-ticker manifest
- 1 immutable collection receipt

No optional retained paths are permitted in the success package. A request or dispatch correlation ID belongs inside the collection receipt rather than in a fifty-first file.

The success receipt binds:

- Source repository name and numeric ID
- Workflow path
- Workflow run ID and run attempt
- Workflow event
- Head branch and head SHA
- Artifact ID, artifact name, and artifact digest
- Package SHA-256
- Collector release ID, commit SHA, and digest
- Public acquisition contract ID and SHA-256
- Private analytical contract ID and SHA-256
- Queue receipt SHA-256
- Manifest path and SHA-256
- Collection start and completion times
- Per-request start, response, and provider-event timestamps
- Provider request, retry, transient-failure, permanent-failure, and valid-empty counts
- Bundle count and exact path count
- Licensing disposition for every bundle
- `authorized_actions: []`

## Provider licensing and public-storage policy

Every provider operation must have one frozen disposition before collection:

- `raw_public_allowed`
- `sanitized_public_allowed`
- `hash_and_metadata_only`
- `encrypted_private_handoff`
- `public_storage_prohibited`

A public workflow must not upload a raw payload merely because it was successfully fetched.

For every bundle, the manifest records:

- Provider and operation
- Licensing disposition
- Whether source content was modified
- Whether a raw payload is present
- Raw response hash when permitted to compute it
- Sanitized bundle hash
- Fields removed or transformed
- Encryption identity when encrypted handoff is used
- Retention class

If a provider's terms do not support the required transfer model, the run fails closed or the provider must be replaced through a reviewed contract revision.

## Objective public validation

Public validation is deterministic and must not decide semantic approval or countability.

### Expectation history

Require:

- Exact ticker match
- Nonempty supported estimate periods or a frozen valid-empty status
- Provider dates and retrieval timestamps
- Numeric estimate fields where required
- No future provider-event dates
- Stable operation and schema versions

### Independent recognition

Require:

- Exact ticker or reviewed alias fields
- Canonical source URL and source domain
- Article or recognition timestamp
- No official-company domain counting as independent
- Deterministic duplicate identity
- Frozen valid-empty status distinct from provider failure

### Market time series

Require:

- Exact ticker match
- Ordered unique trading dates
- Minimum required history
- Numeric OHLC and volume fields
- OHLC consistency checks
- No future bars or duplicate dates
- Explicit split-adjustment policy

### Specialized contract data

Require:

- Exact underlying ticker
- Contract type, expiration, strike, and quote timestamp
- Numeric quote/open-interest fields where required
- No expired or future-impossible timestamps
- Frozen valid-empty status distinct from provider failure

## Public retry, sharding, and failure rules

The preferred collection shape is three four-ticker shards followed by one public aggregator:

- Shard 1: `AAPL, MU, NVDA, AMD`
- Shard 2: `AVGO, INTC, TSM, ARM`
- Shard 3: `QCOM, MRVL, GFS, TXN`
- Aggregator: verify all 48 bundles and create the exact success package

Retry rules:

- Retry only transient network failures, HTTP 429, and reviewed provider 5xx responses.
- Honor `Retry-After`.
- Use bounded exponential backoff with jitter.
- Enforce provider-specific request limits and a maximum elapsed retry time.
- Never retry deterministic schema, licensing, contract, ticker, or authorization failures.
- Never silently substitute a provider.
- Bind every retry to the same contract revision and request identity.

A failed or partial collection produces a separately named failure-diagnostics artifact. It must never use the success artifact name and can never enter the private analysis gate.

## Public workflow security

Provider-bearing public jobs must:

- Run only from the protected default branch or an explicitly approved immutable tag.
- Check out the exact approved ref with persisted credentials disabled.
- Use a protected GitHub environment for provider credentials when available.
- Prevent the initiator from self-approving the protected environment when a second reviewer is available.
- Expose no provider credentials to pull-request jobs.
- Pin third-party actions to full commit SHAs.
- Use least-privilege workflow permissions.
- Scan logs and retained files for exact secrets, authorization headers, query-string credentials, and common encoded forms.
- Rotate or remove the temporary cross-repository bootstrap token after the target repository is established.

Public standard GitHub-hosted runners may be used for this work. Larger runners are not authorized unless separately budgeted.

## Artifact integrity and extraction safety

The public acquisition repository must generate a provenance attestation for the final package when supported.

Before private extraction, verify:

- Repository name and numeric ID
- Workflow path and approved event
- Head repository ID, head branch, and head SHA
- Completed/success conclusion
- Run ID and attempt
- Exact artifact name, ID, and digest
- Package SHA-256 and attestation
- Contract and collector release identities
- Exact 50-path package shape
- Maximum compressed and uncompressed sizes

Safe extraction rejects:

- Absolute paths
- `..` path traversal
- Symbolic links and hard links
- Duplicate archive entries
- Unexpected paths
- Excessive file count
- Excessive expansion ratio
- Files exceeding category-specific limits

After extraction, every file hash is revalidated against the manifest.

## Private trust gate and no-network analysis

The private workflow has two controlled stages.

### Stage A — artifact materialization

Allowed network surface:

- GitHub API access required to resolve and download the exact public artifact and attestation

Required controls:

- Minimal read-only token
- Exact identity verification
- Safe extraction
- Read-only validated input directory
- Deterministic handoff receipt

### Stage B — final private analysis

Required controls:

- No provider credentials
- No GitHub token
- No external network
- Read-only input mount
- Write access only to a bounded runtime output directory
- One job or one tightly controlled container invocation
- One final status publication after completion

The private no-provider rule must be enforced by runtime isolation in addition to source scanning. Source scanning remains a defense-in-depth control, not the primary boundary.

## Freshness, empty results, and atomic credit

Maximum evidence age remains 168 hours.

Freshness is evaluated from the relevant provider-event and response timestamps, not only from one workflow-wide `observed_at` value.

Frozen dispositions:

| Scenario | Disposition |
|---|---|
| One of 48 bundles missing or invalid | No private run |
| One provider operation returns reviewed valid-empty data | Apply the frozen category valid-empty rule |
| Provider failure is mistaken for valid-empty | Reject |
| One new ticker fails final curation or countability | No batch-3 registry credit |
| A prior approved ticker fails the current cumulative score | Batch 3 does not count; prior historical approval remains unchanged |
| Three of four new tickers pass | No partial credit under revision R1 |
| Same artifact and analysis identity are submitted twice | Deterministic no-op |
| Analysis code or configuration changes | New private analysis identity required |

Batch-3 credit is atomic for `QCOM, MRVL, GFS, TXN`. Partial-batch credit requires a new frozen contract revision.

## Duplicate-credit and registry-race protection

A unique countability identity includes:

- Public artifact digest
- Private analysis code SHA
- Private configuration hash
- Contract revision
- Batch sequence

Before analysis, capture the registry base SHA and current accepted counts.

Before proposing a registry change:

- Verify the registry base SHA has not changed.
- Verify no existing registry entry uses the same countability identity.
- Verify the current approved ticker count and accepted batch count still match the analysis precondition.
- Produce a one-file append-only registry diff.
- Require a nonempty human review.
- Never auto-merge the registry proposal.

## Trigger and scheduling policy

### Initial pilot

- `ppi-data-acquisition` remains manual-only.
- Public completion does not automatically start private analysis.
- Private schedules remain paused.
- One explicit private `workflow_dispatch` accepts one exact public artifact.
- The private workflow publishes status once at completion.
- Evidence acceptance, scoring, countability, and registry acceptance remain separate gates.

### After the pilot

Reviewed public schedules may be added only after:

- Licensing policy is frozen.
- Success and failure artifacts are separated.
- Retry and sharding behavior is proven.
- Artifact storage limits and cleanup are enforced.
- The private trust gate is proven fail-closed.
- The private monthly budget remains protected.

Private R11 analysis remains explicit and non-fan-out unless a later contract separately authorizes a controlled trigger.

## GitHub Actions and storage budget

Standard GitHub-hosted runners in public repositories are used for long-running public work. Private repositories consume the account's included private minutes.

Private operating limits:

- Hard ceiling: 2,000 minutes per month
- Planned use: no more than 1,000 minutes
- Warning threshold: 1,200 minutes
- Reserve: at least 800 minutes
- Final private batch analysis target: 10–20 minutes
- Focused registry validation target: 5–10 minutes

Private minutes must never be spent on provider retrieval, provider retries, public source monitoring, public packaging, or public artifact upload.

Artifact controls:

- Define maximum compressed and uncompressed package sizes.
- Use short retention for failure diagnostics.
- Retain successful candidates only as long as required for private review.
- Move authoritative accepted receipts or packages to an approved durable archive before public artifact expiration when long-term preservation is required.
- Delete superseded public artifacts after their frozen retention and audit obligations are satisfied.

## Migration gates

### Gate 0 — stop contradictory private implementation

1. Keep private Actions and schedules paused.
2. Do not merge the current private provider-backed batch-3 evidence-path PR.
3. Close it or replace it with an artifact-consumer-only implementation.
4. Mark every private provider-fetch workflow and script as deprecated architecture drift.
5. Inventory every private trigger, not only provider calls.

### Gate 1 — freeze public source intelligence

6. Freeze licensing dispositions for each provider operation.
7. Publish the versioned source catalog, schemas, adapters, and collector release.
8. Record the collector release commit SHA and digest.
9. Pin third-party actions to immutable full commit SHAs.

### Gate 2 — complete the public execution plane

10. Update and merge `ppi-data-acquisition` PR #1 only after it contains the hardened README and current contract lineage.
11. Add protected provider environment controls.
12. Add category-specific objective schemas and timestamp checks.
13. Implement sharded/resumable collection and bounded retries.
14. Separate success artifacts from failure diagnostics.
15. Generate the exact 50-path package, package digest, receipt, and attestation.
16. Enforce package size, storage, retention, and cleanup limits.

### Gate 3 — freeze the immutable handoff

17. Bind repository IDs, workflow path, run identity, head SHA, artifact identity, package digest, attestation, collector release, contracts, queue receipt, manifest, and timestamps.
18. Reject stale, partial, mismatched, unauthorized, unlicensed, or unverified artifacts.
19. Freeze the valid-empty and atomic-credit policies.

### Gate 4 — build the shortest private path

20. Build one manual artifact-consumer workflow.
21. Split artifact materialization from network-disabled analysis.
22. Remove provider clients, credentials, provider retries, and public packaging from the private path.
23. Keep only final curation, analytical normalization, calculations, scoring, countability, and one final report.
24. Keep registry governance separate and short.
25. Replace R11 status fan-out with one final publisher.

### Gate 5 — controlled batch-3 pilot

26. Run one complete fresh twelve-ticker public acquisition.
27. Verify the exact success artifact and its attestation.
28. Run one network-disabled private final-analysis job.
29. Measure actual private billed minutes.
30. Run independent countability.
31. Propose one append-only registry change.
32. Update MMM only after the authoritative registry change is reviewed and merged.

### Gate 6 — decommission private acquisition

33. Disable and archive obsolete private provider-fetch workflows.
34. Remove provider credentials from `ai-signal-engine`.
35. Add repository tests that reject active private provider domains, credential names, retrieval commands, and prohibited triggers.
36. Confirm no R11 event causes private workflow fan-out.
37. Rotate or delete temporary bootstrap credentials.

## No-go checklist

Do not start private batch-3 analysis until all items are true:

- [ ] Private provider-backed PR #217 is closed or superseded.
- [ ] Private architecture PR #218 contains this validated Version 1.2 plan.
- [ ] `ppi-data-acquisition` PR #1 contains the hardened acquisition README.
- [ ] `ppi-data-acquisition/main` is the authoritative public execution plane.
- [ ] Contract lineage uses only the frozen `-R1` identities.
- [ ] Collector release identity is immutable and pinned.
- [ ] Provider licensing and public-storage dispositions are frozen.
- [ ] All twelve tickers receive fresh current-batch evidence.
- [ ] Exact success package shape is 50 paths with no optional files.
- [ ] Category-specific public schemas and per-request timestamps are enforced.
- [ ] Success and failure artifacts have different identities.
- [ ] Retry, sharding, rate-limit, and valid-empty policies are frozen.
- [ ] Provider-bearing jobs are restricted to protected approved refs.
- [ ] Third-party actions are pinned to full commit SHAs.
- [ ] Package size, retention, cleanup, and durable-archive rules are defined.
- [ ] Package attestation is generated and verified.
- [ ] Private extraction rejects archive attacks and unexpected paths.
- [ ] Private final analysis runs without provider credentials or external network.
- [ ] Duplicate-credit and registry-race controls are enforced.
- [ ] Batch-3 credit is atomic under revision R1.
- [ ] One public artifact starts at most one explicit private final-analysis run.
- [ ] Private R11 status is published once, without broad fan-out.
- [ ] Production, publication, broker, order, trading, MMM/raw-data, and R12 authority remain disabled.

## Acceptance criteria

The migration is complete only when:

- Every long-running source-discovery, provider-retrieval, retry, objective-validation, sanitization, hash, package, attestation, retention, and recovery task runs in the two public repositories.
- No active private workflow performs external evidence retrieval or public artifact rebuilding.
- Provider credentials are absent from `ai-signal-engine`.
- The private workflow accepts only one exact immutable and attested public artifact.
- The private final-analysis stage has no provider credentials, GitHub token, or external network.
- Evidence collection, evidence acceptance, scoring, countability, and registry acceptance remain separate stages.
- One public artifact starts at most one explicitly requested private run.
- Duplicate credit and registry races fail closed.
- Monthly private Actions usage remains below 2,000 minutes and normally below 1,000 minutes.
- Production, publication, broker, order, trading, MMM/raw-data, and R12 authority remain disabled.

## Decision summary

All expensive, long-running, retry-heavy, network-dependent, objective-validation, sanitization, hashing, packaging, attestation, retention, and artifact-recovery work belongs in `ai-market-news` and `ppi-data-acquisition`.

`ai-signal-engine` is reduced to the shortest possible private path: verify one immutable public artifact, safely extract it, perform final curation and analytical normalization, calculate, score, determine countability, produce one final report, and complete a separate short registry-governance review.
