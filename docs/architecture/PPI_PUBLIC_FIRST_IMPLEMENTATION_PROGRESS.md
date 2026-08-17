# PPI Public-First Implementation Progress

**Status date:** 2026-08-17  
**Repository:** `poudlesuman32-star/ai-market-news`  
**Architecture reference:** `docs/architecture/PPI_PUBLIC_FIRST_3000_6000_TICKER_EXECUTION_PLAN.md`  
**Tracking issue:** [#104](https://github.com/poudlesuman32-star/ai-market-news/issues/104)

## 1. Executive status

The public-first architecture has advanced from an installed 500-candidate scaffold to a live-proven SEC acquisition stage with a diagnosed artifact-review blocker.

Verified live SEC evidence from source run `30915422311`, attempt `1`:

- branch: `main`
- head SHA: `d019b5e5bf82f395686551c5126393b2a2a0cfa5`
- job: `92012221844`, conclusion `success`
- artifact: `8894830703`, `ppi-sec-universe-pilot-30915422311-1`
- artifact ZIP SHA-256: `552ef8645cd3afd310eb36c4352cff626b942a0a1ed95fbf1205e0886df68437`
- exact artifact path count: `4`
- provisional candidate count: `500`
- exactly one approved SEC bulk source was requested
- raw SEC payload was not retained

The automatic SEC artifact-review run is now located: run `30915460990`, attempt `1`, job `92012334668`. It was correctly triggered from source run `30915422311`, downloaded the exact source artifact, and passed its installed unit tests. The review itself failed closed at source-run identity validation with `Source run identity failed: name` because the reviewer compared GitHub's mutable/display run name rather than the durable workflow path and event.

Draft PR #124 changes the reviewer to bind source identity to `.github/workflows/ppi-sec-universe-pilot.yml` plus `workflow_dispatch`, while retaining exact run ID/attempt, repository, `main`, completed, and success checks. It also adds regression tests for the observed live run-name format and wrong path/event cases. A separate read-only, zero-network PR CI workflow is included so the reviewer regression suite can be hosted without provider access.

Canonical step 8 is therefore not waiting on an undiscovered receipt and does not require another SEC acquisition. It remains incomplete until the reviewer fix is accepted and an independent review of the existing source artifact produces a passing receipt.

OpenFIGI mapping, stable public instrument-ID allocation, immutable snapshot assembly, and their artifact-review gates remain installed downstream. They must not be counted as live-proven without their own exact run/artifact evidence.

A separate operational-hygiene defect was observed in the successful SEC run: configured contact data was rendered in Actions logging. Draft PR #119 proposes masking before validation/resolution/collection. The contact value must not be reproduced in documentation, issues, or reports.

## 2. Architecture boundaries preserved

The implementation remains public-first and fail-closed. No automatic private dispatch, private provider retrieval, billing-budget mutation, registry mutation, production publication, broker/order/trading authority, or broad-universe market screening is authorized by the live SEC evidence.

Batch 3 remains frozen. Private recovery remains held behind its separate explicit billing-reviewed operator gate.

## 3. Installed public chain

```text
Universe foundation validation
        ↓
SEC 500-candidate collection              LIVE-PROVEN
        ↓
SEC artifact review                       RUN LOCATED; FAILED CLOSED ON REVIEWER IDENTITY BUG
        ↓
OpenFIGI identity mapping                 INSTALLED; DOWNSTREAM
        ↓
OpenFIGI artifact review                  INSTALLED; DOWNSTREAM
        ↓
Stable public instrument-ID allocation    INSTALLED; DOWNSTREAM
        ↓
Stable-ID artifact review                 INSTALLED; DOWNSTREAM
        ↓
Immutable universe snapshot assembly      INSTALLED; DOWNSTREAM
        ↓
Immutable snapshot artifact review        INSTALLED; DOWNSTREAM
```

Asset-classification source readiness is installed as policy/readiness work and classifies zero instruments.

## 4. Current ordered status

The canonical 26-step plan remains the governing backlog.

- Steps 1–7: implemented.
- Step 8 SEC acquisition: complete and live-proven.
- Step 8 independent SEC artifact review: run located, but failed closed on the reviewer source-name check; not complete.
- Step 9 live execution: not yet earned from the canonical order.
- Step 9 safe preparatory implementation: in progress on draft PR #122 with a new 3,000-disposition contract, schemas, zero-network validator/reviewer tests, deterministic ordering and non-overlap enforcement, schema/validator parity checks, and a read-only offline CI definition. No acquisition adapter or live execution authority is included.

The earlier progress wording that required the entire OpenFIGI → stable-ID → immutable-snapshot chain to complete step 8 was over-broad. Those are downstream gated stages with their own evidence requirements.

Step 8 may be marked complete only after an exact review receipt bound to source run `30915422311` records at minimum:

```json
{
  "gate_passed": true,
  "artifact_mode": "success",
  "candidate_count": 500
}
```

The reviewer fix itself is not a passing receipt.

## 5. Remaining evidence gap

The next required evidence is a successful review of the already-produced SEC artifact, not another SEC acquisition.

Known review evidence:

1. review workflow run `30915460990`, attempt `1`;
2. review job `92012334668`;
3. source run binding `30915422311` / attempt `1` / `main` / `d019b5e5bf82f395686551c5126393b2a2a0cfa5`;
4. exact source artifact download completed;
5. installed reviewer unit tests passed in the review job;
6. review failed closed only on the source-run `name` identity check;
7. retained failed-review artifact exists but is not passing evidence.

Before step 8 completion, independent verification must still establish a passing receipt with the expected artifact and lineage hashes and no unexpected paths, raw SEC retention, private access, registry authority, publication authority, or trading authority.

Do not recreate evidence by automatically rerunning SEC acquisition.

## 6. Downstream implementation state

OpenFIGI mapping and review are installed and gate-bound to a passing SEC review receipt. Stable-ID allocation and review are installed and gate-bound to a passing OpenFIGI review. Immutable snapshot assembly and review are installed and gate-bound to a passing stable-ID review.

Draft PR #122 prepares the separate step-9 3,000-instrument snapshot contract and offline review machinery without authorizing provider acquisition. Its preparation does not advance the canonical completion marker past step 8.

## 7. Asset-classification readiness

The source-readiness workflow remains policy/readiness only. It evaluates objective evidence support and explicitly prohibits ticker/name substring shortcuts, issuer-country-only classification, or treating absence of an F-6 filing as common-stock proof. Zero instruments are classified by readiness alone.

## 8. Private execution hold

The private execution hold is unchanged. No private recovery is authorized by this ledger update. Billing changes, private provider acquisition, automatic private dispatch, registry mutation, production publication, and broker/trading authority remain outside the public-first execution authority.

## 9. Stale documentation and open remediation

`main` still contains the July 29 ledger that incorrectly says the SEC success artifact is unconfirmed and instructs an operator to configure and run SEC. This branch corrects that stale state.

Open draft remediation remains separated by concern:

- PR #118: this status-ledger reconciliation.
- PR #119: SEC contact/log masking.
- PR #122: safe step-9 3,000-snapshot preparatory contract and zero-network review implementation.
- PR #124: SEC artifact-review source identity fix and zero-network reviewer CI.

PRs #120 and #121 are duplicate provider-cooldown test fixes unrelated to the ordered universe backlog. PR #123 concerns separate R11 acquisition/bootstrap resumability and does not advance this 26-step universe sequence.

## 10. Next safe sequence

1. Obtain hosted or otherwise independently reviewable zero-network test evidence for PR #124.
2. Review and merge PR #124 only through the normal repository process; this ledger does not authorize merge.
3. After the fix is installed, review the existing SEC source artifact from run `30915422311` without rerunning SEC acquisition.
4. If and only if the exact review receipt passes, mark canonical step 8 complete.
5. Reconcile issue #104 and this ledger with the exact passing review run/artifact evidence.
6. Continue step-9 contract/schema/validator/reviewer preparation on PR #122, but keep live 3,000-instrument acquisition held until step 8 passes.
7. Keep later provider acquisition, private recovery, billing, registry, production publication, and trading authority held unless separately and explicitly approved.

## 11. Safety boundary

This ledger records verified public evidence and ordered readiness only. It does not expose configuration values, dispatch provider acquisition, trigger private recovery, alter billing, merge pull requests, mutate registries, publish production output, or enable broker/trading authority.
