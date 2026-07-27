# PPI OpenFIGI Mapping Artifact Review Gate

This public-only gate reviews the exact artifact emitted by `PPI OpenFIGI 500-candidate mapping pilot`.

It accepts only two artifact modes:

- `blocked.json` plus `report.md`, producing `gate_passed: false`.
- The exact four-file 500-record success artifact, producing `gate_passed: true` only after all hashes, counts, mapping states, source-run identity, free-tier settings, and authority boundaries pass.

The gate verifies exactly 500 canonical mapping records, exactly 50 unauthenticated OpenFIGI requests, exact/ambiguous/unmatched totals, normalized-response digest, source and mapping snapshot hashes, manifest and contract hashes, and the absence of raw-response retention or private authority.

The output is limited to `review.json` and `review.md` for 14 days.

This contract does not allocate stable instrument IDs. A later allocator must require the exact passing review receipt and re-verify the mapping artifact before assigning any permanent internal identity.
