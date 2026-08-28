# PPI Public-First Blocker Remediation

**Status:** Draft operational policy
**Scope:** Public-first implementation blockers only
**Canonical backlog:** `docs/architecture/PPI_PUBLIC_FIRST_3000_6000_TICKER_EXECUTION_PLAN.md`
**Status ledger:** `docs/architecture/PPI_PUBLIC_FIRST_IMPLEMENTATION_PROGRESS.md`

## Purpose

This document defines a repeatable blocker-fixer policy for the PPI public-first implementation. It replaces ad hoc remediation with a fail-closed decision process that may automatically prepare safe repository changes but must stop before any action that expands provider, private, billing, registry, publication, or trading authority.

The framework does not change canonical backlog order. A blocker fixer may repair the earliest incomplete safe step or prepare later offline work, but it must not claim a later live step complete while an earlier gate remains unresolved.

## Core rule

Every blocker is classified before remediation.

```text
observe blocker
    ↓
collect repository/workflow evidence
    ↓
classify blocker
    ↓
select only allowlisted remediation actions
    ↓
prepare code/tests/docs/draft PR/issue evidence
    ↓
stop if approval-required authority would be crossed
```

No remediation may silently substitute a provider, rerun acquisition, recover private execution, alter billing, mutate registries, publish production output, merge a PR, or enable broker/order/trading authority.

## Blocker classes

### `ci_policy_or_trigger`

Examples:

- PR workflow is installed but no `pull_request` run is scheduled.
- Path filters prevent expected offline CI.
- Required check is absent because the workflow is not present on the base branch.

Safe remediation:

- inspect workflow and repository evidence;
- add or narrow a zero-network PR workflow;
- add offline regression tests;
- prepare a draft bootstrap PR;
- record the exact missing run/check.

Approval required before:

- merging the bootstrap PR;
- manually dispatching provider-active workflows.

### `reviewer_or_validator_bug`

Examples:

- reviewer fails on mutable presentation metadata;
- schema and validator disagree;
- deterministic ordering or hash verification is incomplete.

Safe remediation:

- patch reviewer/validator logic;
- add regression and negative tests;
- prepare a draft PR;
- document the failure evidence.

Approval required before:

- merging the fix;
- rerunning any provider acquisition to recreate expired evidence.

### `expired_or_missing_artifact`

Examples:

- required Actions artifact has expired;
- artifact exists but the exact review receipt is missing.

Safe remediation:

- verify expiry/missing evidence;
- preserve run IDs, hashes, and failure diagnosis in the ledger;
- prepare reviewer/log-hygiene fixes needed before a replacement run.

Must stop before:

- replacement provider acquisition.

### `log_hygiene_or_secret_exposure`

Examples:

- configured contact value appears in workflow logs;
- constructed user-agent or other sensitive operational value is echoed.

Safe remediation:

- add masking before validation/resolution/collection;
- add regression tests enforcing masking order;
- update automation documentation without reproducing exposed values.

Must stop before:

- another provider run that would exercise the affected path unless the fix is installed and explicitly approved.

### `stale_documentation_or_ledger`

Examples:

- progress ledger claims no successful run after verified live evidence exists;
- issue checklist does not reflect completed acquisition evidence.

Safe remediation:

- reconcile docs against repository state;
- prepare/update documentation PRs;
- update issue comments/body with exact non-secret evidence.

This class never grants execution authority.

### `merge_conflict_or_stale_branch`

Safe remediation:

- refresh the fix onto current `main` in a new branch;
- preserve the narrow scope;
- supersede stale draft PRs in documentation.

Must stop before merge.

### `provider_or_quota_gate`

Examples:

- acquisition requires a fresh SEC/OpenFIGI request;
- cooldown/quota window has not elapsed;
- provider terms/approval are unresolved.

Safe remediation:

- inspect contracts and cooldown evidence;
- prepare offline tests/config/docs;
- record the exact approval or timing requirement.

Must stop before provider acquisition.

### `private_recovery_or_billing_gate`

Safe remediation:

- inspect public evidence and recovery contracts;
- document the exact manual approval string or prerequisite.

Must stop before private recovery, billing mutation, or private provider access.

### `registry_publication_or_trading_gate`

Safe remediation:

- prepare validation-only code/tests/docs;
- record the required explicit authority.

Must stop before registry mutation, production publication, broker/order/trading authority, or any equivalent action.

## Action levels

### Level A — automatically safe preparation

The blocker fixer may perform these when technically possible:

- read repository files/issues/PRs/workflow results;
- create or update documentation on a branch;
- create or update deterministic offline code;
- create or update tests that make zero provider requests;
- create a branch;
- create a draft pull request;
- add issue comments with non-secret evidence;
- inspect CI/workflow results;
- refresh a stale fix onto current `main` without merging.

### Level B — explicit approval required

The blocker fixer must stop and request approval before:

- merging or enabling auto-merge;
- provider acquisition or provider-active workflow dispatch;
- rerunning acquisition to recreate expired artifacts;
- private recovery or private dispatch;
- billing changes;
- registry mutation;
- production publication;
- broker/order/trading authority.

## Evidence record

Every blocker remediation report should capture:

```json
{
  "blocker_class": "reviewer_or_validator_bug",
  "canonical_step": 8,
  "evidence": ["workflow run id", "job id", "error summary"],
  "safe_actions_taken": ["draft PR", "tests"],
  "approval_required_for": ["merge", "replacement provider acquisition"],
  "next_safe_action": "inspect hosted zero-network CI"
}
```

Do not place secrets, contact values, provider credentials, private repository contents, or billing details in this record.

## Anti-loop rule

A recurring implementation run must not repeatedly emit the same blocker status without new evidence. If no new evidence or safe remediation is available, it should record `no_new_safe_progress` and stop rather than creating duplicate PRs/comments.

Duplicate remediation PRs should be avoided. Prefer updating the existing narrow draft PR or refreshing it onto current `main` only when the existing branch is stale or non-mergeable.

## Current step-8 application

As of the current repository state, the SEC acquisition was previously proven, the automatic review failed on reviewer source-run identity handling, and the original artifact later expired. The relevant blocker chain is therefore:

```text
reviewer_or_validator_bug
        +
log_hygiene_or_secret_exposure
        +
expired_or_missing_artifact
```

Safe work may prepare and verify reviewer/log-hygiene fixes. A replacement SEC acquisition remains Level B and requires explicit approval after those fixes are installed.

## Completion rule

A blocker is lifted only when the canonical gate's own evidence requirement is satisfied. A remediation PR being prepared, tested, or merged is not itself proof that the blocked pipeline step passed.
