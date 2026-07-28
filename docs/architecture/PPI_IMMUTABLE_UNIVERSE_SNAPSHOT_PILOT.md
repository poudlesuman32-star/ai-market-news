# PPI Immutable 500-Candidate Universe Snapshot Pilot

This public-only workflow assembles the first immutable universe snapshot from one exact, reviewed stable-instrument-ID allocation artifact.

It creates:

- `universe-instruments.jsonl` for exact FIGI mappings with permanent public IDs;
- `universe-deferred.jsonl` for ambiguous and unmatched candidates;
- `manifest.json` with SEC, OpenFIGI, allocation, and snapshot hashes;
- `receipt.json` with exact run lineage and authority boundaries;
- `report.md` with public-safe counts.

Allocated records remain `classification_status: unresolved_asset_subtype`; the workflow does not guess common-stock versus ADR classification. Deferred candidates receive no instrument ID.

The workflow performs zero provider requests, uses no secrets, accesses no private repository, performs no screening or deep evidence, and does not mutate a registry. It is held until the stable-ID allocation artifact review returns `gate_passed: true`.
