# PPI Three-Repository Architecture and Migration Plan

**Two public repositories perform all long-running work. One private repository performs only the final analytical and acceptance pass.**

**Decision document • Version 1.1 • July 25, 2026**

## Final operating rule

> `ai-market-news` defines and tests public sources and reusable collection code.  
> `ppi-data-acquisition` performs provider retrieval, retries, objective validation, hashing, packaging, and receipts.  
> `ai-signal-engine` performs only final curation, analytical normalization, calculations, scoring, countability, and the short acceptance/registry governance step.

The batch-2 private provider collector is architecture drift. It must not be copied for batch 3 or later batches.

## Repository roles

### 1. `poudlesuman32-star/ai-market-news` — public source intelligence and reusable code

This repository owns source knowledge and reusable public implementation.

Allowed responsibilities:

- Maintain provider and source definitions, endpoints, field maps, category mappings, and source allowlists.
- Maintain public schemas, test fixtures, provider adapters, sanitization rules, and reusable collection libraries.
- Run long source-discovery, public-news retrieval, source-health checks, compatibility tests, and licensing metadata checks.
- Build and test versioned public collection code used by `ppi-data-acquisition`.
- Publish immutable versions, source catalogs, schemas, and compatibility receipts.
- Bootstrap or update `ppi-data-acquisition` through reviewed pull requests while direct connector access is unavailable.

Not allowed:

- Private analytical normalization.
- Proprietary calculations or feature engineering.
- Scoring or countability decisions.
- Ticker approval or private registry mutation.
- Production, broker, order, trading, or R12 authority.

### 2. `spoudel2010-ux/ppi-data-acquisition` — public acquisition execution plane

This repository owns every long-running provider execution task.

Allowed responsibilities:

- Provider API requests, pagination, batching, bounded retries, exponential backoff, timeout handling, and rate-limit handling.
- Retrieval for the complete required ticker cohort and all required evidence categories.
- Raw payload capture where licensing permits.
- Licensing-safe sanitization where raw redistribution is restricted.
- Transport-level canonicalization: deterministic JSON formatting, standard UTC timestamp representation, stable field ordering, and exact-duplicate removal.
- Objective validation: ticker match, required fields, timestamps, future-date rejection, response-size limits, provider status, complete coverage, and bundle counts.
- Secret-leak scans, raw-response hashes, bundle hashes, manifest hashes, and immutable collection receipts.
- Artifact compression, upload, retention, lineage, and public run summaries.
- All provider retries and artifact rebuilding.

Not allowed:

- Semantic evidence curation.
- Analytical normalization or private feature construction.
- Calculations, scoring, countability, ticker approval, or registry mutation.
- Automatic private-repository dispatch during the initial migration.
- Production, broker, order, trading, or R12 authority.

### 3. `musksuman3/ai-signal-engine` — private final analysis only

This repository receives one completed, immutable public artifact.

Its workflow is intentionally short and explicit:

1. Verify the exact public repository, workflow, run ID, attempt, head SHA, artifact ID/digest, contract hash, queue receipt, coverage, and freshness.
2. Perform final semantic curation.
3. Perform analytical normalization and corrections needed for private calculations.
4. Calculate private derived features.
5. Score the cumulative cohort.
6. Determine independent countability.
7. Produce one final private report.
8. After countability passes, use a separate short review to propose an append-only registry update.

The private repository must not:

- Call Alpha Vantage, MarketData, yfinance, news providers, or any other external evidence provider.
- Retry provider requests.
- Rebuild or silently replace a public artifact.
- Perform public source discovery or long acquisition validation.
- Start a cascade of status, observer, reconciliation, and issue-writer workflows.

## Correct data flow

```text
ai-market-news
Public source definitions, schemas, adapters, tests, source health, reusable code
        ↓ versioned public code and contracts
ppi-data-acquisition
Provider retrieval, retries, objective checks, sanitization, hashes, packaging, receipts
        ↓ one immutable public artifact
ai-signal-engine
Identity/freshness gate → final curation → analytical normalization → calculations → scoring → countability
        ↓ separate short governance review
Append-only private registry proposal
```

No missing or stale public evidence may be recollected inside `ai-signal-engine`. The private workflow fails closed and requests a new public acquisition.

## Batch-3 public artifact

The public execution covers all twelve cumulative tickers:

`AAPL, MU, NVDA, AMD, AVGO, INTC, TSM, ARM, QCOM, MRVL, GFS, TXN`

Only these are new batch-3 candidates:

`QCOM, MRVL, GFS, TXN`

Required categories:

- Expectation history
- Independent recognition
- Market time series
- Specialized contract data

Required output:

- 48 evidence bundles
- 1 cumulative twelve-ticker manifest
- 1 immutable collection receipt
- Exact public run identity and artifact digest
- Provider request, retry, and failure counts
- Source and payload hashes where permitted
- Maximum evidence age of 168 hours
- `authorized_actions: []`

## Trigger and scheduling model

### Public repositories

Long-running work may run publicly through reviewed schedules or manual dispatches after the initial pilot.

- `ai-market-news` may schedule source-health and reusable-code compatibility checks.
- `ppi-data-acquisition` may schedule provider acquisition after the manual batch-3 pilot succeeds.
- Public failures and provider retries remain public.
- Public workflows must never expose credentials in logs or artifacts.

### Private repository

- Keep private schedules paused during migration.
- Use one `workflow_dispatch` per exact public artifact.
- Do not use `workflow_run`, issue-comment, broad push, or public-completion triggers for the final analytical workflow.
- Do not automatically trigger the private workflow from a public repository initially.
- Combine the final private stages into one job when security isolation does not require separate jobs.
- Publish private status once at the end.

## Private Actions budget

The account ceiling is 2,000 private minutes per month.

Operating controls:

- Target planned private use: no more than 1,000 minutes per month.
- Warning threshold: 1,200 minutes.
- Keep at least 800 minutes available for failures, PR checks, and emergencies.
- Target one final private batch run at 10–20 minutes.
- Target one focused registry PR validation at 5–10 minutes.
- Never consume private minutes for provider requests, retries, packaging, artifact upload, or source-health monitoring.
- Never blindly rerun a failed private workflow.

## Migration plan

### Phase 1 — freeze and inventory

1. Keep private schedules paused.
2. Inventory every private workflow and script that contacts an external evidence provider.
3. Identify private repository secrets used for provider acquisition.
4. Mark the batch-2 private collector as deprecated architecture drift.

### Phase 2 — complete the public execution plane

5. Complete the reviewed bootstrap of `ppi-data-acquisition`.
6. Merge the manual-only public collector and this architecture document.
7. Store provider credentials only in `ppi-data-acquisition`.
8. Add objective coverage, timestamp, hash, receipt, secret-leak, and artifact-shape validation.
9. Keep provider retries and failure recovery entirely public.

### Phase 3 — define the immutable handoff

10. Freeze the public artifact contract and exact identity fields.
11. Require repository, workflow path, run ID, attempt, head SHA, artifact ID, artifact digest, contract hash, queue receipt, manifest hash, and collection time.
12. Refuse artifacts with missing bundles, stale evidence, identity drift, secret leakage, or unauthorized actions.

### Phase 4 — reduce the private repository

13. Build one manual private artifact-consumer workflow.
14. Remove provider clients and provider-request steps from that workflow.
15. Keep only the identity/freshness preflight, final curation, analytical normalization, calculations, scoring, countability, and final report.
16. Keep the append-only registry proposal as a separate short governance review.
17. Replace multiple status writers with one final publisher.

### Phase 5 — retire private acquisition

18. Disable and then delete or archive private provider-fetch workflows after the public pilot is proven.
19. Remove provider API secrets from `ai-signal-engine` after confirming no active private code uses them.
20. Add a repository test that fails when active private workflow code contains provider domains, provider credential names, or network retrieval commands.

### Phase 6 — controlled batch-3 pilot

21. Run one complete twelve-ticker acquisition in `ppi-data-acquisition`.
22. Review the public artifact before starting private work.
23. Run one private final-analysis workflow using the exact artifact identity.
24. Measure public duration separately from private billed minutes.
25. Run one isolated countability review and one registry proposal.
26. Update MMM only after the authoritative private registry changes.

## Acceptance criteria

The migration is complete only when:

- All long-running source discovery, provider retrieval, retries, validation, hashing, packaging, and artifact retention run in the two public repositories.
- No active private workflow performs external evidence retrieval.
- Provider credentials are absent from `ai-signal-engine`.
- The private workflow accepts only one exact immutable public artifact.
- The private workflow contains only the identity/freshness gate, final curation, analytical normalization, calculations, scoring, countability, and final reporting.
- Evidence collection, private scoring, countability, and registry acceptance remain separate stages.
- One public artifact starts at most one explicitly requested private final-analysis run.
- Monthly private Actions usage stays below 2,000 minutes and normally below 1,000 minutes.
- Production, publication, broker, order, trading, and R12 authority remain disabled.

## Decision summary

All expensive, long-running, retry-heavy, and artifact-building work belongs in `ai-market-news` and `ppi-data-acquisition`. `ai-signal-engine` is reduced to the shortest possible private path: verify one artifact, perform final curation and analytical normalization, calculate, score, determine countability, and complete a separate short acceptance/registry review.
