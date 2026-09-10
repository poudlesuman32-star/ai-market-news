# PPI R11 Batch-3 R2 Progress Status

**Status date:** September 10, 2026  
**Program:** PPI R11 cumulative shadow validation  
**Current authoritative progress:** `8 / 80` approved tickers and `2 / 20` countable batches

This file is the operational status companion to the R2 alignment addendum. It distinguishes controls that are finished in reviewed code from controls that are still blocked, not proven in a successful pilot, or stale in producer identity/configuration. A provider run is never countable merely because collection or handoff succeeded.

## FINISHED — reviewed code and prerequisite gates

| Area | Status | Evidence/state |
|---|---|---|
| Three-repository responsibility split | Finished | Public source/contract plane, public acquisition plane, and private analysis/governance plane remain separated. |
| Canonical producer identity decision | Finished as architecture decision | Canonical producer is `MarketMakingLFG/ppi-data-acquisition`, repository ID `1312286476`; stale producer files listed below still require correction before a countable pilot. |
| R2 public acquisition lineage | Finished | `PPI-R11-PUBLIC-ACQUISITION-003-R2`. |
| R2 collector lineage | Finished | `PPI-PUBLIC-COLLECTOR-003-R2`. |
| Private analytical lineage | Finished | `PPI-R11-BATCH-EVIDENCE-003-R1`. |
| Deterministic producer implementation | Finished except exact regression below | Four deterministic three-ticker shards, resumability/private checkpoints, exact 49-operation ledger, 48-bundle/50-path shape, retained-package secret scan, final-ZIP attestation, success/failure separation, and intended completed-job-log scan stage are merged. |
| Consumer trust/materialization controls | Finished | Exact producer identity/run verification, attestation verification, safe extraction, integrated R2 trust gate, no-network/no-token private analysis, bounded output, replay/no-duplicate-credit protection, review-only registry proposal, and evidence-dossier validation are implemented. |
| Stable-ID allocation prerequisite | Proven and retained | Run `34081406609` attempt `1`; artifact `10003800820`; digest `sha256:af31339079a01d6eb7ca3f20e36f563f369ef679c06c4142019c3f5439d42648`; unexpired through `2026-09-21`. |
| Stable-ID independent review | Proven and retained | Run `34081955551` attempt `1`; artifact `10003963984`; digest `sha256:3202b464bcc46c77ea1a09fda986962ec9a398830f76b7b7a5ec69a355c46168`; unexpired through `2026-09-21`. |
| Immutable snapshot prerequisite | Proven and retained | Run `34082325289` attempt `1`; artifact `10004075428`; digest `sha256:f85ecff12afb8625ab5e8746cbe87c18a782f6645d9b95b42f09732034d5cff2`; unexpired through `2026-09-21`. |
| Immutable snapshot independent review | Proven and retained | Run `34194168149` attempt `1`; artifact `10043252120`; digest `sha256:d8994b956652ba4a317ad7629535a074415ceae468cd5cb6a68964391584d4fb`; unexpired through `2026-09-22`. |

PR `#122` was merged only after the prerequisite chain was proven; its exact pre-merge head `f552dd50cc8e2213cfa34e83daf228f220c44baa` had hosted workflow run `33948943154` green, and the merge commit is `41976b8cd5f7f0758c2d5425fd2c7e6522634e1a`.

## NEWEST EXACT PRODUCER EVIDENCE — still non-countable

A newer manual producer run now supersedes the earlier run as the latest inspected evidence:

- workflow run `34408644594`, attempt `1`;
- repository `MarketMakingLFG/ppi-data-acquisition`;
- exact head `2bbef4dc81c65ab2ee2b723f1bd4de5e34a90e88`;
- overall conclusion `failure`;
- `collect-and-handoff` job `102657604678`: `success`;
- `scan completed producer job log` job `102658500652`: `failure`.

The collection job completed its deterministic provider boundary, four shards, checkpoint persistence/cleanup, retained-package secret scan, exact-package attestation/handoff, public safe-success receipt, and raw-public-upload prohibition. The run retained only safe-success artifact `10126430126`, `ppi-r11-public-success-34408644594-1`, unexpired through `2026-10-09`, with GitHub artifact digest:

`sha256:5659332e977a1cda158764f146f2b1a439b628b55e9654a279bcc7d606472b6a`

Independently rehashed retained files:

- `public-success-receipt.json`: `sha256:99cc1d10218ebd641ffb324b48ce54a75cbe53edaab6edea6c0f0438e1462663`; embedded canonical receipt hash `1999f634490b064e8d30e44dd5a35b6a23151a0f0f456f11c050f4bc1ebacd29`;
- `shard-resume-receipt.json`: `sha256:13a7e92d2f28a3e5e1ee315ed917cb46b3d1d91b386886f3818281aad5245068`;
- `private-handoff-summary.json`: `sha256:5edbddacf9f67725a871fe520d73600ec80ca9bcaf102bdbce6b1ba76e90bb59`;
- `private-handoff-preparation.json`: `sha256:0cf5b4f06975f7cd2e06c9edfef056a0a51aea03475ca2952e69aa1745f55018`;
- exact private package SHA bound by the retained handoff receipts: `cfb9d6931d081b6a5d378a1997f2c58dcd35bbc8c6e23bc293d1f70fafb05cb4`.

The retained shard receipt records four complete shards and `49` provider calls/requests in this attempt, with all production/publication/registry/R12/trading authority flags false.

### Exact regression reproduced

The completed-job-log evidence path failed exactly as before. The `Download completed collect job log` step ran:

```text
gh api "repos/${GITHUB_REPOSITORY}/actions/jobs/${job_id}/logs" > "$RUNNER_TEMP/collect-and-handoff.log"
```

GitHub CLI terminated with:

```text
the response contains terminal escape sequences; pass --allow-escape-sequences to output it anyway
```

Therefore the credential scanner did not execute. The later artifact-retention step warned that no files existed under the job-log-scan path, so **no `ppi-r11-public-job-log-scan-34408644594-1` receipt artifact exists**.

**Disposition:** run `34408644594-1` is **not accepted/countable pilot evidence and grants no registry credit**. Its successful provider collection/private handoff does not satisfy the R11 program gate. This automation did not initiate or retry that run.

The earlier run `34265097209-1` remains historical exact regression evidence with safe-success artifact `10071593777` and digest `sha256:8721f7ce848bb75be653f602ae1eb2ebf8f967bdbb8ee211ac14516fbbd4a9d5`; it is likewise non-countable.

## REMAINING before any batch-3 pilot can be accepted

| Priority | Remaining item | Completion condition |
|---:|---|---|
| 1 | Repair producer job-log download/scanning plumbing | Escape-bearing logs download safely without rendering secrets; raw + safely ANSI-normalized credential scanning remains fail closed; adversarial tests pass; a separately authorized later run retains a passing exact job-log-scan receipt. |
| 2 | Bind provider-bearing job to a protected GitHub environment | Workflow contains the reviewed protected `environment:` boundary and the environment governance is separately proven. Do not mutate environments/secrets without explicit authorization. |
| 3 | Correct stale producer identity/contract references | Both R2 contract JSONs, provider licensing dispositions, generated handoff release-body text, README, and focused consistency tests all identify canonical `MarketMakingLFG/ppi-data-acquisition` / repository ID `1312286476`. |
| 4 | Separately authorize and execute a fresh real producer pilot | Entire producer workflow, including protected-environment evidence and completed-job-log scan, concludes success and retains the exact safe evidence. No provider run is authorized by this document. |
| 5 | Separately authorize private exact-run materialization/analysis | Consumer verifies the same immutable run/package, attestation, trust gate, extraction and no-network scoring. |
| 6 | Complete immutable pilot evidence dossier | Public/private receipts, hashes, review receipts, run identities, scans, attestation, score, countability and replay proofs validate together. |
| 7 | Review the one-file registry proposal | Independent governance accepts the exact append-only proposal. |
| 8 | Register only if every gate passes | Registry may move to `3 / 20` and `12 / 80` only after explicit accepted evidence; otherwise it remains unchanged. |

## Producer identity drift requiring correction

The canonical producer is `MarketMakingLFG/ppi-data-acquisition`, repository ID `1312286476`, but producer `main` still carries the former `spoudel2010-ux/ppi-data-acquisition` slug in identity-bearing surfaces previously verified in:

- `contracts/PPI-R11-PUBLIC-ACQUISITION-003-R2.json`;
- `contracts/PPI-PUBLIC-COLLECTOR-003-R2.json`;
- `config/provider_licensing_dispositions.json`;
- `src/publish_private_handoff.py` release-body text; and
- `README.md`.

Updating README alone is insufficient. These must change together in a reviewable producer branch with focused consistency coverage before a fresh countable pilot.

## Live controller / registry truth

Issue `musksuman3/ai-signal-engine#13` remains fail closed:

- controller state: `R10_SOURCE_CONTROL_ACTIVE`;
- R11 registry: `collecting`;
- approved tickers: `8 / 80`;
- accepted cumulative batches: `2 / 20`;
- frozen next batch: `3: QCOM, MRVL, GFS, TXN`;
- automatic registry mutation: `disabled`;
- production/publication/broker/order/trading/R12 authority: `none`.

The controller was last evaluated at `2026-09-10T12:16:27Z`. Its current read-only watch records public verification `34475375568-1` as `completed/failure` at `2026-09-10T12:12:00Z`, while the automation-health section records a newer public verification `34476116173-1`, event `workflow_dispatch`, `completed/failure` at `2026-09-10T12:19:50Z`, and a newer activation evaluation `34476210660-1`, event `schedule`, at `2026-09-10T12:20:50Z`. Automation health remains `stalled` because the expected schedule slots are late/unbound. These read-only R10 observations do not create R11 pilot evidence, do not change `8 / 80` or `2 / 20`, and grant no registry credit.

The latest repository-level public verification observed after that issue-body evaluation is `34476543720-1`, `PPI primary-source live coverage verification`, exact `ai-market-news` main `41976b8cd5f7f0758c2d5425fd2c7e6522634e1a`, `completed/failure` at `2026-09-10T12:24:50Z`. This newer observation likewise changes no R11 evidence or authority.

The latest producer remediation-controller run is `34462497917-1`, event `schedule`, exact `MarketMakingLFG/ppi-data-acquisition` main `2bbef4dc81c65ab2ee2b723f1bd4de5e34a90e88`, `completed/success` at `2026-09-10T09:46:38Z`. It is control-plane state only and does not supersede the latest inspected producer evidence run `34408644594-1` or make that run countable.

## Documentation / merge gate

PR `#144` is the current documentation branch. Any new documentation commit changes its exact head and must be re-evaluated for mergeability, review cleanliness, and exact-head CI. Do not merge merely because the content is documentation; exact-head CI must be green under the authorized merge policy.

## Authority boundary

No provider acquisition, private recovery/dispatch, billing/payment/subscription/spend-limit change, registry mutation, production publication, broker connectivity, orders, trading, funds movement, secret exposure, MMM/raw-data write, or R12 authority is authorized by this status document. Pilot evidence and registry credit remain incomplete until exact accepted evidence exists.
