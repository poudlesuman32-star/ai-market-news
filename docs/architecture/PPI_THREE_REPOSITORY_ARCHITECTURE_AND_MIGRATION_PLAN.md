# PPI Three-Repository Architecture and Migration Plan

**Two public repositories for acquisition; one private repository for curation, calculations, scoring, validation, and acceptance**

**Decision document • Version 1.0 • July 25, 2026**

## Final operating rule

> Public repositories fetch, validate, sanitize, hash, package, and prove what was collected.  
> The private repository curates, fixes/normalizes, calculates, scores, validates, decides countability, and proposes registry acceptance.

## Why this document is needed

Your concern is valid. The intended design was public acquisition and private interpretation, but the batch-2 implementation drifted: the private repository installed a provider client, loaded provider credentials, and made provider requests. That mixed acquisition with private analysis and consumed private GitHub Actions minutes.

**Decision:** do not repeat the private batch-2 collection pattern for batch 3 or later batches.

## The three operational repositories

| Repository | Visibility | Primary role |
|---|---|---|
| `poudlesuman32-star/ai-market-news` | Public | Public source intelligence, reusable collector/reference code, source definitions, schemas, and temporary bootstrap control plane. |
| `spoudel2010-ux/ppi-data-acquisition` | Public | Dedicated provider acquisition, retries, raw/sanitized bundles, manifests, receipts, and immutable artifacts. |
| `musksuman3/ai-signal-engine` | Private | Curation, fixing/normalization, calculations, scoring, validation, countability, and append-only registry proposals. |

`jansuman200001-prog/MMM` remains audit/documentation only and is outside the three-repository runtime pipeline.

## Corrected data flow

1. `ai-market-news` maintains reviewed public source definitions, reusable adapters, schemas, and bootstrap/reference code.
2. `ppi-data-acquisition` performs the provider collection on public runners.
3. `ppi-data-acquisition` produces raw or licensing-safe sanitized bundles, a cumulative manifest, and an immutable receipt.
4. No private workflow starts automatically.
5. `ai-signal-engine` verifies exact public artifact identity.
6. `ai-signal-engine` performs curation, normalization, calculations, scoring, and countability validation.
7. Registry acceptance remains a separate, isolated review.

`ai-market-news → ppi-data-acquisition → immutable public artifact → ai-signal-engine`

## Batch-3 contract

- Cumulative tickers: `AAPL, MU, NVDA, AMD, AVGO, INTC, TSM, ARM, QCOM, MRVL, GFS, TXN`
- New candidates: `QCOM, MRVL, GFS, TXN`
- Categories: expectation history, independent recognition, market time series, specialized contract data
- Output: 48 bundles + 1 cumulative manifest + 1 immutable receipt
- Freshness limit: 168 hours

## GitHub Actions cost plan

- Private monthly ceiling: 2,000 minutes
- Planned use: 1,500 minutes
- Reserve: 500 minutes
- Public acquisition and provider retries run in public repositories
- One explicit private orchestrator per accepted public artifact
- Private schedules remain paused during migration
- No blind reruns or broad workflow fan-out

## Migration plan

1. Keep private schedules paused.
2. Complete the `ppi-data-acquisition` bootstrap and review its draft PR.
3. Merge the manual-only public collector.
4. Add provider secrets only to `ppi-data-acquisition`.
5. Run one public batch-3 collection.
6. Implement one manual private artifact consumer in `ai-signal-engine`.
7. Keep only curation, normalization, calculations, scoring, countability, and registry proposal logic in private.
8. Disable and deprecate private provider-fetch workflows.
9. Remove provider API secrets from private after verification.
10. Run one controlled end-to-end trial.
11. Measure private minutes and set a per-batch budget.
12. Update MMM only after the private registry changes.

## Acceptance criteria

- No active private workflow performs provider retrieval.
- Provider credentials are stored in `ppi-data-acquisition`, not `ai-signal-engine`.
- Public artifacts are immutable and fully identified.
- Private workflows fail closed and never recollect.
- One public artifact causes at most one explicit private orchestrator.
- Collection, scoring, countability, and registry acceptance remain separate.
- Private Actions stay below 2,000 minutes per month.
- Production, publication, broker, order, trading, and R12 authority remain disabled.

## Decision summary

The corrected architecture uses two public repositories for source intelligence and provider acquisition, and one private repository for curation, fixing/normalization, calculations, scoring, validation, countability, and registry decisions. The earlier private provider-fetch implementation is architecture drift and will be retired.
