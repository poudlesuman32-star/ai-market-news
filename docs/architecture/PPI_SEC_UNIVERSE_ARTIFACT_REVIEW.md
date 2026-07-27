# PPI SEC Universe Pilot Artifact Review

This public-only workflow verifies the exact artifact produced by the 500-candidate SEC universe pilot.

## Passed gate

A passed review requires the exact four success paths, exactly 500 canonical JSONL candidates, unique and sorted identities, matching snapshot/manifest/contract hashes, and explicit proof that raw SEC payloads, private access, deep evidence, and registry mutation were not used.

## Blocked gate

A missing `PPI_SEC_USER_AGENT` produces the exact blocked artifact. The reviewer records it as reviewed but does not advance the gate.

## Authority

The workflow can download one exact public artifact, verify it, and publish a safe review receipt. It cannot call OpenFIGI, screen instruments, collect deep evidence, access the private repository, dispatch private work, change billing, or mutate the registry.
