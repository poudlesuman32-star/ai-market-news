# Architecture

## 1. Purpose

`ai-market-news` is the public collection and publication boundary for Iteration 16 market data.

The architecture separates inexpensive recurring public collection from private MMM evaluation. Public GitHub Actions may eventually collect and validate market data. Private MMM may later consume a new, complete, immutable artifact and perform the final private calculation.

Iteration 0 establishes only the repository foundation.

## 2. Trust boundaries

### Public repository

Allowed responsibilities:

- hold public schemas and configuration;
- collect approved market data after later iterations enable collection;
- validate public artifacts deterministically;
- publish immutable snapshots and a latest pointer after later approval;
- expose only public market-data metadata and artifacts.

Prohibited responsibilities:

- access MMM or `raw_data`;
- contain private scoring or candidate-selection logic;
- contain portfolio positions or holdings;
- contain credentials or private provider responses;
- trigger private processing directly;
- publish unvalidated or synthetic market data;
- make production or promotion decisions.

### Private MMM consumer

The private consumer is outside this repository. It may eventually:

- read the public latest pointer;
- check out the exact immutable public commit;
- verify source repository, hashes, schema, and completion flags;
- skip heavy work when no new complete dataset exists;
- run one private evaluation for each new complete public data commit.

The public repository receives no code, credentials, results, or control input from MMM.

## 3. Planned data flow

```text
Public provider
      |
      v
Public collector
      |
      v
Schema and invariant validation
      |
      v
Immutable public snapshot + manifest
      |
      v
Latest pointer
      |
      v
Private MMM verification and evaluation
```

Every later stage must fail closed. A failed collection or validation must not replace the last valid latest pointer.

## 4. Iteration 0 controls

Iteration 0 contains no executable workflow and no network-enabled collector.

Required controls:

1. Repository remains public.
2. `main` is the default branch.
3. Foundation files and tracked directory placeholders are committed.
4. No GitHub Actions schedule exists.
5. No secrets are configured or referenced.
6. No MMM or `raw_data` access exists.
7. No private scoring, portfolio, or promotion logic exists.
8. No automatic publishing exists.

## 5. Future branch

After the foundation is committed to `main`, the `iteration-16-market-data` branch may be created from that exact foundation commit. Publishing behavior is not enabled during Iteration 0.

## 6. Security principles

- Least privilege by default.
- Public contract before collector implementation.
- Deterministic validation before network collection.
- Immutable snapshots before latest-pointer updates.
- Fail closed on missing, invalid, substituted, future, duplicate, or tampered data.
- Keep public collection and private evaluation independent.
