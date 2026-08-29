# PPI Public-First Implementation Progress

**Status date:** 2026-08-29  
**Repository:** `poudlesuman32-star/ai-market-news`  
**Architecture reference:** `docs/architecture/PPI_PUBLIC_FIRST_3000_6000_TICKER_EXECUTION_PLAN.md`  
**Tracking issue:** #104

## 1. Executive status

The public-first architecture has advanced beyond the original 500-candidate scaffold into a partially live-proven identity chain.

Canonical priority status:

- Steps 1–7: implemented.
- Step 8, produce and review the 500-instrument pilot: SEC acquisition and independent SEC review are live-proven; OpenFIGI mapping and its review are also live-proven.
- The remaining step-8 milestone work is zero-provider identity finalization: stable-ID allocation, stable-ID review, immutable 500-candidate snapshot, and immutable snapshot review.
- Step 9, the 3,000-instrument snapshot: offline preparation exists, but live expansion remains held until the complete 500-candidate foundation is proven.
- Public screening remains blocked until an approved sustainable source and terms disposition exist.
- Private recovery remains separately held and must not be triggered from this public-first chain.

## 2. Live evidence now established

### Replacement SEC acquisition

- Source run: `33262467155`
- Event: `workflow_dispatch`
- Branch: `main`
- Head SHA: `3602ae35147371e68f52ff05b527ca919598a00d`
- Workflow path: `.github/workflows/ppi-sec-universe-pilot.yml`
- Conclusion: `success`
- Fresh artifact was retained and was not expired when reviewed.

### Independent SEC artifact review

- Review run: `33262477654`
- Workflow path: `.github/workflows/ppi-sec-universe-artifact-review.yml`
- Event: `workflow_run`
- Head SHA: `3602ae35147371e68f52ff05b527ca919598a00d`
- Conclusion: `success`

This clears the mandatory step-8 SEC dependency that previously failed on mutable Actions run-name identity.

### OpenFIGI mapping and independent review

- Mapping run: `33262486428`
- Workflow path: `.github/workflows/ppi-openfigi-mapping-pilot.yml`
- Event: `workflow_run`
- Head SHA: `3602ae35147371e68f52ff05b527ca919598a00d`
- Conclusion: `success`
- Review run: `33262596949`
- Workflow path: `.github/workflows/ppi-openfigi-mapping-artifact-review.yml`
- Event: `workflow_run`
- Head SHA: `3602ae35147371e68f52ff05b527ca919598a00d`
- Conclusion: `success`

The repository's installed downstream chain then stopped before stable-ID allocation. No stable-ID completion claim is made by this ledger.

## 3. Remediations merged before replacement acquisition

The replacement run used the hardened `main` state that includes:

- PR #125: hosted zero-network SEC reviewer CI bootstrap.
- PR #133: fixed GitHub workflow registration by removing the case-variant `NO_PROXY` / `no_proxy` workflow-environment collision and pinning actions.
- PR #132: durable SEC source-run identity validation based on workflow path, event, branch, run identity and exact source metadata rather than mutable display name.
- PR #131: SEC contact and constructed-user-agent masking before validation and collection.

The replacement SEC acquisition was explicitly operator-approved. These remediations did not authorize future provider acquisition automatically.

## 4. Current blocker: GitHub workflow-run chain depth

Observed live sequence:

```text
SEC pilot
  -> SEC artifact review
  -> OpenFIGI mapping
  -> OpenFIGI artifact review
  -> STOP
```

The stable-ID allocator is zero-provider and already installed, but no live stable-ID run followed successful OpenFIGI review run `33262596949`.

Draft PR #134, `Bridge GitHub workflow_run chain-depth limit`, is the current remediation candidate. It proposes a fail-closed control-plane bridge that:

- reads the latest successful OpenFIGI review;
- downloads and validates the exact review receipt;
- requires a passing 500-candidate success receipt with no stable-ID authority granted by the upstream review;
- checks for an exact existing stable-ID dispatch;
- dispatches only the existing zero-provider stable-ID allocation workflow once;
- performs no SEC/OpenFIGI/provider call, private access, registry mutation, production publication or trading action.

PR #134 is draft and must not be merged without explicit approval.

### Hosted CI status for PR #134

At head `ccfbe7ceb818636397cdfc242791b95e3fd13232`, no hosted pull-request workflow run is attached yet. The PR includes a deterministic static regression test, but that test is not yet independently proven by hosted CI.

A safe attempt was made to add a read-only, zero-provider pull-request CI workflow for this bridge. The connected write was blocked by the platform safety layer, so no repository mutation was made from that attempt.

## 5. Current live stage table

| Stage | Implementation | Live evidence |
|---|---|---|
| Public-first architecture | Complete | Canonical plan merged. |
| Universe foundation | Complete | Installed. |
| SEC 500-candidate collector | Complete | Run `33262467155` passed. |
| SEC artifact reviewer | Complete | Run `33262477654` passed. |
| OpenFIGI mapper | Complete | Run `33262486428` passed. |
| OpenFIGI artifact reviewer | Complete | Run `33262596949` passed. |
| Stable-ID allocator | Installed, blocked on orchestration | No live completion proven after the passing OpenFIGI review. |
| Stable-ID reviewer | Installed, held | Requires a successful exact stable-ID artifact first. |
| Immutable 500-candidate snapshot | Installed, held | Requires passing stable-ID review first. |
| Immutable snapshot reviewer | Installed, held | Requires an exact immutable snapshot artifact first. |
| Asset-classification readiness | Installed | Readiness architecture exists; zero instruments should be claimed classified until prerequisite snapshot review and objective evidence gates pass. |
| 3,000-instrument expansion | Offline preparation only | Live step 9 remains held until complete 500-candidate foundation proof. |
| Public screening | Blocked | Sustainable provider/terms approval unresolved. |
| Private analysis | Held | Separate explicit private-recovery gate. |

## 6. Canonical dependency order from here

The next dependency-safe sequence is:

1. Prove PR #134's bridge logic with hosted zero-provider CI or equivalent independent exact-head evidence.
2. Obtain explicit approval before merging PR #134.
3. After merge, allow only the zero-provider stable-ID allocation for the exact passing OpenFIGI review.
4. Verify stable-ID allocation artifact and its independent review.
5. Verify immutable 500-candidate snapshot and its independent review.
6. Reconcile exact/ambiguous/unmatched and allocated/deferred counts.
7. Only after the full 500-candidate foundation passes, advance live step 9 under a separately reviewed 3,000-instrument contract.

No new SEC/OpenFIGI/provider acquisition is required merely to complete the remaining zero-provider identity stages for the already-reviewed 500-candidate chain.

## 7. Safety boundaries

The public-first automation may continue safe repository inspection, deterministic offline code/tests/docs, zero-provider CI, branch refreshes, draft PR work and non-secret evidence reconciliation.

Without a new explicit approval, it must not:

- initiate SEC/OpenFIGI or other provider acquisition;
- trigger private recovery or private dispatch;
- change billing;
- merge or auto-merge a pull request;
- mutate registries;
- publish production output;
- enable broker, order or trading authority.

The current approval boundary is the merge of PR #134 only after its exact-head safety evidence is satisfactory.

## 8. Definition of the 500-candidate foundation milestone

The milestone is complete only when one live lineage proves:

```text
500 SEC candidate dispositions
        ↓ passing SEC review
500 OpenFIGI mapping dispositions
        ↓ passing OpenFIGI review
500 stable-ID allocation/deferred dispositions
        ↓ passing stable-ID review
500 immutable universe/deferred dispositions
        ↓ passing immutable-snapshot review
```

The first four live stages above are now proven through OpenFIGI review. The remaining zero-provider identity stages are not yet claimed complete.
