# PPI R11 Batch-3 R2 Progress Status

**Status date:** October 1, 2026 UTC  
**Program:** PPI R11 cumulative shadow validation  
**Batch-3 verdict:** **REGISTERED**  
**Authoritative R11 progress:** **12 / 80 approved tickers and 3 / 20 countable batches**

The canonical detailed ledger is:

`docs/architecture/PPI_R11_BATCH3_R2_REMEDIATION_STATUS.md`

## Current truth

R11 batch 3 is complete and registered. The exact new batch-3 tickers are:

`QCOM, MRVL, GFS, TXN`

The authoritative private registry remains in overall `collecting` state because the full R11 target is 80 tickers / 20 countable batches. Batch 3 advances the registry from 8/80 and 2/20 to **12/80 and 3/20**.

The registered batch is bound to:

- producer repository `MarketMakingLFG/ppi-data-acquisition`, repository ID `1312286476`;
- protected producer run `36815531930`, attempt `1`, head `5d4c03c4a45b44d9abbcd75010af909f670dcb20`;
- exact private handoff ZIP SHA-256 `6564ab2921d53918cf33dea0f53fc61fc8b84579f3c1fc76a93b4eedf6d8a086`;
- provenance attestation `51699208`;
- successful private final-analysis run `36816359238`, attempt `1`, head `5f6e673b32e7b72f09d92eb02d194be9117079dc`;
- private score SHA-256 `f41055ac35eea47783837f87a201ed961c22a045b161b7eda3d7a314872e0382`; and
- registry merge commit `20cc9c706cb4578f3c11b575b2524f42e15d8dcd`.

No protection bypass was used. Production, publication, broker, order, trading, MMM/raw-data, and R12 authority remain disabled.
