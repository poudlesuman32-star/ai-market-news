# PPI R11 Batch-3 R2 Remediation Status

**Status:** remediation complete; real pilot evidence not yet generated  
**Verified:** September 8, 2026  
**Scope:** `poudlesuman32-star/ai-market-news`, `MarketMakingLFG/ppi-data-acquisition` (repository ID `1312286476`), and `musksuman3/ai-signal-engine`

This document is the current-state companion to `PPI_R11_BATCH3_R2_ALIGNMENT_ADDENDUM.md`. The alignment addendum records the frozen architecture decision. This document records what has actually been deployed and what still has to happen before a real pilot evidence dossier can be completed.

Nothing in this document authorizes provider acquisition, private analysis, registry mutation, package publication, production/publication/broker/order/trading/MMM/raw-data/R12 authority, or secret disclosure.

## Frozen identities

- Private analytical contract: `PPI-R11-BATCH-EVIDENCE-003-R1`
- Public acquisition contract: `PPI-R11-PUBLIC-ACQUISITION-003-R2`
- Public collector release: `PPI-PUBLIC-COLLECTOR-003-R2`
- Producer repository: `MarketMakingLFG/ppi-data-acquisition`
- Producer repository ID: `1312286476`
- Consumer repository: `musksuman3/ai-signal-engine`

## Finished remediation

### Control-plane and architecture

- `poudlesuman32-star/ai-market-news#116` is merged. The R2 alignment addendum is on `main` and records the exact 48-bundle / 50-path / 49-provider-operation boundary, canonical producer identity, and disabled downstream authority.
- `poudlesuman32-star/ai-market-news#123` is merged. Producer propagation was delegated to the dedicated producer-remediation path and completed through producer PR #13.
- Issue #117 is closed as completed for remediation tracking.

### Private consumer

- `musksuman3/ai-signal-engine#222` is merged at head `7509f166ee6dd2d54fae56da934519042f90648e`.
- The consumer derives the frozen R2 provider ledger from actual receipts rather than scalar claims.
- Trusted GitHub run/materialization identity is bound to repository, workflow, run ID, attempt, and head SHA.
- Required authority fields must be present and exactly `false`.
- Exact 48-bundle / 50-path package enforcement, safe extraction, attestation-before-extraction, timestamp causality, scoring under `runtime/shadow`, no-network/no-token private analysis, review-only registry proposal, secret-leak evidence, failure separation, deterministic replay evidence, retention controls, shard/resume validation, protected-environment validation, adversarial negative tests, and dossier-root validation are implemented.
- The protected-environment receipt validator is schema `1.1.0` and supports either `human_required_reviewers` or `custom_deployment_protection_rule`. Automated approval is valid only when the rule is independent of producer execution; it may not masquerade as human review.
- Administrator bypass must remain `denied` in either approval mode.
- Exact-head validation for the final #222 head passed in `PPI R2 exact-head validation` run `31274440122`, job `93145643903`.
- The same head also passed protected-environment contract CI (`31274440145`), shard/resume contract CI (`31274440117`), pilot dossier contract CI (`31274440149`), adversarial validation (`31274440127`), private evidence/ingestion/dossier validation (`31274440147`), and shadow-closure validation (`31274440125`).
- The separate `Validate PPI R2 handoff trust gate` run `31274440116` passed checkout, compilation, and the complete focused fail-closed suite; its workflow conclusion was failure only because the final PR evidence-comment POST was forbidden by GitHub permissions.
- `musksuman3/ai-signal-engine#223` and `#224` are merged. Dossier remediation and the canonical R2 producer-identity compatibility boundary are on `main`.

### Public producer

- The repository migration to `MarketMakingLFG/ppi-data-acquisition` is complete while preserving repository ID `1312286476`.
- Producer provenance attestation is deployed: the exact final ZIP is prepared once, attested with a SHA-pinned GitHub action, and that same digest-bound archive is published.
- Producer PR #13 (`Harden PPI R11 R2 resumability and job-log evidence`) is merged at head `79d2f8db54c9c74c5210e4516369c16fea44a4dc` with exact-head validation run `32258655978` successful.
- The producer now restores a prior private checkpoint, collects or reuses four verified deterministic shards, persists the resumability checkpoint privately, and cleans temporary checkpoints after successful handoff.
- Success and failure evidence are retained separately.
- The producer scans retained package outputs for credential leakage.
- A separate post-job step downloads the completed producer job log and scans the exact log for credential leakage, retaining only a safe scan receipt.
- Public success metadata is retained for 30 days and failure diagnostics for 7 days.
- No currently visible open R11/PPI-R2 remediation PR remains across the three tracked repositories as of this verification.

## Remaining before a real pilot dossier can be complete

### 1. Protected GitHub Environment on the producer

The producer workflow still needs to target a protected GitHub Environment with machine-verifiable policy evidence. This is the remaining infrastructure/governance setup, not a missing consumer validator.

Required properties:

- the acquisition job explicitly targets the environment;
- deployment branch restrictions are configured for the approved `main` path;
- administrator bypass is denied;
- provider credentials are available only after the environment gate passes and remain unavailable to pull requests, forks, untrusted reusable workflows, and private analysis;
- least-privilege workflow permissions remain enforced;
- the run emits a public-safe protected-environment receipt bound to the exact repository, workflow, SHA, run ID, and attempt;
- the receipt contains no secret values or secret derivatives and keeps every downstream authority field `false`.

For the lowest-touch operating model, use an independent GitHub App custom deployment-protection rule. The consumer already accepts this mode when the receipt proves the rule is enabled, independently operated, approved the deployment, and is bound to stable App/rule identifiers. This removes per-run human approval without allowing the producer to self-approve.

If a custom deployment-protection App is not installed, the fallback remains GitHub required reviewers.

### 2. Generate one authorized real producer pilot

No remediation loop should fabricate this evidence. After the protected environment is genuinely configured, an authorized pilot must execute the producer workflow and produce real provider evidence.

The successful producer run must prove:

- exactly 12 cumulative tickers;
- exactly 48 evidence bundles;
- exactly 50 retained private package paths;
- exactly 49 provider operations with the frozen R2 mapping;
- verified shard/resume evidence;
- protected-environment evidence for that exact run;
- retained-output and completed-job-log leak-scan receipts;
- exact final ZIP provenance attestation;
- success/failure artifact separation and retention controls;
- no automatic private-analysis dispatch from the public producer.

### 3. Complete the private pilot evidence dossier from that real handoff

After the real producer handoff exists, the private side can verify and materialize it through the already-merged fail-closed gates. A complete pilot dossier must bind the real producer run, attestation, package validation, timestamp validation, protected-environment receipt, shard/resume receipt, leak-scan evidence, isolated private score, replay identity, and review-only registry proposal/root-manifest evidence.

This step must still leave registry mutation, production publication, broker/order/trading authority, MMM/raw-data authority, and R12 authority disabled.

## Not remaining remediation

The following are not open code-remediation items anymore:

- repository migration;
- provider mapping enforcement;
- trusted run/materialization binding;
- mandatory false authority fields;
- 48-bundle / 50-path validation;
- safe ZIP extraction;
- R2 validation before scoring;
- `runtime/shadow` scoring root;
- no-network/no-token private analysis;
- review-only registry proposal;
- provenance generation and verification logic;
- sharded/resumable producer implementation;
- secret and completed-job-log scanning;
- failure artifact separation;
- replay/retention controls;
- adversarial negative-test coverage;
- dossier validation implementation;
- canonical producer-identity compatibility handling.

## Operational rule

Treat remediation as complete but the pilot as **not yet evidenced**. Do not reopen completed code gates merely because the real pilot has not run. Conversely, do not claim the pilot dossier is complete until the protected-environment evidence and one real successful producer/private evidence chain exist for the same immutable run lineage.
