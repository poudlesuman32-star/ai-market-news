# PPI Public Migration Scheduler

The scheduler converts the validated Version 1.2 migration plan into small, reviewable tasks without granting a scheduled workflow implementation authority.

## Initial operation

- Only one task is active: `T01`, public architecture and bootstrap readiness.
- All later tasks remain blocked.
- Advancing the queue requires a reviewed pull request that updates `config/ppi_public_migration_schedule.json`.
- The workflow is read-only and produces a readiness report artifact.
- It cannot collect provider data, use secrets, write another repository, dispatch private Actions, merge pull requests, mutate the registry, or grant production/trading/R12 authority.

## Schedule

The workflow runs on weekdays at `14:15 UTC`, approximately `08:15` or `09:15` in `America/Chicago` depending on daylight saving time. It can also be run manually from `main`.

## Task sequence

| Task | Gate | Description | Initial status |
|---|---:|---|---|
| `T01` | 0 | Public architecture and bootstrap readiness | Active |
| `T02` | 1 | Freeze provider licensing dispositions | Blocked |
| `T03` | 1 | Freeze R1 contracts and collector release | Blocked |
| `T04` | 2 | Add category-specific public validation | Blocked |
| `T05` | 2 | Add sharding, bounded retries, and resume | Blocked |
| `T06` | 2 | Separate success/failure artifacts and enforce 50 paths | Blocked |
| `T07` | 2 | Protect secrets, pin Actions, and add attestations | Blocked |
| `T08` | 3 | Freeze the public-to-private handoff | Blocked |
| `T09` | 4 | Build the no-network private artifact consumer | Blocked |
| `T10` | 5 | Run the controlled batch-3 pilot | Blocked |
| `T11` | 6 | Retire private acquisition and rotate the bootstrap token | Blocked |

`T01` passes only after the local Version 1.2 boundary is intact, target repository identity is verified, target pull request 1 remains open and draft, and its branch contains the hardened README.

The scheduler reports the next manual action but never performs or advances it automatically.
