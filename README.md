# AI Market News — Public Market Data Collector

This repository is the public, auditable market-data collection layer for Iteration 16.

Its scope is intentionally narrow: collect, validate, and eventually publish corporate-action-adjusted daily market data under a frozen public contract.

Private MMM code, scoring logic, portfolio information, credentials, private provider responses, and evaluation outputs must never be copied into this repository.

## Current status

**Iteration 0 — repository foundation only**

This foundation intentionally contains:

- no scheduled GitHub Actions workflows;
- no API secrets;
- no market-data network calls;
- no automatic publishing;
- no access to MMM or `raw_data`;
- no private scoring rules or portfolio information.

## Repository layout

```text
.github/workflows/   Future public workflows; empty during Iteration 0
config/              Future frozen public collection configuration
schemas/             Future public schemas and data contracts
scripts/             Future collector, manifest, and validation tools
tests/               Future deterministic tests and fixtures
data/latest/         Future pointer to the latest validated public snapshot
data/archive/        Future immutable validated snapshots
```

Git does not track empty directories, so `.gitkeep` placeholders are included until implementation files are added.

## Trust boundary

This repository is a one-way public producer. A separate private MMM consumer may later read immutable, validated artifacts from this repository. This public repository must never read from, authenticate to, or receive private code or data from MMM.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the architecture and safety rules.

## License

Licensed under the MIT License. See [LICENSE](LICENSE).
