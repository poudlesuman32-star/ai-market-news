# PPI Stable Instrument ID Allocation Pilot

This public-only workflow allocates deterministic internal instrument IDs only after an exact OpenFIGI mapping artifact review passes.

## Rules

- `exact` mapping: allocate one ID from the primary FIGI.
- `ambiguous` mapping: preserve as `deferred_ambiguous`; never guess.
- `unmatched` mapping: preserve as `deferred_unmatched`; never guess.
- duplicate FIGIs across exact records fail closed.
- ticker and CIK are not permanent security-level primary keys.
- the workflow makes no network requests and does not mutate a registry.

The deterministic identity input is:

```text
PPI-STABLE-INSTRUMENT-ID-V1|FIGI|<FIGI>
```

The public ID is:

```text
ppi-us-equity-<first 24 lowercase hex characters of SHA-256>
```

This pilot produces a reviewable artifact only. It does not authorize screening, deep evidence, private work, registry mutation, production, publication, or trading.
