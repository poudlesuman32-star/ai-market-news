# PPI Migration Autopilot

The autopilot converts the validated Version 1.2 architecture into an idempotent, fail-closed reconciliation loop. It runs without human dispatch and performs only the next machine-verifiable action.

## Schedule

The workflow runs every hour at minute `23` and may also be dispatched manually for diagnostics. Normal operation requires no manual run, task advancement, pull-request merge, or public collection dispatch.

## Autonomous actions

The autopilot may:

- verify the exact source, acquisition, and private repository names and numeric IDs;
- verify that `RAW_TOKEN` has write access to the acquisition and private repositories;
- rerun the reviewed acquisition bootstrap idempotently;
- synchronize `PPI_PRIVATE_HANDOFF_TOKEN` into the acquisition repository;
- synchronize provider credentials when they are configured in `ai-market-news`;
- keep target PR #1 current;
- mark and merge target PR #1 only after all machine-verifiable hardening gates pass;
- dispatch one bounded public collection when no active or recent successful run exists;
- dispatch the private final-analysis workflow only after it exists and an eligible public success run is available.

## Fail-closed rules

The autopilot stops and reports a blocked reason when:

- a repository name, ID, visibility, archive state, or permission drifts;
- required secrets are absent or cannot be synchronized;
- target PR #1 lacks the hardened licensing, contract, validation, handoff, action-pinning, success/failure, or exact-package controls;
- the public retry ceiling is reached;
- the private final-analysis workflow is not installed;
- any expected workflow, branch, contract, or release identity is missing.

A blocked run exits without production, publication, registry, broker, order, trading, MMM/raw-data, or R12 authority.

## Task sequence

| Task | Description | Advancement rule |
|---|---|---|
| `T01` | Synchronize and verify public acquisition bootstrap | Derived from repository and PR state |
| `T02` | Freeze provider licensing and non-public payload handoff | Required files and markers must exist |
| `T03` | Freeze R1 contracts and collector release | Exact contract identities and hashes |
| `T04` | Enforce category-specific public validation | Validator files and tests must pass |
| `T05` | Enforce bounded retries, resume, and retry ceilings | Collector and workflow controls must pass |
| `T06` | Separate public receipts from private evidence packages | Success/failure identities and 50-path rule |
| `T07` | Protect secrets, pin Actions, and add attestations | SHA pins and protected secret flow |
| `T08` | Create private release handoff and trust gate | No raw MarketData payload is published publicly |
| `T09` | Run network-disabled private final analysis | No provider credentials or external network |
| `T10` | Run the controlled batch-3 pilot | Fresh 12-ticker success and countability |
| `T11` | Retire private acquisition and rotate credentials | Legacy paths and secrets removed |

The queue is not advanced by editing a status field. Each hourly run derives the next safe action from authoritative GitHub state, making repeated runs deterministic and idempotent.
