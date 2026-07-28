# PPI Asset-Classification Source Readiness

This public-only scheduler checks whether objective evidence sources are ready for a future common-stock versus ADR classifier.

- OpenFIGI `marketSector`, `securityType`, and `securityType2` are instrument-level metadata.
- `securityType2 = Common Stock` may support common-stock classification after exact reviewed FIGI lineage.
- `securityType2 = Depositary Receipt` may support ADR classification after exact reviewed FIGI lineage.
- SEC Forms F-6 and F-6EF are positive ADR evidence only when the subject CIK is linked exactly.
- Absence of F-6 or F-6EF does not prove common stock.
- Security-name, ticker-suffix, and issuer-country heuristics are prohibited.
- The Nasdaq symbol directory remains pending terms and semantic review and has no classification authority.

The workflow performs one unauthenticated OpenFIGI enum probe, emits only `readiness.json` and `readiness.md`, and classifies zero instruments. It performs no screening, deep evidence, private access, registry mutation, publication, or trading.
