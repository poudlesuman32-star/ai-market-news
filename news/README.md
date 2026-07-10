# PPI public news pipeline

This namespace contains the public-only news collection, deterministic transformation, and manual preview foundation for PPI.

## Implemented

- Fixture-driven SEC filing collector
- Fixture-driven official company-release collector
- Canonical URL normalization with tracking-parameter removal
- Deterministic cross-provider duplicate grouping
- Stable SHA-256 record, event, duplicate-group, and source identifiers
- Deterministic catalyst tagging
- Deterministic AI-infrastructure-layer tagging
- Hardened closed public news-record schema
- Duplicate provider-identity and duplicate record-ID rejection
- HTTPS, ticker, timestamp, text, synthetic-content, and modified-content validation
- Byte-identical output when source-file order changes
- Manual `workflow_dispatch` preview workflow
- Read-only repository permission for preview
- Three-day preview-artifact retention
- Preview receipt, manifest, run report, and transformed `news.jsonl`

## Manual preview gate

- Required successful runs: 5
- Successful runs currently recorded: 0
- Publication authorized: no
- Repository write permission authorized: no
- Schedule authorized: no
- Provider network calls authorized: no

The preview workflow must complete five reviewed successful runs before immutable publication can be proposed.

## Deduplication hierarchy

1. SEC accession number
2. Matching provider article identity
3. Canonical URL
4. Source hash
5. Normalized headline within the controlled timestamp window
6. Deterministic cross-provider event group

## Intentionally disabled

- Live SEC network collection
- Live investor-relations crawling
- Polygon/Massive news calls
- Finnhub news calls
- Provider credentials
- Schedules
- Public-news publishing
- External repository writes
- Private repository access
- MMM or raw_data access
- Dossier compilation
- Private scoring
- Candidate promotion
- Trading

Commercial providers remain blocked until endpoint access and redistribution terms are confirmed.
