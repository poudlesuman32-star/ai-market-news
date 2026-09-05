# PPI Public-First 3,000-Instrument Snapshot Contract

**Status:** Draft; design-only; execution not authorized  
**Canonical backlog:** `docs/architecture/PPI_PUBLIC_FIRST_3000_6000_TICKER_EXECUTION_PLAN.md`, step 9  
**Predecessor:** reviewed 500-instrument public pilot

## Purpose

Define the new contract required by canonical step 9 without modifying frozen Batch 3 or silently expanding the 500-candidate pilot contract.

This document authorizes no provider request or workflow dispatch. Implementation and execution remain gated on independently verified completion of step 8.

## Entry gate

Step-9 execution MUST fail closed unless durable evidence identifies a passing SEC pilot review receipt bound to the exact live 500-candidate source run. The receipt must record at minimum:

- `gate_passed: true`
- `artifact_mode: success`
- `candidate_count: 500`
- exact source run/attempt identity
- exact reviewed artifact identity and hashes

The currently known SEC acquisition evidence alone is not sufficient to execute step 9 until that review receipt is independently verified.

Implementation work that performs zero provider/network acquisition MAY proceed before the receipt is located. Such work is limited to contracts, schemas, validators, deterministic transformations over fixtures, artifact reviewers, workflow authority checks, and tests. No implementation branch may make step-9 provider acquisition automatic.

## Scope

The step-9 snapshot is a new immutable public-universe contract targeting exactly 3,000 candidate dispositions. It MUST NOT:

- alter the frozen Batch 3 ticker set or its handoff contract;
- mutate the existing 500-candidate pilot contract;
- infer common-stock versus ADR status from names, ticker suffixes, issuer country, or absence of F-6 evidence;
- require private-repository provider access;
- mutate any instrument registry;
- publish production output;
- dispatch private recovery;
- change billing or quota authority;
- enable broker, order, or trading authority.

## Required record states

Every candidate must have a deterministic public identity/disposition and explicit classification state. Unresolved identity or subtype evidence must remain unresolved or deferred rather than guessed.

The implementation MUST preserve the established identity principles:

- deterministic source lineage;
- stable internal IDs only from reviewed exact identity evidence;
- ambiguous and unmatched identities remain deferred;
- classification remains independently reviewable from identity;
- complete content hashes and source-run lineage.

The step-9 contract does not redefine the stable-instrument-ID namespace or algorithm. Existing reviewed stable-ID rules remain authoritative; expansion code must reuse them rather than introduce a 3,000-specific identity scheme.

## Snapshot invariants

A successful step-9 artifact MUST demonstrate:

1. exactly 3,000 total candidate dispositions;
2. deterministic ordering and reproducibility from the same approved inputs;
3. no duplicate candidate identities;
4. no duplicate stable instrument IDs among allocated records;
5. allocated and deferred sets are non-overlapping;
6. every record carries source lineage and explicit identity/classification status;
7. unresolved asset subtype remains explicit where objective evidence is insufficient;
8. exact path allowlisting;
9. SHA-256 binding for each retained data file plus a combined snapshot hash;
10. zero raw provider-response retention unless a separately reviewed source contract explicitly permits it.

## Artifact contract

Before executable workflow code is accepted, the implementation PR MUST freeze the exact success and blocked path sets. Placeholder filenames in this design document are not execution authority.

The intended normalized success shape is:

```text
universe-instruments-3000.jsonl
universe-deferred-3000.jsonl
manifest.json
receipt.json
report.md
```

The implementation contract must define canonical JSON/JSONL serialization, ordering keys, line-ending rules, per-file SHA-256 calculation, and the combined-snapshot hash algorithm so an independent reviewer can reproduce every digest without network access.

A blocked run must emit only its separately allowlisted diagnostic paths, with no provider payload, contact/configuration value, API key, credential, or partial success snapshot.

## Review gate

The 3,000-instrument snapshot requires an independent artifact reviewer before canonical step 10 may begin. The reviewer must recalculate counts, uniqueness, hashes, lineage, authority boundaries, and unresolved/deferred preservation from retained normalized artifacts.

The reviewer MUST be capable of running with network access disabled and MUST NOT trust producer-computed counts or hashes without recalculation.

A successful receipt should explicitly bind:

```json
{
  "gate_passed": true,
  "artifact_mode": "success",
  "total_candidate_dispositions": 3000
}
```

No later screening-source work may claim step-9 completion from implementation scaffolding alone.

## Source and network policy

Implementation must use only sources already approved for the intended operation or introduce a separately reviewed source-inventory disposition before network use. Free access is not equivalent to unlimited or approved access.

Provider acquisition must remain manual/operator-controlled during the implementation and pilot phase. Tests and documentation must not trigger network acquisition. A workflow may not be scheduled, chained from another workflow, or otherwise made automatically provider-active merely because the step-9 contract is implemented.

## Required implementation split

The safe implementation should remain separable into these authority layers:

1. **Pure contract/schema layer** — zero network, no repository mutation.
2. **Deterministic validator/assembler layer** — consumes only explicitly supplied normalized inputs; zero provider acquisition.
3. **Independent reviewer layer** — recalculates paths, counts, identity invariants, hashes, and lineage; zero provider acquisition.
4. **Acquisition adapter** — separate manual/operator-controlled authority, held until step 8 is independently proven and source approval is confirmed.

Tests for layers 1–3 may proceed now. Layer 4 execution may not.

## Test requirements before execution

At minimum, implementation tests must cover:

- exact 3,000-disposition enforcement;
- deterministic ordering and byte-for-byte reproducibility;
- duplicate candidate rejection;
- duplicate stable-ID rejection;
- allocated/deferred non-overlap;
- unresolved-classification preservation;
- rejection of guessed classification shortcuts;
- source-run and artifact-hash binding;
- independent recomputation of all retained hashes;
- exact success artifact path enforcement;
- exact blocked artifact path enforcement;
- rejection of unexpected and raw-provider paths;
- blocked-mode behavior without partial success output;
- zero-network behavior for validator/assembler/reviewer tests;
- reuse of the existing stable-ID rule rather than a new namespace;
- prohibition of automatic provider dispatch;
- prohibition of private dispatch, registry mutation, production publication, billing mutation, and trading authority;
- absence of committed contact values, API keys, or provider credentials.

## Implementation acceptance gate

A step-9 implementation PR is not execution approval. Before any live 3,000-instrument run, review must establish all of the following:

1. the exact step-8 review receipt has been independently verified;
2. source inventory dispositions cover every intended network operation;
3. schemas and exact artifact paths are frozen;
4. validator/assembler/reviewer tests pass without network access;
5. the live workflow remains manual/operator-controlled;
6. no private, billing, registry, publication, production, broker, order, or trading authority was added.

## Current hold

This contract is safe preparatory work only. Step-9 execution remains held until the exact automatic SEC artifact-review receipt for the live 500-candidate pilot is independently located and verified.
