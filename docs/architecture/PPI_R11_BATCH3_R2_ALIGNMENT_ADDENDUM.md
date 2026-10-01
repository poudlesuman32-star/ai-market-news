# PPI R11 Batch-3 R2 Contract Alignment Addendum

**Status:** **implemented, executed, and registered for batch 3**  
**Originally approved:** July 29, 2026  
**Execution verified:** October 1, 2026 UTC  
**Applies to:** `poudlesuman32-star/ai-market-news`, `MarketMakingLFG/ppi-data-acquisition` (repository ID `1312286476`), and `musksuman3/ai-signal-engine`

## Frozen lineage

The executed batch-3 lineage is:

- Private analytical contract: `PPI-R11-BATCH-EVIDENCE-003-R1`
- Public acquisition contract: `PPI-R11-PUBLIC-ACQUISITION-003-R2`
- Public collector release: `PPI-PUBLIC-COLLECTOR-003-R2`

R2 supersedes only the public acquisition and collector R1 identities. Historical R1 receipts remain immutable.

## Frozen provider mapping

| Evidence category | Frozen provider operation |
|---|---|
| Expectation history | `yahoo_finance_via_yfinance:1.5.1` |
| Independent recognition | `alpha_vantage:NEWS_SENTIMENT` |
| Market time series | `marketdata:daily_candles` |
| Specialized contract data | `marketdata:option_chain` |

The benchmark is `QQQ`.

The executed package contained exactly 12 cumulative tickers, 48 bundles, 50 total package paths, and 49 provider operations. The cumulative cohort is:

`AAPL, MU, NVDA, AMD, AVGO, INTC, TSM, ARM, QCOM, MRVL, GFS, TXN`

The batch-3 additions are:

`QCOM, MRVL, GFS, TXN`

## Executed trust boundary

The only approved producer-execution plane was `MarketMakingLFG/ppi-data-acquisition`, repository ID `1312286476`.

Provider access was gated by the independently hosted GitHub App `ppi-r11-independent-protection` under autonomous fail-closed policy `r11-autonomous-v3`. The live control plane verified App ID `5112236`, installation `165898080`, protection rule `67004141`, branch policy `60290047`, denied administrator bypass, and main-only execution.

The exact accepted producer run was `36815531930/1` at head `5d4c03c4a45b44d9abbcd75010af909f670dcb20`. Its private handoff ZIP SHA-256 is `6564ab2921d53918cf33dea0f53fc61fc8b84579f3c1fc76a93b4eedf6d8a086`, with provenance attestation `51699208`.

The successful private final-analysis run was `36816359238/1` at head `5f6e673b32e7b72f09d92eb02d194be9117079dc`. It ran after trusted materialization and R2 validation, with network isolation and provider/GitHub tokens absent from the scoring boundary.

## Registered result

Private analysis produced `countable_candidate` with no rejection reasons and a deterministic one-file registry proposal.

CI-gated registry PR `musksuman3/ai-signal-engine#265` merged at `20cc9c706cb4578f3c11b575b2524f42e15d8dcd`.

Authoritative R11 progress is now:

- **3 / 20 countable batches**
- **12 / 80 approved tickers**
- registry status `collecting`
- `r12_authorized: false`

No partial or synthetic credit was used, and no protection bypass was used.

## Authority boundary

Batch-3 registration does not authorize production, publication, broker, order, trading, MMM/raw-data, or R12 operation. Those authorities remain disabled.
