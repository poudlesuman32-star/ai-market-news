# PPI OpenFIGI 500-candidate mapping pilot

This public-only workflow maps the exact 500 SEC candidates only after the automatic SEC artifact-review gate passes.

## Gate

The workflow performs no OpenFIGI request unless the exact review receipt contains:

```json
{"gate_passed": true, "artifact_mode": "success", "candidate_count": 500}
```

It then downloads the exact SEC artifact bound by that receipt and re-verifies all file and snapshot hashes.

## Free-tier policy

- Endpoint: `https://api.openfigi.com/v3/mapping`
- No API key or secret
- 10 jobs per request
- Exactly 50 requests for 500 candidates
- At least 2.5 seconds between requests
- Bounded retries for HTTP 429, 500 and 503

## Output

Success:

```text
openfigi-mapping-500.jsonl
manifest.json
receipt.json
report.md
```

Blocked review gate:

```text
blocked.json
report.md
```

Raw OpenFIGI responses are never retained. Results are normalized as `exact`, `ambiguous` or `unmatched`.

This workflow does not screen instruments, collect deep evidence, access the private repository, dispatch private work, mutate billing or mutate the registry.
