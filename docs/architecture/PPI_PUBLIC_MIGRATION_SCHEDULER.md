# PPI Public Migration Scheduler

The scheduler converts the validated PPI migration plan into small, reviewable tasks without granting implementation authority to a scheduled workflow.

## Operating model

- Only one task may be active.
- The initial active task is `T01`: public architecture and bootstrap readiness.
- Advancing to another task requires a reviewed pull request that changes `config/ppi_public_migration_schedule.json`.
- The scheduler is read-only and produces a readiness report artifact.
- It does not collect provider data, use provider credentials, write another repository, dispatch the private repository, merge pull requests, mutate the registry, or grant production/trading/R12 authority.

## Schedule

The workflow runs on weekdays at `14:15 UTC`, approximately `08:15` or `09:15` in `America/Chicago` depending on daylight saving time. It may also be run manually from `main`.

## Task queue

| Task | Gate | Description | Initial status |
|---|---:|---|---|
| `T01` | 0 | Public architecture and bootstrap readiness | Active |
| `T02` | 1 | Freeze provider licensing dispositions | Blocked |
| `T03` | 1 | Freeze R1 contract lineage and collector release identity | Blocked |
| `T04` | 2 | Add category-specific public schemas and validators | Blocked |
| `T05` | 2 | Add sharding, bounded retries, and resumable collection | Blocked |
| `T06` | 2 | Separate success/failure artifacts and enforce 50 paths | Blocked |
| `T07` | 2 | Protect secrets, pin Actions, and add attestations | Blocked |
| `T08` | 3 | Freeze the public-to-private handoff | Blocked |
| `T09` | 4 | Build the no-network private artifact consumer | Blocked |
| `T10` | 5 | Run the controlled batch-3 pilot | Blocked |
| `T11` | 6 | Retire private acquisition and rotate the bootstrap token | Blocked |

## Initial completion rule

`T01` is complete only when the canonical Version 1.2 plan and local bootstrap template pass, target repository identity is verified, target pull request 1 remains open and draft, and the target PR branch contains the hardened README.

The scheduler reports the next manual action but never performs it automatically.
