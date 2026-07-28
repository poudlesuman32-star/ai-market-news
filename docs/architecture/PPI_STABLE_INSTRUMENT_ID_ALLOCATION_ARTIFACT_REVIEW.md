# PPI Stable Instrument ID Allocation Artifact Review

This public-only gate reviews one exact stable instrument ID allocation artifact.

It verifies:

- exactly 500 canonical allocation records;
- deterministic FIGI-derived IDs for every allocated record;
- no IDs for ambiguous or unmatched records;
- unique candidate, listing, and allocated instrument identities;
- exact allocation, manifest, receipt, and report hashes;
- zero network requests and no private or registry authority.

The review emits only `review.json` and `review.md`. It does not assemble a universe snapshot or authorize screening, deep evidence, private execution, registry mutation, publication, or trading.
