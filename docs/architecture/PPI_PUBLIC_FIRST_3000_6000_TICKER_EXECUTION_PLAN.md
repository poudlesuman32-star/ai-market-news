# PPI Public-First 3,000–6,000 Ticker Execution Plan

**Status:** Validated architectural direction; implementation remains phased and gated  
**Scope:** Public-source ingestion, screening, deep-evidence preparation, compact private handoff, and minimal private final analysis  
**Private execution state:** Held until the existing pre-runner failure is reviewed and recovered through the approved manual path

## First design rule

> **Use free, legally usable, high-volume public sources and public-repository runners for nearly all work. Keep the private repository limited to final curation, calculation, scoring, countability, checkpointing and reporting.**

The pipeline should target free or bulk-access sources, but it must not assume every free source is unlimited. A free source may still be rate-limited, operation-limited, or restricted by licensing. Quota-limited sources must be optional, replaceable, cached, or used only for shortlisted candidates.

---

# 1. Revised workload split

## Public repositories — approximately 95%–99% of work

```text
ai-market-news
        +
ppi-data-acquisition
```

Public responsibilities:

- Import the 3,000–6,000 instrument universe
- Track symbols, exchanges, CIKs and FIGIs
- Detect listings, delistings and symbol changes
- Validate instrument types
- Run lightweight screening
- Calculate objective public metrics
- Rank and select candidates
- Fetch all external evidence
- Handle pagination and provider quotas
- Retry transient failures
- Cache reusable responses
- Normalize objective fields
- Detect duplicates
- Validate schemas
- Assign applicability statuses
- Build manifests and receipts
- Hash every file
- Create compact private handoff packages
- Publish public-safe operational reports
- Retain failure diagnostics

## Private repository — approximately 1%–5% of work

```text
ai-signal-engine
```

Private responsibilities only:

1. Verify one exact package.
2. Safely extract it.
3. Verify hashes, provenance and freshness.
4. Perform final semantic curation.
5. Load the previous analytical checkpoint.
6. Run private calculations.
7. Calculate the final score.
8. Perform countability checks.
9. Produce one final report.
10. Produce one incremental checkpoint.
11. Propose or complete the controlled registry update.

Private must not:

- Discover sources
- Fetch listings
- Fetch prices
- Fetch news
- Fetch options
- Call provider APIs
- Contain provider credentials
- Retry provider requests
- Rebuild public packages
- Process the full 3,000–6,000 universe
- Run large public-screening calculations
- Maintain multiple workflow stages or status fan-out

---

# 2. Source policy

Every source and operation must receive a reviewed disposition before use.

## Tier 1 — preferred public bulk sources

Use for the full 3,000–6,000 universe.

Requirements:

- Free access
- Legally usable for the intended operation
- Bulk-file or multi-symbol access
- Stable timestamps
- Deterministic output
- No private-repository credential
- No per-ticker request model where avoidable

Typical uses:

- Listing universe
- Ticker and exchange metadata
- Issuer identifiers
- Symbol changes
- Delisting information
- Basic screening inputs

## Tier 2 — free but rate-limited sources

Use only when necessary.

Suitable uses:

- Mapping identifiers
- Validating ambiguous listings
- Collecting one category for shortlisted candidates
- Filling specific missing fields

Rules:

- Cache successful results publicly.
- Never repeat unchanged requests unnecessarily.
- Track quota consumption.
- Stop before exhausting the daily allowance.
- Do not move a request into private because public quota is exhausted.

## Tier 3 — restricted or expensive sources

Do not use for broad-universe screening.

They may be used only when:

- The operation is legally approved.
- A shortlisted instrument genuinely requires the data.
- The package can be handed off under the approved licensing disposition.
- No approved free or public alternative exists.

When those conditions are not met:

```text
instrument status = deferred
```

The system must not silently substitute an unapproved provider.

---

# 3. Iterative implementation flow

## Iteration 1 — Free-source inventory

Before writing the universe collector, create:

```text
config/ppi_public_source_inventory.json
```

Each source record should include:

```json
{
  "source_id": "example-source",
  "operation": "listing_universe",
  "cost_class": "free",
  "access_model": "bulk",
  "rate_limit": "documented value or unknown",
  "public_runner_allowed": true,
  "raw_publication_allowed": false,
  "derived_metrics_allowed": true,
  "private_handoff_required": false,
  "approved": false
}
```

Exit conditions:

- At least one approved universe source
- At least one approved identifier source
- No private-source dependency

## Iteration 2 — Public universe ingestion

Use approved free public sources to create:

```text
3,000-instrument universe snapshot
```

Public work:

- Download listing files once.
- Normalize records.
- Allocate stable internal IDs.
- Attach CIK and FIGI where available.
- Identify ADRs.
- Detect duplicates.
- Produce an immutable JSONL snapshot and manifest.

Private work:

```text
None
```

## Iteration 3 — Public metadata validation

Validate all instruments publicly:

- Active listing
- Exchange
- Instrument type
- Symbol format
- Issuer identity
- Duplicate identity
- Symbol-history consistency
- Last-confirmed timestamp

Private work:

```text
None
```

## Iteration 4 — Public lightweight screening

Screen the 3,000 instruments in public batches.

```text
3,000 instruments
        ↓
6–12 public cohorts
        ↓
Public screening snapshot
```

Prefer bulk or full-market endpoints rather than one request per symbol.

Calculate publicly:

- Price
- Dollar volume
- Trading-history length
- Recent activity
- Volatility
- Relative strength
- Basic availability flags

Private work:

```text
None
```

## Iteration 5 — Public deterministic selection

The public selector chooses the next candidates.

Inputs:

- Universe snapshot hash
- Screening snapshot hash
- Eligibility contract
- Previous public queue
- Previous private checkpoint identity
- Last-analysis date
- Stable instrument ID

Output:

```text
Next 20 deep-evidence candidates
```

Private work:

```text
None
```

## Iteration 6 — Public deep-evidence collection

For the first generic batch:

```text
20 instruments
4 public shards
5 instruments per shard
```

All external work remains public:

- Expectations
- Recognition
- Market history
- Specialized contracts
- Retries
- Valid-empty detection
- Schema validation
- Licensing checks
- Hashing
- Aggregation

Expected output:

```text
80 evidence bundles
 1 manifest
 1 receipt
──────────────────
82 exact package paths
```

Private work:

```text
None until the package is complete
```

## Iteration 7 — Public analytical preparation

To reduce private work further, the public repository prepares an objective analytical packet.

For each instrument, include:

- Canonical instrument identity
- Normalized numeric series
- Canonical evidence references
- Provider-event timestamps
- Response timestamps
- Availability status
- Raw and normalized hashes
- Objective data-quality flags
- Benchmark-aligned observations
- Precomputed non-private mathematical features

Public may calculate objective features such as:

- Returns
- Volatility
- Relative-strength inputs
- Volume statistics
- Date alignment
- Numeric normalization
- Missing-value indicators

Public must not determine:

- Semantic acceptance
- Final score
- Countability
- Registry credit

## Iteration 8 — Compact private handoff

The private package should contain only what final analysis requires:

```text
manifest
receipt
normalized evidence records
compact semantic-review inputs
objective feature matrix
provenance and hash bindings
```

Avoid transferring:

- Redundant provider responses
- Public logs
- Retry logs
- Duplicate market observations
- Full-universe screening data
- Unselected instruments
- Public operational reports

## Iteration 9 — One short private job

The private job follows one bounded sequence:

```text
Verify package
    ↓
Safely extract
    ↓
Verify provenance and hashes
    ↓
Final semantic curation
    ↓
Load prior checkpoint
    ↓
Calculate final private metrics
    ↓
Score
    ↓
Countability
    ↓
Create final report
    ↓
Create incremental checkpoint
    ↓
Controlled registry result
```

Do not create separate private workflows for downloading, normalization, calculation, scoring, status publication or registry validation. These are steps within one bounded job or local process.

---

# 4. Private runtime target

Initial target:

```text
Private delta:           10 instruments
Expected runtime:         5–10 minutes
Hard workflow maximum:   15 minutes
Private workflows:        1
Provider requests:        0
External network during
final analysis:           0
```

The first 20-instrument public package can be processed as:

```text
Private delta A: 10
Private delta B: 10
```

After measured runtime evidence, one private run may process all 20 only if it remains comfortably inside the hard limit.

---

# 5. Public caching model

Caching is mandatory for 3,000–6,000 instruments.

Content-addressed cache identity:

```text
source
+ operation
+ instrument_id
+ requested period
+ provider-event date
+ collector revision
```

Rules:

- Reuse unexpired public data.
- Do not refetch unchanged listing metadata.
- Do not remap stable FIGIs repeatedly.
- Refresh only stale screening metrics.
- Deeply recollect only shortlisted instruments.
- Never recollect because a private workflow failed.
- A private failure must not trigger public provider retries.

---

# 6. Backpressure

The public system may keep the broad universe current, but deep evidence must stop when private processing is unavailable.

```text
Universe import and refresh       CONTINUE
Identity reconciliation           CONTINUE
Corporate-action tracking         CONTINUE
Lightweight screening             CONTINUE
Candidate queue preparation       CONTINUE

New deep-evidence package         STOP when backlog = 1
New private handoff               STOP when private pending = 1
Private provider retrieval        NEVER
```

---

# 7. Updated priority order

## Priority 1 — Public-only foundation

1. Freeze batch 3.
2. Create the source inventory.
3. Approve free universe sources.
4. Create the universe contract.
5. Create stable identity schemas.
6. Build SEC ingestion.
7. Build identifier mapping.
8. Produce the 500-instrument pilot.
9. Produce the 3,000-instrument snapshot.

## Priority 2 — Public screening

10. Approve a free or sustainable bulk screening source.
11. Build the screening contract.
12. Run a 250-instrument pilot.
13. Screen all 3,000 instruments.
14. Build the deterministic candidate selector.

## Priority 3 — Minimal private recovery

15. Resolve the private runner restriction.
16. Execute one exact private recovery.
17. Measure actual private runtime.
18. Keep private Actions disabled outside controlled final analysis.

## Priority 4 — Generic public deep evidence

19. Create one 20-instrument contract.
20. Run four public shards.
21. Build the 82-path package.
22. Generate the compact objective feature packet.

## Priority 5 — Private finalization

23. Process ten instruments.
24. Produce the final score, countability result and checkpoint.
25. Process the second ten instruments.
26. Measure whether future private deltas can increase.

---

# 8. Final architectural target

```text
Public repositories
────────────────────────────────────
3,000–6,000 instrument inventory
Metadata and identity
Corporate actions
Screening
Ranking
Provider calls
Retries
Caching
Normalization
Objective feature engineering
Evidence validation
Packaging
Provenance
Diagnostics

                ↓ compact trusted package

Private repository
────────────────────────────────────
Final curation
Private calculations
Final scoring
Countability
Checkpoint
Final report
Controlled registry result
```

## Final optimization rule

> **Scale public ingestion and screening to thousands of instruments, but keep every private run limited to one compact, prevalidated analytical delta.**

---

# 9. Current safety boundary

Until private recovery succeeds:

- Public universe import may continue.
- Public metadata validation may continue.
- Public identity reconciliation may continue.
- Public lightweight screening may continue only after source licensing is approved.
- Candidate queue preparation may continue.
- New deep-evidence collection remains blocked when one unprocessed package exists.
- Automatic private dispatch remains disabled.
- Billing-budget mutation remains disabled.
- Public registry mutation remains disabled.
- Private provider retrieval remains permanently forbidden.
