# PPI SEC 500-Instrument Universe Pilot

## Purpose

This public-only pilot downloads the SEC `company_tickers_exchange.json` bulk file once, validates the frozen column layout, normalizes supported exchanges, and selects exactly 500 provisional universe candidates through deterministic SHA-256 ranking.

## Boundary

The workflow may:

- Fetch exactly `https://www.sec.gov/files/company_tickers_exchange.json`
- Use a declared user agent supplied through the public repository variable `PPI_SEC_USER_AGENT`
- Retry only bounded transient failures
- Produce a normalized candidate snapshot, manifest, receipt and report

The workflow may not:

- Classify a candidate as an accepted common stock or ADR
- Call market-data, news, expectations or options providers
- Use provider secrets
- Access the private repository
- Create deep evidence
- Dispatch private analysis
- Mutate billing, registry, production, publication or trading state

## Required repository variable

Set `PPI_SEC_USER_AGENT` to an application name and monitored contact email, for example:

```text
PPI Universe Research operations@example.com
```

When the variable is missing, the workflow exits safely without network access and publishes a blocked report.

## Output

A successful run retains exactly:

```text
sec-universe-pilot-500.jsonl
manifest.json
receipt.json
report.md
```

The raw SEC payload is not retained. Its SHA-256 and HTTP metadata are recorded in the manifest.

## Identity status

Candidate IDs are provisional SEC-seed identities. Final stable instrument identity is assigned only after identifier mapping and conflict review.
