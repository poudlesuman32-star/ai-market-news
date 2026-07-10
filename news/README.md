# PPI public news pipeline

This namespace contains the public-only news collection and deterministic transformation foundation for PPI.

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
- Read-only pull-request and manual CI

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

The next gate should add reviewed live primary-source adapters and a manual preview workflow. Commercial providers remain blocked until endpoint access and redistribution terms are confirmed.
