# PPI Immutable Universe Snapshot Artifact Review

This public-only gate reviews one exact immutable universe snapshot artifact.

It verifies:

- exact success or blocked artifact paths;
- all universe and deferred JSONL records;
- unique stable instrument IDs and non-overlapping candidate sets;
- unresolved asset subtype preservation;
- SEC, OpenFIGI, allocation, instrument, deferred, combined, manifest, and receipt hashes;
- exact source workflow run identity;
- zero network requests and no private, screening, deep-evidence, billing, registry, publication, or trading authority.

The reviewer emits only `review.json` and `review.md`. A passing receipt validates the pilot snapshot but does not authorize asset classification, screening, public registry mutation, or private execution.
