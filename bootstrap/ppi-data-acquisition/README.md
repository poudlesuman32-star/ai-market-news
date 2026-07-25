# PPI Data Acquisition

This public repository is the long-running acquisition execution plane for PPI evidence.

## Operating rule

All provider retrieval, pagination, batching, retries, backoff, rate-limit handling, objective validation, sanitization, hashing, packaging, artifact upload, retention, and failure recovery run here on public GitHub Actions.

The private repository receives one completed immutable artifact and performs only:

- final semantic curation;
- analytical normalization;
- private calculations;
- scoring;
- countability;
- final reporting; and
- a separate short append-only registry-governance review after countability passes.

## Three-repository architecture

### `poudlesuman32-star/ai-market-news`

Public source definitions and reusable code:

- provider/source definitions and allowlists;
- schemas, field maps, adapters, test fixtures, and sanitization rules;
- long source-discovery, source-health, compatibility, and licensing metadata checks;
- versioned reusable collection code and contracts.

### `spoudel2010-ux/ppi-data-acquisition`

Public provider execution:

- provider requests, pagination, batching, retries, and rate-limit handling;
- raw payload capture where licensing permits;
- licensing-safe sanitized representations otherwise;
- deterministic serialization, UTC timestamp representation, stable field ordering, and exact-duplicate removal;
- objective ticker, field, timestamp, future-date, size, status, coverage, and bundle-count checks;
- secret-leak scans, hashes, manifests, receipts, artifacts, and retention;
- all acquisition retries and artifact rebuilding.

### `musksuman3/ai-signal-engine`

Private final analysis only:

1. Verify the exact public repository, workflow, run ID, attempt, head SHA, artifact ID/digest, contract hash, queue receipt, coverage, and freshness.
2. Perform final semantic curation.
3. Perform analytical normalization.
4. Calculate private derived features.
5. Score the cumulative cohort.
6. Determine independent countability.
7. Produce one final private report.
8. Use a separate short review for any append-only registry proposal.

It must not call providers, retry retrieval, rebuild public artifacts, or start broad workflow fan-out.

## Batch-3 scope

Cumulative tickers:

`AAPL, MU, NVDA, AMD, AVGO, INTC, TSM, ARM, QCOM, MRVL, GFS, TXN`

New candidates:

`QCOM, MRVL, GFS, TXN`

Required categories:

- expectation history;
- independent recognition;
- market time series; and
- specialized contract data.

Required public output:

- 48 evidence bundles;
- one cumulative twelve-ticker manifest;
- one immutable collection receipt;
- exact run and artifact identity;
- provider request, retry, failure, timestamp, and hash information;
- maximum evidence age of 168 hours; and
- `authorized_actions: []`.

## Scheduling policy

The initial collector is manual-only. After the manual batch-3 pilot succeeds, reviewed public schedules may be added here. Provider failures and retries remain public.

Private schedules remain paused during migration. Public completion must not automatically start private analysis initially.

## Prohibited authority

This repository may not perform semantic approval, analytical normalization, private feature calculations, scoring, countability, ticker approval, registry mutation, production activation, publication, broker access, orders, trading, MMM/raw-data writes, or R12 authorization.

## Canonical architecture document

The full decision and migration plan is maintained in:

`poudlesuman32-star/ai-market-news/docs/architecture/PPI_THREE_REPOSITORY_ARCHITECTURE_AND_MIGRATION_PLAN.md`
