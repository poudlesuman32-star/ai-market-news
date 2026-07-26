#!/usr/bin/env python3
from __future__ import annotations

import sys

import ppi_migration_autopilot_v2 as v2


R2_REQUIRED_PATHS = (
    "README.md",
    ".github/workflows/collect-r11-public-evidence.yml",
    "config/r11_batch_003.json",
    "config/provider_licensing_dispositions.json",
    "contracts/PPI-R11-PUBLIC-ACQUISITION-003-R1.json",
    "contracts/PPI-R11-PUBLIC-ACQUISITION-003-R2.json",
    "contracts/PPI-PUBLIC-COLLECTOR-003-R1.json",
    "contracts/PPI-PUBLIC-COLLECTOR-003-R2.json",
    "src/collect_raw_provider_evidence.py",
    "src/collect_raw_provider_evidence_r2.py",
    "src/fetch_yfinance_expectations.py",
    "src/publish_private_handoff.py",
    "tests/test_public_boundary.py",
)


def run_bootstrap_r2(token: str) -> None:
    v2.base.run_command(
        [sys.executable, "scripts/bootstrap_ppi_data_acquisition_r2.py"],
        env={
            "PPI_CROSS_REPOSITORY_AUTOMATION": token,
            "TARGET_REPOSITORY": v2.base.TARGET_REPOSITORY,
        },
    )


def target_gate_r2(token: str, ref: str) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    values: dict[str, str] = {}
    for path in R2_REQUIRED_PATHS:
        try:
            values[path] = v2.base.fetch_text(v2.base.TARGET_REPOSITORY, path, ref, token)
        except Exception:
            reasons.append(f"target {ref} is missing {path}")

    workflow = values.get(".github/workflows/collect-r11-public-evidence.yml", "")
    scope = values.get("config/r11_batch_003.json", "")
    licensing = values.get("config/provider_licensing_dispositions.json", "")
    collector = values.get("src/collect_raw_provider_evidence.py", "")
    entrypoint = values.get("src/collect_raw_provider_evidence_r2.py", "")
    helper = values.get("src/fetch_yfinance_expectations.py", "")
    acquisition_r1 = values.get("contracts/PPI-R11-PUBLIC-ACQUISITION-003-R1.json", "")
    acquisition_r2 = values.get("contracts/PPI-R11-PUBLIC-ACQUISITION-003-R2.json", "")
    collector_r1 = values.get("contracts/PPI-PUBLIC-COLLECTOR-003-R1.json", "")
    collector_r2 = values.get("contracts/PPI-PUBLIC-COLLECTOR-003-R2.json", "")

    for marker in (
        "PRIVATE_RELEASE_HANDOFF_ENABLED: true",
        "ppi-r11-public-success-",
        "ppi-r11-public-failure-",
        "persist-credentials: false",
        "'yfinance==1.5.1'",
        "src/collect_raw_provider_evidence_r2.py",
        "src/fetch_yfinance_expectations.py",
    ):
        if marker not in workflow:
            reasons.append(f"collector workflow missing R2 marker: {marker}")
    if "actions/checkout@v" in workflow or "actions/upload-artifact@v" in workflow:
        reasons.append("collector workflow contains mutable action tags")

    for marker in (
        '"contract_id": "PPI-R11-PUBLIC-ACQUISITION-003-R2"',
        '"collector_release_id": "PPI-PUBLIC-COLLECTOR-003-R2"',
        '"expectation_provider": "yahoo_finance_via_yfinance"',
        '"expected_alpha_vantage_request_count": 12',
        '"expected_bundle_count": 48',
        '"expected_path_count": 50',
    ):
        if marker not in scope:
            reasons.append(f"R2 scope missing marker: {marker}")
    if '"contract_id": "PPI-R11-PUBLIC-ACQUISITION-003-R2"' not in licensing:
        reasons.append("licensing policy is not bound to public acquisition R2")
    if '"provider": "yahoo_finance_via_yfinance"' not in licensing:
        reasons.append("licensing policy does not bind Yahoo expectation payloads")
    if '"function": "EARNINGS_ESTIMATES"' in collector:
        reasons.append("R2 collector still uses Alpha Vantage for expectation history")
    if collector.count('"function": "NEWS_SENTIMENT"') != 1:
        reasons.append("R2 recognition operation is not exact")
    if '"alpha_vantage_request_count": 12' not in collector:
        reasons.append("R2 collector does not record the 12-call Alpha Vantage bound")
    if 'PUBLIC_CONTRACT_ID = "PPI-R11-PUBLIC-ACQUISITION-003-R2"' not in entrypoint:
        reasons.append("R2 collector entrypoint contract mismatch")
    if 'COLLECTOR_RELEASE_ID = "PPI-PUBLIC-COLLECTOR-003-R2"' not in entrypoint:
        reasons.append("R2 collector release mismatch")
    if 'EXPECTED_YFINANCE_VERSION = "1.5.1"' not in helper:
        reasons.append("Yahoo expectation helper version is not pinned")

    if '"contract_id": "PPI-R11-PUBLIC-ACQUISITION-003-R1"' not in acquisition_r1:
        reasons.append("immutable public acquisition R1 contract is missing")
    if '"collector_release_id": "PPI-PUBLIC-COLLECTOR-003-R1"' not in acquisition_r1:
        reasons.append("immutable public acquisition R1 lineage drift")
    if '"provider_operations"' not in collector_r1 or "alpha_vantage:EARNINGS_ESTIMATES" not in collector_r1:
        reasons.append("immutable public collector R1 lineage drift")
    if '"supersedes": "PPI-R11-PUBLIC-ACQUISITION-003-R1"' not in acquisition_r2:
        reasons.append("public acquisition R2 supersession is missing")
    if '"supersedes": "PPI-PUBLIC-COLLECTOR-003-R1"' not in collector_r2:
        reasons.append("public collector R2 supersession is missing")
    if '"alpha_vantage_batch_request_count": 12' not in acquisition_r2:
        reasons.append("public acquisition R2 Alpha Vantage bound is missing")
    if '"alpha_vantage_batch_request_count": 12' not in collector_r2:
        reasons.append("public collector R2 Alpha Vantage bound is missing")
    return not reasons, reasons


def latest_successful_current_public_run(token: str):
    main_sha = v2.target_main_sha(token).lower()
    runs = v2.base.list_workflow_runs(v2.base.TARGET_REPOSITORY, v2.base.PUBLIC_WORKFLOW, token)
    for run in runs:
        if (
            run.get("status") == "completed"
            and run.get("conclusion") == "success"
            and str(run.get("head_sha", "")).lower() == main_sha
        ):
            return run
    return None


def main() -> int:
    v2.base.run_bootstrap = run_bootstrap_r2
    v2.target_gate = target_gate_r2
    v2.base.latest_successful_public_run = latest_successful_current_public_run
    return v2.main()


if __name__ == "__main__":
    raise SystemExit(main())
