# PPI public news collectors

This namespace contains the public-only news collection foundation for PPI.

## Implemented in this gate

- Fixture-driven SEC filing collector
- Fixture-driven official company-release collector
- Deterministic SHA-256 record, event, duplicate-group, and source identifiers
- Hardened closed public news-record schema
- Duplicate provider-identity rejection
- HTTPS, ticker, timestamp, and text validation
- Read-only pull-request and manual CI

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

The next gate may add reviewed live adapters and provider-failure handling. Commercial providers remain blocked until endpoint access and redistribution terms are confirmed.
