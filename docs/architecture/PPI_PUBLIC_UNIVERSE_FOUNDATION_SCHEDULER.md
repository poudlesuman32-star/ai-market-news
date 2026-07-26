# PPI Public Universe Foundation Scheduler

## Status

Implementation foundation only.

This scheduler validates the public-first universe contract, source inventory, schema bundle and frozen batch-3 boundary. It intentionally performs no external retrieval.

## Trigger policy

- Manual `workflow_dispatch`
- Push to `main` when a foundation file changes
- Weekly validation at `17 6 * * 1`

## Allowed behavior

- Read repository files
- Validate the source inventory
- Verify at least one approved free universe source
- Verify at least one approved free identifier-mapping source
- Confirm that public screening remains blocked
- Verify the exact Git blob identities of the frozen batch-3 acquisition contract, collector contract and batch configuration
- Validate lifecycle, applicability, identity, event and snapshot schemas
- Publish a safe readiness artifact

## Forbidden behavior

- Network access
- Provider calls
- Provider credentials
- Public screening
- Deep-evidence collection
- Private-repository access
- Private dispatch
- Billing changes
- Registry mutation
- Production, publication, broker, order, trading, MMM/raw-data or R12 authority

## Next implementation gate

After this scheduler passes on `main`, create the SEC 500-instrument ingestion prototype as a separate public workflow and contract revision. That later workflow must keep raw-source licensing, rate limits, deterministic snapshots and public-only execution explicit.
