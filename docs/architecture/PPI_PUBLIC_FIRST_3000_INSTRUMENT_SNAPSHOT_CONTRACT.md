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

A future implementation should preserve the established identity principles:

- deterministic source lineage;
- stable internal IDs only from reviewed exact identity evidence;
- ambiguous and unmatched identities remain deferred;
- classification remains independently reviewable from identity;
- complete content hashes and source-run lineage.

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

## Proposed safe artifact shape

The exact filenames remain subject to implementation review, but the contract should retain only normalized public-safe outputs, for example:

```text
universe-instruments-3000.jsonl
universe-deferred-3000.jsonl
manifest.json
receipt.json
report.md
```

A blocked run should emit only a small diagnostic artifact with no provider payload and no contact/configuration value.

## Review gate

The 3,000-instrument snapshot requires an independent artifact reviewer before canonical step 10 may begin. The reviewer must recalculate counts, uniqueness, hashes, lineage, authority boundaries, and unresolved/deferred preservation from retained normalized artifacts.

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

Provider acquisition must remain manual/operator-controlled during the implementation and pilot phase. Tests and documentation must not trigger network acquisition.

## Test requirements before execution

At minimum, implementation tests must cover:

- exact 3,000-disposition enforcement;
- deterministic ordering;
- duplicate candidate rejection;
- duplicate stable-ID rejection;
- allocated/deferred non-overlap;
- unresolved-classification preservation;
- source-run and artifact-hash binding;
- exact artifact path enforcement;
- blocked-mode behavior;
- prohibition of private dispatch, registry mutation, production publication, and trading authority;
- absence of committed contact values, API keys, or provider credentials.

## Current hold

This contract is safe preparatory work only. Step-9 execution remains held until the exact automatic SEC artifact-review receipt for the live 500-candidate pilot is independently located and verified.
