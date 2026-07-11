# PPI public news pipeline

This namespace contains the public-only collection, deterministic transformation, manual preview, and immutable publication foundation for PPI.

## Implemented

- Fixture-driven SEC filing and official company-release collectors
- Controlled live SEC submissions-metadata adapter using `data.sec.gov`
- Allowlisted official company RSS/Atom adapter
- Declared SEC user agent with contact-email enforcement
- SEC request pacing below the published 10 requests-per-second ceiling
- Retry controls, response-size limits, HTTPS-only access, and redirect-host validation
- Metadata-only SEC records; filing document bodies are not fetched
- Feed-only official-company records; article pages are not fetched
- Per-source failure isolation and explicit request/failure metrics
- Canonical URL normalization with tracking-parameter removal
- Deterministic cross-provider duplicate grouping
- Stable SHA-256 record, event, duplicate-group, and source identifiers
- Deterministic catalyst and AI-infrastructure-layer tagging
- Hardened closed public news-record schema
- Duplicate provider-identity and duplicate record-ID rejection
- HTTPS, ticker, timestamp, text, synthetic-content, and modified-content validation
- Byte-identical output when source-file order changes
- Manual fixture and live-primary-source preview workflows
- Immutable Commit A/B/C publication on the separate `public-news-data` branch

## Live primary-source boundary

The live workflow is `.github/workflows/collect-public-news-live.yml` and remains manual-only with `contents: read`.

Configured SEC companies:

- AAPL — CIK `0000320193`
- MU — CIK `0000723125`
- NVDA — CIK `0001045810`

Active official feeds:

- Apple Newsroom
- NVIDIA Newsroom

Explicitly disabled official feeds:

- Micron Investor Relations — the configured endpoint exhausted all bounded read-timeout retries during reviewed live run `29138091476`. MU remains covered by the allowlisted SEC submissions collector. Re-enabling the feed requires a separate reviewed endpoint-health run with zero failures.

Runtime controls:

- only allowlisted HTTPS hosts;
- no credentials in URLs;
- no commercial news providers;
- no full SEC filing-body download;
- no official article-page download;
- source-provided feed summaries only;
- provider failures remain explicit and make a live preview non-qualifying;
- disabled sources remain explicit and must retain an active reviewed coverage path;
- no repository write, schedule, private-repository access, scoring, promotion, or trading.

A live preview must produce at least one accepted event and zero provider failures before it qualifies for review. It does not publish automatically.

## Deduplication hierarchy

1. SEC accession number
2. Matching provider article identity
3. Canonical URL
4. Source hash
5. Normalized headline within the controlled timestamp window
6. Deterministic cross-provider event group

## Still disabled

- Scheduled live collection
- Automatic live publication
- Polygon/Massive news calls
- Finnhub news calls
- Provider credentials
- External repository writes
- Private repository access
- MMM or `raw_data` access
- Production scoring
- Candidate promotion
- Trading

Commercial providers remain blocked until endpoint access and redistribution terms are confirmed.
